.PHONY: check lint types unit test-props test-agents test-db openapi trace e2e bench dev-api dev-web seed-fleet

check: lint types unit

lint:
	cd apps/api && uv run ruff format --config pyproject.toml --check src tests migrations ../../scripts/*.py ../../scripts/tests
	cd apps/api && uv run ruff check --config pyproject.toml src tests migrations ../../scripts/*.py ../../scripts/tests
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
