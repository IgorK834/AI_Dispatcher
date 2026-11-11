#!/usr/bin/env bash
set -euo pipefail
files=()
for file in "$@"; do
  files+=("$PWD/$file")
done
pnpm --filter web exec eslint --max-warnings=0 "${files[@]}"
