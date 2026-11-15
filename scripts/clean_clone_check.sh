#!/usr/bin/env bash
# Clean-clone check (FEAT-007 FR-4, AC-FEAT-007-04).
#
# Follows steps 1 and 2 of README section 6 in a fresh clone, with no API key in the environment:
# install, migrate, start the API and the web app, then check /ready, /health, the demo login,
# five drivers in the list and the web login page. It prints the elapsed time and fails when any
# step fails or when the whole run takes more than ten minutes (NFR-014).
#
# The commands below are the commands of the README, line by line; `scripts/check_docs.py --readme`
# fails when a README command is missing here. The one change: the README starts the web app with
# `pnpm dev`, the check serves the production build (`pnpm build` and `pnpm start`).
#
# Usage: scripts/clean_clone_check.sh          clone the repository (its last commit) into a temp folder
#        scripts/clean_clone_check.sh --here   use this checkout (a fresh CI checkout); it copies the
#                                              .env examples, so it refuses to run over an existing .env
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
started="$(date +%s)"
api_pid=''
web_pid=''

kill_tree() {
  local child
  for child in $(pgrep -P "$1" 2>/dev/null || true); do kill_tree "$child"; done
  kill "$1" 2>/dev/null || true
}
cleanup() {
  [[ -n "$api_pid" ]] && kill_tree "$api_pid"
  [[ -n "$web_pid" ]] && kill_tree "$web_pid"
  rm -rf "$tmp"
}
trap cleanup EXIT
fail() { echo "FAIL: $1" >&2; exit 1; }
step() { echo "== $1"; }

# The ports of the README must be free: a server that is already there would answer instead.
for port in 8000 3000; do
  if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
    fail "port $port is in use; stop what is listening there and run the check again"
  fi
done

# No provider or routing key, and none of the settings of this machine, reaches the app.
while IFS='=' read -r key _; do
  [[ "$key" =~ ^[A-Z_]+$ ]] && unset "$key"
done < "$root/apps/api/.env.example"
unset NEXT_PUBLIC_API_BASE_URL

if [[ "${1:-}" == --here ]]; then
  work="$root"
  [[ -e "$work/apps/api/.env" || -e "$work/apps/web/.env.local" ]] \
    && fail "--here would overwrite apps/api/.env or apps/web/.env.local; run without --here"
else
  step "Clone"
  git clone --quiet --local "$root" "$tmp/clone"
  work="$tmp/clone"
fi

step "API"
cd "$work"
cd apps/api
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn routepilot.main:app --reload --port 8000 > "$tmp/api.log" 2>&1 &
api_pid=$!
cd ../..

step "Web"
cd apps/web
cp .env.example .env.local
pnpm install
pnpm build
pnpm start > "$tmp/web.log" 2>&1 &
web_pid=$!
cd ../..

wait_for() {  # URL, pid, log file
  local attempt
  for attempt in $(seq 1 180); do
    curl -fsS -o /dev/null "$1" 2>/dev/null && return 0
    kill -0 "$2" 2>/dev/null || { cat "$3" >&2; fail "the process behind $1 stopped"; }
    sleep 1
  done
  cat "$3" >&2
  fail "$1 did not answer in time"
}
step "Ready, health, login, drivers, web"
wait_for http://localhost:8000/ready "$api_pid" "$tmp/api.log"
curl -fsS http://localhost:8000/health > /dev/null || fail "/health failed"

env_value() { grep "^$1=" "$work/apps/api/.env.example" | cut -d= -f2-; }
body="$(printf '{"email":"%s","password":"%s","captchaToken":"clean-clone-check"}' \
  "$(env_value DEMO_EMAIL)" "$(env_value DEMO_PASSWORD)")"
curl -fsS -c "$tmp/cookies" -H 'Origin: http://localhost:3000' -H 'Content-Type: application/json' \
  -d "$body" http://localhost:8000/api/v1/auth/login > /dev/null || fail "the demo login failed"
drivers="$(curl -fsS -b "$tmp/cookies" http://localhost:8000/api/v1/drivers \
  | python3 -c 'import json, sys; print(len(json.load(sys.stdin)["items"]))')"
[[ "$drivers" == 5 ]] || fail "expected 5 drivers, found $drivers"

wait_for http://localhost:3000/login "$web_pid" "$tmp/web.log"
status="$(curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/login)"
[[ "$status" == 200 ]] || fail "the web login page answered $status"

elapsed=$(( $(date +%s) - started ))
echo "Clean-clone check passed in ${elapsed} s (limit 600 s)."
(( elapsed <= 600 )) || fail "it took ${elapsed} s, more than the 10 minutes of NFR-014"
