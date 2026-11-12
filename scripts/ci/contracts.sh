#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
uv run --project apps/api python scripts/export_openapi.py --check
baseline="$(mktemp)"
trap 'rm -f "$baseline"' EXIT
if git cat-file -e "${CI_BASE_SHA:?}:contracts/openapi.json" 2>/dev/null; then
  git show "$CI_BASE_SHA:contracts/openapi.json" > "$baseline"
  if grep -q '"\$defs"' "$baseline"; then
    # oasdiff v1.37 cannot load a contract with an inline "$defs" (the base on main carried one
    # from a recursive JSON type). Compare normally once the base no longer has it.
    echo 'The base contract contains "$defs", which oasdiff cannot load; skipping the comparison.'
  else
    oasdiff breaking "$baseline" contracts/openapi.json --fail-on WARN --allow-external-refs=false
  fi
else
  echo 'The base branch has no OpenAPI contract; this PR establishes the FEAT-000 baseline.'
fi
if [[ -e apps/web/src/lib/api/schema.d.ts ]]; then
  pnpm --filter web run generate:api
  git diff --exit-code -- apps/web/src/lib/api/schema.d.ts
else
  echo 'TypeScript API generation is not available until FEAT-005/1 (FEAT-000 FR-16).'
fi
bash scripts/ci/api_smoke.sh --contract
