# Golden cases — shared conventions

Golden cases (`GOLD-001` … `GOLD-010`) are small scenarios with **hand-checkable expected values**. They come from the scenario list in [`docs/report.md`](../../docs/report.md) §17.5 and are tested in `apps/api/tests/golden/` (planned) through FEAT-003 acceptance criteria `AC-FEAT-003-30` … `AC-FEAT-003-39`.

- **Status of all files here:** `approved` by the owner on 2026-11-11; the values are binding. Any change is a spec change that needs human approval ([`context.md`](../../context.md) → Testing Standards).
- **Data:** every driver, vehicle and offer is synthetic (`is_synthetic = true`). Nothing here is a real freight-exchange offer or a real person.
- **How the numbers were produced:** by hand rules written below, cross-checked with a throwaway calculation that is not part of the repository. A test must reach the same values through the production engine with the golden routing provider described in G1–G3.

> The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance.

## Index

| ID | Scenario | Main point | AC |
|---|---|---|---|
| [GOLD-001](GOLD-001.md) | Consolidated loads on one van (report §3.2) | three offers, 561 profile, capacity trace | AC-FEAT-003-30 |
| [GOLD-002](GOLD-002.md) | Tempting detour | more revenue, less profit | AC-FEAT-003-31 |
| [GOLD-003](GOLD-003.md) | Mass exceeded, pallet count fits | `OVERWEIGHT` | AC-FEAT-003-32 |
| [GOLD-004](GOLD-004.md) | Time window forces the order | non-geographic delivery order | AC-FEAT-003-33 |
| [GOLD-005](GOLD-005.md) | International: 45-minute break makes delivery late | plan rejected | AC-FEAT-003-34 |
| [GOLD-006](GOLD-006.md) | No feasible combination | rejection report with codes | AC-FEAT-003-35 |
| [GOLD-007](GOLD-007.md) | Domestic: break after 6 h of work, 12-hour day | PL profile, daily rest | AC-FEAT-003-36 |
| [GOLD-008](GOLD-008.md) | Weekend return | chain with a return offer, `home_by` | AC-FEAT-003-37 |
| [GOLD-009](GOLD-009.md) | Fleet: one offer best for two drivers | exact assignment beats greedy | AC-FEAT-003-38 |
| [GOLD-010](GOLD-010.md) | Industrial pallets overflow 8 places | 1.5 EUR equivalents | AC-FEAT-003-39 |

## Conventions G1–G14

Each convention is marked **decided** (it follows from `context.md` or the report) or **proposed** (a detail the existing documents do not fix; recorded as an open question in [`FEAT-003`](../FEAT-003-optimizer-and-working-time.md) §11). Proposed conventions are the Architect's default; the owner confirms or changes them when approving the spec. If one changes, the affected golden values must be recalculated. **On 2026-11-11 the owner accepted every convention still marked "proposed" below** (G9 was replaced on the same day); the labels are kept to show where each rule came from.

| # | Convention | Status |
|---|---|---|
| G1 | **Distance.** `haversine_km` uses the mean Earth radius 6 371.0088 km and the city coordinates listed in the case. `distance_km = round_half_up(haversine_km × 1.25, 2 decimals)` (circuity factor 1.25). | factor and speed given by the task brief; radius and rounding **proposed** (OQ-003-01) |
| G2 | **Driving time.** `drive_min = ceil(distance_km × 60 × van_speed_factor / 65)` with `van_speed_factor = 1.08`: average speed 65 km/h, and the factor multiplies *time* (a van is slower than a car — report §19.3). | **proposed** reading (OQ-003-01) |
| G3 | The matrix is symmetric; a leg inside one city is 0 km / 0 min and burns no fuel. | proposed (OQ-003-01) |
| G4 | **PL profile breaks.** A 30-minute `BREAK` is inserted when work since the last break reaches 360 min and more work follows. When daily work reaches 540 min and the breaks taken that day total less than 45 min, a further `BREAK` of `45 − breaks_today` minutes (normally 15) is inserted. A break of ≥ 30 min resets `work_since_break`. | 30 min / 6 h **decided** (Core Domain Rule 7); the 15-minute top-up **proposed** (OQ-003-04) |
| G5 | **561 profile breaks.** Every inserted break is 45 min. It is inserted when driving since the last break reaches 270 min or work since the last break reaches 360 min, whichever comes first; it resets both counters. | 45 min / 4 h 30 min **decided** (Rule 8); "always 45 min" **proposed** (OQ-003-04) |
| G6 | **Forward schedule.** The plan is simulated as soon as possible: drive, then wait if early, then service. Driving is splittable (a break or rest can interrupt a leg, location "en route"). Service is atomic: if the service would cross a break or daily limit, the break or rest is taken *before* it. A `DAILY_REST` is 660 min and starts when daily work reaches 720 min (PL), daily driving reaches 540 min (561), or the clock reaches *day start + 13 h* (both profiles). When a rest and a break fall due together, only the rest is taken. | limits **decided** (Rules 7–8); placement details **proposed** (OQ-003-06, OQ-003-07) |
| G7 | **Waiting** before a window opens counts as work (Core Domain Rule 9). A wait of ≥ 660 min is taken as a daily rest of that length instead. | work = **decided**; long-wait rule **proposed** (OQ-003-06) |
| G8 | **Start.** The driver departs at `available_from`. If that would cause waiting at the *first* stop, the departure is delayed by the same number of minutes (idle time before departure is not work). The top-ranked plans of the golden cases never need this rule. | **proposed** (OQ-003-06) |
| G9 | **Per diem.** A plan with at least one stop outside the home country: 0 (a driver in international road transport is not on a business trip — Art. 26f of the Act on Drivers' Working Time, Dz.U. 2026 poz. 477). A domestic plan (Art. 21a), with `T = finish_at − departure`: for `T ≤ 24 h` the multiplier is 0 below 8 h, 0.5 from 8 h to 12 h, 1 above 12 h; for `T > 24 h` it is 1 per full 24 h plus, for a non-zero remainder, 0.5 up to 8 h and 1 above 8 h. `per_diem_minor = round_half_up(1059 × multiplier)`; the rate 10.59 € is 45 zł ÷ 4.25. | **decided** (owner, 2026-11-11; closes OQ-003-05) |
| G10 | **Fuel.** Per leg: `v = distance_km × 60 / drive_min`; `speed_curve(v)` interpolates `VAN_DEFAULT_V1` linearly between its points (50 → 1.10, 70 → 0.95, 90 → 1.00, 110 → 1.18, 130 → 1.35) and is constant outside them; `L100 = (c_empty + (c_full − c_empty) × load_kg / payload_kg) × speed_curve(v)`; `leg_fuel_l = round_half_up(distance_km × L100 / 100, 3 decimals)`; `fuel_l = Σ leg_fuel_l`. `co2_kg = round_half_up(fuel_l × 2.6, 2 decimals)`. | formula **decided** (Rule 12); interpolation and rounding **proposed** (OQ-003-02, OQ-003-03) |
| G11 | **Costs in minor units**, each rounded half-up once: fuel = `fuel_l × 181`; driver = `(drive_min + service_min + wait_min) × 1400 / 60` (breaks and rests are not paid); vehicle = `distance_km × 12`; accommodation = 5 500 per `DAILY_REST` taken away from the home base when `sleeper_cab = false`; toll = 0 in PL and DE for ≤ 3.5 t. `net_profit = revenue − Σ costs`. | formulas **decided** (report §19.1, §17.4); rounding points **proposed** (OQ-003-03) |
| G12 | **Ranking and ties.** Objective `profit`: larger net profit, then earlier `finish_at`, then less fuel. Remaining ties between orders of the same offer set: compare the action sequences position by position, `DELIVERY` before `PICKUP`, then smaller offer id. Remaining ties between sets: the sorted tuple of offer ids. | objective **decided** (Rule 13); final tie-breaks **proposed** (OQ-003-03) |
| G13 | **End of plan.** If `home_by` is set and lies inside the horizon, the plan ends with an `END` stop at the home base and `finish_at` is the arrival there. Otherwise the plan ends after the last delivery and `finish_at` is the end of its service. | **decided** (Rule 10; report §19.2) |
| G14 | **Calendar.** `MOCK_REFERENCE_DATE` = Monday 2026-11-16. Poland and Germany are both on CET (UTC+1) that week. Times in the tables are local; UTC values are given where a test asserts a timestamp. Service time is `default_service_min = 30` per stop. | reference date is a golden input; the rest **decided** |

## Reading a case

1. **Inputs** — cities with coordinates, driver state, vehicle, cost profile `GOLD-CP-1`, offers, engine parameters, the routing table for the legs used.
2. **Expected outcome** — ranked offer sets, the schedule of the best plan with the load after every stop, the fuel table per leg and the cost breakdown, each with its arithmetic.
3. **Assertions** — what the automated test must check. Values listed there are exact (integers, minor units, minutes, litres to 3 decimals).
4. **Open questions** — anything the result depends on that is not decided yet.

Cost values marked "assumption" in the cost profile are assumptions from report §17.4, not market facts.
