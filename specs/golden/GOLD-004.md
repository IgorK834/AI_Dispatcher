# GOLD-004: Time window forces the delivery order

- **Status:** approved by the owner on 2026-11-11 — the values are binding (a later change = spec change + human approval).
- **Covers:** FEAT-003 · AC-FEAT-003-33 · invariants 1–8, 10 ([`context.md`](../../context.md) → Optimization Engine Invariants).
- **Conventions:** [`specs/golden/README.md`](README.md) (G1–G14). Depends on proposed conventions / open questions: OQ-003-01…04.
- **Data:** synthetic (`is_synthetic = true`); not real freight-exchange offers and not real people.

> The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance.

## 1. Scenario

Driver D2 is in Wrocław with a 10-pallet van. Offers G (to Opole) and H (to Katowice) both load in Wrocław early in the morning. Opole lies on the road to Katowice, so the short route delivers G first. But G can only be unloaded from 12:00, while H must be unloaded by 11:00. The engine must drive past Opole, deliver H in Katowice first and come back to Opole.

## 2. Inputs

**Reference date (`MOCK_REFERENCE_DATE`):** Monday 2026-11-16; all local times are CET (UTC+1) — Europe/Warsaw and Europe/Berlin are both UTC+1 on these dates.

**Engine parameters:** `horizon_days=5`, `max_offers_per_plan=6`, `top_k_per_driver=10`, `max_pool_per_driver=60`, `node_budget_per_driver=1_500_000`, `max_first_deadhead_km=350`, `default_service_min=30`, `van_speed_factor=1.08`; objective under test: `profit` unless stated otherwise.

### 2.1 Cities

| City | Country | Lat | Lon | Time zone |
|---|---|---|---|---|
| Wrocław | PL | 51.1079 | 17.0385 | Europe/Warsaw |
| Opole | PL | 50.6751 | 17.9213 | Europe/Warsaw |
| Katowice | PL | 50.2649 | 19.0238 | Europe/Warsaw |

### 2.2 Driver, state and vehicle — D2

| Field | Value |
|---|---|
| Driver | `D2` (synthetic), home base Wrocław |
| Current position | Wrocław |
| `available_from` | Mon 2026-11-16 06:00 (05:00Z) |
| `home_by` | none (no return constraint) |
| Counters (min) | `work_today` 0, `drive_today` 0, `work_since_break` 0, `drive_since_break` 0, `work_week` 0, `drive_week` 0, `drive_prev_week` 0 |
| Vehicle | `GOLD-VAN-10S`: `VEHICLE_UP_TO_3_5_T`, `CURTAIN_SIDER`, 10 pallet places (`EUR_MIXED_6X4`), interior 4.85 × 2.10 × 2.10 m, `payload_kg` 1050, `sleeper_cab` true |
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
| G | `GOLD-004-G` | Wrocław → Opole | 3 × EUR 1200×800 | 3.0 | 300 | 150.00 | Mon 11-16 06:00–08:00 | Mon 11-16 12:00–15:00 | 30 + 30 |
| H | `GOLD-004-H` | Wrocław → Katowice | 3 × EUR 1200×800 | 3.0 | 350 | 220.00 | Mon 11-16 06:00–08:00 | Mon 11-16 08:00–11:00 | 30 + 30 |

All offers: `vehicleProperties.type = ["VEHICLE_UP_TO_3_5_T"]`, body `CURTAIN_SIDER`, pallets `generated_mock`, service time `default` (30 min per stop, flag `SERVICE_TIME_DEFAULTED`).

### 2.5 Routing assumption

`distance_km = round_half_up(haversine_km × 1.25, 2)`; `drive_min = ceil(distance_km × 60 × van_speed_factor / 65)` (average speed 65 km/h, time multiplied by `van_speed_factor = 1.08`); same-city legs are 0 km / 0 min; the matrix is symmetric (conventions G1–G3).

| Leg | Haversine km | × 1.25 → `distance_km` | `km × 60 × 1.08 / 65` | `drive_min` (ceil) |
|---|---|---|---|---|
| Wrocław ↔ Opole | 78.422 | 98.03 | 97.728 | 98 |
| Wrocław ↔ Katowice | 168.360 | 210.45 | 209.802 | 210 |
| Opole ↔ Katowice | 90.380 | 112.98 | 112.632 | 113 |

## 3. Expected outcome

Both offers are delivered, H first. The plan is 112 km longer than the geographic order but it is the only feasible order for the pair.

### 3.1 Ranked feasible offer sets (objective `profit`; exhaustive enumeration of all pickup/delivery orders)

| Rank | Offer set | Best sequence | Profile | Net profit € | Finish | Fuel l |
|---|---|---|---|---|---|---|
| 1 | {G, H} | pick G → pick H → drop H → drop G | `pl_domestic_employee_v1` | 155.83 | Mon 13:53 | 39.775 |
| 2 | {H} | pick H → drop H | `pl_domestic_employee_v1` | 86.24 | Mon 10:30 | 25.143 |
| 3 | {G} | pick G → drop G | `pl_domestic_employee_v1` | 26.20 | Mon 13:00 | 11.625 |

Infeasible combinations (every order fails):

| Offer set | Sequences tried | Failure codes |
|---|---|---|

### 3.2 Rank 1 plan — schedule, load and costs (profile `pl_domestic_employee_v1`)

| # | Action | Place | Leg km | Leg drive min | Inserted on leg | Arrival | Wait min | Service start | Departure | Load after (EUR eq / kg) |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | START | Wrocław | — | — | — | — | 0 | Mon 06:00 | Mon 06:00 | 0.0 / 0 |
| 1 | PICKUP G | Wrocław | 0.00 | 0 | — | Mon 06:00 | 0 | Mon 06:00 | Mon 06:30 | 3.0 / 300 |
| 2 | PICKUP H | Wrocław | 0.00 | 0 | — | Mon 06:30 | 0 | Mon 06:30 | Mon 07:00 | 6.0 / 650 |
| 3 | DELIVERY H | Katowice | 210.45 | 210 | — | Mon 10:30 | 0 | Mon 10:30 | Mon 11:00 | 3.0 / 300 |
| 4 | DELIVERY G | Opole | 112.98 | 113 | BREAK 30 min (Mon 12:00–Mon 12:30) | Mon 13:23 | 0 | Mon 13:23 | Mon 13:53 | 0.0 / 0 |

Fuel per leg (`L100 = (c_empty + (c_full − c_empty) × load_kg / payload_kg) × speed_curve(v)`, `v = km × 60 / drive_min`):

| Leg | km | drive min | v km/h | curve(v) | load kg | L/100 km | litres (3 dp) |
|---|---|---|---|---|---|---|---|
| Wrocław → Wrocław | 0.00 | 0 | — | — | 0 | — | 0.000 |
| Wrocław → Wrocław | 0.00 | 0 | — | — | 300 | — | 0.000 |
| Wrocław → Katowice | 210.45 | 210 | 60.129 | 1.02404 | 650 | 12.5322 | 26.374 |
| Katowice → Opole | 112.98 | 113 | 59.989 | 1.02508 | 300 | 11.8616 | 13.401 |
| **Total** | **323.43** | **323** | | | | | **39.775** |

Totals and cost breakdown (EUR; minor units are cents):

| Item | Arithmetic | Value |
|---|---|---|
| Distance | Σ legs (empty km: 0) | 323.43 km |
| Driving | Σ leg drive min | 323 min |
| Service | 4 stops × 30 min | 120 min |
| Waiting | | 0 min |
| Work (drive + service + wait) | 323 + 120 + 0 | 443 min |
| Breaks / daily rests inserted | | 30 min / 0 min |
| Start → finish | Mon 06:00 → Mon 13:53 (2026-11-16T05:00Z → 2026-11-16T12:53Z) | 473 min |
| Revenue | Σ offer prices | 370.00 |
| Fuel cost | 39.775 l × 1.81 €/l | 71.99 |
| Toll cost | PL/DE ≤ 3.5 t: 0 €/km | 0.00 |
| Driver cost | 443 min ÷ 60 × 14.00 €/h | 103.37 |
| Per diem | domestic, 473 min < 8 h (G9) | 0.00 |
| Accommodation | 0 daily rest(s) away from base, sleeper cab: yes | 0.00 |
| Vehicle cost | 323.43 km × 0.12 €/km | 38.81 |
| **Total cost** | | **214.17** |
| **Net profit** | 370.00 − 214.17 | **155.83** (margin 42.12 %) |
| CO₂ | 39.775 l × 2.6 kg/l | 103.42 kg |

## 4. Assertions a test must make

1. The rank 1 plan for objective `profit` contains exactly offers {G, H} in the order `PICKUP G → PICKUP H → DELIVERY H → DELIVERY G`.
2. `load_pallet_eq_after` per stop = 3.0 → 6.0 → 3.0 → 0.0; `load_kg_after` = 300 → 650 → 300 → 0; both stay within the vehicle capacity (invariant 1).
3. `rules_profile = pl_domestic_employee_v1`.
4. Service start times: PG Mon 06:00, PH Mon 06:30, DH Mon 10:30, DG Mon 13:23; every one lies inside its window (invariant 4).
5. Totals: `distance_km = 323.43`, `drive_min = 323`, `work_min = 443`, `wait_min = 0`, breaks 30 min, daily rests 0 min, `finish_at = 2026-11-16T12:53Z`.
6. `fuel_l = 39.775`, `co2_kg = 103.42` (= `fuel_l × 2.6`, invariant 17).
7. Cost breakdown in minor units: fuel 7199, toll 0, driver 10337, per diem 0, accommodation 0, vehicle 3881; `cost_total_minor = 21417`; `revenue_minor = 37000`; `net_profit_minor = 15583` (reconstruction exact to 1 minor unit, invariant 7).
8. `RouteValidator` accepts the plan; running the optimisation twice on the same snapshot gives an identical result (invariant 8).
9. `DELIVERY H` (Katowice) precedes `DELIVERY G` (Opole) although Opole lies on the way to Katowice. The geographic order (Opole first) arrives in Opole at Mon 08:38, must wait for the window to open at 12:00, and then reaches Katowice after H's window closed at 11:00 → `DELIVERY_WINDOW_MISSED`.
10. A 30-minute `BREAK` is inserted at Mon 12:00, when work since the start reaches 6 h (30 + 30 + 210 + 30 + 60 = 360 min).
11. Rank order of offer sets: {G, H} > {H} > {G}.

## 5. Open questions

- The single-offer plan {G} includes 232 minutes of waiting at Opole, counted as work (Core Domain Rule 9). Its exact profit depends on the waiting semantics of convention G7 (OQ-003-06); a test should assert only its rank, not its value.
