# ADR-0011: Driver working time — a `DriverRules` port with two legal profiles

- Status: accepted (2026-11-11)
- Date: 2026-11-09

> The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance.

## Context

Working time decides whether a van can take a load. Two regimes apply to the fleet (findings and sources in [`docs/report.md`](../report.md) §20.1, verified 2026-11-09):

- Since 2026-07-01, Regulation (EC) No 561/2006 covers the carriage of goods by vehicles over 2.5 t **in international transport and cabotage** (Art. 2(1)(aa)) — confidence V.
- Domestically, drivers employed under an employment contract fall under the Polish **Act on Drivers' Working Time (ustawa o czasie pracy kierowców)**, consolidated text Dz.U. 2024 poz. 220 — confidence V. It limits *working* time (driving + loading/unloading + waiting), not driving time, for goods vans.
- That a driver in international transport is subject to both the 561 driving rules and the working-time rules is an inference (confidence I).

The engine must insert breaks and rests into schedules, the rules must be testable in isolation, and the product must never claim legal compliance.

## Decision

- **A pure port `DriverRules`** in the `compliance` module: `advance_drive`, `advance_work`, `advance_wait`, `remaining`. The engine knows only the port, not the regulations.
- **Profile `pl_domestic_employee_v1`:** daily work ≤ 12 h (a parameter; equivalent working-time system), a 30-minute break after 6 h of work (45 minutes when daily work exceeds 9 h), daily rest 11 h, weekly work ≤ 60 h, weekly rest 35 h (planned at base). No driving-time limits.
- **Profile `eu561_van_international_v1`:** a 45-minute break before exceeding 4 h 30 min of driving, daily driving ≤ 9 h, daily rest 11 h within 24 h (≤ 13 h duty span), weekly driving ≤ 56 h and two-week driving ≤ 90 h, **plus** the working-time limits (break after 6 h of work, weekly work ≤ 60 h); daily rest in the vehicle only with a sleeper cab, otherwise an accommodation cost.
- **Profile choice:** any international leg or cabotage in a plan ⇒ the whole plan uses the 561 profile (conservative). Otherwise the PL profile.
- **Service and waiting count as work**, not as a break.
- **Mandatory notice** (above) next to every schedule; no compliance claims anywhere.
- Exact step semantics and the open details are specified in FEAT-003 §4.1 and §11.

## Alternatives

| Alternative | Why it was rejected |
|---|---|
| One profile (561) for everything | wrong for domestic trips: the Act limits working time, not driving time, and allows 12-hour days in the equivalent system; plans would be needlessly restrictive or wrongly permissive |
| One profile (the Act) for everything | ignores the 561 driving limits and breaks that apply to international van transport since 2026-07-01 |
| Switching profiles per day or per leg inside a plan | more precise, but complex and error-prone; whole-plan 561 is conservative; precise switching is post-MVP |
| Rules hard-coded inside the search | untestable in isolation, impossible to verify independently, hard to change when the law or the interpretation changes |
| Full legal model (split breaks, reduced and split rests, 10-hour extensions, compensation, night work, posting) | far beyond one week; each rule adds search branching; listed as out of MVP scope in report §20.2 |
| No working-time model, only a warning | removes the main value of the product (report §1, fact 2: 27.5 h vs more than 42 h on a 1 500 km route) |

## Consequences

- The model is deliberately **conservative and simplified**; schedules may be longer than a skilled dispatcher would plan (no split breaks, no 10-hour days).
- Several details are not fixed by the source documents (the 45-minute break timing in the PL profile, waiting semantics, the 24-hour window anchor, week boundaries); they are open questions OQ-003-04, 06, 07, 08 with proposed defaults.
- Driver state (counters, last rests) comes from the demo generator or manual entry in the MVP; real planning needs tachograph data (post-MVP).
- The consolidated text of the Act is from 2024; later amendments were not verified (report §2). A legal review is needed before any real use.
- New or changed rules get a new profile version (`…_v2`), never a silent change, and need human approval.
