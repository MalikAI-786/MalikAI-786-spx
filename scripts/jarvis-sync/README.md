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

## Fix for Google "401 Invalid Credentials" (rclone shared client ID retired)
1. https://console.cloud.google.com → create project `jarvis-sync`.
2. APIs & Services → Library → enable **Google Drive API**.
3. OAuth consent screen → External → app name `jarvis-sync`, your email → add yourself under **Test users** → then **Publish app** (otherwise tokens expire every 7 days).
4. Credentials → Create credentials → OAuth client ID → **Desktop app** → copy Client ID + Client secret.
5. Re-run the installer with them:
   `GDRIVE_CLIENT_ID='…' GDRIVE_CLIENT_SECRET='…' bash <(curl -fsSL https://raw.githubusercontent.com/MalikAI-786/MalikAI-786-spx/claude/gmail-workspace-organization-d9xr53/scripts/jarvis-sync/install-jarvis-sync.sh)`
   At the "Google hasn't verified this app" screen: Advanced → Go to jarvis-sync → Allow.
