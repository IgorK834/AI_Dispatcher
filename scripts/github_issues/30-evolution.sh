# Evolution backlog (backlog.md §9): owner actions O-13 … O-21 and slices of the draft specifications
# FEAT-011 … FEAT-017. Sourced by scripts/create_github_issues.sh.
# Every specification here is `draft`: every slice depends on the owner action that approves its specification
# and must not start before that issue is closed.
# shellcheck shell=bash disable=SC2034

EVO_NOTE='`docs/research/2026-11-17-ai-dispatcher-evolution.md`'
EVO_CONTEXT_COMMON="- ${EVO_NOTE} (research note behind the evolution backlog; it changes nothing by itself)
- \`backlog.md\` §9 (phases, owner actions, slices)"

EVO_TIPS_COMMON='- The specification is `draft` until its owner action is closed. If it is still `draft`, comment here and stop.
- Everything in the research note is a proposal; the specification wins where they differ. Report differences instead of choosing silently.'

EVO_VERIFY_ENGINE='```bash
cd apps/api && uv run pytest tests/unit tests/props tests/golden -q
make check && make test-props
```'

EVO_VERIFY_BACKEND='```bash
cd apps/api && uv run pytest tests/unit tests/api tests/db tests/integration -q
make check && make test-db && make openapi
```'

EVO_VERIFY_WEB='```bash
cd apps/web && pnpm test && pnpm exec tsc --noEmit && pnpm lint
make check
```'

EVO_VERIFY_AGENTS='```bash
cd apps/api && uv run pytest tests/agents -q
make check && make test-agents
```'

# ---------------------------------------------------------------------------
# Owner actions
# ---------------------------------------------------------------------------

o_13() {
  I_ID="O-13"; I_KIND="owner"; I_TITLE="Review the research note, the draft specifications FEAT-011 … 017 and ADR-0016 … 0018; commit and push them"
  I_DAY="phase-1"; I_SIZE="1–2 h"
  txt T_GOAL <<'EOF'
The research note, the seven draft specifications, the three proposed ADRs, `specs/requirements.md` (REQ-035 … 040, NFR-016 … 020), `backlog.md` §9 and the issue data are reviewed and merged into `main`, so that every link in the evolution issues resolves.
EOF
  txt T_WHY <<'EOF'
The evolution issues link to files under `blob/main/...`. Until these files are on `main`, those links answer 404. Nothing in the evolution backlog is approved by merging these documents: the specifications stay `draft` and the ADRs `proposed` until their own owner actions (O-14 … O-20).
EOF
  txt T_STEPS <<'EOF'
1. Read `docs/research/2026-11-17-ai-dispatcher-evolution.md` §1, §2.10 (documentation drift), §5, §6.7 (legal questions), §16.
2. Skim `specs/FEAT-011` … `FEAT-017` and `docs/adr/ADR-0016` … `0018`; note questions as comments here.
3. Check `git status`: only documents and `scripts/` change; no `.env`, database files or local benchmark results.
4. Commit on a branch (for example `docs/evolution-backlog`), open a PR, merge it after `ci-fast` is green.
5. Re-run `scripts/create_github_issues.sh --only <the evolution ids>` if any text changed in review.
EOF
  txt T_DONE <<'EOF'
- [ ] The documents are on `main`; the links in this issue and in the slice issues resolve.
- [ ] Review comments are recorded here or in the specifications' open questions.
- [ ] `uv run python scripts/trace.py --check` is green (draft ACs without tests are not blocking).
EOF
}
register o_13

evo_approval_owner() {
  # $1 id, $2 FEAT number, $3 title, $4 day, $5 extra steps, $6 extra done items
  I_ID="$1"; I_KIND="owner"; I_DAY="$4"; I_SIZE="1–2 h"; I_DEPS="O-13"
  I_TITLE="$3"
  local spec
  spec=$(spec_path "$2")
  T_GOAL="\`$spec\` moves from \`draft\` to \`approved\` (or gets change requests), so that its slices may start.
"
  T_WHY="No approved specification → no implementation (\`context.md\` → Agent Collaboration Protocol 1). Only the owner sets \`approved\`, accepts ADRs, approves golden values, migrations, prompts, tool allowlists and new dependencies (\`AGENTS.md\` §9).
"
  T_STEPS="1. Read the specification in full, and the research-note sections it names.
2. Answer every open question in §11 (comment here, then write the answer into §11).
$5
- Set \`status: approved\` in the front matter, raise \`revision\` if anything changed, and add a changelog line with the date.
- Re-run this script with \`--only\` for the slices of this specification so their issues show the new status.
"
  T_DONE="- [ ] The specification has \`status: approved\` and a changelog line.
- [ ] The open questions of §11 have answers.
$6
- [ ] \`uv run python scripts/trace.py --check\` lists the approved ACs as open slices (expected), with no other error.
"
}

o_14() { evo_approval_owner "O-14" "011" "Review and approve FEAT-011 (driver rotations and availability)" "phase-1" \
  "3. Decide the default duty start and home-period times (OQ-011-01), the 28-day warning (OQ-011-02) and who may force a commitment conflict (OQ-011-03)." \
  "- [ ] Rotation defaults and the conflict-forcing role are recorded."; }
register o_14

o_15() { evo_approval_owner "O-15" "012" "Review and approve FEAT-012 and accept ADR-0016 (job-level budget, cycle-aware objective)" "phase-1" \
  "3. Accept or change \`docs/adr/ADR-0016-staged-optimizer-evolution.md\` (Stage A is needed now; Stages B and C are confirmed again in O-20).
4. Update \`context.md\` → Optimization Engine Invariants (P14, P17, the per-job meaning of \`wall_clock_safety_s\`) — only the owner edits \`context.md\`.
5. Approve the GOLD-012 values once the Architect agent has hand-calculated them with the real \`CostModel\` (OQ-012-03)." \
  "- [ ] ADR-0016 is \`accepted\` (or \`proposed\` with change requests).
- [ ] \`context.md\` invariants updated; GOLD-012 values approved before slice 012/5 writes its test."; }
register o_15

o_16() { evo_approval_owner "O-16" "013" "Review and approve FEAT-013 and accept ADR-0018 (working-time profiles v2)" "phase-1" \
  "3. Accept or change \`docs/adr/ADR-0018-compliance-profiles-v2-and-rest-ledger.md\`.
4. Approve the new golden cases for v2 before their slices write tests; decide which questions wait for the legal review (O-21)." \
  "- [ ] ADR-0018 is \`accepted\`; golden values for 013/1, 013/3 and 013/4 approved when they are written."; }
register o_16

o_17() { evo_approval_owner "O-17" "014" "Review and approve FEAT-014 and its migrations (assignment integrity and lifecycle)" "phase-1" \
  "3. Review the migration contract (§6): \`assignment_offers\`, the partial unique indexes, the five lifecycle states, \`stop_events\`, the backfill \`active → planned\`.
4. Decide OQ-014-01 … 04." \
  "- [ ] The migration contract is approved; each migration PR still gets a human review."; }
register o_17

o_18() { evo_approval_owner "O-18" "015" "Review and approve FEAT-015, accept ADR-0017 and decide the AI rule 3 wording" "phase-2" \
  "3. Accept or change \`docs/adr/ADR-0017-event-driven-proposals.md\`.
4. Decide OQ-015-04: may the REST proposal inbox approve a deterministic proposal through \`ApprovalService\`? If yes, change \`context.md\` → AI Architecture Rules 3 accordingly." \
  "- [ ] ADR-0017 is \`accepted\`; \`context.md\` AI rule 3 updated (or the decision recorded as no)."; }
register o_18

o_19() { evo_approval_owner "O-19" "016" "Review and approve FEAT-016: new agent tools, allowlists, prompt versions and an ai-evals budget" "phase-2" \
  "3. Approve the Agent Tool Specs of §6 (\`driver_calendar\`, \`evaluate_insertion\`, \`compare_cycle_options\`, \`job_status\`, \`amend_assignment\` — a write tool behind \`interrupt()\`).
4. Agree a token budget for the live \`ai-evals\` campaigns of slices 016/5 and 016/6 (read \`evals/README.md\` and the tokens already spent before agreeing it)." \
  "- [ ] Tools and allowlists approved; prompt versions approved when 016/5 proposes them; live budget recorded here."; }
register o_19

o_20() { evo_approval_owner "O-20" "017" "Review and approve FEAT-017 and the runtime dependency ortools" "phase-2" \
  "3. Confirm Stages B and C of ADR-0016.
4. Approve the dependency \`ortools\` (Apache-2.0; check the current version, licence and wheel size on PyPI) for slice 017/2, and the adoption-gate thresholds (OQ-017-02)." \
  "- [ ] \`ortools\` approved (or rejected, then 017/2 uses only the DFS fallback)."; }
register o_20

o_21() {
  I_ID="O-21"; I_KIND="owner"; I_TITLE="Have the working-time legal questions checked by a professional"
  I_DAY="phase-2"; I_SIZE="external"; I_DEPS="O-13"
  txt T_GOAL <<'EOF'
The legal questions behind FEAT-013 have written answers from a qualified professional before the slices that depend on them start (013/3, 013/6).
EOF
  txt T_WHY <<'EOF'
The research note read the EU texts from legislation.gov.uk copies and the Polish Act from a reproduction; several readings are uncertain. The product never claims compliance, but planning rules must not rest on a misreading. A coding agent must stop when a legal rule is unclear (`AGENTS.md` §5).
EOF
  txt T_STEPS <<'EOF'
1. Send the list of research note §6.7 and FEAT-013 §11 (OQ-013-01 … 04) to the adviser, without personal data.
2. Main points: (a) daily and reduced weekly rest in a van after the 2020 change to Art. 8(8) of Regulation 561/2006; (b) art. 22 of the Polish Act (Dz.U. 2026 poz. 477) for domestic vans ≤ 3.5 t; (c) the time base of the 561 week and the 6 × 24 h clock; (d) 28/7 rotations against Art. 8(8a); (e) the current EUR-Lex consolidated wording.
3. Record the answers (or "not answered") in FEAT-013 §11 and comment here.
EOF
  txt T_DONE <<'EOF'
- [ ] Written answers exist for (a) … (e), or the open points are explicitly accepted as conservative defaults by the owner.
- [ ] FEAT-013 §11 is updated.
EOF
}
register o_21

# ---------------------------------------------------------------------------
# FEAT-011 — Driver rotations and availability
# ---------------------------------------------------------------------------

F011_CONTEXT="$EVO_CONTEXT_COMMON
- ${EVO_NOTE} §5 (rotation RFC: entities, recurrence, validation, API, UI, acceptance tests)
- \`specs/FEAT-011-driver-rotations-and-availability.md\` (the binding text once approved)"

s_011_1() {
  I_ID="011/1"; I_FEAT="011"; I_PRIORITY="P1"; I_TITLE="Pure rotation module: patterns, duty windows, exceptions, legacy fallback"
  I_AREA="backend"; I_SIZE="M"; I_DAY="phase-1"; I_ACS="01 02 03 04 05 06 07"; I_DEPS="O-14"
  I_GATES="make check, make test-props"; I_BRANCH="feat/FEAT-011-rotation-domain"; I_REQS="REQ-035, NFR-020"; I_ADRS="0010"; I_SCOPE_TAG="fleet"
  txt T_GOAL <<'EOF'
A pure, deterministic module computes each driver's duty windows and the rotation part of the home requirement from a pattern, an anchor date, calendar exceptions and the home time zone.
EOF
  T_CONTEXT="$F011_CONTEXT
- FEAT-011 §4 FR-1 … FR-9, §8 (edge cases)
- \`context.md\` → Core Domain Rules 2 (UTC, injected clock)
- \`apps/api/src/routepilot/fleet/generator.py:61-66\` (today's Friday 18:00 rule)
"
  txt T_SCOPE <<'EOF'
- Pydantic models `RotationSegment`, `RotationPattern`, `DriverRotation`, `CalendarException`, `DutyWindow`, `HomeRequirement` (FEAT-011 FR-1 … FR-3, FR-8).
- `windows(rotation, pattern, exceptions, tz, from_utc, to_utc)` with the fixed exception order of FR-5, the vehicle rule of FR-6 and the legacy fallback of FR-7.
- `validate_pattern()` with the `ROTATION_EXCEEDS_RETURN_PERIOD` warning (FR-9).
EOF
  txt T_OUT <<'EOF'
- Database, repositories, API, snapshot integration, generator, UI (later slices).
- The legal-return deadline (FEAT-013) and the engine's `home_requirement()` (FEAT-012).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/fleet/domain/rotation.py` — new (imports `shared` and the standard library only)
- `apps/api/tests/unit/fleet/test_rotation_windows.py` — new
- `apps/api/tests/props/test_rotation_windows.py` — new
EOF
  txt T_IFACE <<'EOF'
```python
def windows(rotation: DriverRotation | None, pattern: RotationPattern | None, exceptions: Sequence[CalendarException],
            tz: str, from_utc: datetime, to_utc: datetime, *, legacy: LegacyState) -> list[DutyWindow]: ...   # suggested
def home_requirement_from_rotation(windows: Sequence[DutyWindow], exceptions: Sequence[CalendarException],
                                   manual_home_by: datetime | None, now: datetime) -> HomeRequirement | None: ...  # suggested
def validate_pattern(pattern: RotationPattern) -> list[str]: ...  # warning codes
```
EOF
  txt T_TESTS <<'EOF'
- `tests/unit/fleet/test_rotation_windows.py` — the 14/7 dates → AC-01; DST 2027-03-28 → AC-03; exception split, extra duty, override → AC-04; vehicle service → AC-05; legacy window → AC-06; warning for 28/7, none for 21/7 and Mon–Fri → AC-07.
- `tests/props/test_rotation_windows.py` — sorted, disjoint, inside the range, `endAt ≤ homeFrom`, deterministic → AC-02.
EOF
  T_VERIFY="$EVO_VERIFY_ENGINE"
  T_TIPS="$EVO_TIPS_COMMON
- Compute in local dates first, convert to UTC last, with \`zoneinfo\` and \`fold=0\`; never use \`datetime.now()\` (inject the clock).
- Keep the import-linter contract: \`fleet.domain\` must not import repositories, FastAPI or \`optimization\`.
"
}
register s_011_1

s_011_2() {
  I_ID="011/2"; I_FEAT="011"; I_PRIORITY="P1"; I_TITLE="Rotation tables, repositories and CRUD endpoints with commitment conflicts"
  I_AREA="backend"; I_SIZE="L"; I_DAY="phase-1"; I_ACS="08 09 10 11 12"; I_DEPS="011/1"
  I_GATES="make check, make test-db, make openapi"; I_LOCK="🔒 \`apps/api/migrations/**\`, \`contracts/openapi.json\`"; I_APPROVAL="yes"
  I_BRANCH="feat/FEAT-011-rotation-api"; I_REQS="REQ-035, NFR-011, NFR-015"; I_ADRS="0002 0009"; I_SCOPE_TAG="fleet"
  txt T_GOAL <<'EOF'
Dispatchers can create, read, update and delete rotation patterns, driver rotations and calendar exceptions through the REST API, with versioning, overlap checks, the acknowledgement of warnings and the commitment-conflict rule.
EOF
  T_CONTEXT="$F011_CONTEXT
- FEAT-011 §4 FR-1 … FR-3, FR-9, FR-10; §6 (API and data contract)
- \`DEVELOPMENT.md\` §4 (REST, problem+json), §5.2 (migration conventions)
- \`apps/api/src/routepilot/fleet/api/routes.py\` (existing CRUD pattern), \`apps/api/migrations/versions/0001_initial.py\`
"
  txt T_SCOPE <<'EOF'
- One Alembic revision with downgrade: `rotation_patterns`, `driver_rotations`, `calendar_exceptions` (FEAT-011 §6).
- Repositories and services; routers for every path of §6 except availability.
- `409 COMMITMENT_CONFLICT` against `active` assignments; `force` for `admin` only, audited.
- Strict request schemas (`extra="forbid"`; no free-text reason).
- Regenerate `contracts/openapi.json` and the web types.
EOF
  txt T_OUT <<'EOF'
- Availability endpoints (011/3); snapshot integration (011/4); UI (011/6).
EOF
  txt T_FILES <<'EOF'
- `apps/api/migrations/versions/<rev>_rotations.py` — new
- `apps/api/src/routepilot/fleet/repository/rotation.py`, `fleet/service/rotation.py`, `fleet/api/rotation_routes.py` — new
- `apps/api/src/routepilot/main.py` — router registration only
- `contracts/openapi.json`, `apps/web/src/lib/api/schema.d.ts` — regenerated
- `apps/api/tests/api/test_rotations.py`, `test_calendar_exceptions.py`, `apps/api/tests/db/test_migrations.py`, `apps/api/tests/security/test_calendar_exceptions_schema.py` — new or extended
EOF
  txt T_TESTS <<'EOF'
- `tests/api/test_rotations.py` — pattern CRUD codes → AC-08; overlap and unacknowledged warning → AC-09; commitment conflict, admin force, dispatcher 403 → AC-10.
- `tests/db/test_migrations.py` — up/down/up → AC-11.
- `tests/security/test_calendar_exceptions_schema.py` — unknown field rejected; no free-text column → AC-12.
EOF
  T_VERIFY="$EVO_VERIFY_BACKEND"
  T_TIPS="$EVO_TIPS_COMMON
- Follow the existing CRUD conventions exactly (\`201\` + \`Location\`, \`PATCH\` with \`version\`, \`DELETE\` → \`204\`, problem+json \`code\`).
- The migration needs a human review before merge; do not edit \`0001_initial\`.
"
}
register s_011_2

s_011_3() {
  I_ID="011/3"; I_FEAT="011"; I_PRIORITY="P1"; I_TITLE="Availability endpoints for one driver and for the fleet"
  I_AREA="backend"; I_SIZE="M"; I_DAY="phase-1"; I_ACS="13 14"; I_DEPS="011/2"
  I_GATES="make check, make openapi"; I_LOCK="\`contracts/openapi.json\`"
  I_BRANCH="feat/FEAT-011-availability-api"; I_REQS="REQ-035, REQ-008"; I_ADRS="0009"; I_SCOPE_TAG="fleet"
  txt T_GOAL <<'EOF'
`GET /drivers/{id}/availability` and `GET /fleet/availability` return duty windows, home requirements, exceptions, warnings and active assignment intervals for up to 63 days, computed by the pure module of 011/1.
EOF
  T_CONTEXT="$F011_CONTEXT
- FEAT-011 §4 FR-12, §6 (API), the response example in the research note §5.12
"
  txt T_SCOPE <<'EOF'
- `AvailabilityService` (fleet service) combining rotations, exceptions, states and active assignments.
- The two endpoints with cursor pagination (≤ 100 drivers per page) and `422 RANGE_TOO_LONG` above 63 days.
EOF
  txt T_OUT <<'EOF'
- Snapshot integration (011/4); the agent tool `driver_calendar` (FEAT-016).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/fleet/service/availability.py` — new
- `apps/api/src/routepilot/fleet/api/rotation_routes.py` — change
- `contracts/openapi.json`, `apps/web/src/lib/api/schema.d.ts` — regenerated
- `apps/api/tests/api/test_availability.py` — new
EOF
  txt T_TESTS <<'EOF'
- `tests/api/test_availability.py` — one driver matches the pure function; 64 days → 422 → AC-13; fleet page with cursor and no duplicates → AC-14.
EOF
  T_VERIFY="$EVO_VERIFY_BACKEND"
  T_TIPS="$EVO_TIPS_COMMON
- Read assignments through the public \`optimization.jobs\` service only if the import-linter contract allows it; otherwise compose in \`main.py\` or pass intervals in. Check the contract before writing the import.
"
}
register s_011_3

s_011_4() {
  I_ID="011/4"; I_FEAT="011"; I_PRIORITY="P1"; I_TITLE="Snapshot integration: duty windows, deadlines, DRIVER_OFF_DUTY and rotation versions"
  I_AREA="backend engine"; I_SIZE="M"; I_DAY="phase-1"; I_ACS="15 16 17"; I_DEPS="011/3 012/3"
  I_GATES="make check, make test-props, make test-db"; I_BRANCH="feat/FEAT-011-snapshot-windows"; I_REQS="REQ-035, REQ-013"; I_ADRS="0004 0008"; I_SCOPE_TAG="jobs"
  txt T_GOAL <<'EOF'
Optimisation jobs plan drivers only inside their duty windows, take the deadline from the home requirement, report off-duty drivers instead of skipping them, and include the rotation versions in the snapshot digest.
EOF
  T_CONTEXT="$F011_CONTEXT
- FEAT-011 §4 FR-11
- \`apps/api/src/routepilot/optimization/jobs/snapshots.py:61-172\` (\`build_snapshot\`; drivers skipped silently at \`:82-83\`)
- FEAT-012 slice 012/3 (\`home_requirement()\` in the engine)
"
  txt T_SCOPE <<'EOF'
- `build_snapshot` reads windows and the home requirement: `available_from = max(state.available_from, window.startAt)`, `home_by = deadline`.
- Drivers off duty for the whole horizon get the rejection `DRIVER_OFF_DUTY` in the result.
- Per-driver `rotationRef` and `exceptionsDigest` in the snapshot (part of its SHA-256).
EOF
  txt T_OUT <<'EOF'
- Stale-plan rejection at approval (FEAT-014 slice 014/2); the cost of the way home (FEAT-012).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/jobs/snapshots.py` — change
- `apps/api/src/routepilot/optimization/jobs/results.py` — change (rejection entry), if needed
- `apps/api/tests/integration/test_snapshot_rotations.py` — new
EOF
  txt T_TESTS <<'EOF'
- `tests/integration/test_snapshot_rotations.py` — off-duty driver rejected → AC-15; window-derived `home_by` and `available_from`, digest changes with an exception → AC-16.
- The existing golden and property suites unchanged → AC-17.
EOF
  T_VERIFY="$EVO_VERIFY_ENGINE"
  T_TIPS="$EVO_TIPS_COMMON
- Drivers without a rotation must produce byte-identical snapshots to today, apart from the new optional fields; prove it with the existing integration tests.
"
}
register s_011_4

s_011_5() {
  I_ID="011/5"; I_FEAT="011"; I_PRIORITY="P1"; I_TITLE="Demo rotations in the fleet generator"
  I_AREA="backend data"; I_SIZE="S"; I_DAY="phase-1"; I_ACS="18"; I_DEPS="011/2"
  I_GATES="make check, make test-props"; I_LOCK="\`data/mock/fleet.json\`"
  I_BRANCH="feat/FEAT-011-demo-rotations"; I_REQS="REQ-035, REQ-004"; I_ADRS="0003"; I_SCOPE_TAG="fleet"
  txt T_GOAL <<'EOF'
The seeded demo fleet has rotations: two Mon–Fri drivers, two on 14/7 and one on 21/7, deterministic per seed and marked synthetic.
EOF
  T_CONTEXT="$F011_CONTEXT
- FEAT-011 §4 FR-13
- \`apps/api/src/routepilot/fleet/generator.py\`, \`apps/api/src/routepilot/bootstrap.py\` (seed on first start)
"
  txt T_SCOPE <<'EOF'
- Generator output gains patterns and driver rotations; the seed and demo reset create them.
- Regenerate `data/mock/fleet.json` (byte-identical for the same seed and reference date).
EOF
  txt T_OUT <<'EOF'
- Any change to offers, cities or the matrix.
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/fleet/generator.py`, `apps/api/src/routepilot/bootstrap.py` — change
- `data/mock/fleet.json` — regenerated
- `apps/api/tests/props/test_fleet_generator.py` — extended
EOF
  txt T_TESTS <<'EOF'
- `tests/props/test_fleet_generator.py` — rotation per driver index, synthetic rows, determinism → AC-18.
EOF
  T_VERIFY="$EVO_VERIFY_ENGINE"
  T_TIPS="$EVO_TIPS_COMMON
- Agent evals and fixtures read demo drivers; run \`make test-agents\` and list any changed behaviour in the completion report.
"
}
register s_011_5

s_011_6() {
  I_ID="011/6"; I_FEAT="011"; I_PRIORITY="P1"; I_TITLE="Rotation editor and fleet calendar (EN/PL)"
  I_AREA="frontend"; I_SIZE="L"; I_DAY="phase-1"; I_ACS="19 20"; I_DEPS="011/3"
  I_GATES="make check, pnpm test, e2e (ci-full)"; I_LOCK="\`apps/web/messages/*.json\`"
  I_BRANCH="feat/FEAT-011-calendar-ui"; I_REQS="REQ-035, REQ-021, NFR-010"; I_ADRS="0015"; I_SCOPE_TAG="web"
  txt T_GOAL <<'EOF'
The driver form has a rotation editor with a 63-day preview and the return-period warning; a new fleet calendar page shows duty, home, exception and assignment bands per driver, with deadline markers.
EOF
  T_CONTEXT="$F011_CONTEXT
- FEAT-011 §4 FR-14; research note §5.14 and §9.6
- \`docs/design/README.md\`, \`docs/design/tokens.json\`; \`apps/web/src/features/fleet/\`, \`apps/web/src/features/plans/timeline.tsx\`
"
  txt T_SCOPE <<'EOF'
- `features/fleet`: rotation editor in the driver form (pattern choice or segments, anchor, preview, warning acknowledgement).
- New `features/calendar`: drivers × 21/42/63 days, bands, deadline markers, keyboard navigation, accessible labels.
- New EN and PL keys; the working-time notice and the SYNTHETIC DATA badge.
EOF
  txt T_OUT <<'EOF'
- Editing assignments from the calendar; drag and drop.
EOF
  txt T_FILES <<'EOF'
- `apps/web/src/features/fleet/*` — change
- `apps/web/src/features/calendar/*` — new; `apps/web/src/app/calendar/page.tsx` — new (thin page)
- `apps/web/messages/en.json`, `apps/web/messages/pl.json` — appended keys
- `tests/e2e/rotations.spec.ts` — new
EOF
  txt T_TESTS <<'EOF'
- `tests/e2e/rotations.spec.ts` — create a 14/7 rotation, see bands in EN and PL with the notice → AC-19.
- `apps/web/src/features/calendar/*.test.tsx` — labels, arrow-key navigation, no hard-coded text → AC-20.
EOF
  T_VERIFY="$EVO_VERIFY_WEB"
  T_TIPS="$EVO_TIPS_COMMON
- Colours only from the design tokens; red is the only accent. Reuse Radix primitives already in the project.
"
}
register s_011_6

# ---------------------------------------------------------------------------
# FEAT-012 — Engine reliability and cycle-aware planning
# ---------------------------------------------------------------------------

F012_CONTEXT="$EVO_CONTEXT_COMMON
- ${EVO_NOTE} §2.3, §5.6, §7
- \`specs/FEAT-012-engine-reliability-and-cycle-aware-planning.md\`, \`docs/adr/ADR-0016-staged-optimizer-evolution.md\`
- \`context.md\` → Optimization Engine Invariants (validators are never weakened)"

s_012_1() {
  I_ID="012/1"; I_FEAT="012"; I_PRIORITY="P1"; I_TITLE="Job-level time budget, truncation report and both profile passes"
  I_AREA="engine"; I_SIZE="M"; I_DAY="phase-1"; I_ACS="01 02 03"; I_DEPS="O-15"
  I_GATES="make check, make test-props, bench (manual)"; I_BRANCH="feat/FEAT-012-job-budget"; I_REQS="NFR-002, NFR-016"; I_ADRS="0004 0016"; I_SCOPE_TAG="engine"
  txt T_GOAL <<'EOF'
`optimize()` stays within one job-level budget shared across drivers, reports which drivers were cut and why, and always runs the international pass on its own share.
EOF
  T_CONTEXT="$F012_CONTEXT
- FEAT-012 §4 FR-1 … FR-3
- \`apps/api/src/routepilot/optimization/engine/search.py:47-152\` (per-driver limit at \`:57-58, 107-108\`; passes at \`:138-151\`), \`optimizer.py:23-118\`, \`models.py:129-141\`
"
  txt T_SCOPE <<'EOF'
- Budget sharing in driver-id order with reclaim of unused time; separate node and time shares per pass (`domestic_pass_share`).
- `truncatedDrivers` in the result; `truncated` derived from it.
- Benchmark output records the per-pass nodes and `truncatedDrivers` (`bench/fleet_5x60.py`).
EOF
  txt T_OUT <<'EOF'
- Dominance and seeding (012/2); any change to the objectives.
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/engine/search.py`, `optimizer.py`, `models.py` — change
- `bench/fleet_5x60.py` — change (report fields and `--drivers N`)
- `apps/api/tests/unit/engine/test_search_budget.py` — new
EOF
  txt T_TESTS <<'EOF'
- `tests/unit/engine/test_search_budget.py` — fake elapsed callback, total ≤ budget × 1.2 → AC-01; `truncatedDrivers` → AC-02; forced domestic truncation keeps international plans → AC-03.
EOF
  T_VERIFY="$EVO_VERIFY_ENGINE"
  T_TIPS="$EVO_TIPS_COMMON
- The engine never reads the clock; only the injected elapsed-time callback.
- Record the benchmark before and after in the completion report; never assert timings.
"
}
register s_012_1

s_012_2() {
  I_ID="012/2"; I_FEAT="012"; I_PRIORITY="P1"; I_TITLE="Label dominance and incumbent seeding without losing exactness"
  I_AREA="engine"; I_SIZE="L"; I_DAY="phase-1"; I_ACS="04 05"; I_DEPS="012/1"
  I_GATES="make check, make test-props, bench (manual)"; I_BRANCH="feat/FEAT-012-dominance"; I_REQS="NFR-002, NFR-001"; I_ADRS="0004 0016"; I_SCOPE_TAG="engine"
  txt T_GOAL <<'EOF'
The search drops dominated partial plans and starts with good incumbents, so it explores fewer nodes, while untruncated results stay identical to the exhaustive oracle.
EOF
  T_CONTEXT="$F012_CONTEXT
- FEAT-012 §4 FR-4, FR-5; \`docs/development-log.md\` §3 I1, I2
- \`apps/api/src/routepilot/optimization/engine/search.py:70-103\` (bound and window pruning), \`fleet.py:94-165\` (baselines), \`oracle.py\`
"
  txt T_SCOPE <<'EOF'
- Dominance over (picked set, on-board set, position) with time, cost, load and every counter compared (FR-4).
- Baseline plans inserted into the top-K before the search (FR-5).
EOF
  txt T_OUT <<'EOF'
- Approximate pruning of any kind; changes to the validators.
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/engine/search.py` — change
- `apps/api/tests/unit/engine/test_dominance.py` — new; `apps/api/tests/props/test_engine_invariants.py` — extended
EOF
  txt T_TESTS <<'EOF'
- `tests/props/test_engine_invariants.py` — oracle equality (P11 extended) → AC-04.
- `tests/unit/engine/test_dominance.py` + bench seeds — identical results, nodes ≤ before → AC-05.
EOF
  T_VERIFY="$EVO_VERIFY_ENGINE"
  T_TIPS="$EVO_TIPS_COMMON
- Every counter of \`DriverState\` must be part of the dominance test, or a plan that is better on one counter is lost — the oracle test will catch it.
"
}
register s_012_2

s_012_3() {
  I_ID="012/3"; I_FEAT="012"; I_PRIORITY="P1"; I_TITLE="One home_requirement() for schedule, validator and oracle (refactor)"
  I_AREA="engine"; I_SIZE="S"; I_DAY="phase-1"; I_ACS="06"; I_DEPS="O-15"
  I_GATES="make check, make test-props"; I_BRANCH="refactor/FEAT-012-home-requirement"; I_REQS="REQ-013"; I_ADRS="0004"; I_SCOPE_TAG="engine"
  txt T_GOAL <<'EOF'
One function decides whether and by when a plan must end at home; the schedule builder, `build_plan`, the validator and the oracle all use it, with no behaviour change.
EOF
  T_CONTEXT="$F012_CONTEXT
- FEAT-012 §4 FR-6
- The four copies: \`schedule.py:276-279\`, \`schedule.py:393-396\`, \`validators.py:105-109\`, \`oracle.py:50-52\`
"
  txt T_SCOPE <<'EOF'
- `optimization/engine/home.py::home_requirement(snapshot, driver)` returning `HomeRequirement | None`.
- Replace the four copies.
EOF
  txt T_OUT <<'EOF'
- Any behaviour change (the return replay is 012/4).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/engine/home.py` — new
- `apps/api/src/routepilot/optimization/engine/schedule.py`, `validators.py`, `oracle.py` — change
EOF
  txt T_TESTS <<'EOF'
- Existing golden and property suites unchanged → AC-06; a small unit test for `home_requirement()` itself.
EOF
  T_VERIFY="$EVO_VERIFY_ENGINE"
  T_TIPS="$EVO_TIPS_COMMON
- The validator keeps its own replay; sharing the *rule* (when a return is required) is allowed, sharing the schedule code is not.
"
}
register s_012_3

s_012_4() {
  I_ID="012/4"; I_FEAT="012"; I_PRIORITY="P1"; I_TITLE="Return replay, return reserve and the cycle-aware objective profit_v2"
  I_AREA="engine"; I_SIZE="L"; I_DAY="phase-1"; I_ACS="07 08 09 10"; I_DEPS="012/3"
  I_GATES="make check, make test-props"; I_BRANCH="feat/FEAT-012-cycle-profit"; I_REQS="REQ-036, REQ-013"; I_ADRS="0004 0016"; I_SCOPE_TAG="engine"
  txt T_GOAL <<'EOF'
When the home deadline lies beyond the horizon, every plan proves under the working-time rules that the driver can still get home in time, and pays the cost of that drive as `return_reserve`; plans are ranked by cycle profit.
EOF
  T_CONTEXT="$F012_CONTEXT
- FEAT-012 §4 FR-7 … FR-9, FR-11; research note §5.6 (worked example, illustrative numbers)
- \`schedule.py:271-322\` (\`finish\`), \`costs.py\`, \`search.py:24-44\` (ranking keys)
"
  txt T_SCOPE <<'EOF'
- Return replay with the plan's `DriverRules` profile; `HOME_BY_AT_RISK`; `returnLeg` on the plan.
- `returnReserveMinor` from the existing cost functions; `cycleProfitMinor`; thresholds on cycle profit.
- Ranking keys of `profit_v2`; `objectiveVersion` on results.
- Validator replays the return leg independently; properties P14 and P17.
EOF
  txt T_OUT <<'EOF'
- `baseline_return_empty` and GOLD-012 (012/5); API and UI fields (012/6).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/engine/schedule.py`, `costs.py`, `search.py`, `models.py`, `validators.py` — change
- `apps/api/tests/unit/engine/test_return_reserve.py` — new; `apps/api/tests/props/test_engine_invariants.py` — extended
EOF
  txt T_TESTS <<'EOF'
- `tests/unit/engine/test_return_reserve.py` — `HOME_BY_AT_RISK` vs accepted → AC-07; reserve equals the cost of an empty leg with accommodation → AC-08; ranking by cycle profit and `objectiveVersion` → AC-10.
- `tests/props/test_engine_invariants.py` — P14, P17 → AC-09.
EOF
  T_VERIFY="$EVO_VERIFY_ENGINE"
  T_TIPS="$EVO_TIPS_COMMON
- Golden cases whose \`home_by\` lies inside the horizon must not change; cases with \`home_by\` outside may change — list each one and get owner approval before changing a golden value.
- No weights: the objective stays lexicographic.
"
}
register s_012_4

s_012_5() {
  I_ID="012/5"; I_FEAT="012"; I_PRIORITY="P1"; I_TITLE="baseline_return_empty, extended invariant 15 and golden case GOLD-012"
  I_AREA="engine docs"; I_SIZE="M"; I_DAY="phase-1"; I_ACS="11 12"; I_DEPS="012/4"
  I_GATES="make check, make test-props"; I_LOCK="🔒 \`specs/golden/GOLD-012.md\` (golden values)"; I_APPROVAL="yes"
  I_BRANCH="feat/FEAT-012-gold-012"; I_REQS="REQ-036, REQ-014"; I_ADRS="0004 0016"; I_SCOPE_TAG="engine"
  txt T_GOAL <<'EOF'
Every result shows what the cycle is worth without freight (`baseline_return_empty`), the profit solution beats every baseline on cycle profit when not truncated, and GOLD-012 locks the 14/7 decision with owner-approved values.
EOF
  T_CONTEXT="$F012_CONTEXT
- FEAT-012 §4 FR-10; OQ-012-03; \`specs/golden/README.md\` (how golden cases are written)
- \`apps/api/src/routepilot/optimization/engine/fleet.py:94-165\`
"
  txt T_SCOPE <<'EOF'
- The new baseline per driver and its fleet total; invariant 15 extended.
- `specs/golden/GOLD-012.md` with hand calculations (proposed by the agent, approved by the owner before the test).
- `tests/golden/test_gold_012.py`.
EOF
  txt T_OUT <<'EOF'
- Changing any approved golden value without the owner.
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/engine/fleet.py`, `optimizer.py` — change
- `specs/golden/GOLD-012.md` — new; `apps/api/tests/golden/test_gold_012.py` — new
EOF
  txt T_TESTS <<'EOF'
- Unit test of the baseline and invariant 15 → AC-11; golden test → AC-12.
EOF
  T_VERIFY="$EVO_VERIFY_ENGINE"
  T_TIPS="$EVO_TIPS_COMMON
- The research note's €-figures are illustrative; GOLD-012 must use the real \`CostModel\`, matrix and rules, with every step of the arithmetic shown.
"
}
register s_012_5

s_012_6() {
  I_ID="012/6"; I_FEAT="012"; I_PRIORITY="P1"; I_TITLE="Plan read model, contract fields and plan screen for cycle profit (EN/PL)"
  I_AREA="backend frontend"; I_SIZE="M"; I_DAY="phase-1"; I_ACS="13 14"; I_DEPS="012/5"
  I_GATES="make check, make openapi, pnpm test, e2e (ci-full)"; I_LOCK="\`contracts/openapi.json\`, \`apps/web/messages/*.json\`"
  I_BRANCH="feat/FEAT-012-cycle-profit-ui"; I_REQS="REQ-036, REQ-009"; I_ADRS="0009 0015"; I_SCOPE_TAG="plans"
  txt T_GOAL <<'EOF'
The API returns plan profit, return reserve, cycle profit, the return leg and the objective version; the plan screen shows them with a tooltip and the working-time notice.
EOF
  T_CONTEXT="$F012_CONTEXT
- FEAT-012 §4 FR-12, FR-13; §6 (additive, non-breaking)
- \`apps/web/src/features/plans/\`
"
  txt T_SCOPE <<'EOF'
- Read-model fields; regenerated OpenAPI and types; `oasdiff` shows no breaking change.
- Plan header and variant cards; EN and PL keys.
EOF
  txt T_OUT <<'EOF'
- Agent tool output changes (FEAT-016).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/jobs/results.py` (and the plan read model) — change
- `contracts/openapi.json`, `apps/web/src/lib/api/schema.d.ts` — regenerated
- `apps/web/src/features/plans/*`, `apps/web/messages/en.json`, `pl.json` — change
- `tests/e2e/plan-cycle-profit.spec.ts` — new
EOF
  txt T_TESTS <<'EOF'
- `tests/contract/test_openapi_drift.py` → AC-13; e2e EN/PL → AC-14.
EOF
  T_VERIFY="$EVO_VERIFY_WEB"
  T_TIPS="$EVO_TIPS_COMMON
- Format money only through \`lib/format/*\`; label the reserve as an estimate.
"
}
register s_012_6

# ---------------------------------------------------------------------------
# FEAT-013 — Working-time profiles v2
# ---------------------------------------------------------------------------

F013_CONTEXT="$EVO_CONTEXT_COMMON
- ${EVO_NOTE} §2.4, §6 (regulation table, engine proposal, legal questions)
- \`specs/FEAT-013-compliance-profiles-v2.md\`, \`docs/adr/ADR-0018-compliance-profiles-v2-and-rest-ledger.md\`
- \`apps/api/src/routepilot/compliance/rules.py\`, \`compliance/models.py:15-27\`"

s_013_1() {
  I_ID="013/1"; I_FEAT="013"; I_PRIORITY="P1"; I_TITLE="Weekly-rest clock: last_weekly_rest_end in DriverState and WEEKLY_REST_DUE"
  I_AREA="engine"; I_SIZE="M"; I_DAY="phase-1"; I_ACS="01 02 03 04"; I_DEPS="O-16 012/3"
  I_GATES="make check, make test-props"; I_LOCK="🔒 golden values (new case)"; I_APPROVAL="yes"
  I_BRANCH="feat/FEAT-013-weekly-rest-due"; I_REQS="REQ-037, REQ-012"; I_ADRS="0011 0018"; I_SCOPE_TAG="compliance"
  txt T_GOAL <<'EOF'
No plan runs past the latest legal start of the next weekly rest (end of the previous weekly rest + 6 × 24 h) unless it is at home before it; the stored `last_weekly_rest_end` finally reaches the engine.
EOF
  T_CONTEXT="$F013_CONTEXT
- FEAT-013 §4 FR-1
- \`apps/api/src/routepilot/optimization/jobs/snapshots.py:156-170\` (the field is dropped today)
"
  txt T_SCOPE <<'EOF'
- `DriverState.last_weekly_rest_end`; snapshot mapping; `WEEKLY_REST_UNKNOWN` flag.
- Rejection `WEEKLY_REST_DUE` in the schedule; validator check; property P15.
- One new golden case (owner-approved values).
EOF
  txt T_OUT <<'EOF'
- Inserting a weekly rest (013/4); the rule table (013/2).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/compliance/models.py`, `compliance/state.py`, `compliance/rules.py` — change
- `apps/api/src/routepilot/optimization/jobs/snapshots.py`, `optimization/engine/schedule.py`, `validators.py` — change
- `specs/golden/GOLD-013.md`, tests under `apps/api/tests/golden`, `tests/unit/compliance`, `tests/props` — new or extended
EOF
  txt T_TESTS <<'EOF'
- Golden rejection and acceptance → AC-01; mapping and flag → AC-02; P15 → AC-03; validator on a crafted plan → AC-04.
EOF
  T_VERIFY="$EVO_VERIFY_ENGINE"
  T_TIPS="$EVO_TIPS_COMMON
- This tightens the rules; some existing demo plans may become infeasible. Report every changed golden or eval result instead of loosening the rule.
"
}
register s_013_1

s_013_2() {
  I_ID="013/2"; I_FEAT="013"; I_PRIORITY="P1"; I_TITLE="Shared, versioned rule table for rules and validator; v1 replay"
  I_AREA="engine"; I_SIZE="M"; I_DAY="phase-2"; I_ACS="05 06 15"; I_DEPS="013/1"
  I_GATES="make check, make test-props"; I_BRANCH="refactor/FEAT-013-rule-table"; I_REQS="REQ-037, NFR-003"; I_ADRS="0011 0018"; I_SCOPE_TAG="compliance"
  txt T_GOAL <<'EOF'
Every working-time constant lives in a versioned `RuleTable` read by both the rules and the validator; v1 results are unchanged and stored v1 plans replay with the v1 table.
EOF
  T_CONTEXT="$F013_CONTEXT
- FEAT-013 §4 FR-2, FR-9; \`optimization/engine/validators.py:8-13, 246\` (shared constants today)
"
  txt T_SCOPE <<'EOF'
- `compliance/profiles/<profile_id>.py` frozen tables; `DriverRules.table`.
- Validator reads the table; its replay algorithm stays separate.
EOF
  txt T_OUT <<'EOF'
- Any v2 rule.
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/compliance/profiles/*.py` — new; `compliance/rules.py`, `compliance/ports.py`, `optimization/engine/validators.py` — change
- `apps/api/tests/unit/compliance/test_rule_table.py` — new
EOF
  txt T_TESTS <<'EOF'
- Golden and properties unchanged → AC-05; one-source test → AC-06; v1 replay → AC-15.
EOF
  T_VERIFY="$EVO_VERIFY_ENGINE"
  T_TIPS="$EVO_TIPS_COMMON"
}
register s_013_2

s_013_3() {
  I_ID="013/3"; I_FEAT="013"; I_PRIORITY="P1"; I_TITLE="v2 driving options: 10 h extension, 15 + 30 split break, reduced daily rest"
  I_AREA="engine"; I_SIZE="L"; I_DAY="phase-2"; I_ACS="07 08 09"; I_DEPS="013/2 O-21"
  I_GATES="make check, make test-props"; I_LOCK="🔒 golden values (new cases)"; I_APPROVAL="yes"
  I_BRANCH="feat/FEAT-013-driving-options"; I_REQS="REQ-037"; I_ADRS="0011 0018"; I_SCOPE_TAG="compliance"
  txt T_GOAL <<'EOF'
The international v2 profile can use the options a van driver has — at most two 10 h driving days per week, the 15 + 30 split break, up to three reduced 9 h daily rests — only when a plan is otherwise infeasible, and records each use.
EOF
  T_CONTEXT="$F013_CONTEXT
- FEAT-013 §4 FR-3; Regulation 561/2006 Art. 6(1), 7, 8(4) as listed in the research note §6.2
"
  txt T_SCOPE <<'EOF'
- Profile `eu561_van_international_v2` (rules and table), behind `COMPLIANCE_PROFILE_VERSION`.
- `ledgerFacts` on plans.
EOF
  txt T_OUT <<'EOF'
- Weekly rest insertion (013/4); making v2 the default (owner decision).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/compliance/*` — change/new; `optimization/engine/schedule.py`, `validators.py` — change
- Golden cases and unit tests for each option — new
EOF
  txt T_TESTS <<'EOF'
- Extension used once and a third rejected → AC-07; split break valid, planner inserts 45 min → AC-08; fourth reduced rest refused → AC-09.
EOF
  T_VERIFY="$EVO_VERIFY_ENGINE"
  T_TIPS="$EVO_TIPS_COMMON
- Wait for the O-21 answers on in-vehicle rest; if they are not available, keep the conservative defaults named in FEAT-013 §11.
"
}
register s_013_3

s_013_4() {
  I_ID="013/4"; I_FEAT="013"; I_PRIORITY="P1"; I_TITLE="Weekly rest insertion with accommodation, compensation ledger and migration"
  I_AREA="engine backend"; I_SIZE="L"; I_DAY="phase-2"; I_ACS="10 11 12 16"; I_DEPS="013/3"
  I_GATES="make check, make test-props, make test-db"; I_LOCK="🔒 \`apps/api/migrations/**\`, 🔒 golden values"; I_APPROVAL="yes"
  I_BRANCH="feat/FEAT-013-weekly-rest"; I_REQS="REQ-037"; I_ADRS="0011 0018"; I_SCOPE_TAG="compliance"
  txt T_GOAL <<'EOF'
Multi-day international plans insert a regular 45 h weekly rest where the rules require it, with accommodation cost away from home; reduced weekly rests create compensation entries with due dates that later plans must honour.
EOF
  T_CONTEXT="$F013_CONTEXT
- FEAT-013 §4 FR-4, FR-5; §6 (ledger columns)
"
  txt T_SCOPE <<'EOF'
- Weekly rest insertion (regular first, reduced only under the two-week rule and when needed); never two consecutive reduced rests in v2.
- Compensation ledger in `driver_states.weekly_rest_ledger`; `COMPENSATION_DUE`.
- Migration for the ledger columns (with downgrade).
EOF
  txt T_OUT <<'EOF'
- The four-week return (013/5); the cabotage ledger.
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/compliance/*`, `optimization/engine/schedule.py`, `costs.py`, `validators.py`, `fleet/repository/models.py`, `optimization/jobs/snapshots.py` — change
- `apps/api/migrations/versions/<rev>_rest_ledger.py` — new
EOF
  txt T_TESTS <<'EOF'
- Golden 4-day tour with a weekly rest abroad → AC-10; ledger entry → AC-11; `COMPENSATION_DUE` → AC-12; migration up/down/up → AC-16.
EOF
  T_VERIFY="$EVO_VERIFY_ENGINE"
  T_TIPS="$EVO_TIPS_COMMON"
}
register s_013_4

s_013_5() {
  I_ID="013/5"; I_FEAT="013"; I_PRIORITY="P1"; I_TITLE="Four-week driver return as HomeRequirement kind legal_return"
  I_AREA="engine"; I_SIZE="S"; I_DAY="phase-2"; I_ACS="13"; I_DEPS="013/4 011/4"
  I_GATES="make check, make test-props"; I_BRANCH="feat/FEAT-013-legal-return"; I_REQS="REQ-037, REQ-035"; I_ADRS="0018"; I_SCOPE_TAG="compliance"
  txt T_GOAL <<'EOF'
The deadline of a driver's home requirement also respects the employer's four-week return obligation (Art. 8(8a)), computed from the last weekly rest taken at home.
EOF
  T_CONTEXT="$F013_CONTEXT
- FEAT-013 §4 FR-6; FEAT-011 FR-8; \`optimization/engine/home.py\` (012/3)
"
  txt T_SCOPE <<'EOF'
- `home_requirement()` takes the earliest of rotation, exception, manual and legal-return deadlines.
EOF
  txt T_OUT <<'EOF'
- Documentation of how the obligation is met (phase 3 report).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/engine/home.py`, `compliance/*` — change
EOF
  txt T_TESTS <<'EOF'
- Unit test: legal return earlier than the rotation end → AC-13.
EOF
  T_VERIFY="$EVO_VERIFY_ENGINE"
  T_TIPS="$EVO_TIPS_COMMON"
}
register s_013_5

s_013_6() {
  I_ID="013/6"; I_FEAT="013"; I_PRIORITY="P1"; I_TITLE="Profile selection by mass and operation, unsupported_v1, PL domestic v2 policy parameters"
  I_AREA="engine"; I_SIZE="M"; I_DAY="phase-2"; I_ACS="14 17"; I_DEPS="013/2 O-21"
  I_GATES="make check, make test-props"; I_BRANCH="feat/FEAT-013-profile-selection"; I_REQS="REQ-037, REQ-012"; I_ADRS="0011 0018"; I_SCOPE_TAG="compliance"
  txt T_GOAL <<'EOF'
Each plan gets the right rule profile from vehicle mass, operation type and countries; cases outside the model are refused explicitly; the Polish domestic profile marks its stricter limits as company policy.
EOF
  T_CONTEXT="$F013_CONTEXT
- FEAT-013 §4 FR-7, FR-8; OQ-013-01, OQ-013-05; \`compliance/profiles.py\`
"
  txt T_SCOPE <<'EOF'
- Selection table and `unsupported_v1` with `UNSUPPORTED_RULE_PROFILE`; `MASS_UNKNOWN_STRICTER_PROFILE`.
- `pl_domestic_van_employee_v2` with the two policy parameters.
- A nullable vehicle `permissible_mass_kg` only if FEAT-001 has no such field (needs the owner; otherwise stop and ask).
EOF
  txt T_OUT <<'EOF'
- Rules for vehicles > 3.5 t.
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/compliance/profiles.py`, `compliance/*` — change
- `apps/api/tests/unit/compliance/test_profile_selection.py` — new
EOF
  txt T_TESTS <<'EOF'
- Selection table → AC-14; policy parameter off → AC-17.
EOF
  T_VERIFY="$EVO_VERIFY_ENGINE"
  T_TIPS="$EVO_TIPS_COMMON
- A schema change for vehicle mass is a contract and migration change: it needs the owner's approval in this issue first.
"
}
register s_013_6

# ---------------------------------------------------------------------------
# FEAT-014 — Assignment integrity, lifecycle and execution
# ---------------------------------------------------------------------------

F014_CONTEXT="$EVO_CONTEXT_COMMON
- ${EVO_NOTE} §2.3, §8.4 (questions 5–8), §8.6
- \`specs/FEAT-014-commitments-and-execution.md\`
- \`apps/api/src/routepilot/optimization/jobs/service/__init__.py:800-955\` (\`_checked_plans\`, \`assign_many\`, \`cancel\`), \`apps/api/migrations/versions/0001_initial.py:406-432\`"

s_014_1() {
  I_ID="014/1"; I_FEAT="014"; I_PRIORITY="P1"; I_TITLE="Database-enforced assignment uniqueness with assignment_offers and BEGIN IMMEDIATE"
  I_AREA="backend"; I_SIZE="M"; I_DAY="phase-1"; I_ACS="01 02 03"; I_DEPS="O-17"
  I_GATES="make check, make test-db"; I_LOCK="🔒 \`apps/api/migrations/**\`"; I_APPROVAL="yes"
  I_BRANCH="feat/FEAT-014-assignment-uniqueness"; I_REQS="REQ-038, REQ-010, NFR-003"; I_ADRS="0002 0008"; I_SCOPE_TAG="jobs"
  txt T_GOAL <<'EOF'
Two concurrent approvals of plans that share an offer — even from two processes — can never both succeed; the database, not an in-process lock, guarantees it.
EOF
  T_CONTEXT="$F014_CONTEXT
- FEAT-014 §4 FR-1, FR-2; §6 (data)
"
  txt T_SCOPE <<'EOF'
- `assignment_offers` with the partial unique index on open commitments; the per-driver partial index; backfill from existing plans.
- `assign_many` and `cancel` in `BEGIN IMMEDIATE`; `IntegrityError → CONCURRENT_ASSIGNMENT`.
EOF
  txt T_OUT <<'EOF'
- New lifecycle states (014/3); staleness (014/2).
EOF
  txt T_FILES <<'EOF'
- `apps/api/migrations/versions/<rev>_assignment_offers.py` — new
- `apps/api/src/routepilot/optimization/jobs/service/__init__.py`, `optimization/jobs/repository/*` — change
- `apps/api/tests/db/test_assignment_uniqueness.py` — new; `tests/db/test_migrations.py` — extended
EOF
  txt T_TESTS <<'EOF'
- Two processes on one SQLite file → AC-01; direct insert raises → AC-02; migration with backfill → AC-03.
EOF
  T_VERIFY="$EVO_VERIFY_BACKEND"
  T_TIPS="$EVO_TIPS_COMMON
- Start the second process with \`spawn\` (see AC-FEAT-004-15 for why); use a temp file, never the dev database.
- Declare partial indexes with both \`sqlite_where\` and \`postgresql_where\` for portability.
"
}
register s_014_1

s_014_2() {
  I_ID="014/2"; I_FEAT="014"; I_PRIORITY="P1"; I_TITLE="Stale-plan rejection at approval and offer version bump on cancel"
  I_AREA="backend"; I_SIZE="M"; I_DAY="phase-1"; I_ACS="04 05 06"; I_DEPS="014/1 011/4"
  I_GATES="make check, make test-db, make openapi"; I_LOCK="\`contracts/openapi.json\`"
  I_BRANCH="feat/FEAT-014-plan-stale"; I_REQS="REQ-038, REQ-017"; I_ADRS="0008"; I_SCOPE_TAG="jobs"
  txt T_GOAL <<'EOF'
A plan is refused at approval when its driver's state, rotation or exceptions changed after the job; cancelling an assignment makes old plans for its offers unassignable.
EOF
  T_CONTEXT="$F014_CONTEXT
- FEAT-014 §4 FR-3, FR-4; FEAT-011 FR-11 (snapshot versions)
"
  txt T_SCOPE <<'EOF'
- `PLAN_STALE` with `field` in `errors`; offer version bump in `cancel()`.
- The ApprovalGate already turns domain errors into notes; add agent tests for the new code.
EOF
  txt T_OUT <<'EOF'
- Lifecycle endpoints.
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/jobs/service/__init__.py` — change
- `contracts/openapi.json` — regenerated (error codes)
- `apps/api/tests/api/test_assignments_lifecycle.py` — new; `apps/api/tests/agents/*` — extended
EOF
  txt T_TESTS <<'EOF'
- Driver state changed → AC-04; rotation changed → AC-05; cancel then old plan → AC-06.
EOF
  T_VERIFY="$EVO_VERIFY_BACKEND"
  T_TIPS="$EVO_TIPS_COMMON"
}
register s_014_2

s_014_3() {
  I_ID="014/3"; I_FEAT="014"; I_PRIORITY="P1"; I_TITLE="Assignment lifecycle, dispatch and complete endpoints, stop events"
  I_AREA="backend"; I_SIZE="L"; I_DAY="phase-2"; I_ACS="07 08 09"; I_DEPS="014/1"
  I_GATES="make check, make test-db, make openapi"; I_LOCK="🔒 \`apps/api/migrations/**\`, \`contracts/openapi.json\`"; I_APPROVAL="yes"
  I_BRANCH="feat/FEAT-014-lifecycle"; I_REQS="REQ-038, NFR-015, NFR-008"; I_ADRS="0002 0009"; I_SCOPE_TAG="jobs"
  txt T_GOAL <<'EOF'
Assignments move through `planned → dispatched → in_progress → completed` (or `cancelled`), and dispatchers record stop events with actual times through the API.
EOF
  T_CONTEXT="$F014_CONTEXT
- FEAT-014 §4 FR-5, FR-6; §6 (API, data)
"
  txt T_SCOPE <<'EOF'
- Status check migration (`active → planned`), `stop_events` table.
- Transition rules, `dispatch`, `complete`, stop-event endpoints; `status=active` alias.
EOF
  txt T_OUT <<'EOF'
- Driver state from execution and committed prefix (014/4); UI (014/5).
EOF
  txt T_FILES <<'EOF'
- `apps/api/migrations/versions/<rev>_assignment_lifecycle.py` — new
- `apps/api/src/routepilot/optimization/jobs/*` (service, domain, api) — change
- `contracts/openapi.json`, `apps/web/src/lib/api/schema.d.ts` — regenerated
- `apps/api/tests/unit/jobs/test_assignment_states.py`, `apps/api/tests/api/test_assignments_lifecycle.py` — new or extended
EOF
  txt T_TESTS <<'EOF'
- Transition table → AC-07; dispatch/complete with roles and CSRF → AC-08; stop-event validation → AC-09.
EOF
  T_VERIFY="$EVO_VERIFY_BACKEND"
  T_TIPS="$EVO_TIPS_COMMON"
}
register s_014_3

s_014_4() {
  I_ID="014/4"; I_FEAT="014"; I_PRIORITY="P1"; I_TITLE="Committed prefix in snapshots and driver state from execution"
  I_AREA="backend engine"; I_SIZE="L"; I_DAY="phase-2"; I_ACS="10 11"; I_DEPS="014/3 011/4"
  I_GATES="make check, make test-props, make test-db"; I_BRANCH="feat/FEAT-014-execution-state"; I_REQS="REQ-038"; I_ADRS="0008 0011"; I_SCOPE_TAG="jobs"
  txt T_GOAL <<'EOF'
The next optimisation starts each driver after their committed stops, with the committed load on board; completing an assignment writes a new driver state replayed under the working-time rules.
EOF
  T_CONTEXT="$F014_CONTEXT
- FEAT-014 §4 FR-7, FR-8; \`optimization/jobs/snapshots.py\`; \`fleet/service/fleet.py\` (\`add_state\`)
"
  txt T_SCOPE <<'EOF'
- Snapshot start position, time and load after the committed prefix; `CONFLICTING_COMMITMENT` at approval.
- `driver_states` row with `source = "execution"`, counters replayed with the same rules as the validator.
EOF
  txt T_OUT <<'EOF'
- Inserting new offers into committed routes (FEAT-015).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/jobs/snapshots.py`, `optimization/jobs/service/__init__.py`, `fleet/service/fleet.py` — change
- `apps/api/tests/integration/test_execution_flow.py` — new
EOF
  txt T_TESTS <<'EOF'
- Prefix in the snapshot → AC-10; execution state equals the validator replay → AC-11.
EOF
  T_VERIFY="$EVO_VERIFY_ENGINE"
  T_TIPS="$EVO_TIPS_COMMON
- Respect the module boundaries: \`optimization.jobs\` may call the public fleet service, never its repository.
"
}
register s_014_4

s_014_5() {
  I_ID="014/5"; I_FEAT="014"; I_PRIORITY="P1"; I_TITLE="Assignments screen with lifecycle and stop recording (EN/PL)"
  I_AREA="frontend"; I_SIZE="L"; I_DAY="phase-2"; I_ACS="12"; I_DEPS="014/3"
  I_GATES="make check, pnpm test, e2e (ci-full)"; I_LOCK="\`apps/web/messages/*.json\`"
  I_BRANCH="feat/FEAT-014-assignments-ui"; I_REQS="REQ-038, REQ-021"; I_ADRS="0015"; I_SCOPE_TAG="web"
  txt T_GOAL <<'EOF'
Dispatchers see all assignments with lifecycle chips and can dispatch, record stop events, complete and cancel them; the plan screen shows planned vs actual times.
EOF
  T_CONTEXT="$F014_CONTEXT
- FEAT-014 §4 FR-9; \`apps/web/src/features/plans/\`
"
  txt T_SCOPE <<'EOF'
- New `features/assignments` and a thin page; confirmation dialogs; EN and PL keys.
EOF
  txt T_OUT <<'EOF'
- Driver mobile app.
EOF
  txt T_FILES <<'EOF'
- `apps/web/src/features/assignments/*`, `apps/web/src/app/assignments/page.tsx` — new
- `apps/web/src/features/plans/*`, `apps/web/messages/*.json` — change
- `tests/e2e/assignments.spec.ts` — new
EOF
  txt T_TESTS <<'EOF'
- e2e dispatch → stops → complete in EN and PL → AC-12.
EOF
  T_VERIFY="$EVO_VERIFY_WEB"
  T_TIPS="$EVO_TIPS_COMMON"
}
register s_014_5

# ---------------------------------------------------------------------------
# FEAT-015 — Event-driven evaluation and proposals
# ---------------------------------------------------------------------------

F015_CONTEXT="$EVO_CONTEXT_COMMON
- ${EVO_NOTE} §7.6, §8.2–8.5, §9.3
- \`specs/FEAT-015-event-driven-proposals.md\`, \`docs/adr/ADR-0017-event-driven-proposals.md\`
- \`apps/api/src/routepilot/optimization/jobs/service/__init__.py:80-84, 254-322\` (worker, recovery)"

s_015_1() {
  I_ID="015/1"; I_FEAT="015"; I_PRIORITY="P1"; I_TITLE="Transactional outbox, relay, job kinds, leases and job cancel"
  I_AREA="backend"; I_SIZE="L"; I_DAY="phase-2"; I_ACS="01 02 03 04"; I_DEPS="O-18 014/1"
  I_GATES="make check, make test-db, make openapi"; I_LOCK="🔒 \`apps/api/migrations/**\`, \`contracts/openapi.json\`"; I_APPROVAL="yes"
  I_BRANCH="feat/FEAT-015-outbox-jobs"; I_REQS="REQ-025"; I_ADRS="0008 0017"; I_SCOPE_TAG="jobs"
  txt T_GOAL <<'EOF'
Changes to offers, stop events and assignments emit outbox events in the same transaction; the in-process worker relays them into idempotent jobs of several kinds, claimed with leases, and any job can be cancelled.
EOF
  T_CONTEXT="$F015_CONTEXT
- FEAT-015 §4 FR-1 … FR-4; SQLite WAL and \`BEGIN IMMEDIATE\` notes in the research note §9.5
"
  txt T_SCOPE <<'EOF'
- `outbox_events`; job columns `kind`, `priority`, `lease_until`, `cancel_requested`, `attempts`, `run_at` (OQ-015-01).
- Relay with idempotency keys; claim with `UPDATE … RETURNING`; lease extension and reaper.
- `POST /optimization-jobs/{id}/cancel`.
EOF
  txt T_OUT <<'EOF'
- Evaluation and replan services; proposals.
EOF
  txt T_FILES <<'EOF'
- `apps/api/migrations/versions/<rev>_outbox_jobs.py` — new
- `apps/api/src/routepilot/optimization/jobs/*`, `apps/api/src/routepilot/freight/service/*` (emit events) — change
- `apps/api/tests/db/test_outbox.py`, `test_job_claim.py`, `apps/api/tests/api/test_jobs_cancel.py` — new
EOF
  txt T_TESTS <<'EOF'
- Outbox in the same transaction → AC-01; duplicate relay → AC-02; concurrent claim and lease expiry → AC-03; cancel → AC-04.
EOF
  T_VERIFY="$EVO_VERIFY_BACKEND"
  T_TIPS="$EVO_TIPS_COMMON
- \`freight\` must not import \`optimization\`: it writes outbox rows through a small shared port or a function in \`shared\`; check the import-linter contracts first.
"
}
register s_015_1

s_015_2() {
  I_ID="015/2"; I_FEAT="015"; I_PRIORITY="P1"; I_TITLE="OfferEvaluationService: insertion after the committed prefix"
  I_AREA="backend engine"; I_SIZE="L"; I_DAY="phase-2"; I_ACS="05 06 07"; I_DEPS="015/1 014/4 012/4"
  I_GATES="make check, make test-props"; I_BRANCH="feat/FEAT-015-offer-evaluation"; I_REQS="REQ-025, NFR-017, NFR-018"; I_ADRS="0004 0017"; I_SCOPE_TAG="jobs"
  txt T_GOAL <<'EOF'
A new or changed offer is evaluated deterministically for nearby on-duty drivers: the best feasible insertions after their committed stops, ranked by Δ cycle profit, become candidate proposals.
EOF
  T_CONTEXT="$F015_CONTEXT
- FEAT-015 §4 FR-5, FR-9; \`optimization/engine/schedule.py:380-406\` (\`build_plan\`)
"
  txt T_SCOPE <<'EOF'
- Candidate drivers, insertion positions, validator check, ranking, threshold, top-N, time box.
- Property P16 (committed prefix unchanged).
EOF
  txt T_OUT <<'EOF'
- Insertion between committed stops; storing proposals (015/4 stores them; this slice returns them in the job result).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/jobs/service/evaluation.py` — new
- `apps/api/tests/integration/test_event_pipeline.py`, `apps/api/tests/props/test_insertion.py` — new
EOF
  txt T_TESTS <<'EOF'
- Insertion proposal for the right driver → AC-05; P16 and validator → AC-06; no feasible insertion → AC-07.
EOF
  T_VERIFY="$EVO_VERIFY_ENGINE"
  T_TIPS="$EVO_TIPS_COMMON
- Reuse \`build_plan()\`; do not add a new solver.
"
}
register s_015_2

s_015_3() {
  I_ID="015/3"; I_FEAT="015"; I_PRIORITY="P1"; I_TITLE="ReplanService: delays and withdrawn offers"
  I_AREA="backend engine"; I_SIZE="M"; I_DAY="phase-2"; I_ACS="08 09"; I_DEPS="015/2"
  I_GATES="make check, make test-props"; I_BRANCH="feat/FEAT-015-replan"; I_REQS="REQ-025"; I_ADRS="0017"; I_SCOPE_TAG="jobs"
  txt T_GOAL <<'EOF'
A delay or a withdrawn offer on a committed route is replayed deterministically; affected stops and deadline risks are reported and up to three recovery options are prepared.
EOF
  T_CONTEXT="$F015_CONTEXT
- FEAT-015 §4 FR-6
"
  txt T_SCOPE <<'EOF'
- Replay from actual times; `WINDOW_MISSED`, `HOME_BY_AT_RISK`; recovery options ranked by Δ cycle profit; `impact = none`.
- Supersede older open proposals of the same assignment.
EOF
  txt T_OUT <<'EOF'
- Automatic application of any option.
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/jobs/service/replan.py` — new
- `apps/api/tests/integration/test_event_pipeline.py` — extended
EOF
  txt T_TESTS <<'EOF'
- Delay with and without impact → AC-08; withdrawn offer → AC-09.
EOF
  T_VERIFY="$EVO_VERIFY_ENGINE"
  T_TIPS="$EVO_TIPS_COMMON"
}
register s_015_3

s_015_4() {
  I_ID="015/4"; I_FEAT="015"; I_PRIORITY="P1"; I_TITLE="Proposals, one ApprovalService for REST and graph, eager expiry, no-LLM path"
  I_AREA="backend agents"; I_SIZE="L"; I_DAY="phase-2"; I_ACS="10 11 12 13"; I_DEPS="015/2"
  I_GATES="make check, make test-db, make test-agents, make openapi"; I_LOCK="🔒 \`apps/api/migrations/**\`, \`contracts/openapi.json\`"; I_APPROVAL="yes"
  I_BRANCH="feat/FEAT-015-approval-service"; I_REQS="REQ-025, REQ-017, NFR-005"; I_ADRS="0006 0017"; I_SCOPE_TAG="jobs"
  txt T_GOAL <<'EOF'
Proposals are stored, listed, approved and rejected through the API; every approval — chat or inbox — goes through one `ApprovalService` that re-validates versions and writes atomically; stale approvals expire on a schedule; all of it works without an LLM.
EOF
  T_CONTEXT="$F015_CONTEXT
- FEAT-015 §4 FR-7, FR-8, FR-10, FR-11; \`agents/graph.py:451-530\` (ApprovalGate), \`agents/service.py:265-291\` (lazy expiry)
- The owner's decision on OQ-015-04 in O-18 (\`context.md\` AI rule 3)
"
  txt T_SCOPE <<'EOF'
- `proposals` table and endpoints; `ApprovalService.approve/reject`; ApprovalGate delegates to it.
- `expire_proposals` job; template explanation without a model.
EOF
  txt T_OUT <<'EOF'
- Agent tools (FEAT-016); UI (015/5).
EOF
  txt T_FILES <<'EOF'
- `apps/api/migrations/versions/<rev>_proposals.py` — new
- `apps/api/src/routepilot/optimization/jobs/service/approval.py`, `proposals.py` — new; `agents/graph.py`, `agents/tools/registry.py` — change (delegation only)
- `contracts/openapi.json` — regenerated
- `apps/api/tests/agents/test_approval_service.py`, `apps/api/tests/api/test_proposals.py` — new
EOF
  txt T_TESTS <<'EOF'
- Same audit events from graph and REST → AC-10; stale, not open, demo → AC-11; eager expiry → AC-12; no-LLM pipeline → AC-13.
EOF
  T_VERIFY="$EVO_VERIFY_AGENTS"
  T_TIPS="$EVO_TIPS_COMMON
- Do not start before O-18 records the AI rule 3 decision; a write path outside \`interrupt()\` without it is rejected in review.
- The \`interrupt()\` in the ApprovalGate stays outside \`try/except\`, and the code before it stays idempotent.
"
}
register s_015_4

s_015_5() {
  I_ID="015/5"; I_FEAT="015"; I_PRIORITY="P1"; I_TITLE="Approval inbox and operational alerts (EN/PL)"
  I_AREA="frontend"; I_SIZE="L"; I_DAY="phase-2"; I_ACS="14"; I_DEPS="015/4"
  I_GATES="make check, pnpm test, e2e (ci-full)"; I_LOCK="\`apps/web/messages/*.json\`"
  I_BRANCH="feat/FEAT-015-inbox-ui"; I_REQS="REQ-025, REQ-021"; I_ADRS="0015"; I_SCOPE_TAG="web"
  txt T_GOAL <<'EOF'
Dispatchers see one inbox of open proposals and agent approval requests with a stop diff and Δ values, approve or reject them with a comment, and see operational alerts.
EOF
  T_CONTEXT="$F015_CONTEXT
- FEAT-015 §4 FR-12; research note §9.6; \`apps/web/src/features/agent-chat/approval-card*\`
"
  txt T_SCOPE <<'EOF'
- `features/approvals` (inbox, diff, approve/reject), alerts panel, SSE or polling per OQ-015-03; EN and PL.
EOF
  txt T_OUT <<'EOF'
- Notifications outside the app.
EOF
  txt T_FILES <<'EOF'
- `apps/web/src/features/approvals/*`, `apps/web/src/app/approvals/page.tsx` — new
- `apps/web/messages/*.json` — change; `tests/e2e/approvals.spec.ts` — new
EOF
  txt T_TESTS <<'EOF'
- e2e approve an insertion proposal in EN and PL → AC-14.
EOF
  T_VERIFY="$EVO_VERIFY_WEB"
  T_TIPS="$EVO_TIPS_COMMON"
}
register s_015_5

# ---------------------------------------------------------------------------
# FEAT-016 — Agent tools for planning
# ---------------------------------------------------------------------------

F016_CONTEXT="$EVO_CONTEXT_COMMON
- ${EVO_NOTE} §8
- \`specs/FEAT-016-agent-tools-for-planning.md\` (Agent Tool Specs in §6)
- \`apps/api/src/routepilot/agents/tools/registry.py\`, \`agents/tools/contracts.py\`, \`agents/graph.py\`, \`evals/README.md\`"

s_016_1() {
  I_ID="016/1"; I_FEAT="016"; I_PRIORITY="P1"; I_TITLE="Agent tool driver_calendar (Fleet & Compliance)"
  I_AREA="agents"; I_SIZE="M"; I_DAY="phase-2"; I_ACS="01"; I_DEPS="O-19 011/3"
  I_GATES="make check, make test-agents"; I_LOCK="🔒 tool allowlist"; I_APPROVAL="yes"
  I_BRANCH="feat/FEAT-016-driver-calendar"; I_REQS="REQ-040, REQ-018"; I_ADRS="0006"; I_SCOPE_TAG="agents"
  txt T_GOAL <<'EOF'
The Fleet & Compliance agent can read a driver's duty windows, home requirement and rest-ledger facts through a typed, allowlisted read tool whose numbers pass the GroundingGuard.
EOF
  T_CONTEXT="$F016_CONTEXT
- FEAT-016 §4 FR-1, §6 Tool \`driver_calendar\`
"
  txt T_SCOPE <<'EOF'
- Input and output contracts, registry entry with role and kind, adapter over the availability service.
EOF
  txt T_OUT <<'EOF'
- Prompt changes (016/5).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/agents/tools/contracts.py`, `registry.py` — change
- `apps/api/tests/agents/test_planning_tools.py` — new
EOF
  txt T_TESTS <<'EOF'
- Allowlist, grounding pass and failure → AC-01.
EOF
  T_VERIFY="$EVO_VERIFY_AGENTS"
  T_TIPS="$EVO_TIPS_COMMON
- Aliases only; no names, phone numbers or home addresses in tool output.
"
}
register s_016_1

s_016_2() {
  I_ID="016/2"; I_FEAT="016"; I_PRIORITY="P1"; I_TITLE="Agent tools evaluate_insertion and compare_cycle_options (Route Planner)"
  I_AREA="agents backend"; I_SIZE="L"; I_DAY="phase-2"; I_ACS="02 03"; I_DEPS="O-19 015/2 012/5"
  I_GATES="make check, make test-agents"; I_LOCK="🔒 tool allowlist"; I_APPROVAL="yes"
  I_BRANCH="feat/FEAT-016-planning-tools"; I_REQS="REQ-040"; I_ADRS="0006 0016"; I_SCOPE_TAG="agents"
  txt T_GOAL <<'EOF'
The Route Planner can ask where a new offer fits and compare offer combinations against going home empty, with every number coming from the engine.
EOF
  T_CONTEXT="$F016_CONTEXT
- FEAT-016 §4 FR-2, FR-3, §6 Tools \`evaluate_insertion\`, \`compare_cycle_options\`; research note §5.6
"
  txt T_SCOPE <<'EOF'
- Two read tools; new read method `PlanService.compare_cycle_options`.
EOF
  txt T_OUT <<'EOF'
- Prompt changes (016/5).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/agents/tools/contracts.py`, `registry.py`, `optimization/jobs/service/__init__.py` (read method) — change
- `apps/api/tests/agents/test_planning_tools.py` — extended
EOF
  txt T_TESTS <<'EOF'
- Bounded insertion output without offer text → AC-02; comparison equals engine values for GOLD-012 → AC-03.
EOF
  T_VERIFY="$EVO_VERIFY_AGENTS"
  T_TIPS="$EVO_TIPS_COMMON
- Zero business logic in the tool: combinations are enumerated in the service, not in the adapter.
"
}
register s_016_2

s_016_3() {
  I_ID="016/3"; I_FEAT="016"; I_PRIORITY="P1"; I_TITLE="Write tool amend_assignment behind interrupt() and the ApprovalService"
  I_AREA="agents"; I_SIZE="M"; I_DAY="phase-2"; I_ACS="04 05"; I_DEPS="O-19 015/4"
  I_GATES="make check, make test-agents"; I_LOCK="🔒 new write tool"; I_APPROVAL="yes"
  I_BRANCH="feat/FEAT-016-amend-assignment"; I_REQS="REQ-040, REQ-017"; I_ADRS="0006 0017"; I_SCOPE_TAG="agents"
  txt T_GOAL <<'EOF'
An approved amendment of an active assignment is written exactly once, only from the ApprovalGate after a human `approve`, through the shared `ApprovalService`.
EOF
  T_CONTEXT="$F016_CONTEXT
- FEAT-016 §4 FR-4, FR-5, §6 Tool \`amend_assignment\`; \`context.md\` → AI Architecture Rules 3, 4
"
  txt T_SCOPE <<'EOF'
- `amend_assignment` with `roles=()`, kind `write`; `request_approval` kind `amend`.
- Idempotent re-entry after resume.
EOF
  txt T_OUT <<'EOF'
- Any other write tool.
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/agents/tools/registry.py`, `contracts.py`, `agents/graph.py` — change
- `apps/api/tests/agents/test_amend_assignment.py` — new
EOF
  txt T_TESTS <<'EOF'
- Reject, expiry, approve once, no direct call → AC-04; crash between write and checkpoint → AC-05.
EOF
  T_VERIFY="$EVO_VERIFY_AGENTS"
  T_TIPS="$EVO_TIPS_COMMON
- A write tool without \`interrupt()\` is rejected in review; keep the \`interrupt()\` outside \`try/except\`.
"
}
register s_016_3

s_016_4() {
  I_ID="016/4"; I_FEAT="016"; I_PRIORITY="P1"; I_TITLE="Job handles in agent tools, run recovery at startup, durability sync"
  I_AREA="agents"; I_SIZE="M"; I_DAY="phase-2"; I_ACS="06 07 08"; I_DEPS="O-19"
  I_GATES="make check, make test-agents"; I_BRANCH="feat/FEAT-016-job-handles"; I_REQS="REQ-040, NFR-004"; I_ADRS="0006 0008"; I_SCOPE_TAG="agents"
  txt T_GOAL <<'EOF'
Long tools return a job handle instead of blocking for 60 s, a run that was running at a crash no longer blocks its thread, and approval runs survive a restart.
EOF
  T_CONTEXT="$F016_CONTEXT
- FEAT-016 §4 FR-6 … FR-8; \`registry.py:467\` (hard 60 s wait), \`agents/service.py:32, 152-155, 335-341\`
"
  txt T_SCOPE <<'EOF'
- `horizonDays` and `driverAliases` inputs; `job_status` tool; `AGENT_TOOL_SYNC_WAIT_S`.
- Startup recovery `RUN_INTERRUPTED`; `durability="sync"` (verify the parameter in the pinned LangGraph version first).
EOF
  txt T_OUT <<'EOF'
- Budget defaults (016/5).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/agents/tools/*`, `agents/service.py`, `main.py` (startup hook) — change
- `apps/api/tests/agents/test_job_handles.py`, `test_durability.py`, `apps/api/tests/integration/test_agent_run_recovery.py` — new
EOF
  txt T_TESTS <<'EOF'
- Job handle and polling → AC-06; recovery → AC-07; durability after a kill → AC-08.
EOF
  T_VERIFY="$EVO_VERIFY_AGENTS"
  T_TIPS="$EVO_TIPS_COMMON"
}
register s_016_4

s_016_5() {
  I_ID="016/5"; I_FEAT="016"; I_PRIORITY="P1"; I_TITLE="New prompt versions and eval scenarios 31–38 (offline; live within the budget)"
  I_AREA="agents"; I_SIZE="L"; I_DAY="phase-2"; I_ACS="09 10"; I_DEPS="016/1 016/2 016/3 016/4"
  I_GATES="make check, make test-agents, make eval-offline; live ai-evals only with the O-19 budget"; I_LOCK="🔒 \`apps/api/src/routepilot/agents/prompts/**\`, 🔒 paid \`ai-evals\`"; I_APPROVAL="yes"
  I_BRANCH="feat/FEAT-016-prompts-evals"; I_REQS="REQ-040, NFR-012"; I_ADRS="0006 0013"; I_SCOPE_TAG="agents"
  txt T_GOAL <<'EOF'
The agents know the new tools through approved prompt versions; eight new scenarios cover them offline in CI and live within an agreed budget, without losing the current eval results.
EOF
  T_CONTEXT="$F016_CONTEXT
- FEAT-016 §4 FR-9 … FR-11; \`docs/reports/FEAT-006-live-evals-2026-11-14.md\`; development log P10, P13
"
  txt T_SCOPE <<'EOF'
- `fleet_compliance.v3`, `route_planner.v2`, `dispatcher.v3` (owner-approved).
- `evals/agents/31-38*.yaml`; offline campaign; one live campaign within the recorded budget; budget defaults from measured runs.
EOF
  txt T_OUT <<'EOF'
- The single-agent experiment (016/6).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/agents/prompts/*.v*.md` — new versions
- `evals/agents/31-*.yaml` … `38-*.yaml` — new; `evals/README.md` — change
- `apps/api/src/routepilot/shared/config.py` — budget defaults (owner-approved)
EOF
  txt T_TESTS <<'EOF'
- Offline campaign all green → AC-09; live campaign report → AC-10.
EOF
  T_VERIFY="$EVO_VERIFY_AGENTS"
  T_TIPS="$EVO_TIPS_COMMON
- Check the budget and the tokens already spent before any live run; stop at the allowance even if unfinished.
"
}
register s_016_5

s_016_6() {
  I_ID="016/6"; I_FEAT="016"; I_PRIORITY="P2"; I_TITLE="Experiment: single dispatcher agent with tools vs the supervisor"
  I_AREA="agents"; I_SIZE="M"; I_DAY="phase-3"; I_ACS="11"; I_DEPS="016/5"
  I_GATES="make check; live ai-evals only with the O-19 budget"; I_LOCK="🔒 paid \`ai-evals\`"; I_APPROVAL="yes"
  I_BRANCH="exp/FEAT-016-single-agent"; I_REQS="REQ-040, NFR-012"; I_ADRS="0006"; I_SCOPE_TAG="agents"
  txt T_GOAL <<'EOF'
The owner gets a measured comparison (success, tool-call correctness, violations, tokens, latency) of a single dispatcher agent holding all read tools against today's supervisor, without changing any production default.
EOF
  T_CONTEXT="$F016_CONTEXT
- FEAT-016 §4 FR-12; research note §8.1 (sources on multi-agent vs single agent)
"
  txt T_SCOPE <<'EOF'
- An experimental graph configuration selectable only in the eval runner; the report in `evals/reports/`.
EOF
  txt T_OUT <<'EOF'
- Changing the default graph.
EOF
  txt T_FILES <<'EOF'
- `evals/runner.py`, `evals/fixtures.py` — change; `apps/api/src/routepilot/agents/graph.py` — an experimental builder only
EOF
  txt T_TESTS <<'EOF'
- Report produced with both variants → AC-11.
EOF
  T_VERIFY="$EVO_VERIFY_AGENTS"
  T_TIPS="$EVO_TIPS_COMMON"
}
register s_016_6

# ---------------------------------------------------------------------------
# FEAT-017 — Larger fleets
# ---------------------------------------------------------------------------

F017_CONTEXT="$EVO_CONTEXT_COMMON
- ${EVO_NOTE} §7.3–7.7, §13
- \`specs/FEAT-017-larger-fleets.md\`, \`docs/adr/ADR-0016-staged-optimizer-evolution.md\`
- \`bench/README.md\`, \`bench/fleet_5x60.py\`, \`apps/api/src/routepilot/optimization/engine/fleet.py:47-91\`"

s_017_1() {
  I_ID="017/1"; I_FEAT="017"; I_PRIORITY="P1"; I_TITLE="Benchmark grid, scaled synthetic generators and the metrics report"
  I_AREA="engine data"; I_SIZE="L"; I_DAY="phase-1"; I_ACS="01 02 03"; I_DEPS="O-20 011/5"
  I_GATES="make check, make test-props, bench (manual)"; I_BRANCH="feat/FEAT-017-bench-grid"; I_REQS="REQ-039, NFR-002, NFR-017"; I_ADRS="0016"; I_SCOPE_TAG="bench"
  txt T_GOAL <<'EOF'
A reproducible benchmark measures the engine on synthetic fleets of 5–100 vans, 1–21-day horizons, three densities, two consolidation levels, mixed rotations and dynamic arrivals, and writes every metric of FEAT-017 FR-3.
EOF
  T_CONTEXT="$F017_CONTEXT
- FEAT-017 §4 FR-1 … FR-3
"
  txt T_SCOPE <<'EOF'
- `bench/grid.py` (full grid and 36-cell fractional design), generator parameters, JSON report with machine information.
EOF
  txt T_OUT <<'EOF'
- New solvers; CI workflow changes (owner approval needed for a nightly job).
EOF
  txt T_FILES <<'EOF'
- `bench/grid.py`, `bench/tests/test_grid.py` — new; `bench/README.md` — change
- `apps/api/src/routepilot/fleet/generator.py`, `freight/generator.py` — change (parameters only)
- `apps/api/tests/props/test_scaled_generators.py` — new
EOF
  txt T_TESTS <<'EOF'
- Fractional design and byte-identical instances → AC-01; generator properties → AC-02; report fields → AC-03.
EOF
  T_VERIFY="$EVO_VERIFY_ENGINE"
  T_TIPS="$EVO_TIPS_COMMON
- Never commit local benchmark result files (\`bench/results/*.json\`); timings are recorded, not asserted.
"
}
register s_017_1

s_017_2() {
  I_ID="017/2"; I_FEAT="017"; I_PRIORITY="P1"; I_TITLE="FleetSelector port with CP-SAT set packing and the DFS fallback"
  I_AREA="engine"; I_SIZE="L"; I_DAY="phase-2"; I_ACS="04 05 06 07"; I_DEPS="017/1 012/5"
  I_GATES="make check, make test-props, bench (manual)"; I_LOCK="🔒 new dependency (\`apps/api/pyproject.toml\`, \`uv.lock\`)"; I_APPROVAL="yes"
  I_BRANCH="feat/FEAT-017-cpsat-selection"; I_REQS="REQ-039, REQ-010, NFR-001, NFR-019"; I_ADRS="0004 0016"; I_SCOPE_TAG="engine"
  txt T_GOAL <<'EOF'
Fleet selection scales to 50+ drivers with an exact, deterministic CP-SAT model behind a port, while the existing DFS stays the default, the oracle and the fallback.
EOF
  T_CONTEXT="$F017_CONTEXT
- FEAT-017 §4 FR-4, FR-5; OR-Tools facts in the research note §7.3 and §15.4
"
  txt T_SCOPE <<'EOF'
- `FleetSelector` port; `DfsFleetSelector` (moved, unchanged); `CpSatFleetSelector` (staged lexicographic, 1 worker, fixed seed, time limit).
- `ENGINE_FLEET_SELECTOR`, `SELECTOR_FALLBACK`; `ortools` added (version and licence verified on PyPI first).
EOF
  txt T_OUT <<'EOF'
- Changing the default selector; the candidate generator (017/3).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/engine/selection.py` — new; `fleet.py`, `optimizer.py` — change
- `apps/api/pyproject.toml`, `uv.lock` — change (owner-approved dependency)
- `apps/api/tests/props/test_fleet_selector.py`, `apps/api/tests/unit/engine/test_fleet_selector.py` — new
EOF
  txt T_TESTS <<'EOF'
- Equality with the DFS → AC-04; determinism → AC-05; fallback → AC-06; 50 × 10 recorded → AC-07.
EOF
  T_VERIFY="$EVO_VERIFY_ENGINE"
  T_TIPS="$EVO_TIPS_COMMON
- Import \`ortools\` lazily inside the selector so the engine stays importable without it; the engine package must not gain IO.
"
}
register s_017_2

s_017_3() {
  I_ID="017/3"; I_FEAT="017"; I_PRIORITY="P2"; I_TITLE="CandidateGenerator port, OR-Tools PDPTW generator with repair, adoption-gate report"
  I_AREA="engine"; I_SIZE="L"; I_DAY="phase-3"; I_ACS="08 09 10"; I_DEPS="017/2"
  I_GATES="make check, make test-props, bench (manual)"; I_BRANCH="feat/FEAT-017-ortools-generator"; I_REQS="REQ-039, NFR-002"; I_ADRS="0004 0016"; I_SCOPE_TAG="engine"
  txt T_GOAL <<'EOF'
An optional OR-Tools generator proposes routes for large fleets; every route is re-scheduled with the real rules and accepted only by the validator; a gate report tells the owner whether it beats the B&B.
EOF
  T_CONTEXT="$F017_CONTEXT
- FEAT-017 §4 FR-6 … FR-8; OR-Tools issue #4982 (do not use \`SetAllowedVehiclesForIndex\`)
"
  txt T_SCOPE <<'EOF'
- `CandidateGenerator` port; `BranchAndBoundGenerator` (default); `OrToolsPdptwGenerator`; repair loop; `bench/gate_report.py`.
EOF
  txt T_OUT <<'EOF'
- Switching the default generator (owner decision from the report).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/engine/candidates.py` — new; `optimizer.py` — change
- `bench/gate_report.py`, `bench/tests/test_gate_report.py` — new
- `apps/api/tests/props/test_ortools_generator.py` — new (marked `slow`)
EOF
  txt T_TESTS <<'EOF'
- Golden unchanged behind the port → AC-08; validator acceptance and repair stats → AC-09; gate rule → AC-10.
EOF
  T_VERIFY="$EVO_VERIFY_ENGINE"
  T_TIPS="$EVO_TIPS_COMMON
- Register transit costs as matrices; never put Python callbacks in the inner loop.
"
}
register s_017_3
