# GitHub Setup — MalikAI-786 SPX v5.0

Step-by-step for taking the local repos produced by `bootstrap.sh` and getting
them live on github.com under the **malikai-786** account.

> **All commands assume macOS.** Replace `~` with `$HOME` if your shell strips it.

---

## 0. Pre-requisites (one-time)

### 0.1 Install Homebrew (skip if present)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 0.2 Install the GitHub CLI

```bash
brew install gh
gh --version          # confirm
```

### 0.3 Authenticate gh

```bash
gh auth login
#  ? What account? → GitHub.com
#  ? Protocol?     → SSH
#  ? Upload SSH?   → Yes (gh will create one if needed)
#  ? Login method? → Login with a web browser
#  → paste the one-time code shown
```

Confirm:

```bash
gh auth status
# Should report: Logged in to github.com as malikai-786 (keyring)
```

### 0.4 Generate / register SSH key (only if `gh auth` did not do it)

```bash
ssh-keygen -t ed25519 -C "yasiramalik@gmail.com" -f ~/.ssh/id_ed25519_malikai
eval "$(ssh-agent -s)"
ssh-add --apple-use-keychain ~/.ssh/id_ed25519_malikai
gh ssh-key add ~/.ssh/id_ed25519_malikai.pub --title "MacBook — MalikAI"
ssh -T git@github.com    # expect: "Hi malikai-786! You've successfully authenticated"
```

---

## 1. Create the two GitHub repos

```bash
gh repo create malikai-786/MalikAI-786-spx \
    --public \
    --description "SPX 0DTE morning-bias + EOD monitor — educational, not investment advice"

gh repo create malikai-786/malikai-spx-dashboard \
    --public \
    --description "Public dashboard for MalikAI-786 SPX — github.io rendering"
```

Both will be empty repos with no default branch yet.

---

## 2. Run the bootstrap

From wherever you cloned/downloaded the v5 tree:

```bash
cd /path/to/spx/v5/deploy
chmod +x bootstrap.sh
./bootstrap.sh "$HOME"
```

This produces:
- `~/Documents/MalikAI-786-spx/` — commit ready, origin pointed at GitHub
- `~/Documents/malikai-spx-dashboard/` — commit ready, origin pointed at GitHub

---

## 3. Push

```bash
cd ~/Documents/MalikAI-786-spx
git push -u origin main

cd ~/Documents/malikai-spx-dashboard
git push -u origin main
```

If the first push asks about a host key for `github.com`, accept it (`yes`).

---

## 4. Enable GitHub Pages on the dashboard repo

UI route (recommended, takes 20 seconds):

1. Go to https://github.com/malikai-786/malikai-spx-dashboard/settings/pages
2. **Source**: Deploy from a branch
3. **Branch**: `main`  →  `/ (root)`
4. Click **Save**.
5. After ~60 seconds, Pages will publish at:
   **https://malikai-786.github.io/malikai-spx-dashboard/**

CLI alternative (requires the `pages` extension):

```bash
gh extension install actions/gh-actions-cache  # if not already
gh api -X POST /repos/malikai-786/malikai-spx-dashboard/pages \
  -f source.branch=main -f source.path=/
```

---

## 5. Set up the cross-repo deploy key

The SPX repo runs a daily workflow that needs to **push** to the dashboard repo.
Use a **deploy key** (preferred over PAT — scoped to one repo, revocable, no expiry).

### 5.1 Generate a dedicated keypair

```bash
ssh-keygen -t ed25519 -C "spx-dashboard-deploy" -f ~/.ssh/spx_dashboard_deploy -N ""
```

Two files are created:
- `~/.ssh/spx_dashboard_deploy` — private (will go into SPX repo secrets)
- `~/.ssh/spx_dashboard_deploy.pub` — public (will go into dashboard deploy keys)

### 5.2 Add public key to dashboard repo

```bash
gh repo deploy-key add ~/.ssh/spx_dashboard_deploy.pub \
    --repo malikai-786/malikai-spx-dashboard \
    --title "spx-sync (write)" \
    --allow-write
```

### 5.3 Add private key as a secret in the SPX repo

```bash
gh secret set DASHBOARD_DEPLOY_KEY \
    --repo malikai-786/MalikAI-786-spx \
    < ~/.ssh/spx_dashboard_deploy
```

Confirm:

```bash
gh secret list --repo malikai-786/MalikAI-786-spx
# DASHBOARD_DEPLOY_KEY    Updated 2026-...
```

### 5.4 (Optional, for safety) Remove the private key from disk

```bash
shred -u ~/.ssh/spx_dashboard_deploy
# or on macOS:
rm -P ~/.ssh/spx_dashboard_deploy
```

The pubkey can stay; it's already on github.

---

## 6. Verify the sync workflow

The SPX repo ships with `.github/workflows/sync-dashboard.yml` (see below for
the full file as deployed). To trigger it once manually:

```bash
gh workflow run sync-dashboard.yml --repo malikai-786/MalikAI-786-spx
gh run watch --repo malikai-786/MalikAI-786-spx
```

Expected end state: a new commit on `malikai-786/malikai-spx-dashboard`
authored by **github-actions[bot]** updating `data/*.json`.

---

## 7. Workflow file (already committed to SPX repo)

For reference, this is what `bootstrap.sh` deposits at
`MalikAI-786-spx/.github/workflows/sync-dashboard.yml`:

```yaml
name: sync-dashboard

on:
  push:
    branches: [main]
    paths:
      - 'dashboard/data/**'
      - 'SPX-Reports/**'
  schedule:
    # 9:35 AM ET = 13:35 UTC (winter) / 14:35 UTC (summer DST handled below)
    - cron: '35 13 * * 1-5'
    # 4:20 PM ET = 20:20 UTC (winter) / 21:20 UTC (summer DST handled below)
    - cron: '20 20 * * 1-5'
  workflow_dispatch:

concurrency:
  group: sync-dashboard
  cancel-in-progress: false

jobs:
  sync:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - name: Checkout SPX repo
        uses: actions/checkout@v4
        with:
          path: spx

      - name: Set up SSH deploy key for dashboard repo
        env:
          DEPLOY_KEY: ${{ secrets.DASHBOARD_DEPLOY_KEY }}
        run: |
          mkdir -p ~/.ssh
          echo "$DEPLOY_KEY" > ~/.ssh/id_deploy
          chmod 600 ~/.ssh/id_deploy
          ssh-keyscan github.com >> ~/.ssh/known_hosts 2>/dev/null
          cat > ~/.ssh/config <<EOF
          Host github.com
            IdentityFile ~/.ssh/id_deploy
            StrictHostKeyChecking yes
          EOF

      - name: Checkout dashboard repo via SSH
        run: |
          GIT_SSH_COMMAND="ssh -i ~/.ssh/id_deploy" \
            git clone git@github.com:malikai-786/malikai-spx-dashboard.git dashboard

      - name: Copy data files
        run: |
          mkdir -p dashboard/data
          if [ -d spx/dashboard/data ]; then
            cp -R spx/dashboard/data/. dashboard/data/
          fi

      - name: Commit & push to dashboard
        working-directory: dashboard
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          if git diff --quiet; then
            echo "No data changes to sync."
            exit 0
          fi
          git add -A
          git commit -m "chore(data): auto-sync from SPX repo $(date -u +%Y-%m-%dT%H:%MZ)"
          GIT_SSH_COMMAND="ssh -i ~/.ssh/id_deploy" git push origin main
```

> **DST note:** the cron times above are in **UTC** and assume winter ET (EST).
> During EDT (mid-March → early November) the 9:35 AM ET window runs at 13:35
> UTC, and the 4:20 PM ET window runs at 20:20 UTC. GitHub Actions does not
> auto-adjust for DST. The two cron entries above intentionally fire once per
> trading day in EST; during EDT they fire ~1 hour earlier in local time. Add a
> second pair of cron lines (`'35 14 * * 1-5'` and `'20 21 * * 1-5'`) only if
> you want exact local times in both seasons (workflow is idempotent — duplicate
> runs do nothing if there are no data changes).

---

## 8. Daily audit workflow

`bootstrap.sh` also installs `.github/workflows/audit.yml` (see the file for
details). It runs daily at 9:00 UTC and:

- Verifies the ledger CSV is **append-only** (compares against `audits/last-sha.txt`)
- Verifies all expected daily SPX-Reports files exist for the last N days
- Greps for accidentally committed secrets (`.env`, `token.json`, etc.)
- Compiles all Python under `scripts/` with `python -m compileall`
- Posts a status check that can be set as a required check for PRs to `main`

To set the status check as required:

1. Settings → Branches → Branch protection rules → Add rule
2. Branch name pattern: `main`
3. Require status checks to pass before merging → **integrity-audit**
4. Save changes

---

## 9. Common issues

| Symptom                                              | Cause / Fix                                                                     |
|------------------------------------------------------|---------------------------------------------------------------------------------|
| `Permission denied (publickey)` on push              | SSH key not added — re-run §0.4 `ssh-add` and `gh ssh-key add`                  |
| Sync workflow fails: `Permission denied (publickey)` | `DASHBOARD_DEPLOY_KEY` secret missing or pubkey not added with `--allow-write`  |
| Pages shows 404 for 10+ minutes after enabling       | First build can take up to ~10 min. Check Actions tab for the `pages-build-deployment` workflow |
| Bootstrap warns "skipped (differs)"                  | Existing local file diverged from v5 source — review then re-run with `--force` |
| Audit workflow fails on first run                    | `audits/last-sha.txt` not seeded — see audit.yml header for one-time seed command |

---

## 10. Disclaimer

This project is for **educational and research purposes only**. It does **not**
constitute investment advice, a recommendation, or an offer to buy or sell any
security. No compensation flows are associated with this project.
