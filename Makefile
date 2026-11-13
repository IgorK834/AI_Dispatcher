.PHONY: check lint types unit test-props test-agents test-db openapi trace e2e bench dev-api dev-web seed-fleet eval-offline eval-smoke eval-live

check: lint types unit

lint:
	cd apps/api && uv run ruff format --config pyproject.toml --check src tests migrations ../../scripts/*.py ../../scripts/tests ../../evals
	cd apps/api && uv run ruff check --config pyproject.toml src tests migrations ../../scripts/*.py ../../scripts/tests ../../evals
	pnpm format:check
	pnpm --filter web lint
	cd apps/api && uv run lint-imports

types:
	cd apps/api && uv run mypy --strict src/routepilot
	pnpm --filter web typecheck

unit:
	cd apps/api && uv run pytest tests ../../scripts/tests
	pnpm --filter web test

test-db:
	cd apps/api && uv run pytest tests/db

test-props:
	@echo "not available until FEAT-003"

test-agents:
	bash scripts/ci/pytest_optional.sh tests/agents -q

# Scripted model on the real application flow; never calls a provider.
eval-offline:
	cd apps/api && PYTHONPATH=../.. uv run python -m evals.runner --mode offline --phase evals

# Paid provider calls under the hard campaign ledger (smoke 80 000, evals 920 000 tokens; campaign of 2026-11-13).
# Needs the local apps/api/.env; each phase may be attempted once per ledger.
eval-smoke:
	cd apps/api && PYTHONPATH=../.. uv run python -m evals.runner --mode live --phase smoke --confirm-live $(EVAL_ARGS)

eval-live:
	cd apps/api && PYTHONPATH=../.. uv run python -m evals.runner --mode live --phase evals --confirm-live $(EVAL_ARGS)

openapi:
	cd apps/api && uv run python ../../scripts/export_openapi.py

trace:
	cd apps/api && uv run python ../../scripts/trace.py --check

e2e:
	@echo "not available until FEAT-007"

bench:
	cd apps/api && uv run pytest -c pyproject.toml -m bench ../../bench/fleet_5x60.py -q -s

dev-api:
	cd apps/api && uv run uvicorn routepilot.main:app --reload --port 8000

dev-web:
	pnpm --filter web dev

# Regenerates the committed demo data; the defaults reproduce the files in data/mock/ byte for byte.
SEED ?= 20261109
REFERENCE_DATE ?= 2026-11-16
FLEET_OUT ?= ../../data/mock/fleet.json
OFFERS_OUT ?= ../../data/mock/offers.timocom.json
ENRICHMENT_OUT ?= ../../data/mock/offers.enrichment.json

seed-fleet:
	cd apps/api && uv run python -m routepilot.fleet.generator --seed $(SEED) --reference-date $(REFERENCE_DATE) --out $(FLEET_OUT)
	cd apps/api && uv run python -m routepilot.freight.generator --seed $(SEED) --reference-date $(REFERENCE_DATE) --out $(OFFERS_OUT) --enrichment-out $(ENRICHMENT_OUT)
