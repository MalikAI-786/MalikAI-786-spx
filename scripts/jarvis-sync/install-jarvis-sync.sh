#!/usr/bin/env bash
# install-jarvis-sync.sh — ONE-SHOT macOS installer: Google Drive → Box:Jarvis agent layer.
#   bash <(curl -fsSL https://raw.githubusercontent.com/MalikAI-786/MalikAI-786-spx/claude/gmail-workspace-organization-d9xr53/scripts/jarvis-sync/install-jarvis-sync.sh)
# What it does: Homebrew (if missing) → rclone → writes filter + sync script → Google & Box sign-in (browser opens
# twice) → size preflight → first real sync → launchd job every 6 h. Re-running is safe (idempotent).
set -euo pipefail
say() { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }

say "1/7  Homebrew"
if ! command -v brew >/dev/null 2>&1; then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"

say "2/7  rclone"
command -v rclone >/dev/null 2>&1 || brew install rclone

say "3/7  Writing filter + sync script"
mkdir -p "$HOME/.config/rclone" "$HOME/jarvis-sync"
cat > "$HOME/.config/rclone/jarvis-filter.txt" <<'FILTER_EOF'
# jarvis-filter.txt  —  rclone reads top-down, FIRST match wins.
# Save to: ~/.config/rclone/jarvis-filter.txt

# ── 1. Never send these to the agent layer (media / internal / junk) ──
- /08_Photos_Media/**
- /15_Google_Workspace/**
- /16_Archives/**
- /17_Existing_Folders/**
- /_To_Be_Deleted*/**
- /To Be Deleted/**
- **/.git/**
- **/node_modules/**
- **/whatsapp_*/**
- **/.DS_Store
- **/Thumbs.db

# ── 2. Documents the agent can actually read ──
+ *.pdf
+ *.docx
+ *.doc
+ *.xlsx
+ *.xls
+ *.csv
+ *.pptx
+ *.ppt
+ *.txt
+ *.md
+ *.rtf
+ *.json

# ── 3. Everything else (photos, video, audio, zips) stays in Drive ONLY ──
- *
FILTER_EOF
cat > "$HOME/jarvis-sync/jarvis-sync.sh" <<'SYNC_EOF'
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
SYNC_EOF
chmod +x "$HOME/jarvis-sync/jarvis-sync.sh" || { echo "   ✗ First sync did not succeed — paste the lines above to Claude."; exit 1; }

say "4/7  Google Drive sign-in (browser will open — use yasiramalik@gmail.com)"
# Your own Google client ID (rclone's shared one is being shut off in 2026 and returns 401).
# Pass it as: GDRIVE_CLIENT_ID=... GDRIVE_CLIENT_SECRET=... bash <(curl ...)
if [ -n "${GDRIVE_CLIENT_ID:-}" ] || ! rclone lsf gdrive: --max-depth 1 --dirs-only >/dev/null 2>&1; then
  pkill -f "rclone size gdrive:" 2>/dev/null || true
  rclone config delete gdrive 2>/dev/null || true
  if [ -n "${GDRIVE_CLIENT_ID:-}" ]; then
    rclone config create gdrive drive scope drive client_id "$GDRIVE_CLIENT_ID" client_secret "${GDRIVE_CLIENT_SECRET:?set GDRIVE_CLIENT_SECRET too}"
  else
    rclone config create gdrive drive scope drive
  fi
fi
if rclone lsf gdrive: --max-depth 1 --dirs-only >/dev/null; then echo "   ✓ gdrive connected"
else echo "   ✗ Google Drive login failed (401). Create your own client ID — see scripts/jarvis-sync/README.md — then re-run with GDRIVE_CLIENT_ID/GDRIVE_CLIENT_SECRET."; exit 1; fi

say "5/7  Box sign-in (browser will open)"
if ! rclone listremotes | grep -q '^box:$'; then
  rclone config create box box
fi
if rclone lsf box:Jarvis >/dev/null; then echo "   ✓ box:Jarvis reachable"; else echo "   ✗ Box login failed — run: rclone config reconnect box:"; exit 1; fi

say "6/7  Preflight + first sync (documents only; Drive is never modified)"
"$HOME/jarvis-sync/jarvis-sync.sh"

say "7/7  Scheduling every 6 hours (launchd, survives reboot/sleep)"
PLIST="$HOME/Library/LaunchAgents/com.malik.jarvis-sync.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.malik.jarvis-sync</string>
  <key>ProgramArguments</key><array><string>$HOME/jarvis-sync/jarvis-sync.sh</string></array>
  <key>StartInterval</key><integer>21600</integer>
  <key>RunAtLoad</key><false/>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
  <key>StandardOutPath</key><string>$HOME/jarvis-sync/launchd.out</string>
  <key>StandardErrorPath</key><string>$HOME/jarvis-sync/launchd.err</string>
</dict></plist>
PLIST_EOF
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "   ✓ launchd job loaded"

say "DONE. Status written to Box → Jarvis/_Agent_Output/_sync_status.json. Tell Claude 'check jarvis sync' to verify."
echo "   Log: $HOME/jarvis-sync/rclone-jarvis.log"
