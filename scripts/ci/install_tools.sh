#!/usr/bin/env bash
set -euo pipefail
destination="${RUNNER_TEMP:?}/routepilot-tools"
mkdir -p "$destination"
# Digests verified against the official release assets on 2026-11-11.
curl -fsSL https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz -o "$destination/gitleaks.tar.gz"
echo "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb  $destination/gitleaks.tar.gz" | sha256sum --check
tar -xzf "$destination/gitleaks.tar.gz" -C "$destination" gitleaks
curl -fsSL https://github.com/oasdiff/oasdiff/releases/download/v1.37.0/oasdiff_1.37.0_linux_amd64.tar.gz -o "$destination/oasdiff.tar.gz"
echo "eac87307d31d08c36800c58a409c247f1c5db37fbb72e2544402f22a87cbca3c  $destination/oasdiff.tar.gz" | sha256sum --check
tar -xzf "$destination/oasdiff.tar.gz" -C "$destination" oasdiff
echo "$destination" >> "${GITHUB_PATH:?}"
