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

# 0. Auth check — both remotes must answer, or stop (never sync on a broken login)
pkill -f "rclone size gdrive:" 2>/dev/null || true
auth_fail=""
"$RCLONE" lsf gdrive: --max-depth 1 --dirs-only >/dev/null 2>>"$LOG" || auth_fail="gdrive"
"$RCLONE" lsf box:Jarvis --max-depth 1 >/dev/null 2>>"$LOG" || auth_fail="${auth_fail:+$auth_fail+}box"

# 1. Size guard — how big is the documents-only slice of Drive?
bytes=0; count=0; gb="0.00"; size_ok=0
if [ -z "$auth_fail" ] && size_json="$("$RCLONE" size gdrive: --filter-from "$FILTER" --json 2>>"$LOG")"; then
  bytes="$(echo "$size_json" | sed -E 's/.*"bytes":([0-9]+).*/\1/')"
  count="$(echo "$size_json" | sed -E 's/.*"count":([0-9]+).*/\1/')"
  gb="$(awk -v b="$bytes" 'BEGIN{printf "%.2f", b/1024/1024/1024}')"
  size_ok=1
  echo "filtered set: $count files, ${gb} GB (budget ${BOX_BUDGET_GB} GB)" | tee -a "$LOG"
fi
if [ -n "$auth_fail" ]; then
  echo "ABORT: login failed for: $auth_fail — run: rclone config reconnect ${auth_fail%%+*}:" | tee -a "$LOG"
  result="auth_failed_$auth_fail"
elif [ "$size_ok" -ne 1 ]; then
  echo "ABORT: could not measure Drive (see log) — nothing synced." | tee -a "$LOG"
  result="size_check_failed"
elif awk -v g="$gb" -v m="$BOX_BUDGET_GB" 'BEGIN{exit !(g>m)}'; then
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
if [ -z "$DRY" ] && [[ "$auth_fail" != *box* ]]; then
  "$RCLONE" copyto "$STATUS" box:Jarvis/_Agent_Output/_sync_status.json --log-file "$LOG" --log-level ERROR || true
fi
echo "[$finished] jarvis-sync $result — log: $LOG" | tee -a "$LOG"
[ "$result" = "ok" ]
