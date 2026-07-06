#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
ENV_FILE="$PROJECT_ROOT/.env.local"
LOG_DIR="$PROJECT_ROOT/logs"
LOCK_FILE="$PROJECT_ROOT/.pipeline.lock"

cd "$PROJECT_ROOT"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Missing virtual environment at $VENV_PYTHON"
  echo "Create it first or reinstall the local environment."
  exit 1
fi

: "${TA_STORAGE_ROOT:?TA_STORAGE_ROOT is required. Put it in .env.local.}"

if [[ "${TA_EXPAND_FEED_TOPICS_WITH_SERPER:-false}" =~ ^(1|true|yes|on)$ ]]; then
  : "${SERPER_API_KEY:?SERPER_API_KEY is required when TA_EXPAND_FEED_TOPICS_WITH_SERPER is enabled. Put it in .env.local.}"
fi

mkdir -p "$LOG_DIR"
mkdir -p "$TA_STORAGE_ROOT"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "Another TA pipeline run is already active. Skipping this run."
  exit 0
fi

LOG_FILE="$LOG_DIR/run_$(date -u +%Y%m%dT%H%M%SZ).log"

echo "Running full TA pipeline..."
echo "Logs: $LOG_FILE"

PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}" \
  "$VENV_PYTHON" -m ta_pipeline --mode full --print-config | tee "$LOG_FILE"
