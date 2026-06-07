"""
pricing.py — Phase 4: Tariff Pricing Agent.

Turns the Phase-3 demand forecast into a bounded, dynamic per-kWh tariff and quantifies
the brief's three metrics against a FLAT baseline:
  * Revenue Gain %        (vs a flat tariff = each zone's mean price; ₹15/kWh for the India view)
  * Charger Utilization   before vs after (simulated)
  * Off-Peak Uplift       % more energy in low-demand (forecast util < 0.30) slots after discounts

Method
------
1. ELASTICITY (associational, controlled — NOT causal): constant-elasticity demand curve
   q(p) = q0 * (p/p0)^eps, with eps estimated by FWL on the 108 price-varying zones
   (log q ~ log price, absorbing zone + hour-of-day + day-of-week fixed effects).
   eps_energy drives revenue; eps_util drives utilization/congestion response.
2. POLICY: a transparent bounded multiplier on the flat baseline, driven by FORECAST
   utilization u-hat (Phase 3): surge ramp for u-hat >= 0.80, discount ramp for u-hat < 0.30,
   neutral (1.0) in between — exactly the brief's triggers.
3. SIMULATION on the held-out TEST window (final 4 days, chained from Phase 3 forecasts):
   each "after" number is simulated under the estimated elasticity and labelled as such.

Because demand is INELASTIC (|eps|<1), discounting reduces per-slot revenue while surging raises
it; we therefore map the revenue<->uplift<->congestion trade-off across policy settings (a sweep)
and pick a balanced operating point, rather than assuming a free revenue lunch.

Outputs: elasticity_estimates.csv, pricing_policy.csv, tariff_simulation.csv,
         revenue_gain.csv, offpeak_uplift.csv,
         figures/fig12_pricing_policy.png, fig13_policy_frontier.png, fig14_outcomes.png
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression

import config as C

TEAL, ORANGE, GREY, RED, BLUE = "#0F766E", "#EA7317", "#64748B", "#b91c1c", "#1d4ed8"
LO, HI = C.UTIL_DISCOUNT, C.UTIL_SURGE          # 0.30 / 0.80 triggers


# ===========================================================================
# 1. Elasticity (FWL with zone + hour + dow fixed effects)
# ===========================================================================
def _fwl_elasticity(s, ycol):
    D = pd.get_dummies(s[["zone", "hour", "dayofweek"]].astype(str), drop_first=True).astype(float).values
    lp = np.log(s.price_mean.values)
    ly = np.log(s[ycol].values)
    rp = lp - LinearRegression().fit(D, lp).predict(D)
    ry = ly - LinearRegression().fit(D, ly).predict(D)
    beta = float((rp @ ry) / (rp @ rp))
    resid = ry - beta * rp
    n, k = len(ry), D.shape[1] + 2
    se = float(np.sqrt((resid @ resid) / (n - k) / (rp @ rp)))
    return beta, se, n


def estimate_elasticity(panel):
    pv = panel.groupby("zone")["price_mean"].nunique()
    zones = pv[pv > 1].index
    base = panel[panel.zone.isin(zones) & (panel.price_mean > 0)]
    rows = []
    for ycol in ["energy_kwh", "utilization"]:
        for scope, sub in [("overall", base),
                           ("peak_hours", base[base.hour.isin([0, 1, 2, 3, 4, 5, 6, 23])]),
                           ("offpeak_hours", base[base.hour.isin([9, 10, 11, 14, 15, 16, 17, 18])])]:
            s = sub[sub[ycol] > 0]
            b, se, n = _fwl_elasticity(s, ycol)
            rows.append({"target": ycol, "scope": scope, "elasticity": round(b, 4),
                         "se": round(se, 4), "ci_low": round(b - 1.96 * se, 4),
                         "ci_high": round(b + 1.96 * se, 4), "n": n, "price_varying_zones": len(zones)})
    est = pd.DataFrame(rows)
    est.to_csv(C.OUTPUT_DIR / "elasticity_estimates.csv", index=False)
    eps_e = est.query("target=='energy_kwh' and scope=='overall'").elasticity.iloc[0]
    eps_u = est.query("target=='utilization' and scope=='overall'").elasticity.iloc[0]
    return est, eps_e, eps_u


# ===========================================================================
# 2. Bounded utilization-targeting multiplier
# ===========================================================================
def multiplier(u, m_min, m_max):
    """Tariff multiplier from forecast utilization u. Surge ramp >=0.80, discount ramp <0.30."""
    u = np.clip(np.asarray(u, float), 0, 1)
    surge = 1 + (m_max - 1) * (u - HI) / (1 - HI)
    disc = 1 - (1 - m_min) * (LO - u) / LO
    return np.where(u >= HI, surge, np.where(u < LO, disc, 1.0))


def policy_table(eps_e, m_min, m_max, p_cny):
    grid = np.round(np.arange(0, 1.0001, 0.05), 2)
    m = multiplier(grid, m_min, m_max)
    region = np.where(grid >= HI, "surge", np.where(grid < LO, "discount", "neutral"))
    df = pd.DataFrame({"forecast_utilization": grid, "multiplier": np.round(m, 3),
                       "region": region,
                       "tariff_inr_per_kwh": np.round(m * C.INR_FLAT_BASELINE, 2),
                       "tariff_cny_example": np.round(m * p_cny, 3)})
    df.to_csv(C.OUTPUT_DIR / "pricing_policy.csv", index=False)
    return df


# ===========================================================================
# 3. Simulation (test window, forecast-driven)
# ===========================================================================
def simulate(test, eps_e, eps_u, m_min, m_max, p0_map):
    u_hat = test.util_pred.values
    util_obs = test.util_actual.values
    q_obs = test.energy_actual.values
    p0 = test.zone.map(p0_map).values

    m = multiplier(u_hat, m_min, m_max)
    rev_base = p0 * q_obs                       # flat baseline revenue
    rev_after = p0 * q_obs * m ** (1 + eps_e)   # = (m*p0) * q_obs*m^eps_e
    util_after = np.clip(util_obs * m ** eps_u, 0, 1)

    disc = m < 1.0      # slots that received a discount (forecast util < 0.30)
    surge = m > 1.0
    peak_obs = util_obs >= HI    # actually-congested slots
    out = {
        "rev_gain_pct": (rev_after.sum() / rev_base.sum() - 1) * 100,
        "util_before": util_obs.mean(),
        "util_after": util_after.mean(),
        "offpeak_uplift_pct": (q_obs[disc].sum() and
                               (q_obs[disc] * m[disc] ** eps_e).sum() / q_obs[disc].sum() - 1) * 100,
        "peak_util_before": util_obs[peak_obs].mean() if peak_obs.any() else np.nan,
        "peak_util_after": util_after[peak_obs].mean() if peak_obs.any() else np.nan,
        "pct_surge_slots": surge.mean() * 100,
        "pct_discount_slots": disc.mean() * 100,
    }
    out["peak_reduction_pp"] = (out["peak_util_before"] - out["peak_util_after"]) * 100
    return out, dict(m=m, rev_base=rev_base, rev_after=rev_after, util_after=util_after,
                     disc=disc, surge=surge, p0=p0)


def sweep(test, eps_e, eps_u, p0_map):
    rows = []
    for m_min in [0.70, 0.75, 0.80, 0.85, 0.90, 0.95]:
        for m_max in [1.20, 1.30, 1.40, 1.50, 1.60]:
            o, _ = simulate(test, eps_e, eps_u, m_min, m_max, p0_map)
            rows.append({"m_min": m_min, "m_max": m_max, **o})
    sw = pd.DataFrame(rows)
    # Recommendation: maximize operational benefit (off-peak uplift + peak congestion relief)
    # subject to staying ~revenue-neutral (rev gain >= -0.3%). Under inelastic demand the
    # revenue lever is weak, so the sensible objective is revenue-neutral load-shifting.
    sw["ops_benefit"] = sw.offpeak_uplift_pct + sw.peak_reduction_pp
    elig = sw[sw.rev_gain_pct >= -0.3]
    rec_idx = (elig if len(elig) else sw).sort_values("ops_benefit", ascending=False).index[0]
    sw["is_recommended"] = sw.index == rec_idx
    sw.round(4).to_csv(C.OUTPUT_DIR / "revenue_gain.csv", index=False)
    rec = sw.loc[rec_idx]
    return sw, float(rec.m_min), float(rec.m_max)


# ===========================================================================
# 4. Figures
# ===========================================================================
def figures(pol, sw, test, sim, eps_e, eps_u, m_min, m_max, p_cny):
    # fig12 — policy curve
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.axvspan(0, LO, color=TEAL, alpha=.10); ax.axvspan(HI, 1, color=ORANGE, alpha=.10)
    ax.plot(pol.forecast_utilization, pol.multiplier, color="#111", lw=2.5)
    ax.axhline(1, ls=":", color=GREY)
    ax.text(0.13, m_min + .02, "DISCOUNT", color=TEAL, fontweight="bold", ha="center")
    ax.text(0.55, 1.02, "neutral", color=GREY, ha="center")
    ax.text(0.9, m_max - .04, "SURGE", color=ORANGE, fontweight="bold", ha="center")
    ax.set(xlabel="Forecast utilization (from demand agent)", ylabel="Tariff multiplier ×",
           title=f"Dynamic tariff policy  (discount {m_min:.2f}× / surge {m_max:.2f}×)")
    ax2 = ax.twinx()
    ax2.set_ylim(ax.get_ylim()[0] * C.INR_FLAT_BASELINE, ax.get_ylim()[1] * C.INR_FLAT_BASELINE)
    ax2.set_ylabel("Illustrative tariff (₹/kWh, flat = ₹15)")
    fig.text(0.5, -0.02, "→ Transparent, bounded rule: surge only the rare congested slots, discount "
             "the genuinely empty ones, leave the middle untouched.", ha="center", style="italic",
             color=GREY, fontsize=10)
    fig.savefig(C.FIG_DIR / "fig12_pricing_policy.png")
    plt.close(fig)

    # fig13 — trade-off frontier
    fig, ax = plt.subplots(figsize=(9.5, 6))
    sc = ax.scatter(sw.rev_gain_pct, sw.offpeak_uplift_pct, c=sw.peak_reduction_pp,
                    cmap="viridis", s=70, edgecolor="white")
    plt.colorbar(sc, label="Peak utilization reduction (pp)")
    rec = sw[sw.is_recommended].iloc[0]
    ax.scatter(rec.rev_gain_pct, rec.offpeak_uplift_pct, marker="*", s=420,
               color=RED, edgecolor="black", zorder=5, label="Recommended (revenue-neutral)")
    ax.axvline(0, ls="--", color=GREY, lw=1)
    ax.set(xlabel="Revenue gain % (vs flat baseline)", ylabel="Off-peak uplift % (energy)",
           title="Policy trade-off frontier (each point = a discount/surge setting)")
    ax.legend(loc="upper right")
    fig.text(0.5, -0.02, "→ Revenue and off-peak uplift trade off under inelastic demand; the "
             "recommended point balances revenue, uplift and congestion relief.", ha="center",
             style="italic", color=GREY, fontsize=10)
    fig.savefig(C.FIG_DIR / "fig13_policy_frontier.png")
    plt.close(fig)

    # fig14 — recommended outcomes
    fig, ax = plt.subplots(1, 2, figsize=(13, 5.2))
    # before/after mean utilization by observed band
    band = np.where(test.util_actual.values >= HI, "peak (≥0.80)",
                    np.where(test.util_actual.values < LO, "off-peak (<0.30)", "shoulder"))
    dd = pd.DataFrame({"band": band, "before": test.util_actual.values, "after": sim["util_after"]})
    g = dd.groupby("band")[["before", "after"]].mean().reindex(["off-peak (<0.30)", "shoulder", "peak (≥0.80)"])
    x = np.arange(len(g)); w = 0.38
    ax[0].bar(x - w/2, g.before, w, label="before", color=GREY)
    ax[0].bar(x + w/2, g.after, w, label="after (simulated)", color=TEAL)
    ax[0].set_xticks(x); ax[0].set_xticklabels(g.index, fontsize=9)
    ax[0].set(ylabel="Mean utilization", title="Utilization before vs after (by band)")
    ax[0].legend(fontsize=9)
    # headline metrics
    rec = sw[sw.is_recommended].iloc[0]
    names = ["Revenue\ngain %", "Off-peak\nuplift %", "Peak util\nreduction (pp)"]
    vals = [rec.rev_gain_pct, rec.offpeak_uplift_pct, rec.peak_reduction_pp]
    cols = [TEAL if v >= 0 else RED for v in vals]
    ax[1].bar(names, vals, color=cols)
    for i, v in enumerate(vals):
        ax[1].text(i, v + (0.1 if v >= 0 else -0.3), f"{v:+.1f}", ha="center", fontsize=11)
    ax[1].axhline(0, color="#111", lw=.8)
    ax[1].set(title=f"Recommended policy outcomes (discount {m_min:.2f}× / surge {m_max:.2f}×)")
    fig.text(0.5, -0.02, "→ Dynamic pricing's gains here are mostly operational (uplift + congestion "
             "relief) given inelastic demand; revenue is roughly held.", ha="center", style="italic",
             color=GREY, fontsize=10)
    fig.savefig(C.FIG_DIR / "fig14_outcomes.png")
    plt.close(fig)


# ===========================================================================
def main():
    print("=" * 64, "\nPHASE 4  — Tariff Pricing Agent\n", "=" * 64, sep="")
    panel = pd.read_csv(C.OUTPUT_DIR / "urbanev_panel_hourly.csv.gz")
    test = pd.read_csv(C.OUTPUT_DIR / "demand_predictions.csv")        # Phase-3 forecasts
    p0_map = panel.groupby("zone")["price_mean"].mean().to_dict()       # flat baseline per zone
    p_cny = panel.price_mean.mean()

    est, eps_e, eps_u = estimate_elasticity(panel)
    print(f"Elasticity (associational, FWL zone+hour+dow FE): energy {eps_e:+.3f} | utilization {eps_u:+.3f}")

    sw, m_min, m_max = sweep(test, eps_e, eps_u, p0_map)
    pol = policy_table(eps_e, m_min, m_max, p_cny)
    rec_metrics, sim = simulate(test, eps_e, eps_u, m_min, m_max, p0_map)
    figures(pol, sw, test, sim, eps_e, eps_u, m_min, m_max, p_cny)

    # per-zone-hour simulation deliverable (recommended policy)
    tsim = pd.DataFrame({
        "zone": test.zone, "hour_index": test.hour_index, "timestamp": test.timestamp,
        "util_obs": test.util_actual, "util_forecast": test.util_pred,
        "region": np.where(sim["surge"], "surge", np.where(sim["disc"], "discount", "neutral")),
        "multiplier": np.round(sim["m"], 4), "p0_cny": np.round(sim["p0"], 4),
        "price_dyn_cny": np.round(sim["m"] * sim["p0"], 4),
        "energy_obs": test.energy_actual,
        "rev_base": np.round(sim["rev_base"], 4), "rev_after": np.round(sim["rev_after"], 4),
        "util_after": np.round(sim["util_after"], 4),
    }).round(5)
    tsim.to_csv(C.OUTPUT_DIR / "tariff_simulation.csv", index=False)

    # off-peak uplift breakdown (recommended)
    cbd_map = panel.groupby("zone")["CBD"].first().to_dict()
    t = tsim.assign(CBD=tsim.zone.map(cbd_map))
    d = t[t.region == "discount"]
    def uplift(frame):
        if frame.empty or frame.energy_obs.sum() == 0:
            return np.nan
        q_after = frame.energy_obs * frame.multiplier ** eps_e
        return (q_after.sum() / frame.energy_obs.sum() - 1) * 100
    up = pd.DataFrame([
        {"segment": "all_discount_slots", "uplift_pct": uplift(d), "n_slots": len(d)},
        {"segment": "CBD", "uplift_pct": uplift(d[d.CBD == 1]), "n_slots": int((d.CBD == 1).sum())},
        {"segment": "non_CBD", "uplift_pct": uplift(d[d.CBD == 0]), "n_slots": int((d.CBD == 0).sum())},
    ]).round(3)
    up.to_csv(C.OUTPUT_DIR / "offpeak_uplift.csv", index=False)

    # revenue gain by CBD + frontier corners
    rg_cbd = (t.groupby("CBD").apply(
        lambda f: (f.rev_after.sum() / f.rev_base.sum() - 1) * 100, include_groups=False).round(3))
    rmax = sw.loc[sw.rev_gain_pct.idxmax()]
    umax = sw.loc[sw.offpeak_uplift_pct.idxmax()]

    # ---- findings doc (data-driven) --------------------------------------
    rm = rec_metrics
    md = f"""# Phase 4 — Tariff Pricing Agent: logic & outcomes

## Demand response (associational, NOT causal)
Constant-elasticity demand q(p) = q0·(p/p0)^ε, estimated by FWL with zone + hour-of-day +
day-of-week fixed effects on the {int(est.price_varying_zones.iloc[0])} price-varying zones:
**ε_energy = {eps_e:+.3f}**, **ε_util = {eps_u:+.3f}** (see `elasticity_estimates.csv`). Demand is
**inelastic** (|ε| < 1). Observational price variation only — used to *simulate* response, not to
claim causation (per the brief).

## Policy (the brief's triggers)
A transparent bounded multiplier on a flat baseline (each zone's mean price; ₹15/kWh for the India
view), driven by the **Phase-3 forecast utilization**: surge ramp for û ≥ {HI:.0%}, discount ramp
for û < {LO:.0%}, neutral in between. Recommended bounds: **discount {m_min:.2f}× / surge {m_max:.2f}×**
(`pricing_policy.csv`). On the held-out test window, {rm['pct_surge_slots']:.1f}% of slots trigger
surge and {rm['pct_discount_slots']:.1f}% trigger a discount.

## Outcomes (simulated under the estimated elasticity, test = final 4 days)
| Metric | Value |
|---|---|
| **Revenue gain %** vs flat baseline | **{rm['rev_gain_pct']:+.2f}%** (CBD {rg_cbd.get(1, float('nan')):+.2f}% / non-CBD {rg_cbd.get(0, float('nan')):+.2f}%) |
| **Charger utilization** before → after | {rm['util_before']:.3f} → {rm['util_after']:.3f} |
| **Off-peak uplift %** (energy in discounted slots) | **{rm['offpeak_uplift_pct']:+.2f}%** |
| **Peak congestion relief** (util at congested slots) | {rm['peak_util_before']:.3f} → {rm['peak_util_after']:.3f} (**{rm['peak_reduction_pp']:+.2f} pp**) |

## The key (honest) finding
Because demand is **inelastic**, and off-peak slots hold far more energy than the rare congested
slots, **dynamic pricing cannot meaningfully grow revenue here** — across the whole policy sweep the
best case is **{rmax.rev_gain_pct:+.2f}%** (effectively revenue-neutral). Its real value is
**operational load-shifting**: surging the rare congested slots delivers ~{abs(rm['peak_reduction_pp']):.1f} pp
of peak relief at almost no revenue cost, while off-peak discounts add modest uplift
(up to {umax.offpeak_uplift_pct:+.2f}% at the deep-discount corner) at a small revenue cost.
We therefore recommend a **revenue-neutral load-shifting** operating point rather than chasing
revenue. The full trade-off frontier is in `revenue_gain.csv` / fig13.

→ Hand-off to Phase 5: the monitoring agent rolls this policy out episode-by-episode, tracks realized
revenue / utilization / wait-time proxy / pricing efficiency, and adapts the bounds online.
"""
    (C.OUTPUT_DIR / "pricing_findings.md").write_text(md)

    print(f"\nRecommended policy (revenue-neutral load-shifting): discount {m_min:.2f}× , surge {m_max:.2f}×")
    print(f"  Revenue gain %        : {rm['rev_gain_pct']:+.2f}   (CBD {rg_cbd.get(1, np.nan):+.2f} | non-CBD {rg_cbd.get(0, np.nan):+.2f})")
    print(f"  Utilization before    : {rm['util_before']:.4f}  ->  after {rm['util_after']:.4f}")
    print(f"  Off-peak uplift %      : {rm['offpeak_uplift_pct']:+.2f}  (energy in discounted slots)")
    print(f"  Peak util before/after: {rm['peak_util_before']:.3f} -> {rm['peak_util_after']:.3f}  ({rm['peak_reduction_pp']:+.2f} pp)")
    print(f"  Surge slots {rm['pct_surge_slots']:.1f}% | discount slots {rm['pct_discount_slots']:.1f}%")
    print(f"\nFrontier corners — revenue-max: {rmax.rev_gain_pct:+.2f}% (m_min {rmax.m_min}, m_max {rmax.m_max}); "
          f"uplift-max: {umax.offpeak_uplift_pct:+.2f}% (m_min {umax.m_min}, m_max {umax.m_max})")
    print("[outputs] elasticity_estimates.csv, pricing_policy.csv, tariff_simulation.csv, revenue_gain.csv, offpeak_uplift.csv, pricing_findings.md")
    print("[figures] fig12_pricing_policy.png, fig13_policy_frontier.png, fig14_outcomes.png")


if __name__ == "__main__":
    main()
