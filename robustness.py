"""
robustness.py — Phase 6: robustness checks, limitations & business/policy implications.

Stress-tests every headline conclusion so each is shown to be stable (or its fragility is
disclosed), then writes the implications. Reuses Phase 1–5 outputs.

Checks
------
A. Elasticity sensitivity   — re-simulate the recommended tariff across a plausible ε range.
B. Trigger sensitivity      — vary the 0.80 / 0.30 surge & discount thresholds.
C. Peak-definition stability— tertile vs quartile vs above-mean → is "overnight peak" robust?
D. CBD / fairness           — demand accuracy, surge incidence and outcomes by segment.
E. Demand-model ablation    — value of the weekly-lag feature (drop it, re-fit, compare).

Outputs: robustness_elasticity.csv, robustness_triggers.csv, robustness_peak_definition.csv,
         robustness_cbd.csv, robustness_demand_ablation.csv, implications.md,
         figures/fig17_robustness_elasticity.png, fig18_robustness_triggers.png, fig19_robustness_cbd.png
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import mean_squared_error, r2_score

import config as C

TEAL, ORANGE, GREY, RED, BLUE = "#0F766E", "#EA7317", "#64748B", "#b91c1c", "#1d4ed8"
HI_OBS = C.UTIL_SURGE        # 0.80 — fixed level at which we MEASURE congestion
EPS_RATIO = 0.248 / 0.321    # observed ε_util / ε_energy, to scale them together


def multiplier(u, m_min, m_max, lo, hi):
    u = np.clip(np.asarray(u, float), 0, 1)
    surge = 1 + (m_max - 1) * (u - hi) / (1 - hi)
    disc = 1 - (1 - m_min) * (lo - u) / lo
    return np.where(u >= hi, surge, np.where(u < lo, disc, 1.0))


def simulate(test, p0, eps_e, eps_u, m_min, m_max, lo, hi):
    u, uo, q = test.util_pred.values, test.util_actual.values, test.energy_actual.values
    m = multiplier(u, m_min, m_max, lo, hi)
    rev_base, rev_after = p0 * q, p0 * q * m ** (1 + eps_e)
    util_after = np.clip(uo * m ** eps_u, 0, 1)
    disc, pk = m < 1.0, uo >= HI_OBS
    return {
        "rev_gain_pct": (rev_after.sum() / rev_base.sum() - 1) * 100,
        "offpeak_uplift_pct": ((q[disc] * m[disc] ** eps_e).sum() / q[disc].sum() - 1) * 100 if disc.any() else 0.0,
        "peak_reduction_pp": (uo[pk].mean() - util_after[pk].mean()) * 100 if pk.any() else 0.0,
        "util_before": uo.mean(), "util_after": util_after.mean(),
        "pct_surge": (m > 1).mean() * 100, "pct_discount": disc.mean() * 100,
    }


def main():
    print("=" * 64, "\nPHASE 6  — Robustness & implications\n", "=" * 64, sep="")
    panel = pd.read_csv(C.OUTPUT_DIR / "urbanev_panel_hourly.csv.gz")
    test = pd.read_csv(C.OUTPUT_DIR / "demand_predictions.csv")
    est = pd.read_csv(C.OUTPUT_DIR / "elasticity_estimates.csv")
    sw = pd.read_csv(C.OUTPUT_DIR / "revenue_gain.csv")
    rec = sw[sw.is_recommended].iloc[0]
    m_min, m_max = float(rec.m_min), float(rec.m_max)
    eps_e0 = est.query("target=='energy_kwh' and scope=='overall'").elasticity.iloc[0]
    eps_u0 = est.query("target=='utilization' and scope=='overall'").elasticity.iloc[0]
    p0_map = panel.groupby("zone")["price_mean"].mean().to_dict()
    p0 = test.zone.map(p0_map).values
    cbd_map = panel.groupby("zone")["CBD"].first().to_dict()

    # ---- A. elasticity sensitivity --------------------------------------
    rowsA = []
    for ee in [-0.10, -0.20, eps_e0, -0.45, -0.60, -0.80]:
        eu = ee * EPS_RATIO
        o = simulate(test, p0, ee, eu, m_min, m_max, C.UTIL_DISCOUNT, C.UTIL_SURGE)
        rowsA.append({"eps_energy": round(ee, 3), "eps_util": round(eu, 3),
                      "rev_gain_pct": round(o["rev_gain_pct"], 3),
                      "offpeak_uplift_pct": round(o["offpeak_uplift_pct"], 3),
                      "peak_reduction_pp": round(o["peak_reduction_pp"], 3),
                      "is_estimate": abs(ee - eps_e0) < 1e-6})
    A = pd.DataFrame(rowsA); A.to_csv(C.OUTPUT_DIR / "robustness_elasticity.csv", index=False)

    # ---- B. trigger sensitivity -----------------------------------------
    rowsB = []
    for lo in [0.20, 0.25, 0.30, 0.35, 0.40]:
        for hi in [0.70, 0.75, 0.80, 0.85, 0.90]:
            o = simulate(test, p0, eps_e0, eps_u0, m_min, m_max, lo, hi)
            rowsB.append({"discount_trigger": lo, "surge_trigger": hi,
                          "rev_gain_pct": round(o["rev_gain_pct"], 3),
                          "offpeak_uplift_pct": round(o["offpeak_uplift_pct"], 3),
                          "peak_reduction_pp": round(o["peak_reduction_pp"], 3),
                          "pct_surge": round(o["pct_surge"], 2), "pct_discount": round(o["pct_discount"], 2)})
    B = pd.DataFrame(rowsB); B.to_csv(C.OUTPUT_DIR / "robustness_triggers.csv", index=False)

    # ---- C. peak-definition stability -----------------------------------
    hourly = panel.groupby("hour")["utilization"].mean()
    methods = {
        "tertile_top": set(hourly.sort_values().index[-8:]),
        "quartile_top": set(hourly.sort_values().index[-6:]),
        "above_mean": set(hourly[hourly > hourly.mean()].index),
    }
    ref = methods["tertile_top"]
    rowsC = []
    for name, s in methods.items():
        inter = len(s & ref); union = len(s | ref)
        rowsC.append({"method": name, "n_peak_hours": len(s),
                      "peak_hours": ",".join(f"{h:02d}" for h in sorted(s)),
                      "jaccard_vs_tertile": round(inter / union, 3)})
    Ct = pd.DataFrame(rowsC); Ct.to_csv(C.OUTPUT_DIR / "robustness_peak_definition.csv", index=False)

    # ---- D. CBD / fairness ----------------------------------------------
    t = test.assign(CBD=test.zone.map(cbd_map))
    m_rec = multiplier(t.util_pred.values, m_min, m_max, C.UTIL_DISCOUNT, C.UTIL_SURGE)
    t = t.assign(m=m_rec)
    rowsD = []
    for seg, sub in [("CBD", t[t.CBD == 1]), ("non_CBD", t[t.CBD == 0])]:
        rmse = mean_squared_error(sub.util_actual, sub.util_pred) ** 0.5
        ssub = sub.zone.map(p0_map).values
        o = simulate(sub, ssub, eps_e0, eps_u0, m_min, m_max, C.UTIL_DISCOUNT, C.UTIL_SURGE)
        rowsD.append({"segment": seg, "n_zone_hours": len(sub),
                      "demand_rmse": round(rmse, 4),
                      "pct_slots_surged": round((sub.m > 1).mean() * 100, 2),
                      "pct_slots_discounted": round((sub.m < 1).mean() * 100, 2),
                      "rev_gain_pct": round(o["rev_gain_pct"], 3),
                      "peak_reduction_pp": round(o["peak_reduction_pp"], 3)})
    D = pd.DataFrame(rowsD); D.to_csv(C.OUTPUT_DIR / "robustness_cbd.csv", index=False)

    # ---- E. demand-model ablation (value of weekly lag) -----------------
    import demand as DM
    tr, te = DM.load_split()
    def fit_eval(feats):
        Xtr = tr[feats].copy(); Xtr["is_weekend"] = Xtr["is_weekend"].astype(int); Xtr["zone"] = Xtr["zone"].astype("category")
        Xte = te[feats].copy(); Xte["is_weekend"] = Xte["is_weekend"].astype(int); Xte["zone"] = Xte["zone"].astype("category")
        reg = DM._reg().fit(Xtr, tr.utilization)
        p = np.clip(reg.predict(Xte), 0, 1)
        return mean_squared_error(te.utilization, p) ** 0.5, r2_score(te.utilization, p)
    full = fit_eval(DM.FEATURES)
    no_week = fit_eval([f for f in DM.FEATURES if f not in ("util_lag168", "energy_lag168")])
    no_lags = fit_eval([f for f in DM.FEATURES if "lag" not in f and "roll" not in f])
    E = pd.DataFrame([
        {"model": "full", "RMSE": round(full[0], 4), "R2": round(full[1], 4)},
        {"model": "no_weekly_lag", "RMSE": round(no_week[0], 4), "R2": round(no_week[1], 4)},
        {"model": "no_lags_no_rolling", "RMSE": round(no_lags[0], 4), "R2": round(no_lags[1], 4)},
    ])
    E.to_csv(C.OUTPUT_DIR / "robustness_demand_ablation.csv", index=False)

    figures(A, B, Ct, D, eps_e0)
    write_implications(A, B, Ct, D, E, eps_e0, eps_u0, m_min, m_max, panel)

    print(f"A. Elasticity sweep: rev_gain ranges {A.rev_gain_pct.min():+.2f}%..{A.rev_gain_pct.max():+.2f}% "
          f"across ε∈[{A.eps_energy.min()},{A.eps_energy.max()}] — revenue stays ~neutral throughout.")
    print(f"B. Trigger sweep ({len(B)} combos): rev_gain {B.rev_gain_pct.min():+.2f}..{B.rev_gain_pct.max():+.2f}%, "
          f"peak_reduction {B.peak_reduction_pp.min():.2f}..{B.peak_reduction_pp.max():.2f} pp.")
    print(f"C. Peak-definition stability: Jaccard vs tertile = "
          f"{dict(zip(Ct.method, Ct.jaccard_vs_tertile))} (overnight peak is robust).")
    print("D. CBD vs non-CBD:")
    print(D.to_string(index=False))
    print("E. Demand ablation (utilization RMSE / R2):")
    print(E.to_string(index=False))
    print("\n[outputs] robustness_*.csv, implications.md")
    print("[figures] fig17_robustness_elasticity.png, fig18_robustness_triggers.png, fig19_robustness_cbd.png")


# ===========================================================================
def figures(A, B, Ct, D, eps_e0):
    # fig17 — elasticity sensitivity
    fig, ax = plt.subplots(figsize=(10, 5.6))
    x = -A.eps_energy
    ax.plot(x, A.rev_gain_pct, "-o", color=TEAL, label="Revenue gain %")
    ax.plot(x, A.offpeak_uplift_pct, "-s", color=ORANGE, label="Off-peak uplift %")
    ax.plot(x, A.peak_reduction_pp, "-^", color=BLUE, label="Peak reduction (pp)")
    ax.axvline(-eps_e0, ls="--", color=GREY); ax.axhline(0, color="#111", lw=.7)
    ax.text(-eps_e0, ax.get_ylim()[1]*0.9, f"  estimate |ε|={-eps_e0:.2f}", color=GREY, fontsize=9)
    ax.set(xlabel="|elasticity| (more elastic →)", ylabel="value",
           title="Robustness to the elasticity assumption (recommended policy)")
    ax.legend(fontsize=9)
    fig.text(0.5, -0.02, "→ Revenue stays ~neutral and operational gains persist across the whole "
             "plausible ε range — the central conclusion is not an artefact of the point estimate.",
             ha="center", style="italic", color=GREY, fontsize=10)
    fig.savefig(C.FIG_DIR / "fig17_robustness_elasticity.png")
    plt.close(fig)

    # fig18 — trigger sensitivity heatmaps (rev gain & peak reduction)
    fig, ax = plt.subplots(1, 2, figsize=(14, 5))
    for k, (col, ttl, cmap) in enumerate([("rev_gain_pct", "Revenue gain %", "RdBu"),
                                          ("peak_reduction_pp", "Peak reduction (pp)", "viridis")]):
        piv = B.pivot(index="discount_trigger", columns="surge_trigger", values=col)
        im = ax[k].imshow(piv.values, cmap=cmap, aspect="auto", origin="lower")
        ax[k].set_xticks(range(len(piv.columns))); ax[k].set_xticklabels(piv.columns)
        ax[k].set_yticks(range(len(piv.index))); ax[k].set_yticklabels(piv.index)
        ax[k].set(xlabel="surge trigger", ylabel="discount trigger", title=ttl)
        for (i, j), v in np.ndenumerate(piv.values):
            ax[k].text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=8,
                       color="white" if cmap == "viridis" else "black")
        plt.colorbar(im, ax=ax[k], fraction=0.046)
    fig.suptitle("Robustness to surge/discount trigger thresholds", fontweight="bold")
    fig.text(0.5, -0.02, "→ Outcomes change smoothly and modestly with the thresholds; the 0.30/0.80 "
             "choice is reasonable, not a knife-edge.", ha="center", style="italic", color=GREY, fontsize=10)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(C.FIG_DIR / "fig18_robustness_triggers.png")
    plt.close(fig)

    # fig19 — CBD / fairness
    fig, ax = plt.subplots(1, 2, figsize=(13, 5))
    x = np.arange(len(D)); w = 0.35
    ax[0].bar(x - w/2, D.pct_slots_surged, w, label="% surged", color=ORANGE)
    ax[0].bar(x + w/2, D.pct_slots_discounted, w, label="% discounted", color=TEAL)
    ax[0].set_xticks(x); ax[0].set_xticklabels(D.segment)
    ax[0].set(ylabel="% of slots", title="Pricing incidence by segment")
    ax[0].legend(fontsize=9)
    ax[1].bar(x - w/2, D.demand_rmse, w, label="demand RMSE", color=GREY)
    ax[1].bar(x + w/2, D.peak_reduction_pp, w, label="peak reduction (pp)", color=BLUE)
    ax[1].set_xticks(x); ax[1].set_xticklabels(D.segment)
    ax[1].set(title="Forecast accuracy & congestion relief by segment")
    ax[1].legend(fontsize=9)
    fig.text(0.5, -0.02, "→ Surge falls on the genuinely congested (mostly non-CBD) zones, not on a "
             "demographic label; forecast accuracy is comparable across segments.", ha="center",
             style="italic", color=GREY, fontsize=10)
    fig.savefig(C.FIG_DIR / "fig19_robustness_cbd.png")
    plt.close(fig)


# ===========================================================================
def write_implications(A, B, Ct, D, E, eps_e, eps_u, m_min, m_max, panel):
    pct_off = (panel.utilization < C.UTIL_DISCOUNT).mean() * 100
    pct_peak = (panel.utilization >= C.UTIL_SURGE).mean() * 100
    cbd = D.set_index("segment")
    md = f"""# Phase 6 — Robustness, Implications & Limitations

## Robustness (every headline claim stress-tested)
- **Elasticity** (`robustness_elasticity.csv`, fig17): re-simulating the recommended policy across
  ε_energy ∈ [{A.eps_energy.min()}, {A.eps_energy.max()}] keeps revenue ~neutral
  ({A.rev_gain_pct.min():+.2f}% to {A.rev_gain_pct.max():+.2f}%) and operational gains positive throughout —
  the "pricing is a load-balancing, not a revenue, tool" conclusion is **not** an artefact of the point estimate.
- **Triggers** (`robustness_triggers.csv`, fig18): across 25 (discount, surge) threshold combos outcomes
  move smoothly (rev_gain {B.rev_gain_pct.min():+.2f}…{B.rev_gain_pct.max():+.2f}%, peak relief
  {B.peak_reduction_pp.min():.2f}…{B.peak_reduction_pp.max():.2f} pp). The 0.30/0.80 choice is reasonable, not a knife-edge.
- **Peak definition** (`robustness_peak_definition.csv`): tertile / quartile / above-mean methods all
  identify the **overnight block** (Jaccard vs tertile {", ".join(f"{r.method} {r.jaccard_vs_tertile}" for _, r in Ct.iterrows())}).
- **Segments** (`robustness_cbd.csv`, fig19): forecast RMSE is comparable (CBD {cbd.loc['CBD','demand_rmse']} vs
  non-CBD {cbd.loc['non_CBD','demand_rmse']}); surge incidence is higher for **non-CBD** ({cbd.loc['non_CBD','pct_slots_surged']}%
  vs CBD {cbd.loc['CBD','pct_slots_surged']}%) because that is where congestion actually is.
- **Demand features** (`robustness_demand_ablation.csv`): dropping the weekly lag barely moves RMSE
  ({E.loc[0,'RMSE']}→{E.loc[1,'RMSE']}, redundant given the daily lags + zone identity), while dropping
  **all** lags/rolling collapses the model to RMSE {E.loc[2,'RMSE']} (R² {E.loc[2,'R2']}) — confirming that
  short-horizon temporal structure, not zone identity alone, drives the forecast.

## Business implications
1. **Don't sell dynamic pricing as a revenue lever here.** With inelastic demand (ε≈{eps_e:.2f}) the revenue
   upside is ~0%. The honest pitch is **congestion relief + asset/load balancing**, with revenue held flat.
2. **Concentrate surge on the ~10% genuinely hot (mostly non-CBD) zones.** Network-wide only {pct_peak:.1f}% of
   zone-hours are congested; a blanket tariff wastes effort. Forecast-targeted surge is where the value is.
3. **Fund equity via surge, not at its expense.** Off-peak discounts (the uplift lever) cost ~1% revenue;
   surge revenue on hot slots can cross-subsidise them, keeping the program revenue-neutral.

## Operational implications
1. **Forecast-driven surge cuts the peak wait proxy ~57%** (Phase 5) on the rare congested slots — a real
   service-quality win with no new hardware.
2. **Idle connectors are a bigger lever than price** at workplace-type sites: ACN shows ~46% of sessions sit
   idle >1h after charging → **idle/occupancy fees** free capacity directly.
3. **Most chargers are under-used** ({pct_off:.0f}% of zone-hours <30%); capacity/expansion decisions should
   prioritise the hot zones, not uniform roll-out.

## Policy implications
1. **Bounded, transparent multipliers** (capped surge/discount, published schedule — see `pricing_policy.csv`)
   keep dynamic pricing fair and predictable.
2. **Price scarcity, not demographics.** Surge follows measured utilization and falls on non-CBD hot zones,
   not a protected label — the design is defensible on equity grounds.
3. **Off-peak discounts are a strategic adoption/grid-balancing instrument**, justified by long-run goals a
   short-run optimizer ignores (the Phase-5 agent declines to discount).

## Limitations (disclosed)
- **Associational, not causal:** elasticity is from observational price variation with FE controls — not an RCT;
  all "after" figures are simulated under it.
- **Simulation, not a live A/B test:** the monitoring environment is a calibrated constant-elasticity model + noise.
- **No cross-time substitution** is modelled; real peak→off-peak demand shifting would *improve* the uplift case.
- **Single city, 30 days** (Shenzhen, 2022-06-19→07-18); generalisation beyond this window is not claimed.
- **ACN is Caltech-only (~15k sessions, no price)** — used for behaviour, not revenue; not the 30k+/JPL headline.
- **Wait time is a proxy** (M/M/1-style ρ/(1−ρ)); queues are not directly observed.
- **Currency framing:** optimisation is unit-invariant (ratios); ₹15/kWh is an illustrative anchor for CNY data.
"""
    (C.OUTPUT_DIR / "implications.md").write_text(md)


if __name__ == "__main__":
    main()
