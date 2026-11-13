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
- the campaign total is 500 000 tokens, split into the `smoke` phase (80 000) and the `evals`
  phase (420 000); a finished phase is not run again without `--retry-phase`.

The `ai-evals` workflow (`.github/workflows/ai-evals.yml`) starts it by hand with the confirmation
text `run-paid-evals`. Do not start it, and do not change prompts to improve a score: a prompt
change is a new prompt version with its own owner approval and its own run.
