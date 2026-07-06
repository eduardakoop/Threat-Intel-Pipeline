#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
ENV_FILE="$PROJECT_ROOT/.env.local"

cd "$PROJECT_ROOT"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Missing virtual environment at $VENV_PYTHON"
  echo "Run ./scripts/setup_local_env.sh first."
  exit 1
fi

: "${TA_STORAGE_ROOT:?TA_STORAGE_ROOT is required. Put it in .env.local.}"

TA_WEB_HOST="${TA_WEB_HOST:-0.0.0.0}"
TA_WEB_PORT="${TA_WEB_PORT:-8765}"

echo "Starting TAsAutomation web console..."
echo "Local URL: http://127.0.0.1:${TA_WEB_PORT}"
echo "Team URL: http://$(hostname -I | awk '{print $1}'):${TA_WEB_PORT}"

PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}" \
  "$VENV_PYTHON" -m ta_pipeline.web_ui --host "$TA_WEB_HOST" --port "$TA_WEB_PORT"
