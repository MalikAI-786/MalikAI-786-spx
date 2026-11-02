# Jarvis sync — Google Drive (master) → Box:Jarvis (compact agent layer)

Google Drive stays the guard / full-fidelity copy. Box holds a documents-only
mirror that the agent ("Jarvis") reads through the Box connector. One-way sync,
never deletes from Drive.

Files:
- `jarvis-filter.txt` — rclone filter (what goes to Box). First match wins.
- `jarvis-sync.sh`    — the sync command. `--dry-run` first.

Box landing folder: `Jarvis` (id 433327612667). Agent writes go to
`Jarvis/_Agent_Output/` only — anything else under `Jarvis/` is overwritten by sync.

One-time setup (Mac):
```bash
brew install rclone
rclone config          # n → gdrive → "drive" → scope 1 (full) → auto-config → y
rclone config          # n → box    → "box"   → auto-config → y
mkdir -p ~/.config/rclone && cp jarvis-filter.txt ~/.config/rclone/
chmod +x jarvis-sync.sh
./jarvis-sync.sh --dry-run     # read ~/rclone-jarvis.log
./jarvis-sync.sh               # real run
```
Fully automated install (one command, Mac):
`bash <(curl -fsSL https://raw.githubusercontent.com/MalikAI-786/MalikAI-786-spx/claude/gmail-workspace-organization-d9xr53/scripts/jarvis-sync/install-jarvis-sync.sh)`
