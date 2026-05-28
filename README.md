# MalikAI-786 SPX 0DTE

**An educational research project** that produces a daily directional bias
signal for S&P 500 0-day-to-expiration (0DTE) options and tracks the outcome.
At 9:00 AM ET on US trading days it runs a 5-bucket model (futures, macro,
news, international, sentiment), scores a composite with a calibration overlay
from a rolling 10-day ledger, writes a morning report, updates a public
dashboard, and drafts a 9:30 AM email with click-by-click instructions. At
4:15 PM ET it determines the outcome, updates the running P&L ledger, and
drafts a close-of-day email.

---

> ## DISCLAIMER
>
> **This project is for educational and research purposes only. It is NOT
> investment advice, NOT a recommendation, and NOT an offer to buy or sell
> any security. No compensation flows are associated with this project.
> Past performance does not indicate future results. Options trading
> involves substantial risk of loss. Do not act on signals produced by
> this system with real money.**

---

## Tech stack

- **Python 3.9+** — model, ledger, report rendering
- **bash** — orchestration, bootstrap, scheduled wrappers
- **Gmail OAuth** — drafting morning/close emails (drafts only, no auto-send to non-owners)
- **GitHub Actions** — daily sync to public dashboard + integrity audits
- **GitHub Pages** — public dashboard rendering
- **launchd** (macOS) — local scheduling at 9:00 AM ET and 4:15 PM ET

---

## Quick start

```bash
# 1. Clone
git clone git@github.com:malikai-786/MalikAI-786-spx.git
cd MalikAI-786-spx

# 2. Bootstrap both local repos (idempotent, paranoid by default)
./deploy/bootstrap.sh "$HOME"

# 3. Configure Gmail OAuth
cp scripts/.env.example scripts/.env
# Edit scripts/.env -- DO NOT commit it (.gitignore handles this)
python scripts/setup_gmail_oauth.py

# 4. Schedule via launchd (macOS)
./scripts/install_launchd.sh

# 5. Manual dry run
python scripts/run_morning.py --dry-run
python scripts/run_close.py   --dry-run
```

For the full GitHub setup (creating the two repos under `malikai-786`,
enabling Pages, configuring the cross-repo deploy key), see
[`deploy/GITHUB-SETUP.md`](deploy/GITHUB-SETUP.md).

---

## Repo layout

```
MalikAI-786-spx/
├── skill/                   # SKILL.md + supporting files used by Claude Code
│   ├── SKILL.md             # v5.0 spec -- 3 AI sources + self-improving loop
│   └── ...
├── scripts/                 # Python + bash orchestration
│   ├── run_morning.py       # 9:00 AM ET pipeline
│   ├── run_close.py         # 4:15 PM ET pipeline
│   ├── score_calibration.py # rolling-10-day calibration overlay
│   ├── render_report.py     # markdown -> HTML for SPX-Reports/
│   ├── publish_dashboard.py # writes JSON into dashboard/data/
│   └── install_launchd.sh
├── ledger/                  # APPEND-ONLY P&L + signal ledger
│   └── spx_ledger.csv
├── audits/                  # integrity anchors + audit memo
│   ├── audit-memo-v5.md     # ethics + regulatory review
│   └── last-sha.txt         # ledger append-only anchor (see .github/workflows/audit.yml)
├── sources/                 # the 5-bucket research source manifest
│   ├── cards/               # per-source card (futures, macro, news, intl, sentiment)
│   └── responses/           # raw daily responses (gitignored after retention window)
├── docs/                    # methodology + design notes
│   ├── methodology.md
│   └── self-improving-loop.md
├── SPX-Reports/             # daily reports
│   ├── morning/YYYY-MM-DD.md
│   └── close/YYYY-MM-DD.md
├── dashboard/               # data + assets pushed to malikai-spx-dashboard
│   └── data/                # JSON files synced daily
├── deploy/                  # this directory -- bootstrap + setup docs
│   ├── bootstrap.sh
│   └── GITHUB-SETUP.md
├── .github/workflows/
│   ├── sync-dashboard.yml   # cross-repo data deploy (9:35 ET / 4:20 ET / push)
│   └── audit.yml            # daily integrity audit (09:00 UTC)
├── README.md                # this file
├── LICENSE                  # MIT
└── .gitignore
```

---

## Documentation

- **Methodology**: [`docs/methodology.md`](docs/methodology.md) — the model, the
  5 buckets, the calibration overlay, and the limits of the approach.
- **Audit memo (v5.0)**: [`audits/audit-memo-v5.md`](audits/audit-memo-v5.md) —
  ethics + regulatory review, including why this project is educational
  research and not investment advice.
- **Self-improving loop**: [`docs/self-improving-loop.md`](docs/self-improving-loop.md)
  — how the rolling ledger feeds back into next-day calibration.

---

## License

[MIT](LICENSE) — Copyright (c) 2026 Yasir A. Malik.

## Author + contact

**Yasir A. Malik**
Email: yasiramalik@gmail.com
GitHub: [@malikai-786](https://github.com/malikai-786)

For questions, open an [issue](https://github.com/malikai-786/MalikAI-786-spx/issues).
