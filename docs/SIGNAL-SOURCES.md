# Signal source registry — what is authorized to produce an "SPX 0DTE" signal

**Read this before wiring up a new automation, a new scheduled task, or a new
bot that touches SPX 0DTE.** It exists so a duplicate never has to be
rediscovered by archaeology through Gmail again — it happened once, on
2026-08-18, and it took a real investigation to reconstruct. Keep this file
current instead.

## Authorized

| Source | What it is | Status |
|---|---|---|
| `scripts/SKILL.md` (this repo) | The 5-bucket morning-bias model. 9:00–9:30 ET, owner-only email. | **Live.** Sole authorized source since 2026-06-05. |
| `scripts/SKILL-close.md` (this repo) | EOD synthetic P&L tracker, 4:15 ET. | **Live.** |
| `scripts/SKILL-portfolio.md` (this repo) | Weekly tech-sleeve outlook, Fridays. | Pending merge — see `MalikAI-786-spx#1`. |

Anything that emails, texts, or trades an "SPX 0DTE" call and is **not** one
of the above is unauthorized drift. Two showed up already; both are recorded
below so the pattern is recognizable next time.

## Retired — found during the 2026-08-18 audit

### ChatGPT scheduled task ("[Task Update] SPX 0DTE ...")

- **Sender:** `noreply@tm.openai.com`. Ran daily 2026-05-20 → 2026-06-02,
  then stopped. Not reachable by any tool available to this session — no
  OpenAI/ChatGPT connector exists here, so its status can only be confirmed
  from `chatgpt.com` → Settings → Tasks, by the owner.
- **What was actually wrong:** on at least two runs (2026-05-20, 2026-05-29)
  the notification's subject/preview was the model's own scratch reasoning —
  `"We need current market use web finance maybe. Need check market open
  date 202..."` and `"Need search current. Use web. Need get market open.
  Need compare with prior p..."` — instead of a real summary. The task's
  title-generation step was failing intermittently well before it stopped
  altogether.
- **Why it's not worth fixing:** the report itself never reached this
  repository, this ledger, or this dashboard — it only ever lived inside
  ChatGPT's own UI, behind a "View message" link back to `chatgpt.com`. It
  could not have fed the model here even working correctly. It was a fully
  parallel, disconnected signal with its own (unaudited) prompt.
- **Action for the owner:** open `chatgpt.com` → Settings → Tasks and confirm
  it is actually deleted, not merely quiet — a task that silently stopped
  emailing could still be enabled and failing every run without notice.

### Option Alpha bot "Live with TastyTrade" — REAL MONEY

- **Sender:** `noreply@optionalpha.com`. Ran 2026-05-22 → 2026-06-05,
  opening and closing real SPX short call/put spreads through a live
  TastyTrade brokerage connection — confirmed by "Position Opened" /
  "Position Closed" emails with real strikes and fill times, not synthetic
  ones.
- **Why this one matters more than the ChatGPT task:** every other system in
  this account is explicitly synthetic — `docs/LEDGER-SCHEMA.md`:
  *"This entire system is a SYNTHETIC PAPER-TRADE LEDGER. Real money is never
  moved."* This bot was the one exception, moving real money on the same
  0DTE structures the educational model illustrates. It is not reachable by
  any tool available to this session — no Option Alpha or TastyTrade
  connector exists here.
- **This is already why `SKILL.md` §0.7 bans the strings `"Option Alpha"` and
  `"Tastytrade"` from every email body**, implementing audit-memo finding
  **F-01 (High severity)** — holding-out risk under the Investment Advisers
  Act of 1940 §202(a)(11): an educational newsletter that also names a live
  broker and a live bot reads as investment advice, not research. The v5.0
  redesign didn't just add a disclaimer; it was written to distance itself
  from exactly this bot. See `audits/AUDIT-MEMO-v5.0.md` F-01.
- **Action for the owner:** open Option Alpha's dashboard and confirm the
  bot is fully deactivated (not just paused, not just out of positions) and
  that the TastyTrade API connection backing it has been revoked. This is
  the one item on this page with real dollars attached; verify it directly
  rather than inferring from silence.

## Why both went quiet at the same time

`git log` shows the v5.0 educational-only redesign (`6395ac6`,
2026-05-28) landed a week before either external system stopped
(2026-06-02 / 2026-06-05). Read together with the owner's own words in the
close-of-day thread from 2026-05-27 — *"I will run the model for 10 days and
then give it a few K to trade"* — the sequence reads as: build the governed
version, run the ungoverned experiments a little longer to compare, then cut
over. That is a reasonable thing to have done. It just was not written down
anywhere until now, which is what made it look, from a cold read of the
inbox, like something was still actively broken.

## How to re-check this without redoing the whole investigation

```
# In Gmail, as yasiramalik@gmail.com:
from:noreply@tm.openai.com subject:(SPX)      # ChatGPT task — should be empty going forward
from:noreply@optionalpha.com                  # Option Alpha bot — should be empty going forward
```

If either query returns something dated after 2026-06-05, an unauthorized
source is active again — stop it, and update this file with what happened
rather than leaving the next reader to reconstruct it from scratch.
