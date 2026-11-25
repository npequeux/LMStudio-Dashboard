#!/usr/bin/env sh
set -e

# Works whether this file is at the extraction root or inside companion-metrics-server.
cd "$(dirname "$0")"
if [ -f "companion-metrics-server/pyproject.toml" ]; then
  cd companion-metrics-server
fi

exec uv run uvicorn metrics_server.app:app --host 0.0.0.0 --port 8000 "$@"
