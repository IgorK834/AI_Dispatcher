# GOLD-008: Weekend return: profit needs a chain with a return offer

- **Status:** approved by the owner on 2026-11-11 — the values are binding (a later change = spec change + human approval).
- **Covers:** FEAT-003 · AC-FEAT-003-37 · invariants 1–8, 13, 15 ([`context.md`](../../context.md) → Optimization Engine Invariants).
- **Conventions:** [`specs/golden/README.md`](README.md) (G1–G14). Depends on proposed conventions / open questions: OQ-003-01…04.
- **Data:** synthetic (`is_synthetic = true`); not real freight-exchange offers and not real people.

> The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance.

## 1. Scenario

It is Thursday morning. Driver D1 (base Katowice, 10-pallet van, no sleeper cab) must be home by Friday 18:00. Offer L goes to Poznań; offer M comes back from Poznań to Katowice at a lower "return" rate; offer N to Gdańsk pays the most. Any plan must end at the base, so one-way offers pay for an empty return. L and N cannot be co-loaded (6 + 5 = 11 pallets > 10, and 1 100 kg > 1 085 kg).

## 2. Inputs

**Reference date (`MOCK_REFERENCE_DATE`):** Monday 2026-11-16 (the scenario starts on Thursday 2026-11-19); all local times are CET (UTC+1) — Europe/Warsaw and Europe/Berlin are both UTC+1 on these dates.

**Engine parameters:** `horizon_days=5`, `max_offers_per_plan=6`, `top_k_per_driver=10`, `max_pool_per_driver=60`, `node_budget_per_driver=1_500_000`, `max_first_deadhead_km=350`, `default_service_min=30`, `van_speed_factor=1.08`; objective under test: `profit` unless stated otherwise.

### 2.1 Cities

| City | Country | Lat | Lon | Time zone |
|---|---|---|---|---|
| Katowice | PL | 50.2649 | 19.0238 | Europe/Warsaw |
| Poznań | PL | 52.4064 | 16.9252 | Europe/Warsaw |
| Gdańsk | PL | 54.3520 | 18.6466 | Europe/Warsaw |

### 2.2 Driver, state and vehicle — D1

| Field | Value |
|---|---|
| Driver | `D1` (synthetic), home base Katowice |
| Current position | Katowice |
| `available_from` | Thu 2026-11-19 06:00 (05:00Z) |
| `home_by` | Fri 2026-11-20 18:00 (17:00Z) |
| Counters (min) | `work_today` 0, `drive_today` 0, `work_since_break` 0, `drive_since_break` 0, `work_week` 1500, `drive_week` 1100, `drive_prev_week` 0 |
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
| L | `GOLD-008-L` | Katowice → Poznań | 6 × EUR 1200×800 | 6.0 | 600 | 330.00 | Thu 11-19 06:00–09:00 | Thu 11-19 11:00–18:00 | 30 + 30 |
| M | `GOLD-008-M` | Poznań → Katowice | 4 × EUR 1200×800 | 4.0 | 350 | 215.00 | Thu 11-19 12:00–18:00 | Fri 11-20 06:00–14:00 | 30 + 30 |
| N | `GOLD-008-N` | Katowice → Gdańsk | 5 × EUR 1200×800 | 5.0 | 500 | 500.00 | Thu 11-19 06:00–09:00 | Thu 11-19 14:00–20:00 | 30 + 30 |

All offers: `vehicleProperties.type = ["VEHICLE_UP_TO_3_5_T"]`, body `CURTAIN_SIDER`, pallets `generated_mock`, service time `default` (30 min per stop, flag `SERVICE_TIME_DEFAULTED`).

### 2.5 Routing assumption

`distance_km = round_half_up(haversine_km × 1.25, 2)`; `drive_min = ceil(distance_km × 60 × van_speed_factor / 65)` (average speed 65 km/h, time multiplied by `van_speed_factor = 1.08`); same-city legs are 0 km / 0 min; the matrix is symmetric (conventions G1–G3).

| Leg | Haversine km | × 1.25 → `distance_km` | `km × 60 × 1.08 / 65` | `drive_min` (ceil) |
|---|---|---|---|---|
| Katowice ↔ Poznań | 279.181 | 348.98 | 347.906 | 348 |
| Katowice ↔ Gdańsk | 455.187 | 568.98 | 567.229 | 568 |
| Poznań ↔ Gdańsk | 244.606 | 305.76 | 304.819 | 305 |

## 3. Expected outcome

Only the chain L → M is profitable. The best-paying single offer N loses money once the empty return is included.

### 3.1 Ranked feasible offer sets (objective `profit`; exhaustive enumeration of all pickup/delivery orders)

| Rank | Offer set | Best sequence | Profile | Net profit € | Finish | Fuel l |
|---|---|---|---|---|---|---|
| 1 | {L, M} | pick L → drop L → pick M → drop M | `pl_domestic_employee_v1` | 46.36 | Fri 07:21 | 84.854 |

Infeasible combinations (every order fails):

| Offer set | Sequences tried | Failure codes |
|---|---|---|
| {L, N} | 6 infeasible | `OVERWEIGHT`, `PICKUP_WINDOW_MISSED` |
| {M, N} | 6 infeasible | `DELIVERY_WINDOW_MISSED`, `PICKUP_WINDOW_MISSED` |
| {L, M, N} | 90 infeasible | `DELIVERY_WINDOW_MISSED`, `OVERWEIGHT`, `PICKUP_WINDOW_MISSED` |

### 3.2 Rank 1 plan — schedule, load and costs (profile `pl_domestic_employee_v1`)

| # | Action | Place | Leg km | Leg drive min | Inserted on leg | Arrival | Wait min | Service start | Departure | Load after (EUR eq / kg) |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | START | Katowice | — | — | — | — | 0 | Thu 06:00 | Thu 06:00 | 0.0 / 0 |
| 1 | PICKUP L | Katowice | 0.00 | 0 | — | Thu 06:00 | 0 | Thu 06:00 | Thu 06:30 | 6.0 / 600 |
| 2 | DELIVERY L | Poznań | 348.98 | 348 | BREAK 30 min (Thu 12:00–Thu 12:30) | Thu 12:48 | 0 | Thu 12:48 | Thu 13:18 | 0.0 / 0 |
| 3 | PICKUP M | Poznań | 0.00 | 0 | — | Thu 13:18 | 0 | Thu 13:18 | Thu 13:48 | 4.0 / 350 |
| 4 | DELIVERY M | Katowice | 348.98 | 348 | BREAK 15 min (Thu 15:30–Thu 15:45); DAILY_REST 660 min (Thu 18:45–Fri 05:45) | Fri 06:51 | 0 | Fri 06:51 | Fri 07:21 | 0.0 / 0 |
| 5 | END | Katowice | 0.00 | 0 | — | Fri 07:21 | 0 | Fri 07:21 | Fri 07:21 | 0.0 / 0 |

Fuel per leg (`L100 = (c_empty + (c_full − c_empty) × load_kg / payload_kg) × speed_curve(v)`, `v = km × 60 / drive_min`):

| Leg | km | drive min | v km/h | curve(v) | load kg | L/100 km | litres (3 dp) |
|---|---|---|---|---|---|---|---|
| Katowice → Katowice | 0.00 | 0 | — | — | 0 | — | 0.000 |
| Katowice → Poznań | 348.98 | 348 | 60.169 | 1.02373 | 600 | 12.3933 | 43.250 |
| Poznań → Poznań | 0.00 | 0 | — | — | 0 | — | 0.000 |
| Poznań → Katowice | 348.98 | 348 | 60.169 | 1.02373 | 350 | 11.9215 | 41.604 |
| Katowice → Katowice | 0.00 | 0 | — | — | 0 | — | 0.000 |
| **Total** | **697.96** | **696** | | | | | **84.854** |

Totals and cost breakdown (EUR; minor units are cents):

| Item | Arithmetic | Value |
|---|---|---|
| Distance | Σ legs (empty km: 0) | 697.96 km |
| Driving | Σ leg drive min | 696 min |
| Service | 4 stops × 30 min | 120 min |
| Waiting | | 0 min |
| Work (drive + service + wait) | 696 + 120 + 0 | 816 min |
| Breaks / daily rests inserted | | 45 min / 660 min |
| Start → finish | Thu 06:00 → Fri 07:21 (2026-11-19T05:00Z → 2026-11-20T06:21Z) | 1521 min |
| Revenue | Σ offer prices | 545.00 |
| Fuel cost | 84.854 l × 1.81 €/l | 153.59 |
| Toll cost | PL/DE ≤ 3.5 t: 0 €/km | 0.00 |
| Driver cost | 816 min ÷ 60 × 14.00 €/h | 190.40 |
| Per diem | domestic, 1521 min = 24 h + 81 min → 1.5 × 10.59 (G9) | 15.89 |
| Accommodation | 1 daily rest(s) away from base, sleeper cab: no | 55.00 |
| Vehicle cost | 697.96 km × 0.12 €/km | 83.76 |
| **Total cost** | | **498.64** |
| **Net profit** | 545.00 − 498.64 | **46.36** (margin 8.51 %) |
| CO₂ | 84.854 l × 2.6 kg/l | 220.62 kg |

## 4. Assertions a test must make

1. The rank 1 plan for objective `profit` contains exactly offers {L, M} in the order `PICKUP L → DELIVERY L → PICKUP M → DELIVERY M`.
2. `load_pallet_eq_after` per stop = 6.0 → 0.0 → 4.0 → 0.0; `load_kg_after` = 600 → 0 → 350 → 0; both stay within the vehicle capacity (invariant 1).
3. `rules_profile = pl_domestic_employee_v1`.
4. Service start times: PL Thu 06:00, DL Thu 12:48, PM Thu 13:18, DM Fri 06:51; every one lies inside its window (invariant 4).
5. Totals: `distance_km = 697.96`, `drive_min = 696`, `work_min = 816`, `wait_min = 0`, breaks 45 min, daily rests 660 min, `finish_at = 2026-11-20T06:21Z`.
6. `fuel_l = 84.854`, `co2_kg = 220.62` (= `fuel_l × 2.6`, invariant 17).
7. Cost breakdown in minor units: fuel 15359, toll 0, driver 19040, per diem 1589, accommodation 5500, vehicle 8376; `cost_total_minor = 49864`; `revenue_minor = 54500`; `net_profit_minor = 4636` (reconstruction exact to 1 minor unit, invariant 7).
8. `RouteValidator` accepts the plan; running the optimisation twice on the same snapshot gives an identical result (invariant 8).
9. The plan ends with an `END` stop at the home base Katowice; `home_reached = true`; `finish_at` (Fri 07:21) ≤ `home_by` (Fri 18:00) — invariant 13.
10. Exactly one plan is returned. Every single-offer plan must drive home empty and loses money: {L} −150.46 €, {N} −233.59 €, {M} −262.48 € (per diem: 1.5 rates for {L} and {M}; 2 rates for {N}, whose trip Thu 06:00 → Fri 14:11 is 24 h + 8 h 11 min) (all < `min_profit = 0`).
11. Rejection report: offer N → `BELOW_MIN_PROFIT` (it is in no returned plan; its best plan is the single-offer plan above).
12. `baseline_single` for D1 is empty (profit 0.00 €); the optimised fleet profit 46.36 € is strictly greater (invariant 15).
13. Weekly counters after the plan: `work_week` = 1 500 + 816 = 2 316 min ≤ 3 600.

## 5. Open questions

- The last stop `DELIVERY M` is at the home base, so the `END` leg is 0 km. A test must still find the `END` stop in the plan.
