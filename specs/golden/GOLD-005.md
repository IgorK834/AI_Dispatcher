# GOLD-005: International leg: the 45-minute break makes the delivery late

- **Status:** approved by the owner on 2026-11-11 — the values are binding (a later change = spec change + human approval).
- **Covers:** FEAT-003 · AC-FEAT-003-34 · invariants 4, 6, 9, 14 ([`context.md`](../../context.md) → Optimization Engine Invariants).
- **Conventions:** [`specs/golden/README.md`](README.md) (G1–G14). Depends on proposed conventions / open questions: OQ-003-01.
- **Data:** synthetic (`is_synthetic = true`); not real freight-exchange offers and not real people.

> The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance.

## 1. Scenario

Driver D2 is in Wrocław with a 10-pallet van. Offer I goes to Dresden (Germany) and must be unloaded by 11:45. The drive takes 288 minutes — more than 4 h 30 min — so the 561 profile requires a 45-minute break on the way. Without the break the van would arrive in time; with it, the delivery starts 18 minutes after the window closes. The plan must be rejected.

## 2. Inputs

**Reference date (`MOCK_REFERENCE_DATE`):** Monday 2026-11-16; all local times are CET (UTC+1) — Europe/Warsaw and Europe/Berlin are both UTC+1 on these dates.

**Engine parameters:** `horizon_days=5`, `max_offers_per_plan=6`, `top_k_per_driver=10`, `max_pool_per_driver=60`, `node_budget_per_driver=1_500_000`, `max_first_deadhead_km=350`, `default_service_min=30`, `van_speed_factor=1.08`; objective under test: `profit` unless stated otherwise.

### 2.1 Cities

| City | Country | Lat | Lon | Time zone |
|---|---|---|---|---|
| Wrocław | PL | 51.1079 | 17.0385 | Europe/Warsaw |
| Dresden | DE | 51.0504 | 13.7373 | Europe/Berlin |

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
| I | `GOLD-005-I` | Wrocław → Dresden | 5 × EUR 1200×800 | 5.0 | 500 | 320.00 | Mon 11-16 06:00–06:30 | Mon 11-16 08:00–11:45 | 30 + 30 |

All offers: `vehicleProperties.type = ["VEHICLE_UP_TO_3_5_T"]`, body `CURTAIN_SIDER`, pallets `generated_mock`, service time `default` (30 min per stop, flag `SERVICE_TIME_DEFAULTED`).

### 2.5 Routing assumption

`distance_km = round_half_up(haversine_km × 1.25, 2)`; `drive_min = ceil(distance_km × 60 × van_speed_factor / 65)` (average speed 65 km/h, time multiplied by `van_speed_factor = 1.08`); same-city legs are 0 km / 0 min; the matrix is symmetric (conventions G1–G3).

| Leg | Haversine km | × 1.25 → `distance_km` | `km × 60 × 1.08 / 65` | `drive_min` (ceil) |
|---|---|---|---|---|
| Wrocław ↔ Dresden | 230.684 | 288.36 | 287.473 | 288 |

## 3. Expected outcome

No feasible plan. The only candidate sequence is `PICKUP I → DELIVERY I`, profile `eu561_van_international_v1` (Wrocław → Dresden crosses the PL/DE border).

| Step | Arithmetic | Time (local) |
|---|---|---|
| `PICKUP I` service | window opens 06:00; 30 min | Mon 06:00–06:30 |
| Drive part 1 | driving since break 0 → 270 min allowed | Mon 06:30–11:00 |
| `BREAK` | 45 min, mandatory before exceeding 4 h 30 min of driving | Mon 11:00–11:45 |
| Drive part 2 | 288 − 270 = 18 min | Mon 11:45–12:03 |
| Earliest `DELIVERY I` service start | 06:30 + 288 + 45 | **Mon 12:03** |
| Delivery window end | | Mon 11:45 |
| Lateness | 12:03 − 11:45 | 18 min |
| Counter-check without the break | 06:30 + 288 = 11:18 ≤ 11:45 | would be on time |

Starting earlier is impossible (the pickup window opens at 06:00, when the driver becomes available), and work since the start (30 + 288 = 318 min) stays below 6 h, so only the driving-time break matters. Under `pl_domestic_employee_v1` the same timing would be feasible — which is why the profile choice is asserted.

## 4. Assertions a test must make

1. The optimisation result for D2 contains **no plan** (empty list, invariant 9).
2. The rejection report contains offer I with stage `search` and reason `DELIVERY_WINDOW_MISSED`; detail: earliest service start `2026-11-16T11:03Z`, window end `2026-11-16T10:45Z`.
3. The evaluated candidate used `rules_profile = eu561_van_international_v1` (invariant 14).
4. `DriverRules.advance_drive` for the 561 profile, called with 288 minutes on a fresh state, returns one inserted `BREAK` of 45 min after 270 min of driving and total elapsed 333 min.
5. A control run that changes only the delivery window end to Mon 12:03 returns exactly one plan with `DELIVERY I` service start `2026-11-16T11:03Z`.

## 5. Open questions

- None beyond the shared conventions (the result does not depend on the cost model).
