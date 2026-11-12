# Report: FEAT-003 / slice 8 (issue #36)

- Status: partial — the import contracts are done; the benchmark target (NFR-002, p95 ≤ 15 s) is **not met**.
- Date of the measurements: 2026-11-12, one laptop (Darwin, arm64, Python 3.13.3).
- Scope: FEAT-003 revision 1 (AC-28, AC-29). Branch `test/FEAT-003-purity-bench`.

## Changes

- `apps/api/pyproject.toml`: contract "oracles are test-only" (`oracle.py` and `fleet_oracle.py` are imported by no module of `src`); pytest marker `bench`.
- `apps/api/tests/unit/test_import_contracts.py`: tests for the engine and compliance purity contracts, the oracle contract and its source list, `lint-imports` passing, and deliberate oracle imports being rejected.
- `bench/fleet_5x60.py`: a `bench`-marked pytest entry that runs the 20 fixed seeds, writes `bench/results/fleet_5x60.json` and records whether p95 ≤ 15 s; `bench/README.md`.
- `Makefile`: `make bench` runs the marked benchmark with the project's pytest configuration.

## Acceptance criteria

| AC | Evidence |
|---|---|
| AC-FEAT-003-28 | `test_engine_and_compliance_purity_contracts_forbid_io_modules`, `test_oracles_are_test_only_contract_is_present`, `test_lint_imports_passes_on_the_real_package`, `test_importing_an_oracle_from_src_is_rejected` |
| AC-FEAT-003-29 | `bench/fleet_5x60.py::test_fleet_5x60` (marker `bench`, not part of `ci-fast`) |

## Gates run

- `make check` — green (519 API tests, 2 web tests).
- `lint-imports` — 31 contracts kept, 0 broken.
- `make trace` — 0 errors.
- `make bench` — 20 seeded runs completed (about 35 minutes).
- `make test-props` — not run: the target is still a stub.

## Benchmark result (NFR-002, target p95 ≤ 15 s): NOT MET

5 drivers, pools capped at 60 offers per driver, 20 fixed seeds.

| Parameters | p50 | p95 | Truncated runs | Median nodes | Max nodes |
|---|---|---|---|---|---|
| Defaults (`horizon_days=5`, `max_offers_per_plan=6`, `top_k_per_driver=10`) | 108.2 s | 150.4 s | 17 of 20 | 127,349 | 227,722 |
| Fallback (`horizon_days=3`, `max_offers_per_plan=4`, `top_k_per_driver=5`) | 19.2 s | 80.2 s | 2 of 20 | 21,993 | 173,463 |

- Every default run stopped at the 30 s per-driver wall-clock safety (`wall_clock_safety_s`) or at the pool cap, not at the node budget: the largest run used 227,722 of the 1,500,000 nodes allowed per driver.
- The fallback parameters of report §18.3 cut the median by about a factor of five but still miss the target.
- Defaults are unchanged, no constraint was relaxed and nothing was tuned.
- The per-run JSON files in `bench/results/` are machine-specific and are not committed.

## Assumptions / Unverified / Risks

- The timings come from one machine and one session; a different laptop will differ. The target says "typical laptop".
- The truncated runs return valid plans, but their fleet profit is not guaranteed optimal (invariant 15 is checked only when `truncated = false`).

## Decisions needed from the owner

1. Accept "not met" for the MVP and ship the fallback parameters as the defaults, or open a performance slice (label dominance, P1, is out of scope for slice 8).
2. Whether `bench/results/` belongs in git or only the summary in `docs/metrics.md` (007/5).
