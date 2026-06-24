#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

export PATH="$SCRIPT_DIR/../.wsl-venv/bin:$PATH"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

PORT="${PORT:-7860}"

echo "Mr. Med Daily agent"
echo "  API: POST http://127.0.0.1:${PORT}/start"
echo "  UI:  serve frontend/ (see frontend/README.md)"
echo ""

.wsl-venv/bin/uv run server.py --host 0.0.0.0 --port "${PORT}"
