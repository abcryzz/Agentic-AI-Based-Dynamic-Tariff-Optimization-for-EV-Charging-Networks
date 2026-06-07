# Data Dictionary — raw inputs (verified)

Two datasets. All facts below were verified by direct inspection.

## UrbanEV / ST-EVCDP — Shenzhen, China
247 traffic zones, 2022-06-19 → 2022-07-18, **5-minute** resolution → **8,640** timesteps
(exactly 30 days). Zone IDs are the `grid` codes (102 … 1173) and align across all files.
**All four time-series matrices contain 0 missing values.**

| File | Shape | Description |
|---|---|---|
| `occupancy.csv` | 8640 × (1+247) | Occupied piles per zone per 5-min (stock). 0–220. |
| `volume.csv` | 8640 × (1+247) | Energy delivered (kWh) per zone per 5-min (flow). 0–1492. |
| `duration.csv` | 8640 × (1+247) | Charging-pile-hours per zone per 5-min. 0–17. (≈ occupancy × 5/60.) |
| `price.csv` | 8640 × (1+247) | Tariff in **CNY/kWh**. 0.25–1.47. 108 zones vary over time; 139 flat. |
| `information.csv` | 247 × 10 | Per-zone metadata (see below). |
| `stations.csv` | 1706 × 6 | Raw stations (22,872 piles) that aggregate into the 247 zones. |
| `adj.csv` | 247 × (1+247) | Binary zone adjacency (symmetric, ~5 neighbours/zone) — spatial graph. |
| `distance.csv` | 247 × (1+247) | Inter-zone distance (km, symmetric). |
| `time.csv` | 8640 × 6 | The datetime index (month, day, year, hour, minute, second). |

`information.csv` columns: `num`, `grid` (zone id), `count` (installed piles),
`fast_count`, `slow_count`, `area` (km²), `lon`, `la` (lat), `CBD` (1 = central business
district; 62 zones), `dynamic_pricing` (1 = flagged dynamic-pricing zone; 57 zones).
Network totals: 18,061 piles (2,056 fast / 16,005 slow).

`stations.csv` columns: `station_id`, `latitude`, `longitude`, `fast`, `slow`, `count`.

## ACN-Data — Caltech workplace, US
`acndata_sessions_json.xlsx` — a flattened JSON dump (one sheet). 16,304 raw rows →
**14,999 real sessions** after dropping null/separator rows; 54 stations, 204 users,
single site/cluster (siteID 2, clusterID 39), **2018-04-25 → 2018-12-16**.

Real session fields (others are JSON-wrapper artifacts and entirely null):

| Field | Description |
|---|---|
| `sessionID`, `_id` | Session identifiers. |
| `stationID`, `spaceID`, `siteID`, `clusterID` | Where the session occurred. |
| `userID`, `timezone` | User id (often null) and session timezone. |
| `connectionTime`, `disconnectTime` | Plug-in / unplug (RFC-2822 GMT strings). |
| `doneChargingTime` | When charging actually completed (≤ disconnect, usually). |
| `kWhDelivered` | Energy delivered. mean 9.0, median 7.4, max 69.4. |
| `requestedDeparture`, `kWhRequested`, `milesRequested`, `minutesAvailable`, `WhPerMile` | **User-stated inputs**, present for ~3,537 raw / 2,225 clean sessions — enable a flexibility/laxity feature. |
| `paymentRequired` | Payment flag. |

**No price field** — Caltech workplace charging is free/subsidised, hence ACN drives
behaviour analysis, not revenue (see `ASSUMPTIONS.md` #1).
