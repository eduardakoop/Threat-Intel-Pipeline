#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RUN_SCRIPT="$PROJECT_ROOT/scripts/run_full_pipeline.sh"
LOG_DIR="$PROJECT_ROOT/logs"
CRON_LOG="$LOG_DIR/cron_weekly_pipeline.log"

CRON_START="# BEGIN TAsAutomation weekly pipeline"
CRON_END="# END TAsAutomation weekly pipeline"

if [[ ! -x "$RUN_SCRIPT" ]]; then
  echo "Pipeline script is not executable: $RUN_SCRIPT"
  exit 1
fi

mkdir -p "$LOG_DIR"

current_cron="$(crontab -l 2>/dev/null || true)"

managed_block="$(cat <<EOF
$CRON_START
CRON_TZ=America/New_York
0 22 * * 0 cd "$PROJECT_ROOT" && "$RUN_SCRIPT" >> "$CRON_LOG" 2>&1
$CRON_END
EOF
)"

new_cron="$(
  printf '%s\n' "$current_cron" | awk \
    -v start="$CRON_START" \
    -v end="$CRON_END" '
      $0 == start {skip = 1; next}
      $0 == end {skip = 0; next}
      !skip {print}
    '
  printf '\n%s\n' "$managed_block"
)"

printf '%s\n' "$new_cron" | sed '/^[[:space:]]*$/N;/^\n$/D' | crontab -

echo "Installed weekly TAsAutomation cron job:"
echo "  Sunday at 10:00 PM America/New_York"
echo "  $RUN_SCRIPT"
echo "  Cron log: $CRON_LOG"
