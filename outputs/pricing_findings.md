# Phase 4 — Tariff Pricing Agent: logic & outcomes

## Demand response (associational, NOT causal)
Constant-elasticity demand q(p) = q0·(p/p0)^ε, estimated by FWL with zone + hour-of-day +
day-of-week fixed effects on the 108 price-varying zones:
**ε_energy = -0.321**, **ε_util = -0.248** (see `elasticity_estimates.csv`). Demand is
**inelastic** (|ε| < 1). Observational price variation only — used to *simulate* response, not to
claim causation (per the brief).

## Policy (the brief's triggers)
A transparent bounded multiplier on a flat baseline (each zone's mean price; ₹15/kWh for the India
view), driven by the **Phase-3 forecast utilization**: surge ramp for û ≥ 80%, discount ramp
for û < 30%, neutral in between. Recommended bounds: **discount 0.90× / surge 1.60×**
(`pricing_policy.csv`). On the held-out test window, 0.7% of slots trigger
surge and 58.7% trigger a discount.

## Outcomes (simulated under the estimated elasticity, test = final 4 days)
| Metric | Value |
|---|---|
| **Revenue gain %** vs flat baseline | **-0.26%** (CBD -0.55% / non-CBD -0.22%) |
| **Charger utilization** before → after | 0.292 → 0.293 |
| **Off-peak uplift %** (energy in discounted slots) | **+0.81%** |
| **Peak congestion relief** (util at congested slots) | 0.873 → 0.847 (**+2.52 pp**) |

## The key (honest) finding
Because demand is **inelastic**, and off-peak slots hold far more energy than the rare congested
slots, **dynamic pricing cannot meaningfully grow revenue here** — across the whole policy sweep the
best case is **-0.08%** (effectively revenue-neutral). Its real value is
**operational load-shifting**: surging the rare congested slots delivers ~2.5 pp
of peak relief at almost no revenue cost, while off-peak discounts add modest uplift
(up to +2.58% at the deep-discount corner) at a small revenue cost.
We therefore recommend a **revenue-neutral load-shifting** operating point rather than chasing
revenue. The full trade-off frontier is in `revenue_gain.csv` / fig13.

→ Hand-off to Phase 5: the monitoring agent rolls this policy out episode-by-episode, tracks realized
revenue / utilization / wait-time proxy / pricing efficiency, and adapts the bounds online.
