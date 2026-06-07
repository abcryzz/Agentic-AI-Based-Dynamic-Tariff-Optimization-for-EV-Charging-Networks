# Phase 2 — EDA Findings (each tied to a pricing implication)

All figures are in `figures/`. Two band concepts are kept distinct:
**operational bands** (per zone-hour: util ≥ 80% surge, < 30% discount — the brief's triggers)
and **temporal peak windows** (which *hours* are systematically busy — defined below).

## 1. The network is chronically under-used (fig01, fig04)
Only **0.9%** of zone-hours exceed the 80% surge trigger, while **61.1%** fall
below the 30% discount trigger. → **Implication:** the dominant revenue/efficiency lever is
**off-peak discounting to fill empty capacity**, with surge as a targeted, secondary tool.

## 2. Demand is driven by time-of-day, not day-of-week (fig01, fig02)
Occupancy peaks **overnight / early-morning** (00:00, 01:00, 02:00, 03:00, 04:00, 05:00, 06:00, 23:00) — vehicles sit plugged in — and
troughs **midday** (09:00, 10:00, 11:00, 14:00, 15:00, 16:00, 17:00, 18:00). Weekend and weekday means are nearly identical
(0.28 vs 0.28), so the cycle is intraday, not weekly. Even the overnight peak
(~0.33) stays far below the 80% surge trigger, while midday dips under the
30% discount line. → **Implication:** the **discount window is daytime**; the demand
agent (Phase 3) can exploit strong, learnable daily seasonality; network-wide surge is essentially
absent and belongs to the zone-level tail (§4), not a time-of-day rule.

## 3. The quiet midday window is modestly the least predictable (fig03)
Coefficient of variation by band — off-peak 0.62, shoulder 0.60,
peak 0.60. The gaps are small but consistent: the daytime trough is the noisiest.
→ **Implication:** daytime discounts should be **scheduled/sustained** rather than triggered reactively
off a volatile signal; the overnight peak is comparatively stable.

## 4. Congestion is concentrated in a few zones — and they are NOT the CBD (fig04, fig05, fig06)
A small set of zones is persistently busy: the **top 10% of zones account for ~100% of all
surge-trigger (util ≥ 80%) incidence**. Counter-intuitively the CBD is **not** that hot set —
CBD zones average **0.24** utilization vs **0.29** for
non-CBD, and none of the 12 busiest zones are CBD. → **Implication:** surge must be **targeted by observed
zone utilization, not by the CBD label**; the rest of the network (most CBD zones included) is discount
territory, and adjacent busy/idle zones enable spatial load-shifting.

## 5. Demand responds to price (fig07) — associational, to be confirmed
Across the **108** price-varying zones, a log-energy ~ log-price model (zone + hour fixed effects)
gives a **preliminary elasticity ≈ -0.32** (higher price ↔ lower demand). This is
**associational, not causal** (per the brief) and is re-estimated rigorously in Phase 4.
→ **Implication:** price is a real demand lever, so the tariff agent can plausibly move utilization.

## 6. ACN behaviour: idle connectors, a morning rush, and mostly anonymous sessions (fig08)
Median dwell **4.7h** but median charging only
**2.2h**; median **18%** of plug-in time is
idle, and **46%** of sessions sit idle >1h after charging. Arrivals spike in the
morning (workplace charging). Only **15%** of sessions carry a user id; among
those identified users demand is concentrated (Gini ≈ 0.58; top-10% of users ≈
40% of identified sessions), and they leave
**1.3h** of median slack before their stated departure.
→ **Implication:** **idle/occupancy fees** plus a **morning-arrival surge** can free capacity without new
hardware; high slack (laxity) means price nudges can shift load — but user-level personalisation is limited
by the 85% anonymity.

## Hand-off to Phase 3 & 4
- **Phase 3 (demand agent):** strong daily/weekly seasonality + spatial structure → use lag/rolling
  + cyclical + zone features; `peak_windows.csv` provides the time-of-use scaffolding.
- **Phase 4 (tariff agent):** asymmetric policy (discount-led, targeted surge); seed elasticity with
  the ≈ -0.32 preliminary estimate, then refine with controls.
