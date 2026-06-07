# Assumptions, Decisions & Limitations

The brief explicitly asks for **transparent assumptions** and **no causal claims**.
This register lists every load-bearing decision so a reviewer can see the reasoning.

## Load-bearing decisions

**1. The two datasets do different jobs — they are not merged.**
UrbanEV (Shenzhen) is the spatio-temporal engine for demand forecasting, tariff
optimization, and monitoring, because it is the only source with **price + demand +
occupancy + a spatial graph** together. ACN (Caltech) is used for session-level
behaviour, dwell/idle/overstay, repeat-user patterns, and as a real-world sanity check
on demand shape and price-flexibility — **not** for revenue (it has no price field).
Fusing them on a shared key would be misleading (different cities, years, and units).

**2. Currency / the ₹15 baseline.**
UrbanEV prices are in **CNY/kWh** (range 0.25–1.47). Every metric the rubric requires —
Revenue Gain %, utilization, off-peak uplift, revenue-per-kWh — is a **ratio and
therefore unit-invariant**, so optimization and evaluation are done in the dataset's
native units (no fabricated FX rate). For the India narrative the dynamic policy is
expressed as a **multiplier on a flat baseline** and mapped illustratively onto
₹15/kWh (`config.INR_FLAT_BASELINE`), clearly labelled as a framing, not a measured price.

**3. Utilization = `clip(occupancy / installed_piles, 0, 1)`** per zone/interval
(the brief's "Charging Time / Total Available Time"). Bounded 0–1; the raw max was 1.08
(0.01% of cells) and is clipped to 1.0. Duration-based utilization is recoverable as a
cross-check (`charging_hours`), and is consistent (duration ≈ occupancy × interval length).

**4. Queue length & wait time are PROXIES, never measured.** Neither dataset records
queues. The proxy is **saturation**: 5-min intervals where occupancy ≥ 95% of installed
piles (`saturation_count`, `is_saturated_hour`). Every wait-time figure downstream is
labelled a model-based proxy.

**5. Modeling grain = hourly (primary).** 5-min data is noisy and real tariffs switch on
coarser blocks, so the panel is aggregated to hourly (720 obs/zone). 5-min detail is
preserved where it matters via the saturation proxy. Aggregation rules: occupancy → mean
(stock), energy/charging-hours/revenue → sum (flow), price → mean (representative tariff);
revenue is computed at 5-min (`volume × price`) then summed, so it is exact.

**6. No causal claims.** Any demand-response / elasticity (Phase 4+) is an
*associational, controlled* relationship used only to **simulate** outcomes; "after
pricing" numbers are simulated under the estimated elasticity, never asserted as cause.

**7. Missing-value strategy.**
- *UrbanEV:* all four matrices are **complete (0 missing)** — verified; no imputation
  applied (the source is pre-filled). Stated rather than silently assumed.
- *ACN:* user-input fields (`requestedDeparture`, `kWhRequested`, …) are
  **missing-not-at-random** (present for ~2,225 of 14,947 sessions) and are **not
  imputed**; instead a `has_user_input` flag is carried and `laxity_hr` is left NaN where
  absent. Invalid charging times and implausible power are nulled **and flagged**.

## ACN cleaning rules (all in `config.py`)
- Drop rows with null `sessionID` (JSON-wrapper/separator rows).
- Remove sessions with non-positive dwell, dwell > **48 h** (`ACN_MAX_DURATION_HR`),
  or `kWhDelivered` < **0.5** (`ACN_MIN_KWH`). Counts logged in `data_quality_report.csv`.
- `charging_hr < 0` (done-charging logged before connection): nulled + `flag_neg_charging`.
- `avg_power_kw > 350` (`ACN_MAX_POWER_KW`, above the fastest real chargers): nulled +
  `flag_implausible_power`.
- `idle_hr` clipped at 0 (tiny negatives are clock noise) + `flag_neg_idle`.
- Timestamps parsed with an **explicit RFC-2822 format**; pandas format-inference is
  unreliable on the sparse `requestedDeparture` column (recovers 13 vs the correct 3,537).

## Known limitations (disclosed)
- **ACN coverage:** the supplied file is **Caltech only, ~15k sessions, single cluster** —
  not the "30,000+ Caltech *and* JPL" headline in the brief. Pulling JPL/more via the ACN
  API is a listed extension (not done here; no network access in this environment).
- **Single-city price panel:** dynamic pricing is learned from one city (Shenzhen) over a
  30-day window (2022-06-19 → 2022-07-18); generalisation beyond that is not claimed.
- **Geographic/behavioural mismatch:** Caltech is workplace charging (long dwell, free);
  UrbanEV is urban public charging. Cross-dataset comparisons are qualitative only.
