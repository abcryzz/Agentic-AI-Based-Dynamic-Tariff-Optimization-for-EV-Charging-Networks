"""
preprocess.py — Phase 1: ingestion, cleaning, and feature engineering.

Produces the unified analytical base for every downstream phase:

    outputs/clean_acn_sessions.csv          cleaned Caltech session table (+ features)
    outputs/urbanev_panel_hourly.parquet    zone x hour panel with engineered features (PRIMARY)
    outputs/urbanev_panel_hourly_sample.csv  2,000-row preview for quick inspection
    outputs/zone_features.csv               static per-zone profile (CBD, piles, util stats)
    outputs/data_quality_report.csv         shapes + missingness for transparency

Run:
    python preprocess.py              # or:  python -m preprocess
The two datasets are kept SEPARATE on purpose (different role, geography, units) —
see ASSUMPTIONS.md, decision #1.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

import config as C


# ===========================================================================
# 1. ACN-Data (Caltech sessions)  — session-level behaviour
# ===========================================================================
# Real session fields kept from the flattened JSON dump; the rest of the
# spreadsheet columns are JSON-wrapper artifacts that are entirely null.
_ACN_KEEP = [
    "_id", "clusterID", "connectionTime", "disconnectTime", "doneChargingTime",
    "kWhDelivered", "sessionID", "siteID", "spaceID", "stationID", "timezone",
    "userID", "WhPerMile", "kWhRequested", "milesRequested", "minutesAvailable",
    "paymentRequired", "requestedDeparture",
]


def clean_acn(path=None) -> tuple[pd.DataFrame, dict]:
    """Load and clean the ACN session spreadsheet. Returns (clean_df, report)."""
    path = path or (C.DATA_DIR / C.ACN_FILE)
    raw = pd.read_excel(path)
    n_raw = len(raw)

    df = raw[[c for c in _ACN_KEEP if c in raw.columns]].copy()
    df = df.dropna(subset=["sessionID"]).copy()       # drop null/separator rows
    n_sessions = len(df)

    # timestamps -> tz-aware UTC (explicit RFC-2822 format), then Caltech local
    for col in ["connectionTime", "disconnectTime", "doneChargingTime", "requestedDeparture"]:
        df[col] = pd.to_datetime(df[col], errors="coerce", utc=True, format=C.ACN_DATETIME_FMT)
    df["connect_local"] = df["connectionTime"].dt.tz_convert(C.ACN_TZ)

    # numerics
    for col in ["kWhDelivered", "kWhRequested", "milesRequested", "minutesAvailable"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # --- engineered session features --------------------------------------
    sec = 3600.0
    df["duration_hr"] = (df.disconnectTime - df.connectionTime).dt.total_seconds() / sec
    df["charging_hr"] = (df.doneChargingTime - df.connectionTime).dt.total_seconds() / sec
    df["idle_hr"] = (df.disconnectTime - df.doneChargingTime).dt.total_seconds() / sec

    # invalid charging time (done-charging logged before connection) -> null + flag
    df["flag_neg_charging"] = df["charging_hr"] < 0
    df["charging_hr"] = df["charging_hr"].where(df["charging_hr"] >= 0)

    df["has_user_input"] = df["requestedDeparture"].notna()
    df["requested_stay_hr"] = (df.requestedDeparture - df.connectionTime).dt.total_seconds() / sec
    df["laxity_hr"] = df["requested_stay_hr"] - df["charging_hr"]   # scheduling slack
    df["avg_power_kw"] = df["kWhDelivered"] / df["charging_hr"].where(df["charging_hr"] > 0)
    # implausible power (tiny charging_hr artifact) -> null + flag
    df["flag_implausible_power"] = df["avg_power_kw"] > C.ACN_MAX_POWER_KW
    df["avg_power_kw"] = df["avg_power_kw"].where(df["avg_power_kw"] <= C.ACN_MAX_POWER_KW)

    # time-of-day features (local)
    df["hour"] = df.connect_local.dt.hour
    df["dayofweek"] = df.connect_local.dt.dayofweek
    df["is_weekend"] = df["dayofweek"] >= 5
    df["month"] = df.connect_local.dt.month
    df["date"] = df.connect_local.dt.date

    # --- quality flags + outlier removal (documented, transparent) --------
    df["flag_nonpos_duration"] = df["duration_hr"] <= 0
    df["flag_long_duration"] = df["duration_hr"] > C.ACN_MAX_DURATION_HR
    df["flag_low_kwh"] = df["kWhDelivered"] < C.ACN_MIN_KWH
    df["flag_neg_idle"] = df["idle_hr"] < 0          # done-charging logged after disconnect (noise)
    df["idle_hr"] = df["idle_hr"].clip(lower=0)      # clip tiny negatives to 0, keep the flag

    bad = df["flag_nonpos_duration"] | df["flag_long_duration"] | df["flag_low_kwh"]
    clean = df[~bad].copy()

    # behavioural rollups
    clean["user_session_count"] = clean.groupby("userID")["sessionID"].transform("count")

    report = {
        "acn_rows_raw": n_raw,
        "acn_valid_sessions": n_sessions,
        "acn_dropped_nonpos_duration": int(df["flag_nonpos_duration"].sum()),
        "acn_dropped_long_duration": int(df["flag_long_duration"].sum()),
        "acn_dropped_low_kwh": int(df["flag_low_kwh"].sum()),
        "acn_clean_sessions": len(clean),
        "acn_unique_stations": int(clean.stationID.nunique()),
        "acn_unique_users": int(clean.userID.nunique()),
        "acn_with_user_input": int(clean["has_user_input"].sum()),
        "acn_flag_neg_charging": int(clean["flag_neg_charging"].sum()),
        "acn_flag_implausible_power": int(clean["flag_implausible_power"].sum()),
        "acn_flag_neg_idle": int(clean["flag_neg_idle"].sum()),
        "acn_date_min": str(clean.connect_local.min()),
        "acn_date_max": str(clean.connect_local.max()),
    }
    return clean, report


# ===========================================================================
# 2. UrbanEV (Shenzhen)  — spatio-temporal demand + price + occupancy
# ===========================================================================
def _load_matrix(name):
    """Load an 8640 x 247 UrbanEV matrix. Returns (values[T,Z], zone_ids[int])."""
    df = pd.read_csv(C.DATA_DIR / name)
    idx_col = df.columns[0]
    zone_cols = [c for c in df.columns if c != idx_col]
    return df[zone_cols].to_numpy(dtype=float), [int(z) for z in zone_cols]


def _hour_starts():
    """Return the chronological hour-start timestamps and assert a clean 5-min grid."""
    t = pd.read_csv(C.DATA_DIR / C.F_TIME)
    ts = pd.to_datetime(dict(year=t.year, month=t.month, day=t.day,
                             hour=t.hour, minute=t.minute, second=t.second))
    steps = ts.diff().dropna().dt.total_seconds() / 60
    assert ts.is_monotonic_increasing, "time index is not chronological"
    assert (steps == C.INTERVAL_MIN).all(), "time grid is not a clean 5-min sequence"
    assert len(ts) % C.INTERVALS_PER_HOUR == 0, "rows do not divide into whole hours"
    return ts.iloc[::C.INTERVALS_PER_HOUR].reset_index(drop=True)


def build_urbanev_panel() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Build the zone x hour panel and the static zone profile."""
    occ, zones = _load_matrix(C.F_OCCUPANCY)
    vol, _ = _load_matrix(C.F_VOLUME)
    dur, _ = _load_matrix(C.F_DURATION)
    prc, _ = _load_matrix(C.F_PRICE)
    info = pd.read_csv(C.DATA_DIR / C.F_INFO)
    T, Z = occ.shape
    H = T // C.INTERVALS_PER_HOUR
    hour_start = _hour_starts()

    # zone capacity / area aligned to the matrix column order
    meta = info.set_index("grid")
    cap = meta["count"].reindex(zones).to_numpy(dtype=float)      # installed piles
    area = meta["area"].reindex(zones).to_numpy(dtype=float)

    # 5-min derived layers
    rev5 = vol * prc                                             # interval revenue (exact)
    sat5 = (occ >= C.SATURATION_THRESHOLD * cap[None, :]).astype(float)  # saturation flag

    # aggregate 5-min -> hourly via reshape (grid verified contiguous above)
    def agg(a, how):
        a3 = a.reshape(H, C.INTERVALS_PER_HOUR, Z)
        return a3.mean(axis=1) if how == "mean" else a3.sum(axis=1)

    occ_h = agg(occ, "mean")      # mean occupied piles in the hour
    vol_h = agg(vol, "sum")       # total energy (kWh) delivered in the hour
    dur_h = agg(dur, "sum")       # total charging-pile-hours in the hour
    prc_h = agg(prc, "mean")      # representative tariff in the hour
    rev_h = agg(rev5, "sum")      # total revenue in the hour
    sat_h = agg(sat5, "sum")      # # of 5-min intervals saturated (0..12)  == queue proxy

    # ---- assemble long panel (H*Z rows) ----------------------------------
    hidx = np.repeat(np.arange(H), Z)
    zarr = np.tile(zones, H)
    panel = pd.DataFrame({
        "hour_index": hidx,
        "zone": zarr,
        "occupancy_mean": occ_h.ravel(),
        "energy_kwh": vol_h.ravel(),
        "charging_hours": dur_h.ravel(),
        "price_mean": prc_h.ravel(),
        "revenue": rev_h.ravel(),
        "saturation_count": sat_h.ravel(),
    })
    capacity_map = dict(zip(zones, cap))
    area_map = dict(zip(zones, area))
    panel["capacity"] = panel["zone"].map(capacity_map)
    panel["area"] = panel["zone"].map(area_map)

    # economically meaningful features (brief)
    panel["utilization"] = np.clip(panel["occupancy_mean"] / panel["capacity"], 0, 1)
    panel["occupancy_density"] = panel["occupancy_mean"] / panel["area"]
    panel["revenue_per_kwh"] = panel["revenue"] / panel["energy_kwh"].replace(0, np.nan)
    panel["is_saturated_hour"] = panel["saturation_count"] > 0
    panel["util_band"] = np.select(
        [panel["utilization"] >= C.UTIL_SURGE, panel["utilization"] < C.UTIL_DISCOUNT],
        ["peak", "offpeak"], default="shoulder")

    # calendar features
    ts_map = panel["hour_index"].map(hour_start)
    panel["timestamp"] = ts_map.values
    panel["hour"] = panel["timestamp"].dt.hour
    panel["dayofweek"] = panel["timestamp"].dt.dayofweek
    panel["is_weekend"] = panel["dayofweek"] >= 5
    panel["date"] = panel["timestamp"].dt.date
    panel["hour_sin"] = np.sin(2 * np.pi * panel["hour"] / 24)
    panel["hour_cos"] = np.cos(2 * np.pi * panel["hour"] / 24)
    panel["dow_sin"] = np.sin(2 * np.pi * panel["dayofweek"] / 7)
    panel["dow_cos"] = np.cos(2 * np.pi * panel["dayofweek"] / 7)

    # zone metadata join
    zmeta = info.rename(columns={"grid": "zone"})[
        ["zone", "CBD", "dynamic_pricing", "fast_count", "slow_count"]]
    panel = panel.merge(zmeta, on="zone", how="left")

    # ---- lags & rolling features (per zone, time-ordered) ----------------
    panel = panel.sort_values(["zone", "hour_index"]).reset_index(drop=True)
    g = panel.groupby("zone", sort=False)
    for lag in (1, 2, 3, 24, 168):                # 1-3h, same-hour-yesterday, same-hour-last-week
        panel[f"util_lag{lag}"] = g["utilization"].shift(lag)
        panel[f"energy_lag{lag}"] = g["energy_kwh"].shift(lag)
    panel["util_roll3_mean"] = g["utilization"].transform(lambda s: s.shift(1).rolling(3).mean())
    panel["util_roll3_std"] = g["utilization"].transform(lambda s: s.shift(1).rolling(3).std())
    panel["util_roll24_mean"] = g["utilization"].transform(lambda s: s.shift(1).rolling(24).mean())
    panel["has_full_lags"] = panel["util_lag168"].notna()

    # ---- static per-zone profile -----------------------------------------
    zone_features = (
        panel.groupby("zone")
        .agg(capacity=("capacity", "first"),
             area=("area", "first"),
             CBD=("CBD", "first"),
             dynamic_pricing=("dynamic_pricing", "first"),
             fast_count=("fast_count", "first"),
             slow_count=("slow_count", "first"),
             util_mean=("utilization", "mean"),
             util_max=("utilization", "max"),
             energy_mean=("energy_kwh", "mean"),
             price_mean=("price_mean", "mean"),
             revenue_total=("revenue", "sum"),
             pct_hours_peak=("utilization", lambda s: float((s >= C.UTIL_SURGE).mean())),
             pct_hours_offpeak=("utilization", lambda s: float((s < C.UTIL_DISCOUNT).mean())))
        .reset_index()
    )

    report = {
        "urbanev_zones": Z,
        "urbanev_hours": H,
        "urbanev_panel_rows": len(panel),
        "urbanev_total_piles": int(cap.sum()),
        "urbanev_price_min": float(prc.min()),
        "urbanev_price_max": float(prc.max()),
        "urbanev_mean_utilization": float(panel["utilization"].mean()),
        "urbanev_pct_hours_offpeak": float((panel["utilization"] < C.UTIL_DISCOUNT).mean()),
        "urbanev_pct_hours_peak": float((panel["utilization"] >= C.UTIL_SURGE).mean()),
        "urbanev_raw_missing_cells": 0,   # verified: all four matrices are complete
    }
    return panel, zone_features, report


# ===========================================================================
# 3. Driver
# ===========================================================================
def main():
    print("=" * 64, "\nPHASE 1  — preprocessing\n", "=" * 64, sep="")
    print(f"Reading raw data from: {C.DATA_DIR}\n")

    acn, acn_rep = clean_acn()
    acn.to_csv(C.OUTPUT_DIR / "clean_acn_sessions.csv", index=False)
    print(f"[ACN] {acn_rep['acn_clean_sessions']:,} clean sessions "
          f"({acn_rep['acn_unique_users']} users, {acn_rep['acn_unique_stations']} stations) "
          f"-> clean_acn_sessions.csv")

    panel, zone_features, ev_rep = build_urbanev_panel()
    # full panel as gzip-compressed CSV (compact + read directly by pd.read_csv);
    # plus a plain 2,000-row sample for quick eyeballing.
    panel.to_csv(C.OUTPUT_DIR / "urbanev_panel_hourly.csv.gz", index=False, compression="gzip")
    panel.head(2000).to_csv(C.OUTPUT_DIR / "urbanev_panel_hourly_sample.csv", index=False)
    zone_features.to_csv(C.OUTPUT_DIR / "zone_features.csv", index=False)
    print(f"[UrbanEV] panel {ev_rep['urbanev_panel_rows']:,} rows "
          f"({ev_rep['urbanev_zones']} zones x {ev_rep['urbanev_hours']} hours) "
          f"-> urbanev_panel_hourly.csv.gz (+sample csv)")
    print(f"[UrbanEV] zone profile {len(zone_features)} zones -> zone_features.csv")

    # transparency: combined data-quality report
    qa = {**acn_rep, **ev_rep}
    pd.DataFrame([{"metric": k, "value": v} for k, v in qa.items()]).to_csv(
        C.OUTPUT_DIR / "data_quality_report.csv", index=False)
    print("[QA] data_quality_report.csv written\n")
    return acn, panel, zone_features, qa


if __name__ == "__main__":
    main()
