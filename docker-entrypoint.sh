#!/bin/sh
set -e
PORT="${PORT:-8080}"
exec uv run server.py -t exotel --host 0.0.0.0 --port "$PORT"
