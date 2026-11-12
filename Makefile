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

# Paid provider calls under the hard campaign ledger (O-6 smoke 80 000, O-7 batch 420 000 tokens).
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
	@echo "not available until FEAT-003"

dev-api:
	cd apps/api && uv run uvicorn routepilot.main:app --reload --port 8000

dev-web:
	pnpm --filter web dev

seed-fleet:
	@echo "not available until FEAT-002"
