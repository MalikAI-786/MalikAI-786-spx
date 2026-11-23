#!/usr/bin/env bash
# install-jarvis-sync.sh — ONE-SHOT macOS installer: Google Drive → Box:Jarvis agent layer.
#   bash <(curl -fsSL https://raw.githubusercontent.com/MalikAI-786/MalikAI-786-spx/claude/gmail-workspace-organization-d9xr53/scripts/jarvis-sync/install-jarvis-sync.sh)
# What it does: Homebrew (if missing) → rclone → writes filter + sync script → Google & Box sign-in (browser opens
# twice) → size preflight → first real sync → launchd job every 6 h. Re-running is safe (idempotent).
set -euo pipefail
say() { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }

say "Jarvis installer v7"
say "1/7  Homebrew"
export HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 HOMEBREW_NO_ENV_HINTS=1
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
SYNC_EOF
chmod +x "$HOME/jarvis-sync/jarvis-sync.sh" || { echo "   ✗ First sync did not succeed — paste the lines above to Claude."; exit 1; }

say "4/7  Google Drive sign-in (browser will open — use yasiramalik@gmail.com)"
# Own Google client ID: run with the word "own" at the end and the installer asks for both values.
if [ "${1:-}" = "own" ] && [ -z "${GDRIVE_CLIENT_ID:-}" ]; then
  echo "   From console.cloud.google.com/auth/clients → your 'rclone' client:"
  read -r -p "   Paste Client ID (ends in .apps.googleusercontent.com): " GDRIVE_CLIENT_ID </dev/tty
  read -r -s -p "   Paste Client secret (hidden as you paste): " GDRIVE_CLIENT_SECRET </dev/tty; echo
fi
GDRIVE_CLIENT_ID="$(printf '%s' "${GDRIVE_CLIENT_ID:-}" | tr -d '[:space:]')"
GDRIVE_CLIENT_SECRET="$(printf '%s' "${GDRIVE_CLIENT_SECRET:-}" | tr -d '[:space:]')"
if [ -n "$GDRIVE_CLIENT_ID" ]; then
  if ! printf '%s' "$GDRIVE_CLIENT_ID" | grep -Eq '^[0-9]+-[A-Za-z0-9_]+\.apps\.googleusercontent\.com$'; then
    echo "   ✗ That Client ID doesn't look right (got: ${GDRIVE_CLIENT_ID:0:24}…). It must look like 1234567890-abc123.apps.googleusercontent.com"; exit 1
  fi
  case "$GDRIVE_CLIENT_SECRET" in
    "") echo "   ✗ Client secret came through EMPTY (0 characters). Copy the GOCSPX-… secret from the rclone client page, then re-run and paste it at the secret prompt."; exit 1;;
    *.apps.googleusercontent.com) echo "   ✗ You pasted the Client ID into the secret field. Copy the Client SECRET (starts with GOCSPX-) and re-run."; exit 1;;
    YOUR-*|PASTE*) echo "   ✗ Client secret is still placeholder text."; exit 1;;
  esac
  echo "   ✓ Client secret received (${#GDRIVE_CLIENT_SECRET} characters, starts with ${GDRIVE_CLIENT_SECRET:0:7})"
  echo "   ✓ Client ID format OK (${GDRIVE_CLIENT_ID:0:12}…)"
fi
pkill -x rclone 2>/dev/null || true                    # stop any stuck rclone run
for p in $(lsof -ti tcp:53682 2>/dev/null); do kill -9 "$p" 2>/dev/null || true; done   # free the sign-in port
sleep 1
if lsof -ti tcp:53682 >/dev/null 2>&1; then echo "   ✗ Port 53682 is still busy: $(lsof -nP -iTCP:53682 -sTCP:LISTEN | tail -1). Close that app and re-run."; exit 1; fi
if [ -n "${GDRIVE_CLIENT_ID:-}" ] || ! rclone lsf gdrive: --max-depth 1 --dirs-only >/dev/null 2>&1; then
  rclone config delete gdrive 2>/dev/null || true
  if [ -n "${GDRIVE_CLIENT_ID:-}" ]; then
    rclone config create gdrive drive scope drive client_id "$GDRIVE_CLIENT_ID" client_secret "${GDRIVE_CLIENT_SECRET:?set GDRIVE_CLIENT_SECRET too}" >/dev/null
  else
    rclone config create gdrive drive scope drive >/dev/null
  fi
fi
if rclone lsf gdrive: --max-depth 1 --dirs-only >/dev/null 2>&1; then echo "   ✓ gdrive connected"
else echo "   ✗ Google Drive login failed. See 'own client ID' in scripts/jarvis-sync/README.md."; exit 1; fi

say "5/7  Box sign-in (browser will open if needed)"
if ! rclone lsf box:Jarvis >/dev/null 2>&1; then
  rclone config delete box 2>/dev/null || true
  rclone config create box box >/dev/null
fi
if rclone lsf box:Jarvis >/dev/null 2>&1; then echo "   ✓ box:Jarvis reachable"; else echo "   ✗ Box login failed."; exit 1; fi

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
