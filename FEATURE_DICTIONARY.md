# Feature Dictionary — engineered outputs

Definitions for every column in the Phase-1 output tables.

## `urbanev_panel_hourly.csv.gz` — zone × hour panel (177,840 rows = 247 zones × 720 hours)

### Keys & raw aggregates
| Column | Unit | Definition |
|---|---|---|
| `hour_index` | — | 0–719, sequential hour since 2022-06-19 00:00. |
| `zone` | — | UrbanEV zone (grid) id. |
| `timestamp` | datetime | Hour-start. |
| `occupancy_mean` | piles | Mean occupied piles during the hour (mean of 12 × 5-min). |
| `energy_kwh` | kWh | Total energy delivered in the hour (sum of 5-min volume). |
| `charging_hours` | pile-hours | Total charging-pile-hours in the hour (sum of 5-min duration). |
| `price_mean` | CNY/kWh | Representative tariff in the hour (mean of 5-min price). |
| `revenue` | CNY | Hourly revenue = Σ(5-min energy × 5-min price) — **exact**, not mean×mean. |
| `capacity` | piles | Installed piles in the zone (from `information.count`). |
| `area` | km² | Zone area. |

### Economic / operational features (the brief's required set)
| Column | Unit | Definition |
|---|---|---|
| `utilization` | 0–1 | **Primary utilization** = clip(occupancy_mean / capacity, 0, 1). |
| `occupancy_density` | piles/km² | occupancy_mean / area. |
| `revenue_per_kwh` | CNY/kWh | revenue / energy_kwh (NaN when energy = 0). Pricing-efficiency base. |
| `saturation_count` | 0–12 | **Queue/saturation proxy**: # of 5-min intervals at ≥95% capacity. |
| `is_saturated_hour` | bool | saturation_count > 0. |
| `util_band` | cat | `peak` (util ≥ 0.80) / `offpeak` (util < 0.30) / `shoulder` (between). |

### Calendar & spatial
| Column | Definition |
|---|---|
| `hour`, `dayofweek`, `is_weekend`, `date` | Calendar fields from `timestamp`. |
| `hour_sin`, `hour_cos`, `dow_sin`, `dow_cos` | Cyclical encodings for modelling. |
| `CBD` | 1 if central-business-district zone. |
| `dynamic_pricing` | 1 if zone flagged as a dynamic-pricing zone in the source. |
| `fast_count`, `slow_count` | Fast / slow piles in the zone. |

### Lag & rolling (per zone, time-ordered; shifted to prevent leakage)
| Column | Definition |
|---|---|
| `util_lag{1,2,3,24,168}` | Utilization 1–3 h ago, same hour yesterday (24), same hour last week (168). |
| `energy_lag{1,2,3,24,168}` | Same lags for energy. |
| `util_roll3_mean`, `util_roll3_std` | Trailing 3-h mean / std of utilization (shifted by 1). |
| `util_roll24_mean` | Trailing 24-h mean of utilization (shifted by 1). |
| `has_full_lags` | bool — True once `util_lag168` exists (after the first week; ~77% of rows). |

## `zone_features.csv` — static per-zone profile (247 rows)
`zone`, `capacity`, `area`, `CBD`, `dynamic_pricing`, `fast_count`, `slow_count`,
`util_mean`, `util_max`, `energy_mean`, `price_mean`, `revenue_total`,
`pct_hours_peak` (share of hours with util ≥ 0.80), `pct_hours_offpeak` (share < 0.30).

## `clean_acn_sessions.csv` — Caltech sessions (14,947 rows)

### Identifiers & raw fields
`sessionID`, `_id`, `stationID`, `spaceID`, `siteID`, `clusterID`, `userID`, `timezone`,
`connectionTime`, `disconnectTime`, `doneChargingTime`, `requestedDeparture` (UTC),
`connect_local` (Caltech local), `kWhDelivered`, `kWhRequested`, `milesRequested`,
`minutesAvailable`, `WhPerMile`, `paymentRequired`.

### Engineered features
| Column | Unit | Definition |
|---|---|---|
| `duration_hr` | h | Total dwell = disconnect − connection. |
| `charging_hr` | h | Actual charging = doneCharging − connection (NaN if invalid). |
| `idle_hr` | h | Post-charge overstay = disconnect − doneCharging (clipped ≥ 0). |
| `requested_stay_hr` | h | requestedDeparture − connection (where user input present). |
| `laxity_hr` | h | Scheduling slack = requested_stay_hr − charging_hr. |
| `avg_power_kw` | kW | kWhDelivered / charging_hr (NaN if > 350 kW or charging_hr ≤ 0). |
| `hour`, `dayofweek`, `is_weekend`, `month`, `date` | — | Calendar (Caltech local). |
| `has_user_input` | bool | requestedDeparture present (enables laxity). |
| `user_session_count` | — | # sessions by this user (repeat-usage signal). |

### Quality flags (rows kept; flags carried for transparency)
`flag_nonpos_duration`, `flag_long_duration`, `flag_low_kwh` (these three drive removal),
`flag_neg_charging`, `flag_implausible_power`, `flag_neg_idle`.
