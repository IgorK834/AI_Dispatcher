# Specifications

This folder holds **what to build**: requirements, feature specifications with acceptance criteria, and golden cases. Rules live in [`context.md`](../context.md); rationale in [`docs/report.md`](../docs/report.md); decisions in [`docs/adr/`](../docs/adr/README.md); how-to in [`DEVELOPMENT.md`](../DEVELOPMENT.md).

> **Status (2026-11-11):** FEAT-000 … FEAT-007 and FEAT-009 are `approved` by the owner; FEAT-008 (P1) is `draft`. Nothing is implemented.

## How specifications work

1. A need is written as a requirement (`REQ-xxx`) or a non-functional requirement (`NFR-xxx`) in [`requirements.md`](requirements.md).
2. A feature specification (`FEAT-xxx-<slug>.md`) is created from [`_template.md`](_template.md). It lists the requirements it covers, the contracts and the acceptance criteria.
3. The owner reviews it and changes the status to `approved`. **No approved specification → no implementation.**
4. An implementation agent gets a task brief that names the specification revision and the ACs in scope.
5. Tests reference the ACs. When all ACs pass in CI and the work is merged, the owner sets the status to `implemented`.
6. A change to a contract, migration, prompt or agent tool always comes with a specification change in the same pull request (the `revision` number goes up and the changelog gets a line).

## Statuses

| Status | Meaning | Who sets it |
|---|---|---|
| `draft` | written, not yet binding; open questions may remain | Architect & Spec Agent |
| `approved` | binding contract for implementation; ACs are testable; blocking open questions are answered | owner (human) only |
| `implemented` | merged; every AC has a passing test in CI | owner, after `make trace` |
| `deprecated` | no longer valid; the changelog names the replacement | owner |

## ID scheme

| Artefact | Format | Example | Where |
|---|---|---|---|
| Requirement | `REQ-nnn` | `REQ-009` | `requirements.md` |
| Non-functional requirement | `NFR-nnn` | `NFR-002` | `requirements.md` |
| Feature specification | `FEAT-nnn` | `FEAT-003` | `FEAT-003-optimizer-and-working-time.md` |
| Acceptance criterion | `AC-FEAT-nnn-nn` | `AC-FEAT-003-07` | section 7 of the FEAT file |
| Open question | `OQ-nnn-nn` (feature number, running number) | `OQ-003-04` | section 11 of the FEAT file |
| Golden case | `GOLD-nnn` | `GOLD-001` | `golden/GOLD-001.md` |
| Decision record | `ADR-nnnn` | `ADR-0004` | `docs/adr/` |

IDs are never reused. A removed AC keeps its number and is marked "withdrawn" in the changelog.

## Acceptance criteria

Every AC has four parts:

```
- **AC-FEAT-003-07** [property] Given <starting state> When <action> Then <observable result>
```

The tag names the test type: `unit`, `property`, `golden`, `contract`, `db`, `integration`, `agent`, `e2e` or `eval`. Types are defined in [`context.md` → Testing Standards](../context.md#testing-standards). `eval` criteria run only in the manual `ai-evals` workflow and never block `ci-fast`.

## Traceability rules

1. Every `REQ`/`NFR` in scope is covered by at least one FEAT; every FEAT lists its requirements in the front matter. The table at the end of [`requirements.md`](requirements.md) maps REQ → FEAT → ACs.
2. Every AC has at least one test that names it:
   - Python: `@pytest.mark.ac("AC-FEAT-003-07")`
   - TypeScript and Playwright: `[AC-FEAT-005-02]` in the test title
3. `scripts/trace.py` (planned, FEAT-000) reads the specifications and the tests, joins them with the CI test reports and writes `docs/traceability.md`.
4. `trace.py --check` fails CI when an AC of an `approved` or `implemented` specification has no test, when a test names an AC that does not exist, or when an `implemented` specification has a failing test.

## Files

| File | Content | Priority |
|---|---|---|
| [`requirements.md`](requirements.md) | REQ-001 … REQ-033, NFR-001 … NFR-015, traceability table | — |
| [`_template.md`](_template.md) | FEAT template with the Agent Tool Spec block | — |
| [`FEAT-000-monorepo-and-ci.md`](FEAT-000-monorepo-and-ci.md) | workspace, tooling, `ci-fast`, scripts, agent-instruction files | P0 |
| [`FEAT-001-domain-sqlite-crud-auth.md`](FEAT-001-domain-sqlite-crud-auth.md) | SQLite, migrations, CRUD endpoints, CORS + CSRF, auth, audit | P0 |
| [`FEAT-002-demo-data-generators.md`](FEAT-002-demo-data-generators.md) | fleet and offer generators, `cities.json`, TIMOCOM v3 mapper, import, seed | P0 |
| [`FEAT-003-optimizer-and-working-time.md`](FEAT-003-optimizer-and-working-time.md) | `DriverRules`, cost model, search, fleet assignment, validators, baselines | P0 |
| [`FEAT-004-routing-and-jobs.md`](FEAT-004-routing-and-jobs.md) | `RoutingProvider`, job worker, job/plan/assignment endpoints | P0 |
| [`FEAT-005-frontend.md`](FEAT-005-frontend.md) | screens, states, i18n, accessibility, typed client, SSE | P0 |
| [`FEAT-006-runtime-agents.md`](FEAT-006-runtime-agents.md) | LangGraph graph, agents, guards, approval flow, tools | P0 |
| [`FEAT-007-quality-readme-ci-full.md`](FEAT-007-quality-readme-ci-full.md) | `ci-full`, E2E, clean-clone test, documentation checklists, metrics | P0 |
| [`FEAT-008-p1-offer-text-and-road-alternatives.md`](FEAT-008-p1-offer-text-and-road-alternatives.md) | offer text interpretation, road alternatives, risk rating | P1 |
| [`FEAT-009-demo-media.md`](FEAT-009-demo-media.md) | demo video script, recording settings, screenshots | P0 |
| [`golden/`](golden/README.md) | GOLD-001 … GOLD-010 with shown arithmetic | P0 |

Suggested implementation order: FEAT-000 → FEAT-001 → FEAT-002 → FEAT-003 → FEAT-004 → FEAT-006 → FEAT-005 → FEAT-007 → FEAT-009; FEAT-008 only if time allows ([`context.md` → Next Implementation Tasks](../context.md#next-implementation-tasks)).
