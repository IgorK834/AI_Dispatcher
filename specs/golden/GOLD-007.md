# GOLD-007: Domestic plan: 30-minute break after 6 h of work and the 12-hour daily work limit

- **Status:** approved by the owner on 2026-11-11 — the values are binding (a later change = spec change + human approval).
- **Covers:** FEAT-003 · AC-FEAT-003-36 · invariants 1–8, 10 ([`context.md`](../../context.md) → Optimization Engine Invariants).
- **Conventions:** [`specs/golden/README.md`](README.md) (G1–G14). Depends on proposed conventions / open questions: OQ-003-01…04 (including the PL break of 30 + 15 min, OQ-003-04).
- **Data:** synthetic (`is_synthetic = true`); not real freight-exchange offers and not real people.

> The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance.

## 1. Scenario

Driver D1 is in Katowice with a 10-pallet van without a sleeper cab. Offer J goes to Gdańsk (569 km); offer K continues from Gdańsk to Szczecin (359 km). Both are domestic, so the plan uses `pl_domestic_employee_v1`: work = driving + loading/unloading + waiting, at most 12 h per day, a break after 6 h of work, 11 h of daily rest.

## 2. Inputs

**Reference date (`MOCK_REFERENCE_DATE`):** Monday 2026-11-16; all local times are CET (UTC+1) — Europe/Warsaw and Europe/Berlin are both UTC+1 on these dates.

**Engine parameters:** `horizon_days=5`, `max_offers_per_plan=6`, `top_k_per_driver=10`, `max_pool_per_driver=60`, `node_budget_per_driver=1_500_000`, `max_first_deadhead_km=350`, `default_service_min=30`, `van_speed_factor=1.08`; objective under test: `profit` unless stated otherwise.

### 2.1 Cities

| City | Country | Lat | Lon | Time zone |
|---|---|---|---|---|
| Katowice | PL | 50.2649 | 19.0238 | Europe/Warsaw |
| Gdańsk | PL | 54.3520 | 18.6466 | Europe/Warsaw |
| Szczecin | PL | 53.4285 | 14.5528 | Europe/Warsaw |

### 2.2 Driver, state and vehicle — D1

| Field | Value |
|---|---|
| Driver | `D1` (synthetic), home base Katowice |
| Current position | Katowice |
| `available_from` | Mon 2026-11-16 06:00 (05:00Z) |
| `home_by` | none (no return constraint) |
| Counters (min) | `work_today` 0, `drive_today` 0, `work_since_break` 0, `drive_since_break` 0, `work_week` 0, `drive_week` 0, `drive_prev_week` 0 |
| Vehicle | `GOLD-VAN-10`: `VEHICLE_UP_TO_3_5_T`, `CURTAIN_SIDER`, 10 pallet places (`EUR_MIXED_6X4`), interior 4.85 × 2.10 × 2.10 m, `payload_kg` 1085, `sleeper_cab` false |
| Fuel parameters | 11.0 l/100 km empty, 13.0 l/100 km full (at 90 km/h), curve `VAN_DEFAULT_V1` (assumption) |

### 2.3 Cost profile `GOLD-CP-1`

| Parameter | Value | Label in report §17.4 |
|---|---|---|
| Currency | EUR | — |
| Fuel price | 1.81 €/l (181 minor/l) | source (V) |
| Driver cost | 14.00 €/h for work + waiting (1400 minor/h) | assumption |
| Vehicle cost | 0.12 €/km (12 minor/km) | assumption |
| Accommodation (no sleeper cab) | 55.00 € per daily rest away from base | assumption |
| Per diem (domestic plans only; 0 on international plans) | 10.59 € per day (45 zł ÷ 4.25) | source (V) |
| Toll per km PL / DE (≤ 3.5 t) | 0 / 0 | source (V) / inferred (I) for concession sections — ignored here |
| `min_profit` / `min_margin_pct` | 0.00 € / 0 % | golden input |
| `CO2_FACTOR_KG_PER_L` | 2.6 | approximation (A) |

### 2.4 Offers

| Offer | `source_offer_id` | Route | Pallets | EUR eq | kg | Price € | Pickup window (local) | Delivery window (local) | Service min |
|---|---|---|---|---|---|---|---|---|---|
| J | `GOLD-007-J` | Katowice → Gdańsk | 5 × EUR 1200×800 | 5.0 | 500 | 520.00 | Mon 11-16 06:00–08:00 | Mon 11-16 12:00–20:00 | 30 + 30 |
| K | `GOLD-007-K` | Gdańsk → Szczecin | 4 × EUR 1200×800 | 4.0 | 400 | 330.00 | Mon 11-16 14:00–20:00 | Tue 11-17 06:00–14:00 | 30 + 30 |

All offers: `vehicleProperties.type = ["VEHICLE_UP_TO_3_5_T"]`, body `CURTAIN_SIDER`, pallets `generated_mock`, service time `default` (30 min per stop, flag `SERVICE_TIME_DEFAULTED`).

### 2.5 Routing assumption

`distance_km = round_half_up(haversine_km × 1.25, 2)`; `drive_min = ceil(distance_km × 60 × van_speed_factor / 65)` (average speed 65 km/h, time multiplied by `van_speed_factor = 1.08`); same-city legs are 0 km / 0 min; the matrix is symmetric (conventions G1–G3).

| Leg | Haversine km | × 1.25 → `distance_km` | `km × 60 × 1.08 / 65` | `drive_min` (ceil) |
|---|---|---|---|---|
| Katowice ↔ Gdańsk | 455.187 | 568.98 | 567.229 | 568 |
| Katowice ↔ Szczecin | 466.800 | 583.50 | 581.705 | 582 |
| Gdańsk ↔ Szczecin | 287.200 | 359.00 | 357.895 | 358 |

## 3. Expected outcome

The chain J → K is the most profitable plan and needs two days.

### 3.1 Ranked feasible offer sets (objective `profit`; exhaustive enumeration of all pickup/delivery orders)

| Rank | Offer set | Best sequence | Profile | Net profit € | Finish | Fuel l |
|---|---|---|---|---|---|---|
| 1 | {J, K} | pick J → drop J → pick K → drop K | `pl_domestic_employee_v1` | 219.85 | Tue 11:11 | 112.612 |
| 2 | {J} | pick J → drop J | `pl_domestic_employee_v1` | 174.14 | Mon 17:13 | 69.475 |

Infeasible combinations (every order fails):

| Offer set | Sequences tried | Failure codes |
|---|---|---|

### 3.2 Rank 1 plan — schedule, load and costs (profile `pl_domestic_employee_v1`)

| # | Action | Place | Leg km | Leg drive min | Inserted on leg | Arrival | Wait min | Service start | Departure | Load after (EUR eq / kg) |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | START | Katowice | — | — | — | — | 0 | Mon 06:00 | Mon 06:00 | 0.0 / 0 |
| 1 | PICKUP J | Katowice | 0.00 | 0 | — | Mon 06:00 | 0 | Mon 06:00 | Mon 06:30 | 5.0 / 500 |
| 2 | DELIVERY J | Gdańsk | 568.98 | 568 | BREAK 30 min (Mon 12:00–Mon 12:30); BREAK 15 min (Mon 15:30–Mon 15:45) | Mon 16:43 | 0 | Mon 16:43 | Mon 17:13 | 0.0 / 0 |
| 3 | PICKUP K | Gdańsk | 0.00 | 0 | — | Mon 17:13 | 0 | Mon 17:13 | Mon 17:43 | 4.0 / 400 |
| 4 | DELIVERY K | Szczecin | 359.00 | 358 | DAILY_REST 660 min (Mon 18:45–Tue 05:45) | Tue 10:41 | 0 | Tue 10:41 | Tue 11:11 | 0.0 / 0 |

Fuel per leg (`L100 = (c_empty + (c_full − c_empty) × load_kg / payload_kg) × speed_curve(v)`, `v = km × 60 / drive_min`):

| Leg | km | drive min | v km/h | curve(v) | load kg | L/100 km | litres (3 dp) |
|---|---|---|---|---|---|---|---|
| Katowice → Katowice | 0.00 | 0 | — | — | 0 | — | 0.000 |
| Katowice → Gdańsk | 568.98 | 568 | 60.104 | 1.02422 | 500 | 12.2104 | 69.475 |
| Gdańsk → Gdańsk | 0.00 | 0 | — | — | 0 | — | 0.000 |
| Gdańsk → Szczecin | 359.00 | 358 | 60.168 | 1.02374 | 400 | 12.0160 | 43.137 |
| **Total** | **927.98** | **926** | | | | | **112.612** |

Totals and cost breakdown (EUR; minor units are cents):

| Item | Arithmetic | Value |
|---|---|---|
| Distance | Σ legs (empty km: 0) | 927.98 km |
| Driving | Σ leg drive min | 926 min |
| Service | 4 stops × 30 min | 120 min |
| Waiting | | 0 min |
| Work (drive + service + wait) | 926 + 120 + 0 | 1046 min |
| Breaks / daily rests inserted | | 45 min / 660 min |
| Start → finish | Mon 06:00 → Tue 11:11 (2026-11-16T05:00Z → 2026-11-17T10:11Z) | 1751 min |
| Revenue | Σ offer prices | 850.00 |
| Fuel cost | 112.612 l × 1.81 €/l | 203.83 |
| Toll cost | PL/DE ≤ 3.5 t: 0 €/km | 0.00 |
| Driver cost | 1046 min ÷ 60 × 14.00 €/h | 244.07 |
| Per diem | domestic, 1751 min = 24 h + 311 min → 1.5 × 10.59 (G9) | 15.89 |
| Accommodation | 1 daily rest(s) away from base, sleeper cab: no | 55.00 |
| Vehicle cost | 927.98 km × 0.12 €/km | 111.36 |
| **Total cost** | | **630.15** |
| **Net profit** | 850.00 − 630.15 | **219.85** (margin 25.86 %) |
| CO₂ | 112.612 l × 2.6 kg/l | 292.79 kg |

Counter trace (minutes): `PICKUP J` 30 → drive 330 → work since break 360 → `BREAK` 30 (Mon 12:00–12:30) → drive 180 → daily work 540 → `BREAK` 15 (Mon 15:30–15:45) → drive 58 → arrive Gdańsk Mon 16:43 with daily work 598 → `DELIVERY J` 30 → 628 → `PICKUP K` 30 → 658 → drive 62 → daily work 720 (and work since the 30-minute break 360) at Mon 18:45 → `DAILY_REST` 660 → Tue 05:45 → drive 296 → arrive Szczecin Tue 10:41 → `DELIVERY K` 30.

## 4. Assertions a test must make

1. The rank 1 plan for objective `profit` contains exactly offers {J, K} in the order `PICKUP J → DELIVERY J → PICKUP K → DELIVERY K`.
2. `load_pallet_eq_after` per stop = 5.0 → 0.0 → 4.0 → 0.0; `load_kg_after` = 500 → 0 → 400 → 0; both stay within the vehicle capacity (invariant 1).
3. `rules_profile = pl_domestic_employee_v1`.
4. Service start times: PJ Mon 06:00, DJ Mon 16:43, PK Mon 17:13, DK Tue 10:41; every one lies inside its window (invariant 4).
5. Totals: `distance_km = 927.98`, `drive_min = 926`, `work_min = 1046`, `wait_min = 0`, breaks 45 min, daily rests 660 min, `finish_at = 2026-11-17T10:11Z`.
6. `fuel_l = 112.612`, `co2_kg = 292.79` (= `fuel_l × 2.6`, invariant 17).
7. Cost breakdown in minor units: fuel 20383, toll 0, driver 24407, per diem 1589, accommodation 5500, vehicle 11136; `cost_total_minor = 63015`; `revenue_minor = 85000`; `net_profit_minor = 21985` (reconstruction exact to 1 minor unit, invariant 7).
8. `RouteValidator` accepts the plan; running the optimisation twice on the same snapshot gives an identical result (invariant 8).
9. Inserted events on day 1: `BREAK` 30 min at Mon 12:00 (work since break = 30 + 330 = 360 min), `BREAK` 15 min at Mon 15:30 (daily work reaches 540 min; total break 45 min for a day with more than 9 h of work — proposed rule G4), `DAILY_REST` 660 min at Mon 18:45 (daily work reaches 720 min = 12 h).
10. Daily work on Monday = 720 min exactly; on Tuesday = 296 + 30 = 326 min; no break is needed on Tuesday (326 ≤ 360).
11. One accommodation (55.00 €) is charged: the daily rest is taken away from the base and the van has no sleeper cab.
12. Rank order of offer sets: {J, K} > {J} ({J} alone: 673 min, half a per diem, 174.14 €). K alone is not offered as a first pickup: the deadhead Katowice → Gdańsk (568.98 km) exceeds `max_first_deadhead_km = 350` → rejection `FIRST_DEADHEAD_TOO_LONG` applies to K as a *first* stop only.

## 5. Open questions

- **OQ-003-04 (blocking for the exact times of this case):** the Act requires a 45-minute break when daily work exceeds 9 h. `context.md` says the break is taken whole in the MVP, but a whole 45-minute break needs look-ahead at the 6-hour mark. This case uses the proposed rule G4 (30 min at 6 h + 15 min at 9 h). If the owner chooses "always 45 min", the first break becomes 45 min, the second disappears, and the times after Mon 12:00 do not change from 15:45 on.
