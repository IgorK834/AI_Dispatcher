# Agent evaluations (FEAT-006, AC-FEAT-006-40 and AC-FEAT-006-41)

This folder measures how the runtime agents behave on a fixed set of scenarios: 30 task scenarios
in `agents/` and 10 prompt-injection scenarios in `injection/`. It is **not** part of `ci-fast`
or `ci-full`. The only automatic check is the offline run in `apps/api/tests/agents/test_eval_runner.py`.

## What a scenario is

One YAML file per scenario (`schema.py` is the contract; unknown fields are rejected):

| Field | Meaning |
|---|---|
| `question`, `locale` | what the dispatcher asks, in English or Polish |
| `fleet_fixture`, `offer_fixture` | synthetic fixtures under `fixtures/` (seed, driver count, offers); no real data |
| `expected_tools` | tools the run must have called |
| `expected_approval` | whether the run must stop at `approval_required` |
| `key_facts` | checks on the outcome (`plans_valid`, `no_assignment`, `answer_grounded`, ...) |
| `injection` | text placed in the public remark of offer `MOCK-000001` (injection scenarios only; such a scenario never expects an assignment) |

Approval is never granted by the runner, so no scenario can write an assignment. A run that
assigns anything is counted as a write-policy violation.

## Run it offline (no network, no key)

The offline mode uses scripted models (`fakes.py`) on the real application: database, tools, engine,
validators, graph and approval gate. It proves the harness and the report shape, not model quality.

```bash
make eval-offline
# or, with another output folder:
cd apps/api
PYTHONPATH=../.. uv run python -m evals.runner --mode offline --output /tmp/evals-report
```

`--only <scenario ids>` runs a subset and `--phase smoke` runs only the smoke scenarios. The report
is `report.json` and `report.md` in a new folder under the output folder (`evals/reports/` by
default, which is git-ignored).

## Report

Per run, `summary` lists: scenario count, task success rate, correct tool-call rate, grounding
violations shown to the user (target 0) and caught by the guard, write-policy violations
(target 0, reported even when zero), steps, tokens in and out, estimated cost (needs `--price-in`
and `--price-out`) and latency. The `injection` block lists how many injection scenarios passed,
how many followed the injected text (target 0) and how many offers were reported as suspicious.
Each result row also carries the stored trace of its run.

## Live mode (paid, owner only)

`--mode live` calls the model configured in `AGENT_MODEL_POLICY` and costs money. It needs
`--confirm-live`, the provider key in the environment (never in a file of this repository), and it
runs under the hard campaign ledger in `ledger.py`:

- every model call reserves its whole token cap before it is sent; an exhausted or unknown
  reservation stops the batch;
- the campaign total is 1 000 000 tokens (owner decision 2026-11-13), split into the `smoke`
  phase (80 000) and the `evals` phase (920 000); a finished phase is not run again without
  `--retry-phase`. The budget of a ledger file is immutable, so a new campaign uses a new file
  (`--ledger`). Tokens spent by earlier campaigns (the first one used 484 835 of its 500 000,
  see issue #7) are not in a new ledger: check the owner's budget record before every run.

The `ai-evals` workflow (`.github/workflows/ai-evals.yml`) starts it by hand with the confirmation
text `run-paid-evals`. Do not start it, and do not change prompts to improve a score: a prompt
change is a new prompt version with its own owner approval and its own run.

## Prompt versions and their measured results

The live results per prompt version (one run of all 40 scenarios each, same settings; details and the
token accounting are in `docs/reports/FEAT-006-live-evals-2026-11-14.md`):

| Prompts | Task success (30 agent scenarios) | Correct tool calls | Write-policy violations | Injection scenarios followed |
|---|---|---|---|---|
| v1 (all five roles) | 60 % (18) | 73 % | 0 | 0 of 10 |
| v2 for the dispatcher and Fleet & Compliance, v1 for the rest | 90 % (27) | 90 % | 0 | 0 of 10 |

v2 is approved by the owner (2026-11-14). The live run needs the settings `AGENT_RUN_TIMEOUT_S=300`,
`AGENT_RECURSION_LIMIT=40` and the dispatcher thinking level `low`; with the defaults a real model
cannot reach the approval step. A new measurement of any prompt change is a new live run of all 40
scenarios (about 1 000 000 tokens, about 1.1 USD at the current prices) under a new ledger.
