#!/usr/bin/env bash
# jarvis-sync.sh — Google Drive (master / guard copy) ──► Box:Jarvis (compact agent layer)
#   ./jarvis-sync.sh --dry-run   # preview only
#   ./jarvis-sync.sh             # real run
# Guards: one-way only (never writes to Drive); aborts if the filtered set would exceed BOX_BUDGET_GB;
#         skips files over Box's ~250 MB per-file limit; writes a status JSON into Box for the agent to read.
set -uo pipefail
FILTER="$HOME/.config/rclone/jarvis-filter.txt"
LOG="$HOME/jarvis-sync/rclone-jarvis.log"
STATUS="$HOME/jarvis-sync/_sync_status.json"
BOX_BUDGET_GB="${BOX_BUDGET_GB:-9.5}"
DRY="${1:-}"
mkdir -p "$(dirname "$LOG")"
RCLONE="$(command -v rclone || echo /opt/homebrew/bin/rclone)"

started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "[$started] jarvis-sync start ${DRY}" >> "$LOG"

# 1. Size guard — how big is the documents-only slice of Drive?
size_json="$("$RCLONE" size gdrive: --filter-from "$FILTER" --json 2>>"$LOG" || echo '{"bytes":0,"count":0}')"
bytes="$(echo "$size_json" | sed -E 's/.*"bytes":([0-9]+).*/\1/')"
count="$(echo "$size_json" | sed -E 's/.*"count":([0-9]+).*/\1/')"
gb="$(awk -v b="$bytes" 'BEGIN{printf "%.2f", b/1024/1024/1024}')"
echo "filtered set: $count files, ${gb} GB (budget ${BOX_BUDGET_GB} GB)" | tee -a "$LOG"
if awk -v g="$gb" -v m="$BOX_BUDGET_GB" 'BEGIN{exit !(g>m)}'; then
  echo "ABORT: ${gb} GB exceeds Box budget ${BOX_BUDGET_GB} GB — tighten jarvis-filter.txt or upgrade Box." | tee -a "$LOG"
  result="aborted_over_budget"
else
  # 2. The sync itself
  "$RCLONE" sync gdrive: box:Jarvis $DRY \
    --filter-from "$FILTER" \
    --exclude "/_Agent_Output/**" --exclude "/README*" \
    --drive-export-formats docx,xlsx,pptx,pdf \
    --max-size 240M \
    --transfers 8 --checkers 16 \
    --log-file "$LOG" --log-level INFO \
    --stats 1m --stats-one-line
  rc=$?
  result=$([ $rc -eq 0 ] && echo "ok" || echo "rclone_exit_$rc")
fi

# 3. Status file → Box so the agent can verify without asking you
finished="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
cat > "$STATUS" <<EOF
{"result":"$result","dry_run":"${DRY:-false}","started":"$started","finished":"$finished",
 "files_in_scope":$count,"size_gb":$gb,"budget_gb":$BOX_BUDGET_GB,"host":"$(hostname)"}
EOF
[ -z "$DRY" ] && "$RCLONE" copyto "$STATUS" box:Jarvis/_Agent_Output/_sync_status.json --log-file "$LOG" --log-level ERROR
echo "[$finished] jarvis-sync $result — log: $LOG" | tee -a "$LOG"
