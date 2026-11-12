# Task: FEAT-006 runtime, prerequisites and O-6/O-7

Owner request: implement the missing agent runtime, eval runner and manual
`ai-evals` workflow, including their prerequisites, following approved specs.
Parallel coding agents were explicitly authorised by the owner.

- Specifications: approved FEAT-001, FEAT-002, FEAT-003, FEAT-004 and FEAT-006;
  FEAT-007 integration scenario and manual eval workflow (AC-02 and AC-09).
- Allowed paths: prerequisite modules `identity`, `fleet`, `freight`,
  `integrations`, `compliance`, `routing`, `optimization`, `agents`; composition
  and necessary shared interfaces/configuration; their tests and generated
  contracts; `data/mock`; eval scenarios/runner; `ai-evals.yml`; required
  Makefile targets, environment examples, traceability and completion reports.
- Shared-file author: root agent owns composition, settings, dependencies and
  locks, contracts, workflows, Makefile and specification metadata. Subagents
  own disjoint module paths and report checkpoint commits for integration.
- Prompt content: the five v1 files approved at `e585b466c124d643c18b7bac7837ee4241e3152d`
  remain unchanged. Any content change requires a new version and approval.
- Initial migration: already reviewed; no migration change is planned.
- Gates: `make check`, engine property/golden tests, `make test-db`,
  `make test-agents`, OpenAPI/type drift checks, workflow/budget tests, integration
  tests, then the separately budgeted live campaign.

## Owner decisions applied during prerequisite review

- Align `context.md` rule 7 with the approved FEAT-003 PL planning model:
  30 minutes at six work hours plus a 15-minute top-up at nine hours when more
  work follows. Golden values remain unchanged.
- Clarify FEAT-003 FR-7: a full break may finish after a short wait's nominal
  end and delay service. Only the overlapping part replaces waiting work;
  ordinary time-window validation rejects a late plan.
- Clarify FEAT-006 FR-20: SSE event IDs increase independently of step sequence
  numbers, which remain in the payload. This preserves every start/finish event
  on reconnect. The owner approved this clarification on 2026-11-11.

## Live allowance

The agreed hard campaign allowance is 500,000 total provider tokens: at most
50,000 for the O-6 smoke run and 450,000 for one O-7 eval batch. Input, output,
thinking and retries count once. Reserve each call's input and maximum output
before dispatch; stop rather than extending the allowance. No paid generation
has run at task start. Keys remain only in ignored local environment files and
GitHub Secrets. Tests never call an external provider.

The runtime must use real prerequisite services, validators and assignments.
Standalone prompt calls cannot substitute for the application approval flow or
for application-level injection and write-policy evaluations.
