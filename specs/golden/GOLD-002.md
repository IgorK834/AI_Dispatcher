# GOLD-002: Tempting detour

- **Status:** approved by the owner on 2026-11-11 — the values are binding (a later change = spec change + human approval).
- **Covers:** FEAT-003 · AC-FEAT-003-31 · invariants 1–8, 10 ([`context.md`](../../context.md) → Optimization Engine Invariants).
- **Conventions:** [`specs/golden/README.md`](README.md) (G1–G14). Depends on proposed conventions / open questions: OQ-003-01…04.
- **Data:** synthetic (`is_synthetic = true`); not real freight-exchange offers and not real people.

> The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance.

## 1. Scenario

Driver D1 is in Katowice with a 10-pallet van. Offer A runs west (Katowice → Wrocław, 200 €). Offer X (Kraków → Częstochowa, 115 €) looks attractive — it adds 57 % revenue and its delivery point lies roughly on the way to Wrocław — but its pickup is an 87 km detour to the east. A greedy "take everything that fits" strategy accepts X; the engine must recognise that the detour costs more than it earns.

## 2. Inputs

**Reference date (`MOCK_REFERENCE_DATE`):** Monday 2026-11-16; all local times are CET (UTC+1) — Europe/Warsaw and Europe/Berlin are both UTC+1 on these dates.

**Engine parameters:** `horizon_days=5`, `max_offers_per_plan=6`, `top_k_per_driver=10`, `max_pool_per_driver=60`, `node_budget_per_driver=1_500_000`, `max_first_deadhead_km=350`, `default_service_min=30`, `van_speed_factor=1.08`; objective under test: `profit` unless stated otherwise.

### 2.1 Cities

| City | Country | Lat | Lon | Time zone |
|---|---|---|---|---|
| Katowice | PL | 50.2649 | 19.0238 | Europe/Warsaw |
| Wrocław | PL | 51.1079 | 17.0385 | Europe/Warsaw |
| Kraków | PL | 50.0647 | 19.9450 | Europe/Warsaw |
| Częstochowa | PL | 50.8118 | 19.1203 | Europe/Warsaw |

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
| A | `GOLD-002-A` | Katowice → Wrocław | 3 × EUR 1200×800 | 3.0 | 300 | 200.00 | Mon 11-16 06:00–12:00 | Mon 11-16 08:00–20:00 | 30 + 30 |
| X | `GOLD-002-X` | Kraków → Częstochowa | 2 × EUR 1200×800 | 2.0 | 200 | 115.00 | Mon 11-16 06:00–12:00 | Mon 11-16 08:00–20:00 | 30 + 30 |

All offers: `vehicleProperties.type = ["VEHICLE_UP_TO_3_5_T"]`, body `CURTAIN_SIDER`, pallets `generated_mock`, service time `default` (30 min per stop, flag `SERVICE_TIME_DEFAULTED`).

### 2.5 Routing assumption

`distance_km = round_half_up(haversine_km × 1.25, 2)`; `drive_min = ceil(distance_km × 60 × van_speed_factor / 65)` (average speed 65 km/h, time multiplied by `van_speed_factor = 1.08`); same-city legs are 0 km / 0 min; the matrix is symmetric (conventions G1–G3).

| Leg | Haversine km | × 1.25 → `distance_km` | `km × 60 × 1.08 / 65` | `drive_min` (ceil) |
|---|---|---|---|---|
| Katowice ↔ Wrocław | 168.360 | 210.45 | 209.802 | 210 |
| Katowice ↔ Kraków | 69.289 | 86.61 | 86.344 | 87 |
| Katowice ↔ Częstochowa | 61.194 | 76.49 | 76.255 | 77 |
| Wrocław ↔ Kraków | 235.690 | 294.61 | 293.704 | 294 |
| Wrocław ↔ Częstochowa | 149.470 | 186.84 | 186.265 | 187 |
| Kraków ↔ Częstochowa | 101.549 | 126.94 | 126.549 | 127 |

## 3. Expected outcome

Offer A alone wins. The combined plan is feasible but less profitable.

### 3.1 Ranked feasible offer sets (objective `profit`; exhaustive enumeration of all pickup/delivery orders)

| Rank | Offer set | Best sequence | Profile | Net profit € | Finish | Fuel l |
|---|---|---|---|---|---|---|
| 1 | {A} | pick A → drop A | `pl_domestic_employee_v1` | 66.68 | Mon 10:30 | 24.898 |
| 2 | {A, X} | pick A → pick X → drop X → drop A | `pl_domestic_employee_v1` | 53.34 | Mon 15:11 | 47.925 |

Infeasible combinations (every order fails):

| Offer set | Sequences tried | Failure codes |
|---|---|---|

### 3.2 Rank 1 plan — schedule, load and costs (profile `pl_domestic_employee_v1`)

| # | Action | Place | Leg km | Leg drive min | Inserted on leg | Arrival | Wait min | Service start | Departure | Load after (EUR eq / kg) |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | START | Katowice | — | — | — | — | 0 | Mon 06:00 | Mon 06:00 | 0.0 / 0 |
| 1 | PICKUP A | Katowice | 0.00 | 0 | — | Mon 06:00 | 0 | Mon 06:00 | Mon 06:30 | 3.0 / 300 |
| 2 | DELIVERY A | Wrocław | 210.45 | 210 | — | Mon 10:00 | 0 | Mon 10:00 | Mon 10:30 | 0.0 / 0 |

Fuel per leg (`L100 = (c_empty + (c_full − c_empty) × load_kg / payload_kg) × speed_curve(v)`, `v = km × 60 / drive_min`):

| Leg | km | drive min | v km/h | curve(v) | load kg | L/100 km | litres (3 dp) |
|---|---|---|---|---|---|---|---|
| Katowice → Katowice | 0.00 | 0 | — | — | 0 | — | 0.000 |
| Katowice → Wrocław | 210.45 | 210 | 60.129 | 1.02404 | 300 | 11.8307 | 24.898 |
| **Total** | **210.45** | **210** | | | | | **24.898** |

Totals and cost breakdown (EUR; minor units are cents):

| Item | Arithmetic | Value |
|---|---|---|
| Distance | Σ legs (empty km: 0) | 210.45 km |
| Driving | Σ leg drive min | 210 min |
| Service | 2 stops × 30 min | 60 min |
| Waiting | | 0 min |
| Work (drive + service + wait) | 210 + 60 + 0 | 270 min |
| Breaks / daily rests inserted | | 0 min / 0 min |
| Start → finish | Mon 06:00 → Mon 10:30 (2026-11-16T05:00Z → 2026-11-16T09:30Z) | 270 min |
| Revenue | Σ offer prices | 200.00 |
| Fuel cost | 24.898 l × 1.81 €/l | 45.07 |
| Toll cost | PL/DE ≤ 3.5 t: 0 €/km | 0.00 |
| Driver cost | 270 min ÷ 60 × 14.00 €/h | 63.00 |
| Per diem | domestic, 270 min < 8 h (G9) | 0.00 |
| Accommodation | 0 daily rest(s) away from base, sleeper cab: no | 0.00 |
| Vehicle cost | 210.45 km × 0.12 €/km | 25.25 |
| **Total cost** | | **133.32** |
| **Net profit** | 200.00 − 133.32 | **66.68** (margin 33.34 %) |
| CO₂ | 24.898 l × 2.6 kg/l | 64.73 kg |

## 4. Assertions a test must make

1. The rank 1 plan for objective `profit` contains exactly offers {A} in the order `PICKUP A → DELIVERY A`.
2. `load_pallet_eq_after` per stop = 3.0 → 0.0; `load_kg_after` = 300 → 0; both stay within the vehicle capacity (invariant 1).
3. `rules_profile = pl_domestic_employee_v1`.
4. Service start times: PA Mon 06:00, DA Mon 10:00; every one lies inside its window (invariant 4).
5. Totals: `distance_km = 210.45`, `drive_min = 210`, `work_min = 270`, `wait_min = 0`, breaks 0 min, daily rests 0 min, `finish_at = 2026-11-16T09:30Z`.
6. `fuel_l = 24.898`, `co2_kg = 64.73` (= `fuel_l × 2.6`, invariant 17).
7. Cost breakdown in minor units: fuel 4507, toll 0, driver 6300, per diem 0, accommodation 0, vehicle 2525; `cost_total_minor = 13332`; `revenue_minor = 20000`; `net_profit_minor = 6668` (reconstruction exact to 1 minor unit, invariant 7).
8. `RouteValidator` accepts the plan; running the optimisation twice on the same snapshot gives an identical result (invariant 8).
9. The set {A, X} is feasible and ranks second with `net_profit_minor = 5334`: adding X raises revenue by 115.00 € but raises cost by 128.34 € (including half a domestic per diem, 5.30 €, because the trip grows to 551 min), so profit drops by 13.34 €.
10. No plan consists of X alone: its single-offer plan earns −19.05 € (< `min_profit`), so it is not returned.

## 5. Open questions

- None beyond the shared conventions.
