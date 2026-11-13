#!/usr/bin/env bash
# Gate 8b (FEAT-007): advisory audit and licence check of the runtime dependencies.
# Without an argument it checks the real lockfiles (Python via `uv export --no-dev`, web via pnpm);
# with a pinned requirements file it checks only that file (used by the fixture tests).
set -euo pipefail
cd "$(dirname "$0")/../.."
requirements="${1:-}"
scratch="$(mktemp)"
trap 'rm -f "$scratch"' EXIT
web=""
if [[ -z "$requirements" ]]; then
  uv export --project apps/api --frozen --no-dev --no-emit-project --no-hashes > "$scratch"
  requirements="$scratch"
  web="--pnpm"
fi
# Every check runs, so one failure never hides another; the gate fails if any of them failed.
status=0
uvx --from pip-audit==2.10.1 pip-audit -r "$requirements" --no-deps --disable-pip --progress-spinner off || status=1
uv run --project apps/api python scripts/ci/license_check.py "$requirements" ${web:+"$web"} || status=1
if [[ -n "$web" ]]; then
  pnpm audit --prod --audit-level high || status=1
fi
exit "$status"
