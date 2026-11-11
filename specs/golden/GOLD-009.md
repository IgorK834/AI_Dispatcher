# GOLD-009: Fleet: the same offer is best for two drivers — global assignment beats greedy

- **Status:** approved by the owner on 2026-11-11 — the values are binding (a later change = spec change + human approval).
- **Covers:** FEAT-003 · AC-FEAT-003-38 · invariants 1–8, 12, 15 ([`context.md`](../../context.md) → Optimization Engine Invariants).
- **Conventions:** [`specs/golden/README.md`](README.md) (G1–G14). Depends on proposed conventions / open questions: OQ-003-01…03, OQ-003-14 (exact definition of `baseline_greedy`).
- **Data:** synthetic (`is_synthetic = true`); not real freight-exchange offers and not real people.

> The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance.

## 1. Scenario

Two drivers: D1 in Katowice (10 pallets, 1 085 kg) and D5 in Kraków (8 pallets, 765 kg). Offer X (Katowice → Wrocław) is the best single offer for both. D1 has a good alternative, offer Y (800 kg — too heavy for D5). D5's only alternative is the weak offer Z. A greedy assignment gives X to D1 and leaves D5 with Z. The exact fleet assignment gives Y to D1 and X to D5 and earns more in total.

## 2. Inputs

**Reference date (`MOCK_REFERENCE_DATE`):** Monday 2026-11-16; all local times are CET (UTC+1) — Europe/Warsaw and Europe/Berlin are both UTC+1 on these dates.

**Engine parameters:** `horizon_days=5`, `max_offers_per_plan=6`, `top_k_per_driver=10`, `max_pool_per_driver=60`, `node_budget_per_driver=1_500_000`, `max_first_deadhead_km=350`, `default_service_min=30`, `van_speed_factor=1.08`; objective under test: `profit` unless stated otherwise.

### 2.1 Cities

| City | Country | Lat | Lon | Time zone |
|---|---|---|---|---|
| Katowice | PL | 50.2649 | 19.0238 | Europe/Warsaw |
| Kraków | PL | 50.0647 | 19.9450 | Europe/Warsaw |
| Wrocław | PL | 51.1079 | 17.0385 | Europe/Warsaw |
| Opole | PL | 50.6751 | 17.9213 | Europe/Warsaw |
| Rzeszów | PL | 50.0412 | 21.9991 | Europe/Warsaw |

### 2.2 Driver, state and vehicle — D1

| Field | Value |
|---|---|
| Driver | `D1` (synthetic), home base Katowice |
| Current position | Katowice |
| `available_from` | Mon 2026-11-16 08:00 (07:00Z) |
| `home_by` | none (no return constraint) |
| Counters (min) | `work_today` 0, `drive_today` 0, `work_since_break` 0, `drive_since_break` 0, `work_week` 0, `drive_week` 0, `drive_prev_week` 0 |
| Vehicle | `GOLD-VAN-10`: `VEHICLE_UP_TO_3_5_T`, `CURTAIN_SIDER`, 10 pallet places (`EUR_MIXED_6X4`), interior 4.85 × 2.10 × 2.10 m, `payload_kg` 1085, `sleeper_cab` false |
| Fuel parameters | 11.0 l/100 km empty, 13.0 l/100 km full (at 90 km/h), curve `VAN_DEFAULT_V1` (assumption) |

### 2.3 Driver, state and vehicle — D5

| Field | Value |
|---|---|
| Driver | `D5` (synthetic), home base Kraków |
| Current position | Kraków |
| `available_from` | Mon 2026-11-16 06:33 (05:33Z) |
| `home_by` | none (no return constraint) |
| Counters (min) | `work_today` 0, `drive_today` 0, `work_since_break` 0, `drive_since_break` 0, `work_week` 0, `drive_week` 0, `drive_prev_week` 0 |
| Vehicle | `GOLD-VAN-8`: `VEHICLE_UP_TO_3_5_T`, `CURTAIN_SIDER`, 8 pallet places (`EUR_MIXED_5X3`), interior 4.20 × 2.10 × 2.15 m, `payload_kg` 765, `sleeper_cab` false |
| Fuel parameters | 11.0 l/100 km empty, 13.0 l/100 km full (at 90 km/h), curve `VAN_DEFAULT_V1` (assumption) |

### 2.4 Cost profile `GOLD-CP-1`

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

### 2.5 Offers

| Offer | `source_offer_id` | Route | Pallets | EUR eq | kg | Price € | Pickup window (local) | Delivery window (local) | Service min |
|---|---|---|---|---|---|---|---|---|---|
| X | `GOLD-009-X` | Katowice → Wrocław | 4 × EUR 1200×800 | 4.0 | 400 | 290.00 | Mon 11-16 08:00–09:00 | Mon 11-16 10:00–18:00 | 30 + 30 |
| Y | `GOLD-009-Y` | Katowice → Opole | 6 × EUR 1200×800 | 6.0 | 800 | 190.00 | Mon 11-16 08:00–09:00 | Mon 11-16 10:00–18:00 | 30 + 30 |
| Z | `GOLD-009-Z` | Kraków → Rzeszów | 2 × EUR 1200×800 | 2.0 | 200 | 150.00 | Mon 11-16 06:00–09:00 | Mon 11-16 09:00–18:00 | 30 + 30 |

All offers: `vehicleProperties.type = ["VEHICLE_UP_TO_3_5_T"]`, body `CURTAIN_SIDER`, pallets `generated_mock`, service time `default` (30 min per stop, flag `SERVICE_TIME_DEFAULTED`).

### 2.6 Routing assumption

`distance_km = round_half_up(haversine_km × 1.25, 2)`; `drive_min = ceil(distance_km × 60 × van_speed_factor / 65)` (average speed 65 km/h, time multiplied by `van_speed_factor = 1.08`); same-city legs are 0 km / 0 min; the matrix is symmetric (conventions G1–G3).

| Leg | Haversine km | × 1.25 → `distance_km` | `km × 60 × 1.08 / 65` | `drive_min` (ceil) |
|---|---|---|---|---|
| Katowice ↔ Kraków | 69.289 | 86.61 | 86.344 | 87 |
| Katowice ↔ Wrocław | 168.360 | 210.45 | 209.802 | 210 |
| Katowice ↔ Opole | 90.380 | 112.98 | 112.632 | 113 |
| Katowice ↔ Rzeszów | 213.421 | 266.78 | 265.959 | 266 |
| Kraków ↔ Wrocław | 235.690 | 294.61 | 293.704 | 294 |
| Kraków ↔ Opole | 158.760 | 198.45 | 197.839 | 198 |
| Kraków ↔ Rzeszów | 146.673 | 183.34 | 182.776 | 183 |
| Wrocław ↔ Opole | 78.422 | 98.03 | 97.728 | 98 |
| Wrocław ↔ Rzeszów | 369.751 | 462.19 | 460.768 | 461 |
| Opole ↔ Rzeszów | 297.704 | 372.13 | 370.985 | 371 |

## 3. Expected outcome

### Candidate plans of D1 (objective `profit`)

| Rank | Offer set | Best sequence | Profile | Net profit € | Finish | Fuel l |
|---|---|---|---|---|---|---|
| 1 | {X} | pick X → drop X | `pl_domestic_employee_v1` | 155.97 | Mon 12:30 | 25.295 |
| 2 | {Y} | pick Y → drop Y | `pl_domestic_employee_v1` | 109.92 | Mon 10:53 | 14.447 |

Infeasible combinations:

| Offer set | Sequences tried | Failure codes |
|---|---|---|
| {Z} | 1 infeasible | `PICKUP_WINDOW_MISSED` |
| {X, Y} | 6 infeasible | `OVERWEIGHT`, `PICKUP_WINDOW_MISSED` |
| {X, Z} | 6 infeasible | `PICKUP_WINDOW_MISSED` |
| {Y, Z} | 6 infeasible | `PICKUP_WINDOW_MISSED` |
| {X, Y, Z} | 90 infeasible | `OVERWEIGHT`, `PICKUP_WINDOW_MISSED` |

### Candidate plans of D5 (objective `profit`)

| Rank | Offer set | Best sequence | Profile | Net profit € | Finish | Fuel l |
|---|---|---|---|---|---|---|
| 1 | {X} | pick X → drop X | `pl_domestic_employee_v1` | 106.35 | Mon 12:30 | 35.744 |
| 2 | {Z} | pick Z → drop Z | `pl_domestic_employee_v1` | 32.14 | Mon 10:36 | 21.637 |

Infeasible combinations:

| Offer set | Sequences tried | Failure codes |
|---|---|---|
| {Y} | 1 infeasible | `OVERWEIGHT` |
| {X, Y} | 6 infeasible | `OVERWEIGHT`, `PICKUP_WINDOW_MISSED` |
| {X, Z} | 6 infeasible | `DELIVERY_WINDOW_MISSED`, `PICKUP_WINDOW_MISSED` |
| {Y, Z} | 6 infeasible | `OVERWEIGHT`, `PICKUP_WINDOW_MISSED` |
| {X, Y, Z} | 90 infeasible | `DELIVERY_WINDOW_MISSED`, `OVERWEIGHT`, `PICKUP_WINDOW_MISSED` |

### Fleet assignment (every conflict-free combination of one plan or no plan per driver)

| D1 | D5 | Fleet profit € |
|---|---|---|
| {Y} | {X} | 216.27 |
| {X} | {Z} | 188.11 |
| {X} | — | 155.97 |
| {Y} | {Z} | 142.06 |
| {Y} | — | 109.92 |
| — | {X} | 106.35 |
| — | {Z} | 32.14 |
| — | — | 0.00 |

Optimum: D1 ← {Y} (109.92 €) and D5 ← {X} (106.35 €) = **216.27 €**.

Baselines: `baseline_single` (drivers in id order, each takes its best remaining single offer): D1 ← X (155.97 €), then D5 ← Z (32.14 €) = 188.11 €. `baseline_greedy` (largest profit increase first): D1 ← X first (155.97 € is the largest single gain), then D5 ← Z = 188.11 €. Uplift of the optimum: 216.27 − 188.11 = **28.16 €** (+15.0 %).

### Plan of D1 in the optimum — {Y}

| # | Action | Place | Leg km | Leg drive min | Inserted on leg | Arrival | Wait min | Service start | Departure | Load after (EUR eq / kg) |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | START | Katowice | — | — | — | — | 0 | Mon 08:00 | Mon 08:00 | 0.0 / 0 |
| 1 | PICKUP Y | Katowice | 0.00 | 0 | — | Mon 08:00 | 0 | Mon 08:00 | Mon 08:30 | 6.0 / 800 |
| 2 | DELIVERY Y | Opole | 112.98 | 113 | — | Mon 10:23 | 0 | Mon 10:23 | Mon 10:53 | 0.0 / 0 |

Fuel per leg (`L100 = (c_empty + (c_full − c_empty) × load_kg / payload_kg) × speed_curve(v)`, `v = km × 60 / drive_min`):

| Leg | km | drive min | v km/h | curve(v) | load kg | L/100 km | litres (3 dp) |
|---|---|---|---|---|---|---|---|
| Katowice → Katowice | 0.00 | 0 | — | — | 0 | — | 0.000 |
| Katowice → Opole | 112.98 | 113 | 59.989 | 1.02508 | 800 | 12.7875 | 14.447 |
| **Total** | **112.98** | **113** | | | | | **14.447** |

Totals and cost breakdown (EUR; minor units are cents):

| Item | Arithmetic | Value |
|---|---|---|
| Distance | Σ legs (empty km: 0) | 112.98 km |
| Driving | Σ leg drive min | 113 min |
| Service | 2 stops × 30 min | 60 min |
| Waiting | | 0 min |
| Work (drive + service + wait) | 113 + 60 + 0 | 173 min |
| Breaks / daily rests inserted | | 0 min / 0 min |
| Start → finish | Mon 08:00 → Mon 10:53 (2026-11-16T07:00Z → 2026-11-16T09:53Z) | 173 min |
| Revenue | Σ offer prices | 190.00 |
| Fuel cost | 14.447 l × 1.81 €/l | 26.15 |
| Toll cost | PL/DE ≤ 3.5 t: 0 €/km | 0.00 |
| Driver cost | 173 min ÷ 60 × 14.00 €/h | 40.37 |
| Per diem | domestic, 173 min < 8 h (G9) | 0.00 |
| Accommodation | 0 daily rest(s) away from base, sleeper cab: no | 0.00 |
| Vehicle cost | 112.98 km × 0.12 €/km | 13.56 |
| **Total cost** | | **80.08** |
| **Net profit** | 190.00 − 80.08 | **109.92** (margin 57.85 %) |
| CO₂ | 14.447 l × 2.6 kg/l | 37.56 kg |

### Plan of D5 in the optimum — {X}

| # | Action | Place | Leg km | Leg drive min | Inserted on leg | Arrival | Wait min | Service start | Departure | Load after (EUR eq / kg) |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | START | Kraków | — | — | — | — | 0 | Mon 06:33 | Mon 06:33 | 0.0 / 0 |
| 1 | PICKUP X | Katowice | 86.61 | 87 | — | Mon 08:00 | 0 | Mon 08:00 | Mon 08:30 | 4.0 / 400 |
| 2 | DELIVERY X | Wrocław | 210.45 | 210 | — | Mon 12:00 | 0 | Mon 12:00 | Mon 12:30 | 0.0 / 0 |

Fuel per leg (`L100 = (c_empty + (c_full − c_empty) × load_kg / payload_kg) × speed_curve(v)`, `v = km × 60 / drive_min`):

| Leg | km | drive min | v km/h | curve(v) | load kg | L/100 km | litres (3 dp) |
|---|---|---|---|---|---|---|---|
| Kraków → Katowice | 86.61 | 87 | 59.731 | 1.02702 | 0 | 11.2972 | 9.784 |
| Katowice → Wrocław | 210.45 | 210 | 60.129 | 1.02404 | 400 | 12.3353 | 25.960 |
| **Total** | **297.06** | **297** | | | | | **35.744** |

Totals and cost breakdown (EUR; minor units are cents):

| Item | Arithmetic | Value |
|---|---|---|
| Distance | Σ legs (empty km: 86.61) | 297.06 km |
| Driving | Σ leg drive min | 297 min |
| Service | 2 stops × 30 min | 60 min |
| Waiting | | 0 min |
| Work (drive + service + wait) | 297 + 60 + 0 | 357 min |
| Breaks / daily rests inserted | | 0 min / 0 min |
| Start → finish | Mon 06:33 → Mon 12:30 (2026-11-16T05:33Z → 2026-11-16T11:30Z) | 357 min |
| Revenue | Σ offer prices | 290.00 |
| Fuel cost | 35.744 l × 1.81 €/l | 64.70 |
| Toll cost | PL/DE ≤ 3.5 t: 0 €/km | 0.00 |
| Driver cost | 357 min ÷ 60 × 14.00 €/h | 83.30 |
| Per diem | domestic, 357 min < 8 h (G9) | 0.00 |
| Accommodation | 0 daily rest(s) away from base, sleeper cab: no | 0.00 |
| Vehicle cost | 297.06 km × 0.12 €/km | 35.65 |
| **Total cost** | | **183.65** |
| **Net profit** | 290.00 − 183.65 | **106.35** (margin 36.67 %) |
| CO₂ | 35.744 l × 2.6 kg/l | 92.93 kg |

## 4. Assertions a test must make

1. `FleetSolution(profit)` assigns D1 ← {Y} and D5 ← {X}; fleet `net_profit_minor = 21627`.
2. Offer X appears in exactly one plan; each driver has at most one plan (`FleetValidator`, invariant 12).
3. `baseline_single` fleet profit = 18811 minor units and `baseline_greedy` fleet profit = 18811 minor units; the optimum is strictly greater (invariant 15).
4. Per-plan values: D1 {Y} — `net_profit_minor = 10992`, `fuel_l = 14.447`, `co2_kg = 37.56`; D5 {X} — `net_profit_minor = 10635`, `fuel_l = 35.744`, `co2_kg = 92.93`, `empty_km = 86.61`.
5. Rejection report for D5 contains offer Y with `OVERWEIGHT` (800 kg > 765 kg).
6. The fleet assignment equals the brute-force result over all combinations in the table above (property P10).
7. Both plans pass `RouteValidator`; the result is deterministic (invariant 8).

## 5. Open questions

- **OQ-003-14:** the report describes `baseline_greedy` as "iteratively the best increase of fleet profit by cheapest insertion". This case uses the reading of FEAT-003 §4.8 (pick the feasible (driver, offer) insertion with the largest positive profit increase; ties by driver id, then offer id). Both baselines give the same total here, so the assertion holds for any reasonable reading.
- `available_from` values are chosen so that each driver reaches its first pickup exactly when the window opens (no start deferral, convention G8).
