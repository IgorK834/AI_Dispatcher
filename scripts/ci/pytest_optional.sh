#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../apps/api"
set +e
uv run pytest "$@"
result=$?
set -e
# FEAT-000 FR-16: only an empty collection passes during foundation setup.
# Assertion, import and configuration failures retain their nonzero status.
if [[ "$result" == 5 ]]; then
  echo "No tests collected yet (FEAT-000 FR-16)."
  exit 0
fi
exit "$result"
