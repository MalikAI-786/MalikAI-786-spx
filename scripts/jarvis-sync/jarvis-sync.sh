#!/usr/bin/env bash
# jarvis-sync.sh — Google Drive (master copy) ──► Box:Jarvis (compact agent layer)
# One-way. Drive is never modified. Documents only. Google Docs/Sheets/Slides
# are exported to docx/xlsx/pptx so Box AI and the agent can read them.
#
#   ./jarvis-sync.sh --dry-run   # preview: what WOULD move, and total size
#   ./jarvis-sync.sh             # do it
set -euo pipefail

FILTER="$HOME/.config/rclone/jarvis-filter.txt"
LOG="$HOME/rclone-jarvis.log"
DRY="${1:-}"

rclone sync gdrive: box:Jarvis $DRY \
  --filter-from "$FILTER" \
  --drive-export-formats docx,xlsx,pptx,pdf \
  --transfers 8 --checkers 16 \
  --log-file "$LOG" --log-level INFO \
  --stats 1m --stats-one-line

echo "✓ finished — log: $LOG"
