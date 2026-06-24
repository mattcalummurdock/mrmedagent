#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

if [ ! -d .wsl-venv ]; then
  python3 -m venv .wsl-venv
fi

.wsl-venv/bin/pip install -q uv
.wsl-venv/bin/uv sync

echo "WSL dependencies installed. Run: bash scripts/wsl-start.sh"
