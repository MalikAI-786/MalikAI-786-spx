#!/usr/bin/env bash
# jarvis-sync.sh v7 — Google Drive (master / guard copy) ──► Box:Jarvis (compact agent layer)
#   ./jarvis-sync.sh --dry-run   # preview only
#   ./jarvis-sync.sh             # real run
# Guards: one-way only (never writes to Drive) · one run at a time (lock) · hard cap on bytes sent to Box
#         (Box free space, max BOX_BUDGET_GB) · skips files > 240 MB (Box free-tier limit) · status JSON to Box.
set -uo pipefail
FILTER="$HOME/.config/rclone/jarvis-filter.txt"
DIR="$HOME/jarvis-sync"; LOG="$DIR/rclone-jarvis.log"; STATUS="$DIR/_sync_status.json"; LOCK="$DIR/.lock"
BOX_BUDGET_GB="${BOX_BUDGET_GB:-9.5}"
DRY="${1:-}"
mkdir -p "$DIR"
RCLONE="$(command -v rclone || echo /opt/homebrew/bin/rclone)"

# 0. One run at a time — a second copy exits instead of disturbing the first
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -f "$LOCK/pid" ] && kill -0 "$(cat "$LOCK/pid")" 2>/dev/null; then
    echo "jarvis-sync already running (pid $(cat "$LOCK/pid")) — leaving it alone." | tee -a "$LOG"; exit 0
  fi
  rm -rf "$LOCK"; mkdir "$LOCK"                       # stale lock from a crashed run
fi
echo $$ > "$LOCK/pid"; trap 'rm -rf "$LOCK"' EXIT

started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "[$started] jarvis-sync v7 start ${DRY}" | tee -a "$LOG"

# 1. Auth check — both remotes must answer
auth_fail=""
"$RCLONE" lsf gdrive: --max-depth 1 --dirs-only >/dev/null 2>>"$LOG" || auth_fail="gdrive"
"$RCLONE" lsf box:Jarvis --max-depth 1 >/dev/null 2>>"$LOG" || auth_fail="${auth_fail:+$auth_fail+}box"

# 2. Budget = Box free space (minus 0.5 GB headroom), never more than BOX_BUDGET_GB
budget_gb="$BOX_BUDGET_GB"
free_bytes="$("$RCLONE" about box: --json 2>/dev/null | sed -nE 's/.*"free": *([0-9]+).*/\1/p')"
if [ -n "$free_bytes" ]; then
  budget_gb="$(awk -v f="$free_bytes" -v m="$BOX_BUDGET_GB" 'BEGIN{g=f/1073741824-0.5; if(g>m)g=m; if(g<0)g=0; printf "%.2f", g}')"
fi
budget_mb="$(awk -v g="$budget_gb" 'BEGIN{printf "%d", g*1024}')"

if [ -n "$auth_fail" ]; then
  echo "ABORT: login failed for: $auth_fail — run: rclone config reconnect ${auth_fail%%+*}:" | tee -a "$LOG"
  result="auth_failed_$auth_fail"
elif [ "$budget_mb" -le 0 ]; then
  echo "ABORT: Box is full — free space before syncing more." | tee -a "$LOG"; result="box_full"
else
  echo "budget: up to ${budget_gb} GB this run · progress line every minute in $LOG" | tee -a "$LOG"
  # 3. The sync — single pass; stops cleanly when the budget is reached
  "$RCLONE" sync gdrive: box:Jarvis $DRY \
    --filter-from "$FILTER" \
    --exclude "/_Agent_Output/**" --exclude "/README*" \
    --drive-export-formats docx,xlsx,pptx,pdf \
    --drive-skip-shortcuts --drive-skip-dangling-shortcuts \
    --max-size 240M --max-transfer "${budget_mb}M" --cutoff-mode soft \
    --transfers 6 --checkers 12 \
    --log-file "$LOG" --log-level INFO \
    --stats 1m --stats-one-line --stats-log-level NOTICE
  rc=$?
  case $rc in
    0) result="ok" ;;
    8) result="budget_reached"; echo "Box budget (${budget_gb} GB) reached — partial sync kept; tighten the filter or upgrade Box for the rest." | tee -a "$LOG" ;;
    *) result="rclone_exit_$rc"; echo "Sync ended with errors — last lines:" | tee -a "$LOG"; grep -E "ERROR|CRITICAL" "$LOG" | tail -5 ;;
  esac
fi

# 4. Status file → Box so the agent can verify without asking you
finished="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
summary="$("$RCLONE" size box:Jarvis --json 2>/dev/null || echo '{}')"
cat > "$STATUS" <<JSON
{"result":"$result","dry_run":"${DRY:-false}","started":"$started","finished":"$finished",
 "budget_gb":$budget_gb,"box_jarvis":$summary,"host":"$(hostname)"}
JSON
if [ -z "$DRY" ] && [[ "$auth_fail" != *box* ]]; then
  "$RCLONE" copyto "$STATUS" box:Jarvis/_Agent_Output/_sync_status.json --log-file "$LOG" --log-level ERROR || true
fi
echo "[$finished] jarvis-sync $result — log: $LOG" | tee -a "$LOG"
case "$result" in ok|budget_reached) exit 0;; *) exit 1;; esac
