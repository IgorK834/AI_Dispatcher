#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
scratch="$(mktemp -d)"
api_pid=''
cleanup() {
  if [[ -n "$api_pid" ]]; then
    pkill -P "$api_pid" 2>/dev/null || true
    kill "$api_pid" 2>/dev/null || true
    wait "$api_pid" 2>/dev/null || true
  fi
  rm -rf "$scratch"
}
trap cleanup EXIT
cd "$root/apps/api"
export APP_ENV=test
export DATABASE_URL="sqlite:///$scratch/smoke.db"
# A free port chosen per run: a fixed port can still be in TIME_WAIT from the previous gate.
port="${API_SMOKE_PORT:-$(uv run python -c "import socket; s = socket.socket(); s.bind(('127.0.0.1', 0)); print(s.getsockname()[1])")}"
uv run alembic upgrade head
uv run uvicorn routepilot.main:app --host 127.0.0.1 --port "$port" > "$scratch/api.log" 2>&1 &
api_pid=$!
ready=false
for attempt in {1..50}; do
  if curl -fsS "http://127.0.0.1:$port/ready" > "$scratch/ready.json"; then
    ready=true
    break
  fi
  if ! kill -0 "$api_pid" 2>/dev/null; then
    cat "$scratch/api.log"
    exit 1
  fi
  sleep 0.2
done
if [[ "$ready" != true ]]; then
  cat "$scratch/api.log"
  exit 1
fi
curl -fsS "http://127.0.0.1:$port/health" > "$scratch/health.json"
curl -fsS -D "$scratch/cors.txt" -o /dev/null -X OPTIONS "http://127.0.0.1:$port/health" \
  -H 'Origin: http://localhost:3000' -H 'Access-Control-Request-Method: GET'
uv run python - "$scratch" <<'PY'
import json
import sys
from pathlib import Path

scratch = Path(sys.argv[1])
if json.loads((scratch / 'health.json').read_text()) != {'status': 'ok'}:
    raise SystemExit('Health response differs from the contract')
if json.loads((scratch / 'ready.json').read_text()) != {'status': 'ready', 'migration': '0001_initial'}:
    raise SystemExit('Readiness response differs from the migration head')
headers = (scratch / 'cors.txt').read_text().lower()
if 'access-control-allow-origin: http://localhost:3000' not in headers or 'access-control-allow-credentials: true' not in headers:
    raise SystemExit('Credentialed CORS preflight failed')
PY
if [[ "${1:-}" == --contract ]]; then
  uv run schemathesis run "$root/contracts/openapi.json" --url "http://127.0.0.1:$port" \
    --phases examples,coverage --checks all
fi
