#!/usr/bin/env bash
# [AC-FEAT-000-01] Both projects install from their committed lockfiles.
set -euo pipefail
cd "$(dirname "$0")/../.."
uv sync --project apps/api --locked
pnpm install --frozen-lockfile
