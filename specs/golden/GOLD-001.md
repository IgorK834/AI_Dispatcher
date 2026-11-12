# GOLD-001: Consolidated loads on one van (example from report §3.2)

- **Status:** approved by the owner on 2026-11-11 — the values are binding (a later change = spec change + human approval).
- **Covers:** FEAT-003 · AC-FEAT-003-30 · invariants 1–8, 10, 14, 17 ([`context.md`](../../context.md) → Optimization Engine Invariants).
- **Conventions:** [`specs/golden/README.md`](README.md) (G1–G14). Depends on proposed conventions / open questions: OQ-003-01…03 (routing time formula, speed curve, rounding). Per diem follows convention G9 (decided 2026-11-11).
- **Data:** synthetic (`is_synthetic = true`); not real freight-exchange offers and not real people.

> The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance.

## 1. Scenario

Driver D1 stands in Katowice with a 10-pallet curtain-sider van (payload 1 085 kg). Three offers lie along the corridor Katowice → Opole → Wrocław → Dresden → Leipzig. The engine must combine all three: `pick A → pick B → drop A → pick C → drop B → drop C`. Pallets on board go 4 → 8 → 4 → 6 → 2 → 0 (≤ 10) and mass 380 → 800 → 420 → 620 → 200 → 0 kg (≤ 1 085). Offers B and C cross the PL/DE border, so the whole plan is computed with `eu561_van_international_v1`. `home_by` is not set, so the plan ends at the last delivery.

## 2. Inputs

**Reference date (`MOCK_REFERENCE_DATE`):** Monday 2026-11-16; all local times are CET (UTC+1) — Europe/Warsaw and Europe/Berlin are both UTC+1 on these dates.

**Engine parameters:** `horizon_days=5`, `max_offers_per_plan=6`, `top_k_per_driver=10`, `max_pool_per_driver=60`, `node_budget_per_driver=1_500_000`, `max_first_deadhead_km=350`, `default_service_min=30`, `van_speed_factor=1.08`; objective under test: `profit` unless stated otherwise.

### 2.1 Cities

| City | Country | Lat | Lon | Time zone |
|---|---|---|---|---|
| Katowice | PL | 50.2649 | 19.0238 | Europe/Warsaw |
| Wrocław | PL | 51.1079 | 17.0385 | Europe/Warsaw |
| Opole | PL | 50.6751 | 17.9213 | Europe/Warsaw |
| Dresden | DE | 51.0504 | 13.7373 | Europe/Berlin |
| Leipzig | DE | 51.3397 | 12.3731 | Europe/Berlin |

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
| A | `GOLD-001-A` | Katowice → Wrocław | 4 × EUR 1200×800 | 4.0 | 380 | 190.00 | Mon 11-16 06:00–10:00 | Mon 11-16 08:00–16:00 | 30 + 30 |
| B | `GOLD-001-B` | Opole → Dresden | 4 × EUR 1200×800 | 4.0 | 420 | 300.00 | Mon 11-16 07:00–12:00 | Mon 11-16 12:00–20:00 | 30 + 30 |
| C | `GOLD-001-C` | Wrocław → Leipzig | 2 × EUR 1200×800 | 2.0 | 200 | 290.00 | Mon 11-16 09:00–14:00 | Tue 11-17 06:00–12:00 | 30 + 30 |

All offers: `vehicleProperties.type = ["VEHICLE_UP_TO_3_5_T"]`, body `CURTAIN_SIDER`, pallets `generated_mock`, service time `default` (30 min per stop, flag `SERVICE_TIME_DEFAULTED`).

### 2.5 Routing assumption

`distance_km = round_half_up(haversine_km × 1.25, 2)`; `drive_min = ceil(distance_km × 60 × van_speed_factor / 65)` (average speed 65 km/h, time multiplied by `van_speed_factor = 1.08`); same-city legs are 0 km / 0 min; the matrix is symmetric (conventions G1–G3).

| Leg | Haversine km | × 1.25 → `distance_km` | `km × 60 × 1.08 / 65` | `drive_min` (ceil) |
|---|---|---|---|---|
| Katowice ↔ Wrocław | 168.360 | 210.45 | 209.802 | 210 |
| Katowice ↔ Opole | 90.380 | 112.98 | 112.632 | 113 |
| Katowice ↔ Dresden | 382.665 | 478.33 | 476.858 | 477 |
| Katowice ↔ Leipzig | 482.227 | 602.78 | 600.925 | 601 |
| Wrocław ↔ Opole | 78.422 | 98.03 | 97.728 | 98 |
| Wrocław ↔ Dresden | 230.684 | 288.36 | 287.473 | 288 |
| Wrocław ↔ Leipzig | 325.860 | 407.33 | 406.077 | 407 |
| Opole ↔ Dresden | 296.559 | 370.70 | 369.559 | 370 |
| Opole ↔ Leipzig | 395.056 | 493.82 | 492.301 | 493 |
| Dresden ↔ Leipzig | 100.355 | 125.44 | 125.054 | 126 |

## 3. Expected outcome

The three-offer plan is the most profitable. At Wrocław `DELIVERY A` and `PICKUP C` cost the same in either order; the tie-break of convention G12 (deliveries before pickups, then offer id) puts `DELIVERY A` first.

### 3.1 Ranked feasible offer sets (objective `profit`; exhaustive enumeration of all pickup/delivery orders)

| Rank | Offer set | Best sequence | Profile | Net profit € | Finish | Fuel l |
|---|---|---|---|---|---|---|
| 1 | {A, B, C} | pick A → pick B → drop A → pick C → drop B → drop C | `eu561_van_international_v1` | 323.54 | Tue 07:55 | 76.601 |
| 2 | {A, B} | pick A → pick B → drop A → drop B | `eu561_van_international_v1` | 175.48 | Mon 17:04 | 60.866 |
| 3 | {B, C} | pick B → pick C → drop B → drop C | `eu561_van_international_v1` | 145.62 | Tue 06:30 | 75.085 |
| 4 | {A} | pick A → drop A | `pl_domestic_employee_v1` | 56.11 | Mon 10:30 | 25.215 |
| 5 | {A, C} | pick A → drop A → pick C → drop C | `eu561_van_international_v1` | 40.85 | Tue 06:30 | 72.664 |
| 6 | {B} | pick B → drop B | `eu561_van_international_v1` | 11.29 | Mon 15:48 | 57.440 |

The feasible {A, C} sequence delivers A in Wrocław on Monday at 10:00 and picks C there at 10:30. On the 407-minute leg to Leipzig, a 45-minute break starts Monday 12:00 and an 11-hour daily rest starts Monday 17:15. Arrival is Tuesday 05:32; 28 minutes of waiting precede delivery at 06:00–06:30. Fuel is 72.664 l, total cost is 439.15 €, and profit is 40.85 €. The other orders of {A, C} may miss windows, but that does not make the offer set infeasible.

### 3.2 Rank 1 plan — schedule, load and costs (profile `eu561_van_international_v1`)

| # | Action | Place | Leg km | Leg drive min | Inserted on leg | Arrival | Wait min | Service start | Departure | Load after (EUR eq / kg) |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | START | Katowice | — | — | — | — | 0 | Mon 06:00 | Mon 06:00 | 0.0 / 0 |
| 1 | PICKUP A | Katowice | 0.00 | 0 | — | Mon 06:00 | 0 | Mon 06:00 | Mon 06:30 | 4.0 / 380 |
| 2 | PICKUP B | Opole | 112.98 | 113 | — | Mon 08:23 | 0 | Mon 08:23 | Mon 08:53 | 8.0 / 800 |
| 3 | DELIVERY A | Wrocław | 98.03 | 98 | — | Mon 10:31 | 0 | Mon 10:31 | Mon 11:01 | 4.0 / 420 |
| 4 | PICKUP C | Wrocław | 0.00 | 0 | — | Mon 11:01 | 0 | Mon 11:01 | Mon 11:31 | 6.0 / 620 |
| 5 | DELIVERY B | Dresden | 288.36 | 288 | BREAK 45 min (Mon 12:00–Mon 12:45) | Mon 17:04 | 0 | Mon 17:04 | Mon 17:34 | 2.0 / 200 |
| 6 | DELIVERY C | Leipzig | 125.44 | 126 | BREAK 45 min (Mon 17:45–Mon 18:30); DAILY_REST 660 min (Mon 19:00–Tue 06:00) | Tue 07:25 | 0 | Tue 07:25 | Tue 07:55 | 0.0 / 0 |

Fuel per leg (`L100 = (c_empty + (c_full − c_empty) × load_kg / payload_kg) × speed_curve(v)`, `v = km × 60 / drive_min`):

| Leg | km | drive min | v km/h | curve(v) | load kg | L/100 km | litres (3 dp) |
|---|---|---|---|---|---|---|---|
| Katowice → Katowice | 0.00 | 0 | — | — | 0 | — | 0.000 |
| Katowice → Opole | 112.98 | 113 | 59.989 | 1.02508 | 380 | 11.9939 | 13.551 |
| Opole → Wrocław | 98.03 | 98 | 60.018 | 1.02486 | 800 | 12.7848 | 12.533 |
| Wrocław → Wrocław | 0.00 | 0 | — | — | 420 | — | 0.000 |
| Wrocław → Dresden | 288.36 | 288 | 60.075 | 1.02444 | 620 | 12.4396 | 35.871 |
| Dresden → Leipzig | 125.44 | 126 | 59.733 | 1.02700 | 200 | 11.6756 | 14.646 |
| **Total** | **624.81** | **625** | | | | | **76.601** |

Totals and cost breakdown (EUR; minor units are cents):

| Item | Arithmetic | Value |
|---|---|---|
| Distance | Σ legs (empty km: 0) | 624.81 km |
| Driving | Σ leg drive min | 625 min |
| Service | 6 stops × 30 min | 180 min |
| Waiting | | 0 min |
| Work (drive + service + wait) | 625 + 180 + 0 | 805 min |
| Breaks / daily rests inserted | | 90 min / 660 min |
| Start → finish | Mon 06:00 → Tue 07:55 (2026-11-16T05:00Z → 2026-11-17T06:55Z) | 1555 min |
| Revenue | Σ offer prices | 780.00 |
| Fuel cost | 76.601 l × 1.81 €/l | 138.65 |
| Toll cost | PL/DE ≤ 3.5 t: 0 €/km | 0.00 |
| Driver cost | 805 min ÷ 60 × 14.00 €/h | 187.83 |
| Per diem | international plan (stops in DE) → none (G9) | 0.00 |
| Accommodation | 1 daily rest(s) away from base, sleeper cab: no | 55.00 |
| Vehicle cost | 624.81 km × 0.12 €/km | 74.98 |
| **Total cost** | | **456.46** |
| **Net profit** | 780.00 − 456.46 | **323.54** (margin 41.48 %) |
| CO₂ | 76.601 l × 2.6 kg/l | 199.16 kg |

Counter trace (minutes): after `PICKUP C` at Mon 11:31 — work since break 331, driving since break 211, driving today 211. 29 minutes into the leg to Dresden work since break reaches 360 → `BREAK` 45 (the 561 profile always inserts 45-minute breaks, G5). Arrival at Dresden with driving today 499. On the last leg: 11 minutes → driving since break 270 → `BREAK` 45; 30 more minutes → driving today 540 and the clock reaches Mon 19:00 = day start 06:00 + 13 h → `DAILY_REST` 11 h; remaining 85 minutes on Tuesday.

## 4. Assertions a test must make

1. The rank 1 plan for objective `profit` contains exactly offers {A, B, C} in the order `PICKUP A → PICKUP B → DELIVERY A → PICKUP C → DELIVERY B → DELIVERY C`.
2. `load_pallet_eq_after` per stop = 4.0 → 8.0 → 4.0 → 6.0 → 2.0 → 0.0; `load_kg_after` = 380 → 800 → 420 → 620 → 200 → 0; both stay within the vehicle capacity (invariant 1).
3. `rules_profile = eu561_van_international_v1`.
4. Service start times: PA Mon 06:00, PB Mon 08:23, DA Mon 10:31, PC Mon 11:01, DB Mon 17:04, DC Tue 07:25; every one lies inside its window (invariant 4).
5. Totals: `distance_km = 624.81`, `drive_min = 625`, `work_min = 805`, `wait_min = 0`, breaks 90 min, daily rests 660 min, `finish_at = 2026-11-17T06:55Z`.
6. `fuel_l = 76.601`, `co2_kg = 199.16` (= `fuel_l × 2.6`, invariant 17).
7. Cost breakdown in minor units: fuel 13865, toll 0, driver 18783, per diem 0, accommodation 5500, vehicle 7498; `cost_total_minor = 45646`; `revenue_minor = 78000`; `net_profit_minor = 32354` (reconstruction exact to 1 minor unit, invariant 7).
8. `RouteValidator` accepts the plan; running the optimisation twice on the same snapshot gives an identical result (invariant 8).
9. Inserted events: `BREAK` 45 min at Mon 12:00 (6 h of work reached before 4 h 30 min of driving), `BREAK` 45 min at Mon 17:45 (4 h 30 min of driving since the previous break), `DAILY_REST` 660 min at Mon 19:00 (9 h of daily driving and the 13-hour span are both reached).
10. The plan carries the warning flags `LOADING_ORDER_NOT_MODELLED` and `SERVICE_TIME_DEFAULTED`.
11. The returned top-K list has 6 entries with distinct offer sets in the order of §3.1 (invariant 10).
12. Objective `fastest` ranks {A} first (`finish_at` Mon 10:30); objective `fuel` ranks {A} first (25.215 l). Both satisfy invariant 16 against the `profit` plan.

## 5. Open questions

- The per-diem line is 0 because the plan is international (convention G9, decided 2026-11-11). For the same reason the single-offer plan {B} is profitable (11.29 €: revenue 300.00 − fuel 103.97 − driver 126.70 − vehicle 58.04; 543 min of work, one 45-minute break, no rest) and is returned as rank 6; {C} alone still loses money.
- The second 45-minute break starts 11 minutes into the last leg and is followed 30 minutes later by the daily rest. This is what the as-soon-as-possible forward schedule produces (convention G6); a smarter placement is out of MVP scope.

## 6. Changelog

- 2026-11-11: Owner approved correction of the exhaustive ranking: the feasible sequence `pick A → drop A → pick C → drop C` is rank 5 (40.85 €, finish Tuesday 06:30, fuel 72.664 l); {B} moves to rank 6. The three-offer winner and every one of its values are unchanged.
