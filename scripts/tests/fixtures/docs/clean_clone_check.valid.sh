#!/usr/bin/env bash
set -euo pipefail
cd apps/api
cp .env.example .env
uv sync
uv run uvicorn routepilot.main:app --reload --port 8000 &
cd ../..
cd apps/web
pnpm install
pnpm build
pnpm start &
