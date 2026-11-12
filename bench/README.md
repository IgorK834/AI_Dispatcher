# Engine benchmark (`fleet_5x60.py`)

Measures the optimisation engine on seeded synthetic instances: 5 drivers, pools of up to 60 offers per driver, the default parameters (5-day horizon). The data comes from the repository generators and is synthetic (`is_synthetic = true`); no database, provider or network call is made.

This benchmark is marked `bench`. It is not part of `make check` or `ci-fast`.

## Run

```bash
make bench
```

It runs 20 times with the fixed seeds `20261116 … 20261135`, prints one JSON line per run and a summary, and writes `bench/results/fleet_5x60.json`.

A single run on fewer seeds, or with the fallback parameters, is available from the command line:

```bash
cd apps/api && uv run python ../../bench/fleet_5x60.py --runs 3
cd apps/api && uv run python ../../bench/fleet_5x60.py --fallback-parameters --out ../../bench/results/fleet_5x60_fallback.json
```

## What is reported

| Field | Meaning |
|---|---|
| `runs[].runtime_ms` | wall-clock time of one `optimize` call |
| `runs[].nodes` | search nodes expanded over all drivers |
| `runs[].truncated`, `runs[].pool_truncated` | whether the node budget or the wall-clock safety stopped the search, or a pool was capped at 60 |
| `summary.p50_ms`, `summary.p95_ms` | median and 95th percentile of the runtimes |
| `summary.nodes_p50`, `summary.nodes_max` | node counts |
| `summary.truncated_runs` | number of truncated runs |
| `summary.target_met`, `summary.target_line` | whether p95 ≤ 15 s (NFR-002); recorded as met or not met, never asserted |

## Target and fallback

The target is p95 ≤ 15 s on a typical laptop. If it is missed, the numbers are reported as they are and the fallback parameters are proposed to the owner: `max_offers_per_plan = 4`, `horizon_days = 3`, `top_k_per_driver = 5` (`--fallback-parameters`). The defaults are never changed silently, and no constraint is relaxed to make a run faster.

The timings depend on the machine, so `bench/results/` holds local measurements; the committed summary lives in `docs/metrics.md` (FEAT-007).
