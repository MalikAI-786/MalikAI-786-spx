---
name: spx-accountability
version: 2.0.0
owner: Yasir A. Malik
status: production-control
companion_skills:
  - scripts/SKILL.md
  - scripts/SKILL-close.md
  - scripts/SKILL-portfolio.md
purpose: >
  Force every SPX publication to lead with falsifiable prior-day performance,
  preserve an append-only evidence trail, separate model performance from real
  portfolio performance, and explain whether edge or failure came from direction,
  structure, timing, or risk discipline.
---

# SPX Accountability Layer — v2.0

This file is a mandatory companion to every SPX morning email, close report,
performance dashboard, and portfolio outlook. Read `AGENTS.md` first. If this
file conflicts with `AGENTS.md` or the Malik Operating System in Notion, the
higher-ranked source wins.

## 1. The first thing a morning email must say

The email does **not** start with today's forecast. It starts with yesterday's
falsifiable result.

Use exactly this logic:

> **IF WE HAD FOLLOWED YESTERDAY'S PUBLISHED MODEL SETUP:** {plain-English result}.
> Synthetic disciplined P&L: **{signed dollar P&L per standardized 1-lot}**.
> Verified cumulative P&L: **{signed cumulative P&L}** across **{verified rows}** audited days.
> {coverage note if historical coverage is incomplete}

For a stand-down day:

> **IF WE HAD FOLLOWED YESTERDAY'S PUBLISHED MODEL SETUP:** we would have stayed flat.
> Synthetic disciplined P&L: **$0**. The model took no exposure.

Never call a stand-down a win merely because the market later moved against an
unpublished hypothetical trade. The ledger records `$0`; the narrative may say
whether the stand-down protected against risk or left an opportunity unused.

## 2. Separate four questions that used to get blended together

Every close result and next-day recap must score these independently:

1. **Direction** — did the sign of the morning bias match the realized SPX move?
2. **Structure** — given the move, did the selected spread structure make or lose money?
3. **Execution rule** — would the published trigger/invalidation/exit rules have improved or worsened the result?
4. **Discipline** — did a stand-down, trigger filter, stop, or size rule avoid an otherwise larger loss?

This is why the system can learn. A bullish call with a losing call debit spread
is not the same failure as a bearish call on a bullish day. One is strike/structure
selection; the other is directional inference.

## 3. Required scorecard in every morning email

Immediately after the prior-day lead, render:

| Metric | Required value |
|---|---|
| Verified cumulative synthetic P&L | Dollar total from `ledger/accountability-v2.csv` |
| Wins / losses / stand-downs | Counts from verified rows |
| Win rate | Wins / (wins + losses); stand-downs excluded |
| Average win | Mean positive disciplined P&L |
| Average loss | Mean negative disciplined P&L |
| Expectancy | Mean disciplined P&L across non-stand-down trades |
| Max drawdown | Peak-to-trough decline in cumulative disciplined P&L |
| Direction hit rate | Only rows where direction evidence is verified |
| Structure hit rate | Only rows where structure outcome is verified |
| Evidence coverage | Verified rows / known published model days |

If a denominator is too small, print `N/A — insufficient verified observations`.
Do not manufacture precision.

## 4. Historical backfill rule

The old ledgers are incomplete and at least one historical record conflicts with
sent-email evidence. **Do not rewrite them.** `AGENTS.md` makes the public ledger
append-only.

`ledger/accountability-v2.csv` is the correction-and-continuation ledger.
Historical rows may be added only when supported by one of:

- a sent morning + close email pair;
- an immutable close report already committed in GitHub;
- broker/automation evidence supplied by the owner, used only to establish a
  separately labeled actual-trade result.

Rows with incomplete evidence use `evidence_status=PARTIAL` or `UNVERIFIED` and
must not enter verified P&L statistics. Never infer an option-spread fill from the
SPX close alone if the published entry/exit price is missing.

## 5. Public model ledger vs. private real portfolio

These are different books.

### Public research book
`ledger/accountability-v2.csv`

Contains only standardized synthetic/paper outcomes and public-safe metadata.
No account values, account numbers, share counts, cost basis, or personal
brokerage balances.

### Private actual portfolio book
The source of truth is the Notion page **Portfolio & Holdings Tracker — PRIVATE**
(or another owner-approved private store). Actual trades supplied by the owner
must never be committed into this public repository.

Daily emails may contain an **Actual Portfolio** section only to the disclosure
level explicitly approved by the owner. Until that decision is recorded, use:

> **Actual portfolio:** private tracking active; no position-level figures published.

The public dashboard may show only approved aggregates, never reconstructable
position-level private data.

## 6. "Why this works / why this failed" diagnostic

After the scorecard, include one short evidence-based diagnosis selected from:

- **Directional edge** — bias sign was right and structure also profited.
- **Direction right, structure wrong** — market call was useful; strikes/structure or entry timing destroyed the edge.
- **Direction wrong, discipline saved capital** — model inference missed, but the control layer worked.
- **Stand-down worked** — no exposure was appropriate under the published uncertainty rule.
- **Stand-down left opportunity unused** — correct to record `$0`; examine whether the uncertainty gate is too conservative.
- **Execution failure** — model may be unscorable because entry/exit/fill evidence is missing.

Never say the model "works" from a handful of observations. Use sample size and
coverage in the same paragraph.

## 7. Required machine outputs

After every verified close result:

```bash
python scripts/accountability_track.py build
```

This reads `ledger/accountability-v2.csv` and writes:

- `dashboard/data/performance.json` — public dashboard data;
- `dashboard/data/accountability-email.html` — the HTML fragment that must
  precede today's market call in the next morning email.

The generator must be deterministic. The email fragment and dashboard summary
must come from the same ledger so they cannot disagree.

## 8. Append contract

New rows are appended through:

```bash
python scripts/accountability_track.py append \
  --date YYYY-MM-DD \
  --bias-label "LEAN BULLISH" \
  --structure "bull_put_spread" \
  --disciplined-pnl 300 \
  --counterfactual-pnl -1000 \
  --model-verdict WON \
  --direction-verdict HIT \
  --structure-verdict HIT \
  --evidence-status VERIFIED \
  --evidence-ref "gmail:<message-id>"
```

Duplicate dates are refused. A correction is a **new row** with a unique
`record_id` and `correction_of=<record_id>`; historical rows are never mutated.

## 9. Recipient and sending boundary

This repository defines analytical content, not permission to transmit it.
`AGENTS.md` says emails are drafted, never sent. A separate authorized sending
process may choose recipients. The content generator must therefore be recipient-
agnostic and must never weaken the educational disclaimer for a friend, family
member, or external reader.

## 10. Minimum daily email order

1. **Yesterday first — hypothetical disciplined result + cumulative scorecard**
2. **Why it worked / failed**
3. Today's bias and evidence
4. Defined-risk educational structure, if any
5. Calibration / disagreement analysis
6. Weekly Tech Sleeve outlook
7. **Actual Portfolio** — private/approved disclosure only
8. Dashboard link
9. Full educational / not-investment-advice disclaimer

The point of v2 is simple: **prediction without a recorded outcome is content;
prediction plus an immutable outcome ledger is analysis.**
