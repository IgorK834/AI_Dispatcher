# AGENTS.md — instructions for AI coding agents

## 1. Purpose

This file is the entry point for any AI coding agent that works on **RoutePilot AI**, an AI dispatcher for a small van fleet (an MVP with a deadline of 2026-11-15, later a portfolio project).

**Read [`context.md`](context.md) before any task; it overrides this file on project rules.** This file tells you how to behave; `context.md` tells you the rules of the project; [`specs/`](specs/README.md) tells you what to build. If the documents disagree, stop and report it.

You are a **coding agent**. Do not confuse yourself with the **runtime agents** (the LangGraph agents inside the product).

## 2. Four behavioural principles

*Behavioural guidelines adapted from the ideas in [andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills/blob/main/CLAUDE.md).*

*They favour caution over speed. For a trivial task (a typo, a rename inside one file) use judgment on how much you say. The workflow (§4), the stop conditions (§5) and the prohibitions (§6) always apply.*

### 2.1 Think before coding

- Before you write anything, say what you understood: the specification, the acceptance criteria (ACs) in scope and your assumptions. If you are uncertain, ask.
- If a requirement can be read in two ways, name both readings and ask. Do not pick one silently.
- If a simpler way exists than the one requested, say so before you start, and push back when the request warrants it.
- If something is unclear, stop. Name what is confusing and ask. §5 lists the cases that need a `blocked` report.
- Example: an AC says "delete a driver". Check the specification for the rule about active assignments (`409`) before you write a plain `DELETE`.

### 2.2 Simplicity first

- Write the smallest code that satisfies the ACs. No feature beyond what was asked; nothing "for later".
- No abstraction for single-use code. No new abstraction, configuration option, dependency, service or runtime agent without a specification (and an ADR where `context.md` requires one).
- No error handling for cases that cannot happen; no feature flags nobody asked for.
- If 200 lines could be 50, rewrite them. Ask: "Would a senior engineer call this overcomplicated?" If yes, simplify.
- Example: the specification asks for cursor pagination on one list. Do not build a generic query-builder framework.

### 2.3 Surgical changes

- Touch only what the task needs. Stay inside the **Allowed paths** of your task brief.
- Match the existing style, even if you would do it differently. Do not reformat, rename or "improve" neighbouring code, comments or formatting, and do not refactor what is not broken.
- Clean up only your own mess: remove imports, variables and files that *your* change made unused. Mention other dead code in the report; do not delete it.
- Shared files (`contracts/openapi.json`, migrations, lockfiles, `context.md`, `specs/requirements.md`, workflows, `Makefile`, `.env.example`, prompts, `messages/*.json`) have one author at a time. Change them only if the brief says so.
- The test: every changed line traces to an AC or to the brief.

### 2.4 Goal-driven execution

- Turn the task into checks you can run. Every AC maps to at least one test that names it (`@pytest.mark.ac("AC-FEAT-003-07")` or `[AC-FEAT-005-02]` in a test title).
- Write or update the tests first, then make them pass. New feature: tests for its ACs. Bug fix: a test that reproduces the bug. Refactor: tests green before and after.
- For multi-step work, state a brief plan with one line per step: `[step] → verify: [check]`.
- Loop until verified: run `make check` (and the extra gates your brief lists) before you report. "It should work" is not a result.
- If a test can only pass by weakening it, stop and ask.

## 3. Project quick facts

> **Status:** design phase. Items marked *(planned)* do not exist yet; they are created by FEAT-000 and later features. Do not assume a planned command works — check.

| Topic | Fact |
|---|---|
| Backend | `apps/api` *(planned)* — Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic; layers `api → service → domain / repository` |
| Frontend | `apps/web` *(planned)* — Next.js 16, React 19, TypeScript strict, Tailwind + Radix UI primitives with design system `docs/design/` (no shadcn/ui, ADR-0015), TanStack Query, next-intl (EN/PL) |
| Database | SQLite (WAL); tests on in-memory SQLite; agent checkpoints in a separate `agents.db` |
| Runtime AI | LangGraph: Dispatcher + Freight Scout, Fleet & Compliance, Route Planner; guards; one write tool `assign_plan` after `interrupt()` |
| Ports | API `http://localhost:8000`, web `http://localhost:3000` |
| Run API *(planned)* | `cd apps/api && uv sync && uv run alembic upgrade head && uv run uvicorn routepilot.main:app --reload --port 8000` |
| Run web *(planned)* | `cd apps/web && pnpm install && pnpm dev` |
| Checks *(planned)* | `make check` (lint, types, unit) · `make test-props` · `make test-agents` · `make test-db` · `make openapi` · `make trace` |
| Tests *(planned)* | `cd apps/api && uv run pytest` · `cd apps/web && pnpm test` |

Repository map (✅ exists today):

```
context.md ✅  AGENTS.md ✅  CLAUDE.md ✅  README.md ✅  DEVELOPMENT.md ✅
specs/ ✅            requirements, FEAT-000…009, golden cases
docs/report.md ✅    research and rationale      docs/adr/ ✅   decisions
docs/design/ ✅      UI design system, tokens    backlog.md ✅  slices; scripts/create_github_issues.sh ✅
apps/api, apps/web, contracts/, data/mock/, other scripts/, tests/e2e/, .github/workflows/   (planned)
```

## 4. Spec-driven workflow (8 steps)

1. Read `context.md` in full.
2. Find the FEAT specification with status `approved`. If there is none, **stop**.
3. Verify the contracts (API, data, ports, agent tools) in the specification and in `contracts/openapi.json`.
4. Check that every module you will touch is in the brief's Allowed paths.
5. Write or update the tests for the ACs in scope, with AC markers.
6. Implement the smallest change that satisfies the ACs.
7. Run `make check`, plus `make test-props` (engine, compliance), `make test-agents` (agents), `make test-db` (database), `make openapi` (contract change).
8. File a completion report (section 8).

## 5. Stop and ask when

- there is no `approved` specification, or an AC is ambiguous;
- `context.md`, a specification and an ADR contradict each other;
- you need to change a contract, migration, prompt, agent policy or a module outside the brief, and the specification did not foresee it;
- an invariant cannot be satisfied, or a legal rule is unclear;
- you need a new dependency, service, runtime agent or `write` tool;
- a test could only pass by weakening, deleting or silencing it;
- you would need secrets, real data or a paid API outside the brief.

Report it as `blocked`, with a description and a proposal. Do not implement the proposal.

## 6. Hard prohibitions

- Do not skip, delete, disable or weaken tests. `xfail` only with a linked bug and human consent.
- No `--no-verify`; no `# type: ignore`, `# noqa`, `eslint-disable` or `@ts-ignore` without a rule code and a written reason; no lowered thresholds.
- No secrets in code, tests, logs, fixtures or commits. Never commit `.env` or database files.
- No real personal data. Demo data comes only from the generators.
- Synthetic data is never presented as real freight-exchange offers or real people (`is_synthetic = true`, UI badge, no exchange branding).
- No `write` tool for runtime agents without `interrupt()` and human approval.
- Never claim that a schedule complies with the law. Keep the working-time notice where schedules are shown.
- Do not present planned things as implemented.
- **Purpose statement** (as in `context.md` → Project Constraints 10): describe the project only as an MVP with a deadline (2026-11-15), later a portfolio project. Write nothing about why or for whom it is built, and name no third-party organisation in that role — in any file, comment, example, commit message or pull request.
- Do not add a package whose existence and version you have not verified in its registry.

## 7. Definition of Done

- [ ] Tests for all ACs in scope pass; `make check` is green; `ci-fast` is green.
- [ ] Coverage thresholds of the touched packages hold; no new unjustified suppressions.
- [ ] Contracts and generated types are regenerated and committed; no unintended breaking change.
- [ ] Agent changes: agent tests green; `ai-evals` run if a prompt, policy or tool changed.
- [ ] Frontend changes: UI texts exist in EN and PL.
- [ ] API changes: status codes, CORS and problem+json follow `DEVELOPMENT.md` §4.
- [ ] The README run steps still work from a clean clone (if you changed dependencies, env variables, migrations or the seed).
- [ ] Specification changelog and traceability (`make trace`) updated; completion report written.

## 8. Completion report format

```markdown
## Report: <FEAT-xxx / slice n>
- Status: done | partial | blocked
- Changes: <file/module — 1 line each>
- ACs covered: AC-… → <test>
- Gates run: lint / types / unit / props / agents / db / build (results)
- Assumptions / Unverified / Spec changes proposed / Dependencies added / Risks
```

Report failures honestly, with the output. Say what you did not verify.

## 9. Operations that need human approval

`git push --force`, rewriting the history of `main`, deleting other people's branches; deleting files outside the Allowed paths; operations on any database other than the local or test one; any action on remote servers, in Cloudflare, ORS or LLM provider consoles; adding or rotating secrets; changes in `.github/workflows/**`; calls to paid APIs outside `ai-evals` with an agreed budget; publishing anything externally (deploy, release, issues or comments in other repositories, recordings).

Also approved only by the owner: specification status `approved`, golden values, ADRs, changes to `context.md`, migrations, breaking API changes, prompts, model policy, tool allowlists, new runtime dependencies. Commits follow Conventional Commits and name `FEAT-xxx` / `AC-…`.
