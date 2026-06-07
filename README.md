# OP26 — Agentic Dynamic Tariff Optimization for EV Charging Networks

Submission package. **All phases (0–7) are complete**: reproducible scaffold; preprocessing &
feature engineering; EDA + empirical peak windows; **Demand Prediction Agent**; **Tariff
Pricing Agent**; **Monitoring & Learning Agent** (the feedback loop); and **robustness + business/policy
implications**; and the **presentation deck**.

## Pipeline (run in order)
`python preprocess.py` → `python eda.py` → `python demand.py` → `python pricing.py` → `python monitoring.py` → `python robustness.py`
(or `notebooks/0{1..6}_*.ipynb`). **Verify it worked:** `python verify.py` (expect `14/14 checks passed`). Full walkthrough in `SETUP_AND_TEST.md`. Provide raw files via `export OP26_DATA=/path` or in `./data_raw/`;
`pip install -r requirements.txt` first.

| Phase | Script | Agent / step |
|---|---|---|
| 1 | `preprocess.py` | unified analytical base (ACN sessions + UrbanEV zone×hour panel) |
| 2 | `eda.py` | EDA + empirical peak/shoulder/off-peak windows |
| 3 | `demand.py` | **Demand Prediction Agent** (utilization, load, congestion prob) |
| 4 | `pricing.py` | **Tariff Pricing Agent** (elasticity → surge/discount → revenue/uplift/congestion) |
| 5 | `monitoring.py` | **Monitoring & Learning Agent** (episodic feedback loop + online learning) |
| 6 | `robustness.py` | robustness checks + business/operational/policy implications |
| 7 | `deck/build_deck.js` | presentation deck (cover + exec summary + 6 content + appendix) → `deck/OP26_deck.pptx` |

The two datasets are deliberately **kept separate** (geography/role/units) — see `ASSUMPTIONS.md` #1.

## Repository layout
```
op26/  config.py · preprocess.py · eda.py · demand.py · pricing.py · monitoring.py
       notebooks/01..06 · outputs/ · figures/ (fig01..fig19) · deck/ (build_deck.js → OP26_deck.pptx) · data_raw/
       requirements.txt · README.md · ASSUMPTIONS.md · DATA_DICTIONARY.md · FEATURE_DICTIONARY.md · RUN_LOG.txt
```

## Key outputs (in `outputs/`)
Analytical base & EDA: `urbanev_panel_hourly.csv.gz`, `clean_acn_sessions.csv`, `zone_features.csv`,
`peak_windows.csv`, `eda_*.csv`, `eda_findings.md`.
Demand agent: `demand_predictions.csv`, `demand_metrics.csv`, `demand_metrics_by_zone.csv`,
`feature_importance.csv`, `demand_model_*.joblib`.
Tariff agent: `elasticity_estimates.csv`, `pricing_policy.csv`, `tariff_simulation.csv`,
`revenue_gain.csv`, `offpeak_uplift.csv`, `pricing_findings.md`.
Monitoring agent: `episode_metrics.csv`, `monitoring_log.csv`, `learned_policy.csv`.
Robustness: `robustness_elasticity.csv`, `robustness_triggers.csv`, `robustness_peak_definition.csv`, `robustness_cbd.csv`, `robustness_demand_ablation.csv`, `implications.md`.
Deck: `deck/OP26_deck.pptx` (10 slides; rebuild with `node deck/build_deck.js`).

## Headline results (data-driven)
**EDA** — chronically under-used (61% of zone-hours <30%, only 0.9% >80%); time-of-day not day-of-week
(overnight peak, midday trough); congestion concentrated in top ~10% of zones and **not** the CBD.

**Demand agent** (test = final 4 days, 23,712 zone-hours): utilization **R² 0.959 / RMSE 0.036**
(−32% vs persistence); energy load **R² 0.971**; congestion P(util≥0.8) **AUC 0.992** (base rate 0.97%).

**Tariff agent** — elasticity **ε_energy −0.32** (inelastic). Off-peak holds ~22% of energy vs ~3% in
surge slots, so **dynamic pricing can't grow revenue** (best ≈ neutral). Recommended **revenue-neutral**
policy (0.90× / 1.60×): **−0.26% revenue, +0.81% off-peak uplift, +2.52 pp peak relief**; frontier reaches
+2.6% uplift at ~1% revenue cost.

**Monitoring & learning agent** — an ε-greedy bandit improves over episodes (peak wait-reduction proxy
29%→58%, pricing efficiency 0.848→0.868) and its online elasticity estimate converges to the true value.
It learns to **surge congested buckets, stay neutral elsewhere**, beating flat and the Phase-4 fixed policy
on revenue (**+0.58%**) and congestion (**+5.85 pp** peak relief, ~57% wait-proxy reduction) — at the cost
of zero off-peak uplift (myopically unprofitable). *(All "after" figures simulated under the estimated,
associational — not causal — elasticity.)*

## Reproducibility / honesty notes
- Fixed seed + all thresholds in `config.py`; deterministic; strict time-based split (no leakage).
- Gradient boosting via sklearn HistGradientBoosting (LightGBM unavailable offline; same algorithm family).
- Elasticity is **associational, not causal**; revenue↔uplift↔congestion trade-off mapped explicitly.
- The learning environment is a calibrated simulation (constant-elasticity demand + noise); no real A/B test.
