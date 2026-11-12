## Summary

<!-- What changes and which specification it implements. One task = one PR. Title: Conventional Commits, naming FEAT-xxx. Describe the project only as an MVP with a deadline (2026-11-15), later a portfolio project. -->

- Specification: <!-- FEAT-xxx, revision, status `approved` -->
- Slice / backlog row: <!-- for example 006/3, O-6 -->

## Report: <!-- FEAT-xxx / slice n -->

- Status: <!-- done | partial | blocked -->
- Changes: <!-- file or module, one line each -->
- ACs covered: <!-- AC-… → test that names it -->
- Gates run: <!-- lint / types / unit / props / agents / db / build — with results; quote failures with their output -->
- Assumptions / Unverified / Spec changes proposed / Dependencies added / Risks:

## Definition of Done

- [ ] Tests for all ACs in scope pass; `make check` is green; `ci-fast` is green
- [ ] Coverage thresholds of the touched packages hold; no new unjustified suppressions
- [ ] Contracts and generated types are regenerated and committed; no unintended breaking change
- [ ] Agent changes: agent tests green; `ai-evals` run if a prompt, policy or tool changed
- [ ] Frontend changes: UI texts exist in EN and PL
- [ ] API changes: status codes, CORS and problem+json follow `DEVELOPMENT.md` §4
- [ ] The README run steps still work from a clean clone (if dependencies, env variables, migrations or the seed changed)
- [ ] Specification changelog and traceability (`make trace`) updated; completion report written

## Needs owner approval

<!-- Tick what this PR contains; approval is per change (AGENTS.md §9). -->

- [ ] Migration
- [ ] Prompt or model policy change
- [ ] Workflow file (`.github/workflows/**`)
- [ ] New runtime dependency
- [ ] Contract or breaking API change
- [ ] Spec status, golden values, ADR or `context.md`
- [ ] Live (paid) provider run — token allowance agreed in the linked issue

## Safety check

- [ ] No secrets, `.env` or database files, and no real personal data in code, tests, fixtures, logs or this description
- [ ] Synthetic data is labelled as synthetic; no write tool without `interrupt()` and human approval
- [ ] No test skipped, deleted or weakened; no `--no-verify`
