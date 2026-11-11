# GOLD-006: No feasible combination — every offer is rejected with a reason

- **Status:** approved by the owner on 2026-11-11 — the values are binding (a later change = spec change + human approval).
- **Covers:** FEAT-003 · AC-FEAT-003-35 · invariants 9 ([`context.md`](../../context.md) → Optimization Engine Invariants).
- **Conventions:** [`specs/golden/README.md`](README.md) (G1–G14). Depends on proposed conventions / open questions: OQ-003-11 (check order).
- **Data:** synthetic (`is_synthetic = true`); not real freight-exchange offers and not real people.

> The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance.

## 1. Scenario

Driver D4 is in Łódź with an 8-pallet van (payload 880 kg) and becomes available on Monday at 08:00. Eight offers are in the pool; each one fails exactly one check. The engine must return an empty plan list and a rejection report with one stable reason code per offer — never an infeasible plan presented as feasible.

## 2. Inputs

**Reference date (`MOCK_REFERENCE_DATE`):** Monday 2026-11-16; all local times are CET (UTC+1).

**Engine parameters:** `horizon_days=5`, `max_offers_per_plan=6`, `top_k_per_driver=10`, `max_pool_per_driver=60`, `node_budget_per_driver=1_500_000`, `max_first_deadhead_km=350`, `default_service_min=30`, `van_speed_factor=1.08`; objective under test: `profit` unless stated otherwise.

### 2.1 Cities

| City | Country | Lat | Lon | Time zone |
|---|---|---|---|---|
| Łódź | PL | 51.7592 | 19.4560 | Europe/Warsaw |
| Warszawa | PL | 52.2297 | 21.0122 | Europe/Warsaw |
| Poznań | PL | 52.4064 | 16.9252 | Europe/Warsaw |
| Gdańsk | PL | 54.3520 | 18.6466 | Europe/Warsaw |
| Katowice | PL | 50.2649 | 19.0238 | Europe/Warsaw |
| Wrocław | PL | 51.1079 | 17.0385 | Europe/Warsaw |

### 2.2 Driver, state and vehicle — D4

| Field | Value |
|---|---|
| Driver | `D4` (synthetic), home base Łódź |
| Current position | Łódź |
| `available_from` | Mon 2026-11-16 08:00 (07:00Z) |
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

| Offer | `source_offer_id` | Route | Load | Price € | Pickup window (local) | Delivery window (local) | Special |
|---|---|---|---|---|---|---|---|
| O1 | `GOLD-006-O1` | Łódź → Warszawa | 6 × EUR, 1 200 kg | 260.00 | Mon 08:00–12:00 | Mon 10:00–18:00 | mass above payload |
| O2 | `GOLD-006-O2` | Łódź → Poznań | 3 × EUR, 300 kg | *missing* | Mon 08:00–12:00 | Mon 10:00–18:00 | `price` absent in the raw record |
| O3 | `GOLD-006-O3` | Gdańsk → Warszawa | 2 × EUR, 200 kg | 300.00 | Mon 14:00–20:00 | Tue 06:00–14:00 | pickup 366.67 km from the driver |
| O4 | `GOLD-006-O4` | Łódź → Katowice | 2 × EUR, 150 kg | 180.00 | Mon 06:00–07:30 | Mon 09:00–14:00 | pickup window closes before `available_from` |
| O5 | `GOLD-006-O5` | Łódź → Wrocław | 2 × EUR, 200 kg | 190.00 | Mon 08:00–12:00 | Mon 10:00–18:00 | `required_body_types = ["BOX"]` only |
| O6 | `GOLD-006-O6` | Łódź → Warszawa | 9 × EUR, 400 kg | 240.00 | Mon 08:00–12:00 | Mon 10:00–18:00 | 9.0 equivalents > 8 places |
| O7 | `GOLD-006-O7` | Łódź → Warszawa | pallets *missing*, `loading_length_m` *missing*, 300 kg | 150.00 | Mon 08:00–12:00 | Mon 10:00–18:00 | no capacity data |
| O8 | `GOLD-006-O8` | Łódź → *unknown place* | 2 × EUR, 200 kg | 200.00 | Mon 08:00–12:00 | Mon 10:00–18:00 | delivery stop has no coordinates and its city is not in `cities.json` |

All offers: `vehicleProperties.type = ["VEHICLE_UP_TO_3_5_T"]`; body `CURTAIN_SIDER` except O5.

### 2.5 Routing assumption

`distance_km = round_half_up(haversine_km × 1.25, 2)`; `drive_min = ceil(distance_km × 60 × 1.08 / 65)` (conventions G1–G3).

| Leg | Haversine km | × 1.25 → `distance_km` | `km × 60 × 1.08 / 65` | `drive_min` (ceil) |
|---|---|---|---|---|
| Łódź ↔ Gdańsk | 293.332 | 366.67 | 365.542 | 366 |

## 3. Expected outcome

Plan list: empty. Rejection report for driver D4 (prefilter checks run in the fixed order of FEAT-003 §4.3; the first failing check gives the code):

| Offer | Check that fails | Arithmetic | Reason code | Stage |
|---|---|---|---|---|
| O1 | mass | 1 200 kg > `payload_kg` 880 | `OVERWEIGHT` | prefilter |
| O2 | revenue present | `price` is null | `MISSING_REVENUE` | prefilter |
| O3 | first deadhead | Łódź → Gdańsk 293.332 × 1.25 = 366.67 km > 350 | `FIRST_DEADHEAD_TOO_LONG` | search (no other offer can precede it) |
| O4 | pickup window reachable | window end Mon 07:30 < `available_from` Mon 08:00 | `PICKUP_WINDOW_UNREACHABLE` | prefilter |
| O5 | body type | vehicle `CURTAIN_SIDER` ∉ [`BOX`] | `BODY_TYPE_MISMATCH` | prefilter |
| O6 | pallet places | 9 × 1.0 = 9.0 > `pallet_places` 8 | `PALLET_CAPACITY_EXCEEDED` | prefilter |
| O7 | capacity data | no pallets and no length | `MISSING_CAPACITY_DATA` | prefilter |
| O8 | coordinates | no `geoCoordinate`, city not geocodable | `MISSING_COORDINATES` | prefilter |

## 4. Assertions a test must make

1. `plans == []` for every objective; `truncated == false`.
2. The rejection report has exactly 8 entries, one per offer, with the codes in the table above.
3. Both baselines (`baseline_single`, `baseline_greedy`) are empty and the fleet profit is 0.
4. `FleetValidator` accepts the empty solution; no error is raised (invariant 9).
5. The API result for this job has status `succeeded` (an empty result is not a failure).

## 5. Open questions

- O3: the first-deadhead limit is a rule for the *first* pickup of a plan, not a pool filter (FEAT-003 §4.3). Here no other offer is feasible, so O3 can never be reached through a chain and is reported with `FIRST_DEADHEAD_TOO_LONG`.
- O5 uses `BOX` as the only required body type. The exact TIMOCOM body enumeration values for refrigerated bodies are not listed in the report; FEAT-002 copies them from the OpenAPI file (OQ-002-02).
