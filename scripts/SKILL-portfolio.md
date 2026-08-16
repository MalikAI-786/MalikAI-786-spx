---
name: portfolio-outlook
version: 1.0.0
owner: Yasir A. Malik
status: pre-production
audit_reference: /repo/audits/AUDIT-MEMO-v5.0.md
schema_reference: /repo/docs/PORTFOLIO-SCHEMA.md
description: >
  On Friday after the US close, score a weekly directional outlook for the
  tech sleeve using five buckets (momentum, breadth, rates, earnings,
  volatility), record the call in an append-only ledger BEFORE the outcome
  is known, fill in the prior week's outcome, refresh the Tech Outlook tab
  on the public dashboard, and emit an email section for the next trading
  day's 9:30 ET publication. This is research and education content — not
  investment advice, not a recommendation, not a solicitation.
distribution:
  to: yasiramalik@gmail.com
  cc: []
  bcc: []
framing: EDUCATIONAL
cadence: weekly (Friday, after 16:00 ET)
---

# Tech Sleeve Weekly Outlook — v1.0 Scheduled Task

**Owner:** Yasir A. Malik
**Run window:** Friday 16:30 ET → 16:40 ET
**Companion skills:** `SKILL.md` (morning bias), `SKILL-close.md` (EOD)
**Schema of record:** `$REPO/docs/PORTFOLIO-SCHEMA.md`

This task is designed to be executable by a fresh agent with no prior
context. Where it references a control (C-xx) or finding (F-xx), that is the
control from `AUDIT-MEMO-v5.0.md` being carried over to this model, because
a second predictive model in the same repository inherits the first one's
governance rather than inventing its own.

---

## 0. Pre-flight (16:30:00 → 16:31:00)

0.1. Set `REPO` to the absolute path of the local clone of
    `MalikAI-786/MalikAI-786-spx`. If it does not exist, halt with
    `ENV_ERROR: REPO not found`.

0.2. Set `WEEK_ENDING` to today's date if today is a Friday, else the most
    recent Friday, in `YYYY-MM-DD`. If the US market was closed all week,
    exit cleanly with `NON_TRADING_WEEK` and write nothing.

0.3. Verify the working tree is clean. A dirty tree means an interrupted
    prior run; resolve it before scoring (control C-02).

0.4. **Hard rules — enforce on every run.** Any violation halts the task:

  - No value read from `$REPO/private/` may be written into any file under
    `dashboard/`, `ledger/`, or `portfolio/`. (AGENTS.md safeguard #3)
  - `private/` must be listed in `.gitignore` and must not appear in
    `git ls-files`. If it does, halt with `PRIVACY_GUARD_VIOLATION`.
  - No account number, account nickname, dollar balance, share count, or
    cost basis may appear in a committed file. (AGENTS.md #1, #3)
  - A bucket with no data must score `null`, never `0.0`. (C-06)
  - The ledger is append-only. A historical row is never edited except
    through the documented amendment path. (C-03, F-04)
  - The educational disclaimer must appear on the tab and in the email
    section. (C-01)
  - While `portfolio/basket.json` has `owner_confirmed: false`, every
    artifact must carry the banner `REFERENCE BASKET — not the owner's
    holdings`. Never imply a generic basket is the owner's account.

---

## 1. Score the prior week's outcome first (16:31:00 → 16:32:00)

```
python $REPO/scripts/portfolio_track.py --score-prior
```

This finds the most recent ledger row with an empty `fwd_1w_basket_pct` and
fills exactly two columns: `fwd_1w_basket_pct` and
`was_directionally_right`. The script re-reads every other column and aborts
if any of them moved.

**Why this runs first.** The prior week's call was written before its
outcome existed. Scoring it before writing this week's call means the new
call cannot be quietly informed by an outcome the ledger has not yet
recorded. If it errors, do not proceed — an unscored ledger is recoverable,
a contaminated one is not.

---

## 2. Load the basket (16:32:00 → 16:32:30)

Read `$REPO/portfolio/basket.json`. Confirm:

- `constituents[].weight_pct` sums to ~100 (±1.0).
- `status` and `owner_confirmed` agree with each other.
- `source` and `as_of` are populated when `owner_confirmed` is `true`.

If `owner_confirmed` is `false`, continue — but every downstream artifact
gets the reference-basket banner, and the ledger row records
`owner_confirmed=false` so a later reader can tell which weeks described
real holdings and which did not.

---

## 3. Fetch market data (16:32:30 → 16:35:00)

Needed: trailing ~1y daily closes for every constituent, the benchmark
(default `XLK`), `^TNX` (10-year yield ×10), and `^VIX`.

Sources are tried in order and both are keyless: **Stooq** daily CSV, then
**Yahoo** chart JSON. A ticker that resolves fewer than 60 closes is treated
as missing.

**Missing data is not an error.** It propagates to bucket abstention (§4).
Do not substitute a proxy ticker, do not carry forward last week's series,
and do not interpolate. A model that quietly swaps its inputs is not the
model that was audited.

---

## 4. Score the five buckets (16:35:00 → 16:36:00)

Each returns a score in `[-2.0, +2.0]` plus a rationale under 280 chars, or
`null` to abstain. Definitions and thresholds are in
`docs/PORTFOLIO-SCHEMA.md` § "The five buckets".

| Bucket | Weight | Abstains when |
|---|---|---|
| `momentum` | 0.30 | fewer than half the sleeve resolved, or <50 sessions |
| `breadth` | 0.20 | fewer than half the sleeve resolved |
| `rates` | 0.20 | `^TNX` unavailable |
| `earnings` | 0.15 | **always, by default** — see below |
| `volatility` | 0.15 | `^VIX` unavailable |

**`earnings` abstains by default and that is deliberate.** There is no
keyless source for consensus forward-EPS revisions. Estimating one from
price action would put a number into a ledger whose entire purpose is that
its numbers are not estimated. Wiring a real revisions feed (or supplying
`earnings_revision_breadth` in a fixture) is the only way to activate it.

---

## 5. Composite, label, confidence (16:36:00 → 16:36:30)

Drop abstaining buckets, renormalize the remaining weights to sum to 1.0,
and compute `composite = Σ(weight × score)`, clipped to `[-2, +2]`.

| Composite | Label |
|---|---|
| `≥ +1.0` | `CONSTRUCTIVE` |
| `+0.3 … +1.0` | `LEAN CONSTRUCTIVE` |
| `-0.3 … +0.3` | `NEUTRAL` |
| `-1.0 … -0.3` | `LEAN DEFENSIVE` |
| `≤ -1.0` | `DEFENSIVE` |

Confidence is derived from bucket span and how many buckets scored — never
asserted. Two or more abstentions forces `low`.

A `low`-confidence week is still recorded. Publishing only the confident
weeks would bias the ledger toward the model's good days, which is the
survivorship problem F-05 exists to prevent.

---

## 6. Write the artifacts (16:36:30 → 16:38:00)

```
python $REPO/scripts/portfolio_track.py --week-ending "$WEEK_ENDING"
```

Writes, in order:

1. **`ledger/portfolio-signals.csv`** — one appended row. Refuses a
   duplicate `week_ending`. Verifies every prior row is byte-identical
   after the write and aborts if not.
2. **`dashboard/data/portfolio.json`** — what the Tech Outlook tab renders.
   Public-safe by construction.
3. **`dashboard/data/portfolio-email.html`** — the public email section.
4. **`private/portfolio-email-private.html`** — written **only** if
   `private/holdings.json` exists. Gitignored. This is the single sink for
   private figures.

### Where the email section slots in

The morning email's section order is fixed by `SKILL.md` §10.3. The tech
outlook is inserted **after** the rolling 10-day trusted-bot P&L table and
**before** the dashboard link:

```
... → rolling 10-day trusted-bot P&L table
    → tech sleeve weekly outlook          ← dashboard/data/portfolio-email.html
    → owner addendum (owner-only runs)    ← private/portfolio-email-private.html
    → dashboard link
    → audit-memo link
    → NOT-INVESTMENT-ADVICE box
    → Hazrat Ali quote
```

The section is included in **every** morning email Monday through Friday,
carrying the same Friday call all week, with the week-ending date shown so
a reader can see the call's age. It is not re-scored intraday. A weekly
model that silently updates daily is a daily model with a weekly label.

The banned-phrase lint in `SKILL.md` §10.4 runs over this fragment too. It
is written to pass: no broker names, no "trade at", no click-by-click.

---

## 7. Commit and publish (16:38:00 → 16:40:00)

```
git -C "$REPO" add portfolio/basket.json \
                   ledger/portfolio-signals.csv \
                   dashboard/data/portfolio.json \
                   dashboard/data/portfolio-email.html
git -C "$REPO" commit -m "portfolio($WEEK_ENDING): weekly tech-sleeve outlook"
git -C "$REPO" push origin main
```

Before staging, assert `git status --porcelain private/` is empty. If
anything under `private/` is stageable, halt with
`PRIVACY_GUARD_VIOLATION` — the `.gitignore` entry has been damaged.

The `sync-dashboard` workflow copies `dashboard/data/*.json` into the
dashboard repository, where the Tech Outlook tab reads `data/portfolio.json`.

---

## 8. Failure modes

| Condition | Action |
|---|---|
| Anything under `private/` is stageable | Hard abort, `PRIVACY_GUARD_VIOLATION` |
| Ledger prior row changed during write | Hard abort, restore from git |
| Duplicate `week_ending` | Refuse append; amend deliberately |
| `--score-prior` altered a non-outcome column | Hard abort |
| All five buckets abstained | Record the row with `composite=0`, `confidence=low`, and `abstained` listing all five. Do **not** skip the week — a week the model could not read is itself a result |
| `owner_confirmed=true` but `source` empty | Halt; provenance is required for an owner-attributed call |

---

## 9. What this model does not do

Stated here so it is not inferred otherwise:

- It does not tell the owner to buy, sell, hold, or change contributions.
  It is an outlook on a long-horizon retirement sleeve, and the honest
  action on almost every weekly reading is *nothing*.
- It does not forecast a year out. The projection on the tab is a bootstrap
  over trailing volatility with the composite call deliberately excluded.
- It does not model fees. The sleeve it describes sits behind roughly 165
  basis points of annual management cost, which compounds against every
  path the projection draws and is not netted out of the index.
- It does not know the owner's tax situation, time horizon, liquidity
  needs, or the rest of his balance sheet — the four things that actually
  determine whether any allocation is appropriate.

---

## 10. Version log

- **v1.0** (initial): five buckets, weekly Friday cadence, append-only
  ledger with outcome columns filled the following week, public/private
  data split enforced in code, projection as a normalized-index scenario,
  `earnings` bucket abstaining pending a real revisions feed.

---

*End of SKILL-portfolio.md v1.0. Owner: Yasir A. Malik. Schema of record:
`/docs/PORTFOLIO-SCHEMA.md`. Educational research only — not investment
advice.*
