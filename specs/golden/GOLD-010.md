# GOLD-010: Industrial pallets (1.5 EUR equivalents) overflow an 8-pallet van

- **Status:** approved by the owner on 2026-11-11 — the values are binding (a later change = spec change + human approval).
- **Covers:** FEAT-003 · AC-FEAT-003-39 · invariants 1, 2, 7–10 ([`context.md`](../../context.md) → Optimization Engine Invariants).
- **Conventions:** [`specs/golden/README.md`](README.md) (G1–G14). Depends on proposed conventions / open questions: OQ-003-01…03.
- **Data:** synthetic (`is_synthetic = true`); not real freight-exchange offers and not real people.

> The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance.

## 1. Scenario

Driver D4 is in Łódź with an 8-pallet van (payload 880 kg). Three offers load in Łódź at the same time and all go to Warszawa. Offer P has 4 industrial pallets (1200×1000), each counted as 1.5 euro-pallet equivalents. By pallet count P + Q is 7 ≤ 8, but in equivalents it is 9.0 > 8. P + R is exactly 8.0 and fits.

## 2. Inputs

**Reference date (`MOCK_REFERENCE_DATE`):** Monday 2026-11-16; all local times are CET (UTC+1) — Europe/Warsaw and Europe/Berlin are both UTC+1 on these dates.

**Engine parameters:** `horizon_days=5`, `max_offers_per_plan=6`, `top_k_per_driver=10`, `max_pool_per_driver=60`, `node_budget_per_driver=1_500_000`, `max_first_deadhead_km=350`, `default_service_min=30`, `van_speed_factor=1.08`; objective under test: `profit` unless stated otherwise.

### 2.1 Cities

| City | Country | Lat | Lon | Time zone |
|---|---|---|---|---|
| Łódź | PL | 51.7592 | 19.4560 | Europe/Warsaw |
| Warszawa | PL | 52.2297 | 21.0122 | Europe/Warsaw |

### 2.2 Driver, state and vehicle — D4

| Field | Value |
|---|---|
| Driver | `D4` (synthetic), home base Łódź |
| Current position | Łódź |
| `available_from` | Mon 2026-11-16 06:00 (05:00Z) |
| `home_by` | none (no return constraint) |
| Counters (min) | `work_today` 0, `drive_today` 0, `work_since_break` 0, `drive_since_break` 0, `work_week` 0, `drive_week` 0, `drive_prev_week` 0 |
| Vehicle | `GOLD-VAN-8B`: `VEHICLE_UP_TO_3_5_T`, `CURTAIN_SIDER`, 8 pallet places (`EUR_MIXED_5X3`), interior 4.20 × 2.10 × 2.30 m, `payload_kg` 880, `sleeper_cab` false |
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
| P | `GOLD-010-P` | Łódź → Warszawa | 4 × industrial 1200×1000 | 6.0 | 320 | 210.00 | Mon 11-16 06:00–07:00 | Mon 11-16 08:00–14:00 | 30 + 30 |
| Q | `GOLD-010-Q` | Łódź → Warszawa | 3 × EUR 1200×800 | 3.0 | 240 | 150.00 | Mon 11-16 06:00–07:00 | Mon 11-16 08:00–14:00 | 30 + 30 |
| R | `GOLD-010-R` | Łódź → Warszawa | 2 × EUR 1200×800 | 2.0 | 160 | 100.00 | Mon 11-16 06:00–07:00 | Mon 11-16 08:00–14:00 | 30 + 30 |

All offers: `vehicleProperties.type = ["VEHICLE_UP_TO_3_5_T"]`, body `CURTAIN_SIDER`, pallets `generated_mock`, service time `default` (30 min per stop, flag `SERVICE_TIME_DEFAULTED`).

### 2.5 Routing assumption

`distance_km = round_half_up(haversine_km × 1.25, 2)`; `drive_min = ceil(distance_km × 60 × van_speed_factor / 65)` (average speed 65 km/h, time multiplied by `van_speed_factor = 1.08`); same-city legs are 0 km / 0 min; the matrix is symmetric (conventions G1–G3).

| Leg | Haversine km | × 1.25 → `distance_km` | `km × 60 × 1.08 / 65` | `drive_min` (ceil) |
|---|---|---|---|---|
| Łódź ↔ Warszawa | 118.696 | 148.37 | 147.913 | 148 |

## 3. Expected outcome

The engine combines P with R and never with Q.

### 3.1 Ranked feasible offer sets (objective `profit`; exhaustive enumeration of all pickup/delivery orders)

| Rank | Offer set | Best sequence | Profile | Net profit € | Finish | Fuel l |
|---|---|---|---|---|---|---|
| 1 | {P, R} | pick P → pick R → drop P → drop R | `pl_domestic_employee_v1` | 196.42 | Mon 10:28 | 18.368 |
| 2 | {Q, R} | pick Q → pick R → drop Q → drop R | `pl_domestic_employee_v1` | 136.93 | Mon 10:28 | 18.091 |
| 3 | {P} | pick P → drop P | `pl_domestic_employee_v1` | 111.42 | Mon 09:28 | 17.815 |
| 4 | {Q} | pick Q → drop Q | `pl_domestic_employee_v1` | 51.92 | Mon 09:28 | 17.539 |
| 5 | {R} | pick R → drop R | `pl_domestic_employee_v1` | 2.42 | Mon 09:28 | 17.263 |

Infeasible combinations (every order fails):

| Offer set | Sequences tried | Failure codes |
|---|---|---|
| {P, Q} | 6 infeasible | `PALLET_CAPACITY_EXCEEDED`, `PICKUP_WINDOW_MISSED` |
| {P, Q, R} | 90 infeasible | `PALLET_CAPACITY_EXCEEDED`, `PICKUP_WINDOW_MISSED` |

### 3.2 Rank 1 plan — schedule, load and costs (profile `pl_domestic_employee_v1`)

| # | Action | Place | Leg km | Leg drive min | Inserted on leg | Arrival | Wait min | Service start | Departure | Load after (EUR eq / kg) |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | START | Łódź | — | — | — | — | 0 | Mon 06:00 | Mon 06:00 | 0.0 / 0 |
| 1 | PICKUP P | Łódź | 0.00 | 0 | — | Mon 06:00 | 0 | Mon 06:00 | Mon 06:30 | 6.0 / 320 |
| 2 | PICKUP R | Łódź | 0.00 | 0 | — | Mon 06:30 | 0 | Mon 06:30 | Mon 07:00 | 8.0 / 480 |
| 3 | DELIVERY P | Warszawa | 148.37 | 148 | — | Mon 09:28 | 0 | Mon 09:28 | Mon 09:58 | 2.0 / 160 |
| 4 | DELIVERY R | Warszawa | 0.00 | 0 | — | Mon 09:58 | 0 | Mon 09:58 | Mon 10:28 | 0.0 / 0 |

Fuel per leg (`L100 = (c_empty + (c_full − c_empty) × load_kg / payload_kg) × speed_curve(v)`, `v = km × 60 / drive_min`):

| Leg | km | drive min | v km/h | curve(v) | load kg | L/100 km | litres (3 dp) |
|---|---|---|---|---|---|---|---|
| Łódź → Łódź | 0.00 | 0 | — | — | 0 | — | 0.000 |
| Łódź → Łódź | 0.00 | 0 | — | — | 320 | — | 0.000 |
| Łódź → Warszawa | 148.37 | 148 | 60.150 | 1.02388 | 480 | 12.3796 | 18.368 |
| Warszawa → Warszawa | 0.00 | 0 | — | — | 160 | — | 0.000 |
| **Total** | **148.37** | **148** | | | | | **18.368** |

Totals and cost breakdown (EUR; minor units are cents):

| Item | Arithmetic | Value |
|---|---|---|
| Distance | Σ legs (empty km: 0) | 148.37 km |
| Driving | Σ leg drive min | 148 min |
| Service | 4 stops × 30 min | 120 min |
| Waiting | | 0 min |
| Work (drive + service + wait) | 148 + 120 + 0 | 268 min |
| Breaks / daily rests inserted | | 0 min / 0 min |
| Start → finish | Mon 06:00 → Mon 10:28 (2026-11-16T05:00Z → 2026-11-16T09:28Z) | 268 min |
| Revenue | Σ offer prices | 310.00 |
| Fuel cost | 18.368 l × 1.81 €/l | 33.25 |
| Toll cost | PL/DE ≤ 3.5 t: 0 €/km | 0.00 |
| Driver cost | 268 min ÷ 60 × 14.00 €/h | 62.53 |
| Per diem | domestic, 268 min < 8 h (G9) | 0.00 |
| Accommodation | 0 daily rest(s) away from base, sleeper cab: no | 0.00 |
| Vehicle cost | 148.37 km × 0.12 €/km | 17.80 |
| **Total cost** | | **113.58** |
| **Net profit** | 310.00 − 113.58 | **196.42** (margin 63.36 %) |
| CO₂ | 18.368 l × 2.6 kg/l | 47.76 kg |

## 4. Assertions a test must make

1. The rank 1 plan for objective `profit` contains exactly offers {P, R} in the order `PICKUP P → PICKUP R → DELIVERY P → DELIVERY R`.
2. `load_pallet_eq_after` per stop = 6.0 → 8.0 → 2.0 → 0.0; `load_kg_after` = 320 → 480 → 160 → 0; both stay within the vehicle capacity (invariant 1).
3. `rules_profile = pl_domestic_employee_v1`.
4. Service start times: PP Mon 06:00, PR Mon 06:30, DP Mon 09:28, DR Mon 09:58; every one lies inside its window (invariant 4).
5. Totals: `distance_km = 148.37`, `drive_min = 148`, `work_min = 268`, `wait_min = 0`, breaks 0 min, daily rests 0 min, `finish_at = 2026-11-16T09:28Z`.
6. `fuel_l = 18.368`, `co2_kg = 47.76` (= `fuel_l × 2.6`, invariant 17).
7. Cost breakdown in minor units: fuel 3325, toll 0, driver 6253, per diem 0, accommodation 0, vehicle 1780; `cost_total_minor = 11358`; `revenue_minor = 31000`; `net_profit_minor = 19642` (reconstruction exact to 1 minor unit, invariant 7).
8. `RouteValidator` accepts the plan; running the optimisation twice on the same snapshot gives an identical result (invariant 8).
9. After `PICKUP P` the load is 6.0 EUR equivalents (4 industrial pallets × 1.5); after `PICKUP R` exactly 8.0 = `pallet_places` (allowed).
10. No returned plan contains both P and Q: 6.0 + 3.0 = 9.0 > 8 although the pallet *count* is 7 ≤ 8 → `PALLET_CAPACITY_EXCEEDED`.
11. Rank order of offer sets: {P, R} > {Q, R} > {P} > {Q} > {R}; profits 196.42, 136.93, 111.42, 51.92, 2.42 €.
12. The vehicle layout template `EUR_MIXED_5X3` is used for display only; the capacity check uses equivalents (ADR-0014).

## 5. Open questions

- None beyond the shared conventions.
