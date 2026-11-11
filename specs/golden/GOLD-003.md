# GOLD-003: Mass exceeded although the pallet count fits

- **Status:** approved by the owner on 2026-11-11 — the values are binding (a later change = spec change + human approval).
- **Covers:** FEAT-003 · AC-FEAT-003-32 · invariants 1, 2, 7–10 ([`context.md`](../../context.md) → Optimization Engine Invariants).
- **Conventions:** [`specs/golden/README.md`](README.md) (G1–G14). Depends on proposed conventions / open questions: OQ-003-01…03.
- **Data:** synthetic (`is_synthetic = true`); not real freight-exchange offers and not real people.

> The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance.

## 1. Scenario

Driver D5 is in Kraków with an 8-pallet van whose payload is only 765 kg. Offers E and F both load in Kraków between 06:00 and 07:00 and each has 4 euro pallets. Together they fill exactly 8 pallet places, but they weigh 850 kg. Mass, not pallet places, is the binding constraint.

## 2. Inputs

**Reference date (`MOCK_REFERENCE_DATE`):** Monday 2026-11-16; all local times are CET (UTC+1) — Europe/Warsaw and Europe/Berlin are both UTC+1 on these dates.

**Engine parameters:** `horizon_days=5`, `max_offers_per_plan=6`, `top_k_per_driver=10`, `max_pool_per_driver=60`, `node_budget_per_driver=1_500_000`, `max_first_deadhead_km=350`, `default_service_min=30`, `van_speed_factor=1.08`; objective under test: `profit` unless stated otherwise.

### 2.1 Cities

| City | Country | Lat | Lon | Time zone |
|---|---|---|---|---|
| Kraków | PL | 50.0647 | 19.9450 | Europe/Warsaw |
| Katowice | PL | 50.2649 | 19.0238 | Europe/Warsaw |
| Opole | PL | 50.6751 | 17.9213 | Europe/Warsaw |

### 2.2 Driver, state and vehicle — D5

| Field | Value |
|---|---|
| Driver | `D5` (synthetic), home base Kraków |
| Current position | Kraków |
| `available_from` | Mon 2026-11-16 06:00 (05:00Z) |
| `home_by` | none (no return constraint) |
| Counters (min) | `work_today` 0, `drive_today` 0, `work_since_break` 0, `drive_since_break` 0, `work_week` 0, `drive_week` 0, `drive_prev_week` 0 |
| Vehicle | `GOLD-VAN-8`: `VEHICLE_UP_TO_3_5_T`, `CURTAIN_SIDER`, 8 pallet places (`EUR_MIXED_5X3`), interior 4.20 × 2.10 × 2.15 m, `payload_kg` 765, `sleeper_cab` false |
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
| E | `GOLD-003-E` | Kraków → Katowice | 4 × EUR 1200×800 | 4.0 | 450 | 140.00 | Mon 11-16 06:00–07:00 | Mon 11-16 07:00–12:00 | 30 + 30 |
| F | `GOLD-003-F` | Kraków → Opole | 4 × EUR 1200×800 | 4.0 | 400 | 230.00 | Mon 11-16 06:00–07:00 | Mon 11-16 08:00–14:00 | 30 + 30 |

All offers: `vehicleProperties.type = ["VEHICLE_UP_TO_3_5_T"]`, body `CURTAIN_SIDER`, pallets `generated_mock`, service time `default` (30 min per stop, flag `SERVICE_TIME_DEFAULTED`).

### 2.5 Routing assumption

`distance_km = round_half_up(haversine_km × 1.25, 2)`; `drive_min = ceil(distance_km × 60 × van_speed_factor / 65)` (average speed 65 km/h, time multiplied by `van_speed_factor = 1.08`); same-city legs are 0 km / 0 min; the matrix is symmetric (conventions G1–G3).

| Leg | Haversine km | × 1.25 → `distance_km` | `km × 60 × 1.08 / 65` | `drive_min` (ceil) |
|---|---|---|---|---|
| Kraków ↔ Katowice | 69.289 | 86.61 | 86.344 | 87 |
| Kraków ↔ Opole | 158.760 | 198.45 | 197.839 | 198 |
| Katowice ↔ Opole | 90.380 | 112.98 | 112.632 | 113 |

## 3. Expected outcome

The engine returns the two single-offer plans and never co-loads E and F.

### 3.1 Ranked feasible offer sets (objective `profit`; exhaustive enumeration of all pickup/delivery orders)

| Rank | Offer set | Best sequence | Profile | Net profit € | Finish | Fuel l |
|---|---|---|---|---|---|---|
| 1 | {F} | pick F → drop F | `pl_domestic_employee_v1` | 101.68 | Mon 10:18 | 24.478 |
| 2 | {E} | pick E → drop E | `pl_domestic_employee_v1` | 75.71 | Mon 08:27 | 10.831 |

Infeasible combinations (every order fails):

| Offer set | Sequences tried | Failure codes |
|---|---|---|
| {E, F} | 6 infeasible | `OVERWEIGHT`, `PICKUP_WINDOW_MISSED` |

### 3.2 Rank 1 plan — schedule, load and costs (profile `pl_domestic_employee_v1`)

| # | Action | Place | Leg km | Leg drive min | Inserted on leg | Arrival | Wait min | Service start | Departure | Load after (EUR eq / kg) |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | START | Kraków | — | — | — | — | 0 | Mon 06:00 | Mon 06:00 | 0.0 / 0 |
| 1 | PICKUP F | Kraków | 0.00 | 0 | — | Mon 06:00 | 0 | Mon 06:00 | Mon 06:30 | 4.0 / 400 |
| 2 | DELIVERY F | Opole | 198.45 | 198 | — | Mon 09:48 | 0 | Mon 09:48 | Mon 10:18 | 0.0 / 0 |

Fuel per leg (`L100 = (c_empty + (c_full − c_empty) × load_kg / payload_kg) × speed_curve(v)`, `v = km × 60 / drive_min`):

| Leg | km | drive min | v km/h | curve(v) | load kg | L/100 km | litres (3 dp) |
|---|---|---|---|---|---|---|---|
| Kraków → Kraków | 0.00 | 0 | — | — | 0 | — | 0.000 |
| Kraków → Opole | 198.45 | 198 | 60.136 | 1.02398 | 400 | 12.3346 | 24.478 |
| **Total** | **198.45** | **198** | | | | | **24.478** |

Totals and cost breakdown (EUR; minor units are cents):

| Item | Arithmetic | Value |
|---|---|---|
| Distance | Σ legs (empty km: 0) | 198.45 km |
| Driving | Σ leg drive min | 198 min |
| Service | 2 stops × 30 min | 60 min |
| Waiting | | 0 min |
| Work (drive + service + wait) | 198 + 60 + 0 | 258 min |
| Breaks / daily rests inserted | | 0 min / 0 min |
| Start → finish | Mon 06:00 → Mon 10:18 (2026-11-16T05:00Z → 2026-11-16T09:18Z) | 258 min |
| Revenue | Σ offer prices | 230.00 |
| Fuel cost | 24.478 l × 1.81 €/l | 44.31 |
| Toll cost | PL/DE ≤ 3.5 t: 0 €/km | 0.00 |
| Driver cost | 258 min ÷ 60 × 14.00 €/h | 60.20 |
| Per diem | domestic, 258 min < 8 h (G9) | 0.00 |
| Accommodation | 0 daily rest(s) away from base, sleeper cab: no | 0.00 |
| Vehicle cost | 198.45 km × 0.12 €/km | 23.81 |
| **Total cost** | | **128.32** |
| **Net profit** | 230.00 − 128.32 | **101.68** (margin 44.21 %) |
| CO₂ | 24.478 l × 2.6 kg/l | 63.64 kg |

## 4. Assertions a test must make

1. The rank 1 plan for objective `profit` contains exactly offers {F} in the order `PICKUP F → DELIVERY F`.
2. `load_pallet_eq_after` per stop = 4.0 → 0.0; `load_kg_after` = 400 → 0; both stay within the vehicle capacity (invariant 1).
3. `rules_profile = pl_domestic_employee_v1`.
4. Service start times: PF Mon 06:00, DF Mon 09:48; every one lies inside its window (invariant 4).
5. Totals: `distance_km = 198.45`, `drive_min = 198`, `work_min = 258`, `wait_min = 0`, breaks 0 min, daily rests 0 min, `finish_at = 2026-11-16T09:18Z`.
6. `fuel_l = 24.478`, `co2_kg = 63.64` (= `fuel_l × 2.6`, invariant 17).
7. Cost breakdown in minor units: fuel 4431, toll 0, driver 6020, per diem 0, accommodation 0, vehicle 2381; `cost_total_minor = 12832`; `revenue_minor = 23000`; `net_profit_minor = 10168` (reconstruction exact to 1 minor unit, invariant 7).
8. `RouteValidator` accepts the plan; running the optimisation twice on the same snapshot gives an identical result (invariant 8).
9. No returned plan contains both E and F. With both on board the pallet count is 8 (= 8 places, allowed) but the mass is 450 + 400 = 850 kg > 765 kg → every order that co-loads them fails with `OVERWEIGHT`; every sequential order misses a pickup window.
10. The result contains exactly two plans: {F} (101.68 €) then {E} (75.71 €).

## 5. Open questions

- None beyond the shared conventions.
