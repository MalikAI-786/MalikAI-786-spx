<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://malikai-786.github.io/assets/brand/banners/malikai-786-spx/banner-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="https://malikai-786.github.io/assets/brand/banners/malikai-786-spx/banner-light.png">
    <img alt="Research Instrument — Yasir A. Malik" src="https://malikai-786.github.io/assets/brand/banners/malikai-786-spx/banner-light.png" width="100%">
  </picture>
</p>

# Research instrument

A governed, fully instrumented decision pipeline, built to study AI decision
quality with markets as the test bed.

I needed a system where a machine makes a call, the call is recorded before the
outcome is known, and the record cannot be quietly revised afterwards. Markets
provide exactly that: a daily decision with an unambiguous answer a few hours
later.

So the interesting part is not the trading. It is the governance scaffolding
around it — a five-bucket scored model, calibration against a rolling ledger,
cross-checks across three independent AI sources, an append-only ledger, and
integrity hashes so a prediction cannot be edited after the fact. It is the
control environment I argue for in writing, built so that I have to live inside
it.

> ## DISCLAIMER
>
> **This project is for educational and research purposes only. It is NOT
> investment advice, NOT a recommendation, and NOT an offer to buy or sell any
> security. No compensation flows are associated with this project. Past
> performance does not indicate future results. Options trading involves
> substantial risk of loss. Do not act on signals produced by this system with
> real money.**

## How it runs

At 9:00 AM ET on US trading days it runs the five-bucket model (futures, macro,
news, international, sentiment), scores a composite with a calibration overlay
from a rolling ten-day ledger, writes a morning report, updates the public
dashboard, and drafts the 9:30 AM email. At 4:15 PM ET it determines the
outcome, updates the running ledger, and drafts a close-of-day email.

## Tech stack

- **Python 3.9+** — model, ledger, report rendering
- **bash** — orchestration, bootstrap, scheduled wrappers
- **Gmail OAuth** — drafting morning and close emails (drafts only, no auto-send)
- **GitHub Actions** — daily dashboard sync and integrity audits
- **GitHub Pages** — public dashboard
- **launchd** (macOS) — scheduling at 9:00 AM and 4:15 PM ET

## Quick start

```bash
git clone git@github.com:malikai-786/MalikAI-786-spx.git
cd MalikAI-786-spx

./deploy/bootstrap.sh "$HOME"          # idempotent, paranoid by default

cp scripts/.env.example scripts/.env   # then edit — .gitignore covers it
python scripts/setup_gmail_oauth.py

./scripts/install_launchd.sh           # schedule

python scripts/run_morning.py --dry-run
python scripts/run_close.py   --dry-run
```

Full setup, including Pages and the cross-repo deploy key, is in
[`deploy/GITHUB-SETUP.md`](deploy/GITHUB-SETUP.md).

## Layout

| Path | What it is |
| --- | --- |
| `skill/` | `SKILL.md` and supporting files used by Claude Code |
| `scripts/` | The morning and close pipelines, calibration, rendering, publishing |
| `ledger/` | Append-only P&L and signal ledger |
| `audits/` | Integrity anchors and the ethics and regulatory review memo |
| `sources/` | The five-bucket source manifest and daily raw responses |
| `docs/` | Methodology, and how the rolling ledger feeds next-day calibration |
| `SPX-Reports/` | Daily morning and close reports |
| `dashboard/` | JSON synced to the public dashboard |

## Documentation

- [`docs/methodology.md`](docs/methodology.md) — the model, the five buckets, the
  calibration overlay, and the limits of the approach
- [`audits/audit-memo-v5.md`](audits/audit-memo-v5.md) — ethics and regulatory
  review, including why this is educational research and not investment advice
- [`docs/self-improving-loop.md`](docs/self-improving-loop.md) — how outcomes
  feed back into calibration

## License

[MIT](LICENSE) — Copyright (c) 2026 Yasir A. Malik. Questions:
[open an issue](https://github.com/MalikAI-786/MalikAI-786-spx/issues).

---

<sub>[Profile](https://github.com/MalikAI-786) · [Site](https://malikai-786.github.io) · [Brand system](https://malikai-786.github.io/brand.html) · [Newsletter](https://proofoverpromise.substack.com) · [LinkedIn](https://linkedin.com/in/yasiramalik)</sub>

<sub><b>Yasir A. Malik</b> · Audit · Risk · Governance · Newark, NJ · NYC metro</sub>
