# Phase 6 — Robustness, Implications & Limitations

## Robustness (every headline claim stress-tested)
- **Elasticity** (`robustness_elasticity.csv`, fig17): re-simulating the recommended policy across
  ε_energy ∈ [-0.8, -0.1] keeps revenue ~neutral
  (-0.34% to -0.08%) and operational gains positive throughout —
  the "pricing is a load-balancing, not a revenue, tool" conclusion is **not** an artefact of the point estimate.
- **Triggers** (`robustness_triggers.csv`, fig18): across 25 (discount, surge) threshold combos outcomes
  move smoothly (rev_gain -0.80…+0.77%, peak relief
  0.59…4.69 pp). The 0.30/0.80 choice is reasonable, not a knife-edge.
- **Peak definition** (`robustness_peak_definition.csv`): tertile / quartile / above-mean methods all
  identify the **overnight block** (Jaccard vs tertile tertile_top 1.0, quartile_top 0.75, above_mean 0.727).
- **Segments** (`robustness_cbd.csv`, fig19): forecast RMSE is comparable (CBD 0.0277 vs
  non-CBD 0.0379); surge incidence is higher for **non-CBD** (0.86%
  vs CBD 0.07%) because that is where congestion actually is.
- **Demand features** (`robustness_demand_ablation.csv`): dropping the weekly lag barely moves RMSE
  (0.0356→0.035, redundant given the daily lags + zone identity), while dropping
  **all** lags/rolling collapses the model to RMSE 0.0832 (R² 0.7763) — confirming that
  short-horizon temporal structure, not zone identity alone, drives the forecast.

## Business implications
1. **Don't sell dynamic pricing as a revenue lever here.** With inelastic demand (ε≈-0.32) the revenue
   upside is ~0%. The honest pitch is **congestion relief + asset/load balancing**, with revenue held flat.
2. **Concentrate surge on the ~10% genuinely hot (mostly non-CBD) zones.** Network-wide only 0.9% of
   zone-hours are congested; a blanket tariff wastes effort. Forecast-targeted surge is where the value is.
3. **Fund equity via surge, not at its expense.** Off-peak discounts (the uplift lever) cost ~1% revenue;
   surge revenue on hot slots can cross-subsidise them, keeping the program revenue-neutral.

## Operational implications
1. **Forecast-driven surge cuts the peak wait proxy ~57%** (Phase 5) on the rare congested slots — a real
   service-quality win with no new hardware.
2. **Idle connectors are a bigger lever than price** at workplace-type sites: ACN shows ~46% of sessions sit
   idle >1h after charging → **idle/occupancy fees** free capacity directly.
3. **Most chargers are under-used** (61% of zone-hours <30%); capacity/expansion decisions should
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
