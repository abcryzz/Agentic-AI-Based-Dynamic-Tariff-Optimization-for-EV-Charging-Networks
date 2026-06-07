"""
eda.py — Phase 2: Exploratory Data Analysis (insight-driven, pricing-linked).

Reads the Phase-1 outputs and produces:
    figures/fig01..fig08*.png        labelled, deck-ready charts
    outputs/peak_windows.csv         EMPIRICAL peak/shoulder/off-peak hours (weekday & weekend)
    outputs/eda_temporal_profile.csv hourly mean utilization / energy / volatility
    outputs/eda_volatility_by_band.csv
    outputs/eda_cbd_comparison.csv
    outputs/eda_price_demand_bins.csv  + a preliminary (associational) price elasticity
    outputs/eda_acn_behavior.csv
    outputs/eda_findings.md          narrative: every finding -> a pricing implication

IMPORTANT distinction (see eda_findings.md):
  * OPERATIONAL bands (per zone-hour): util >= 0.80 surge, < 0.30 discount  -> the brief's
    pricing triggers, applied at the zone-hour level (already in panel.util_band).
  * TEMPORAL peak windows (which HOURS are systematically busy): defined here empirically
    by tertiles of mean hourly utilization -> drives time-of-use structure & narrative.
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.linear_model import LinearRegression

import config as C

_trapz = getattr(np, "trapezoid", getattr(np, "trapz"))   # NumPy 2.x / 1.x compatible
warnings.filterwarnings("ignore")
sns.set_theme(style="whitegrid", context="talk")
plt.rcParams.update({"figure.dpi": 130, "savefig.dpi": 150, "savefig.bbox": "tight",
                     "axes.titleweight": "bold", "font.size": 11})
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
TEAL, ORANGE, GREY = "#0F766E", "#EA7317", "#64748B"


def _foot(fig, text):
    """Attach the pricing-implication takeaway under a figure."""
    fig.text(0.5, -0.02, "→ " + text, ha="center", va="top", fontsize=10,
             style="italic", color=GREY, wrap=True)


def load():
    panel = pd.read_csv(C.OUTPUT_DIR / "urbanev_panel_hourly.csv.gz")
    zf = pd.read_csv(C.OUTPUT_DIR / "zone_features.csv")
    info = pd.read_csv(C.DATA_DIR / C.F_INFO)              # for lon/lat
    acn = pd.read_csv(C.OUTPUT_DIR / "clean_acn_sessions.csv")
    return panel, zf, info, acn


# ===========================================================================
# Temporal profiling + empirical peak windows
# ===========================================================================
def temporal(panel):
    def prof(df):
        return df.groupby("hour").agg(mean_util=("utilization", "mean"),
                                      mean_energy=("energy_kwh", "mean"),
                                      std_util=("utilization", "std")).reset_index()
    overall = prof(panel)
    wd = prof(panel[~panel.is_weekend])
    we = prof(panel[panel.is_weekend])
    for d in (overall, wd, we):
        d["cv_util"] = d["std_util"] / d["mean_util"]

    def bands(d):
        q1, q2 = d["mean_util"].quantile([1/3, 2/3])
        return np.where(d["mean_util"] >= q2, "peak",
                        np.where(d["mean_util"] < q1, "offpeak", "shoulder"))
    for d in (overall, wd, we):
        d["band"] = bands(d)

    # tidy peak_windows.csv
    pw = pd.concat([overall.assign(scope="overall"),
                    wd.assign(scope="weekday"),
                    we.assign(scope="weekend")], ignore_index=True)
    pw = pw[["scope", "hour", "mean_util", "mean_energy", "cv_util", "band"]].round(4)
    pw.to_csv(C.OUTPUT_DIR / "peak_windows.csv", index=False)
    overall.round(4).to_csv(C.OUTPUT_DIR / "eda_temporal_profile.csv", index=False)
    return overall, wd, we


def fig_intraday(overall, wd, we):
    fig, ax = plt.subplots(figsize=(11, 5))
    # shade temporal bands from the overall profile
    for _, r in overall.iterrows():
        col = {"peak": ORANGE, "offpeak": TEAL, "shoulder": "none"}[r.band]
        if col != "none":
            ax.axvspan(r.hour - 0.5, r.hour + 0.5, color=col, alpha=0.10, lw=0)
    ax.plot(wd.hour, wd.mean_util, "-o", color=TEAL, label="Weekday", ms=4)
    ax.plot(we.hour, we.mean_util, "-s", color=ORANGE, label="Weekend", ms=4)
    ax.axhline(C.UTIL_SURGE, ls="--", color="#b91c1c", lw=1)
    ax.text(0.2, C.UTIL_SURGE + .01, "surge trigger (0.80)", color="#b91c1c", fontsize=9)
    ax.axhline(C.UTIL_DISCOUNT, ls="--", color="#1d4ed8", lw=1)
    ax.text(0.2, C.UTIL_DISCOUNT + .01, "discount trigger (0.30)", color="#1d4ed8", fontsize=9)
    ax.set(xlabel="Hour of day", ylabel="Mean utilization", xticks=range(0, 24, 2),
           title="Intraday utilization — Shenzhen network")
    ax.legend(loc="upper right", fontsize=10)
    _foot(fig, "Occupancy peaks overnight (vehicles sit plugged in) yet never nears the 0.80 "
               "surge line; the midday trough dips below the 0.30 discount line — the prime "
               "discount window is daytime, and network-wide surge is essentially absent.")
    fig.savefig(C.FIG_DIR / "fig01_intraday_utilization.png")
    plt.close(fig)


def fig_heatmap(panel):
    piv = (panel.groupby(["dayofweek", "hour"])["utilization"].mean()
           .unstack().reindex(range(7)))
    fig, ax = plt.subplots(figsize=(12, 4.6))
    sns.heatmap(piv, cmap="rocket_r", ax=ax, cbar_kws={"label": "Mean utilization"},
                yticklabels=DOW)
    ax.set(xlabel="Hour of day", ylabel="", title="Mean utilization by hour × day of week")
    _foot(fig, "A consistent overnight/early-morning band with a midday trough on every day — "
               "weekday and weekend look alike, so the tariff calendar is set by time-of-day, "
               "not day-of-week.")
    fig.savefig(C.FIG_DIR / "fig02_util_heatmap_hour_dow.png")
    plt.close(fig)


def fig_volatility(panel, overall):
    band_map = dict(zip(overall.hour, overall.band))
    p = panel.assign(tband=panel.hour.map(band_map))
    g = p.groupby("tband")["utilization"].agg(["mean", "std"])
    g["cv"] = g["std"] / g["mean"]
    g = g.reindex(["offpeak", "shoulder", "peak"])
    g.to_csv(C.OUTPUT_DIR / "eda_volatility_by_band.csv")
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(g.index, g["cv"], color=[TEAL, GREY, ORANGE])
    for i, v in enumerate(g["cv"]):
        ax.text(i, v + .01, f"{v:.2f}", ha="center", fontsize=11)
    ax.set(ylabel="Coefficient of variation (σ/μ)",
           title="Demand volatility by temporal band")
    _foot(fig, "The quiet midday (off-peak) window is modestly but consistently the least "
               "predictable → discounts should be scheduled/sustained across the daytime trough, "
               "not triggered reactively off a noisy signal.")
    fig.savefig(C.FIG_DIR / "fig03_volatility_by_band.png")
    plt.close(fig)
    return g


def fig_zone_dist_cbd(zf):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].hist(zf.util_mean, bins=30, color=TEAL, alpha=.85)
    axes[0].axvline(C.UTIL_DISCOUNT, ls="--", color="#1d4ed8")
    axes[0].axvline(C.UTIL_SURGE, ls="--", color="#b91c1c")
    axes[0].set(xlabel="Zone mean utilization", ylabel="# zones",
                title="Distribution of zone utilization")
    sns.boxplot(data=zf.assign(Zone=np.where(zf.CBD == 1, "CBD", "non-CBD")),
                x="Zone", y="util_mean", ax=axes[1], palette=[ORANGE, TEAL])
    axes[1].set(xlabel="", ylabel="Zone mean utilization", title="CBD vs non-CBD")
    cmp = (zf.assign(grp=np.where(zf.CBD == 1, "CBD", "non-CBD"))
           .groupby("grp").agg(n=("zone", "size"), util_mean=("util_mean", "mean"),
                               pct_peak=("pct_hours_peak", "mean"),
                               pct_offpeak=("pct_hours_offpeak", "mean"),
                               price_mean=("price_mean", "mean"),
                               revenue_total=("revenue_total", "mean")).round(4))
    cmp.to_csv(C.OUTPUT_DIR / "eda_cbd_comparison.csv")
    _foot(fig, "Most zones are chronically under-used and CBD zones are not the busiest; "
               "congestion sits in a small (mostly non-CBD) set of zones → surge must be targeted "
               "by observed utilization, not the CBD label; broad discounts elsewhere.")
    fig.savefig(C.FIG_DIR / "fig04_zone_utilization_distribution.png")
    plt.close(fig)
    return cmp


def fig_map(zf, info):
    m = zf.merge(info[["grid", "lon", "la"]], left_on="zone", right_on="grid")
    fig, ax = plt.subplots(figsize=(8.5, 7.5))
    sc = ax.scatter(m.lon, m.la, c=m.util_mean, s=12 + m.capacity / 2,
                    cmap="rocket_r", alpha=.85, edgecolor="white", lw=.3)
    plt.colorbar(sc, label="Zone mean utilization")
    ax.set(xlabel="Longitude", ylabel="Latitude",
           title="Spatial demand — Shenzhen zones (size = installed piles)")
    _foot(fig, "Demand clusters spatially; neighbouring busy/idle zones enable spatial "
               "load-shifting (price nudges toward nearby empty zones).")
    fig.savefig(C.FIG_DIR / "fig05_spatial_map.png")
    plt.close(fig)


def fig_top_bottom(zf):
    top = zf.nlargest(12, "util_mean"); bot = zf.nsmallest(12, "util_mean")
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), sharex=True)
    axes[0].barh(top.zone.astype(str), top.util_mean, color=ORANGE)
    axes[0].invert_yaxis(); axes[0].set(title="Busiest 12 zones", xlabel="Mean utilization")
    axes[1].barh(bot.zone.astype(str), bot.util_mean, color=TEAL)
    axes[1].invert_yaxis(); axes[1].set(title="Idlest 12 zones", xlabel="Mean utilization")
    _foot(fig, "A short list of surge candidates and a long tail of discount candidates — "
               "the policy is asymmetric by zone.")
    fig.savefig(C.FIG_DIR / "fig06_top_bottom_zones.png")
    plt.close(fig)


def fig_price_demand(panel):
    pv = panel.groupby("zone")["price_mean"].nunique()
    pv_zones = pv[pv > 1].index
    sub = panel[panel.zone.isin(pv_zones) & (panel.energy_kwh > 0) & (panel.price_mean > 0)].copy()

    # binned demand vs price (deciles)
    sub["pbin"] = pd.qcut(sub.price_mean, 10, duplicates="drop")
    b = sub.groupby("pbin").agg(price=("price_mean", "mean"),
                                util=("utilization", "mean"),
                                energy=("energy_kwh", "mean")).reset_index(drop=True)
    b.round(4).to_csv(C.OUTPUT_DIR / "eda_price_demand_bins.csv", index=False)

    # preliminary (ASSOCIATIONAL) elasticity: log energy ~ log price + zone FE + hour FE
    y = np.log(sub.energy_kwh.values)
    X = pd.concat([pd.Series(np.log(sub.price_mean.values), name="log_price", index=sub.index),
                   pd.get_dummies(sub.zone, prefix="z", drop_first=True),
                   pd.get_dummies(sub.hour, prefix="h", drop_first=True)], axis=1).astype(float)
    reg = LinearRegression().fit(X.values, y)
    elasticity = float(reg.coef_[0])

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(b.price, b.util, "-o", color=TEAL)
    ax.set(xlabel="Tariff (CNY/kWh, price-decile mean)", ylabel="Mean utilization",
           title="Price vs demand (price-varying zones)")
    ax.text(0.97, 0.95, f"preliminary elasticity ≈ {elasticity:+.2f}\n(log E ~ log P, zone+hour FE)",
            transform=ax.transAxes, ha="right", va="top", fontsize=10,
            bbox=dict(boxstyle="round", fc="#f1f5f9", ec=GREY))
    _foot(fig, "Higher tariffs associate with lower demand (associational, NOT causal) — a "
               "usable price-response signal to be estimated rigorously in Phase 4.")
    fig.savefig(C.FIG_DIR / "fig07_price_vs_demand.png")
    plt.close(fig)
    return elasticity, len(pv_zones)


# ===========================================================================
# ACN behaviour
# ===========================================================================
def fig_acn(acn):
    acn = acn.copy()
    acn["idle_ratio"] = (acn.idle_hr / acn.duration_hr).clip(0, 1)
    fig, ax = plt.subplots(2, 2, figsize=(13, 10))

    # (a) dwell vs charging vs idle
    cl = acn[acn.duration_hr < 24]
    for col, c, lab in [("duration_hr", GREY, "Dwell (plugged-in)"),
                        ("charging_hr", TEAL, "Charging"),
                        ("idle_hr", ORANGE, "Idle after charge")]:
        ax[0, 0].hist(cl[col].dropna(), bins=40, alpha=.55, color=c, label=lab)
    ax[0, 0].set(xlabel="Hours", ylabel="# sessions", title="Dwell vs charging vs idle")
    ax[0, 0].legend(fontsize=9)

    # (b) idle ratio
    ax[0, 1].hist(acn.idle_ratio.dropna(), bins=30, color=ORANGE, alpha=.85)
    med = acn.idle_ratio.median()
    ax[0, 1].axvline(med, color="#b91c1c", ls="--")
    ax[0, 1].text(med + .02, ax[0, 1].get_ylim()[1]*.8, f"median {med:.0%}", color="#b91c1c")
    ax[0, 1].set(xlabel="Idle time / total dwell", ylabel="# sessions",
                 title="Connector idle ratio (overstay)")

    # (c) sessions by local hour, weekday vs weekend
    wd = acn[~acn.is_weekend].groupby("hour").size()
    we = acn[acn.is_weekend].groupby("hour").size()
    ax[1, 0].plot(wd.index, wd / max(wd.sum(), 1), "-o", color=TEAL, ms=4, label="Weekday")
    ax[1, 0].plot(we.index, we / max(we.sum(), 1), "-s", color=ORANGE, ms=4, label="Weekend")
    ax[1, 0].set(xlabel="Hour of day (local)", ylabel="Share of sessions",
                 title="Caltech arrivals by hour", xticks=range(0, 24, 3))
    ax[1, 0].legend(fontsize=9)

    # (d) Lorenz curve of sessions per IDENTIFIED user (85% of sessions are anonymous)
    ident = acn[acn.userID.notna()]
    counts = ident.userID.value_counts().sort_values().values
    cum = np.cumsum(counts) / counts.sum()
    xx = np.linspace(0, 1, len(cum))
    gini = 1 - 2 * _trapz(cum, xx)
    ax[1, 1].plot(xx, cum, color=TEAL, lw=2)
    ax[1, 1].plot([0, 1], [0, 1], ls="--", color=GREY)
    ax[1, 1].fill_between(xx, cum, xx, color=TEAL, alpha=.12)
    ax[1, 1].text(0.05, 0.85, f"Gini ≈ {gini:.2f}", fontsize=12)
    ax[1, 1].set(xlabel="Cumulative share of identified users",
                 ylabel="Cumulative share of identified sessions",
                 title="User concentration (15% of sessions are identified)")

    fig.suptitle("ACN (Caltech) session behaviour", fontweight="bold")
    _foot(fig, "Long post-charge idle blocks connectors and a heavy morning arrival peak — "
               "idle-fees + a morning surge can free capacity without new hardware.")
    fig.savefig(C.FIG_DIR / "fig08_acn_behaviour.png")
    plt.close(fig)

    summary = {
        "acn_median_dwell_hr": float(acn.duration_hr.median()),
        "acn_median_charging_hr": float(acn.charging_hr.median()),
        "acn_median_idle_hr": float(acn.idle_hr.median()),
        "acn_median_idle_ratio": float(med),
        "acn_pct_idle_gt_1h": float((acn.idle_hr > 1).mean()),
        "acn_pct_identified": float(len(ident) / len(acn)),
        "acn_user_gini": float(gini),
        "acn_top10pct_user_session_share": float(
            ident.userID.value_counts().head(max(1, ident.userID.nunique() // 10)).sum() / len(ident)),
        "acn_median_laxity_hr": float(acn.loc[acn.has_user_input, "laxity_hr"].median()),
    }
    pd.DataFrame([{"metric": k, "value": round(v, 4)} for k, v in summary.items()]
                 ).to_csv(C.OUTPUT_DIR / "eda_acn_behavior.csv", index=False)
    return summary


# ===========================================================================
# Findings doc (data-driven, so numbers always match the run)
# ===========================================================================
def write_findings(panel, overall, vol, cbd, elasticity, n_pv, acn_sum):
    peak_hours = sorted(overall.loc[overall.band == "peak", "hour"].tolist())
    off_hours = sorted(overall.loc[overall.band == "offpeak", "hour"].tolist())
    pct_off = (panel.utilization < C.UTIL_DISCOUNT).mean()
    pct_peak = (panel.utilization >= C.UTIL_SURGE).mean()
    we_mean = panel[panel.is_weekend].utilization.mean()
    wd_mean = panel[~panel.is_weekend].utilization.mean()
    peak_util = overall.loc[overall.band == "peak", "mean_util"].mean()
    zpk = (panel.utilization >= C.UTIL_SURGE).groupby(panel.zone).sum()
    top10_share = zpk.nlargest(max(1, int(round(len(zpk) * 0.1)))).sum() / max(zpk.sum(), 1)

    def hr(hs):
        return ", ".join(f"{h:02d}:00" for h in hs)

    md = f"""# Phase 2 — EDA Findings (each tied to a pricing implication)

All figures are in `figures/`. Two band concepts are kept distinct:
**operational bands** (per zone-hour: util ≥ {C.UTIL_SURGE:.0%} surge, < {C.UTIL_DISCOUNT:.0%} discount — the brief's triggers)
and **temporal peak windows** (which *hours* are systematically busy — defined below).

## 1. The network is chronically under-used (fig01, fig04)
Only **{pct_peak:.1%}** of zone-hours exceed the {C.UTIL_SURGE:.0%} surge trigger, while **{pct_off:.1%}** fall
below the {C.UTIL_DISCOUNT:.0%} discount trigger. → **Implication:** the dominant revenue/efficiency lever is
**off-peak discounting to fill empty capacity**, with surge as a targeted, secondary tool.

## 2. Demand is driven by time-of-day, not day-of-week (fig01, fig02)
Occupancy peaks **overnight / early-morning** ({hr(peak_hours)}) — vehicles sit plugged in — and
troughs **midday** ({hr(off_hours)}). Weekend and weekday means are nearly identical
({we_mean:.2f} vs {wd_mean:.2f}), so the cycle is intraday, not weekly. Even the overnight peak
(~{peak_util:.2f}) stays far below the {C.UTIL_SURGE:.0%} surge trigger, while midday dips under the
{C.UTIL_DISCOUNT:.0%} discount line. → **Implication:** the **discount window is daytime**; the demand
agent (Phase 3) can exploit strong, learnable daily seasonality; network-wide surge is essentially
absent and belongs to the zone-level tail (§4), not a time-of-day rule.

## 3. The quiet midday window is modestly the least predictable (fig03)
Coefficient of variation by band — off-peak {vol.loc['offpeak','cv']:.2f}, shoulder {vol.loc['shoulder','cv']:.2f},
peak {vol.loc['peak','cv']:.2f}. The gaps are small but consistent: the daytime trough is the noisiest.
→ **Implication:** daytime discounts should be **scheduled/sustained** rather than triggered reactively
off a volatile signal; the overnight peak is comparatively stable.

## 4. Congestion is concentrated in a few zones — and they are NOT the CBD (fig04, fig05, fig06)
A small set of zones is persistently busy: the **top 10% of zones account for ~{top10_share:.0%} of all
surge-trigger (util ≥ {C.UTIL_SURGE:.0%}) incidence**. Counter-intuitively the CBD is **not** that hot set —
CBD zones average **{cbd.loc['CBD','util_mean']:.2f}** utilization vs **{cbd.loc['non-CBD','util_mean']:.2f}** for
non-CBD, and none of the 12 busiest zones are CBD. → **Implication:** surge must be **targeted by observed
zone utilization, not by the CBD label**; the rest of the network (most CBD zones included) is discount
territory, and adjacent busy/idle zones enable spatial load-shifting.

## 5. Demand responds to price (fig07) — associational, to be confirmed
Across the **{n_pv}** price-varying zones, a log-energy ~ log-price model (zone + hour fixed effects)
gives a **preliminary elasticity ≈ {elasticity:+.2f}** (higher price ↔ lower demand). This is
**associational, not causal** (per the brief) and is re-estimated rigorously in Phase 4.
→ **Implication:** price is a real demand lever, so the tariff agent can plausibly move utilization.

## 6. ACN behaviour: idle connectors, a morning rush, and mostly anonymous sessions (fig08)
Median dwell **{acn_sum['acn_median_dwell_hr']:.1f}h** but median charging only
**{acn_sum['acn_median_charging_hr']:.1f}h**; median **{acn_sum['acn_median_idle_ratio']:.0%}** of plug-in time is
idle, and **{acn_sum['acn_pct_idle_gt_1h']:.0%}** of sessions sit idle >1h after charging. Arrivals spike in the
morning (workplace charging). Only **{acn_sum['acn_pct_identified']:.0%}** of sessions carry a user id; among
those identified users demand is concentrated (Gini ≈ {acn_sum['acn_user_gini']:.2f}; top-10% of users ≈
{acn_sum['acn_top10pct_user_session_share']:.0%} of identified sessions), and they leave
**{acn_sum['acn_median_laxity_hr']:.1f}h** of median slack before their stated departure.
→ **Implication:** **idle/occupancy fees** plus a **morning-arrival surge** can free capacity without new
hardware; high slack (laxity) means price nudges can shift load — but user-level personalisation is limited
by the 85% anonymity.

## Hand-off to Phase 3 & 4
- **Phase 3 (demand agent):** strong daily/weekly seasonality + spatial structure → use lag/rolling
  + cyclical + zone features; `peak_windows.csv` provides the time-of-use scaffolding.
- **Phase 4 (tariff agent):** asymmetric policy (discount-led, targeted surge); seed elasticity with
  the ≈ {elasticity:+.2f} preliminary estimate, then refine with controls.
"""
    (C.OUTPUT_DIR / "eda_findings.md").write_text(md)


def main():
    print("=" * 64, "\nPHASE 2  — EDA\n", "=" * 64, sep="")
    panel, zf, info, acn = load()
    overall, wd, we = temporal(panel)
    fig_intraday(overall, wd, we)
    fig_heatmap(panel)
    vol = fig_volatility(panel, overall)
    cbd = fig_zone_dist_cbd(zf)
    fig_map(zf, info)
    fig_top_bottom(zf)
    elasticity, n_pv = fig_price_demand(panel)
    acn_sum = fig_acn(acn)
    write_findings(panel, overall, vol, cbd, elasticity, n_pv, acn_sum)

    figs = sorted(p.name for p in C.FIG_DIR.glob("*.png"))
    print(f"[figures] {len(figs)} saved -> figures/:", ", ".join(figs))
    print(f"[peak windows] peak hours (overall): "
          f"{sorted(overall.loc[overall.band=='peak','hour'].tolist())}")
    print(f"[elasticity] preliminary (associational) ≈ {elasticity:+.2f} over {n_pv} price-varying zones")
    print("[outputs] peak_windows.csv, eda_*.csv, eda_findings.md written")


if __name__ == "__main__":
    main()
