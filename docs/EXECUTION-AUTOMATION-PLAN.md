# SPX 0DTE — Automated execution plan

**Prepared:** 2026-09-25 · **Owner:** Yasir A. Malik · **Status:** PROPOSAL, not approved

This plans how the morning-bias signal could be turned into automatically placed
trades. It is staged so that no real money moves until the system has earned it
on its own evidence, and so that the execution layer can never contaminate the
public research repo.

---

## 0. What this changes, and who decides

Today the system's governing invariant is explicit and repeated everywhere:

> This entire system is a SYNTHETIC PAPER-TRADE LEDGER. Real money is never
> moved. — `docs/LEDGER-SCHEMA.md`

Automated execution is a change to that invariant. It is the owner's decision
(`AGENTS.md` safeguard #8) and it has to be recorded in Notion, the rank-1
source, before any executor is switched on. Three things must be decided there:

| Decision | Options | Why it matters |
|---|---|---|
| Which book executes | Paper account first (recommended) / live | Paper execution produces real fill prices — which fixes the ledger's biggest hole — with no capital at risk |
| Distribution | Keep emailing third parties / stop while executing | `audits/AUDIT-MEMO-v5.0.md` F-01: publishing signals to others *and* executing them is the holding-out pattern the v5.0 redesign was written to avoid. Executing only your own account is fine; doing both at once needs a deliberate decision |
| Broker | Any with a paper sandbox and an options API that supports SPX index options | Broker identity and credentials live in the private book only — never in this repo, never in an email body (`SKILL.md` §0.7) |

The last time real money was attached to an SPX 0DTE automation in this account
(the bot retired 2026-06-05, see `docs/SIGNAL-SOURCES.md`), it was run in
parallel with the educational newsletter and had to be unwound. This plan keeps
execution and publication as separate systems from the first line of code.

---

## 1. The prerequisite nobody can skip: the pipeline has to be reliable first

The executor is only as safe as the signal feeding it. Right now the signal
pipeline is not safe to execute against. From the ledger and the sent emails:

- **2026-09-01** — fired 8:29 PM ET, 10+ hours late.
- **2026-09-24** — fired 5:54 PM ET, ~9 hours late, past the close.
- **2026-09-17 → 09-23** — six consecutive sessions with no run at all.
- Git unreachable from the run environment since at least 09-08, so the ledger
  and calibration have not updated from live runs; the 09-24 email itself says
  the calibration overlay is two weeks stale.
- The publisher's identity and repo path are unconfirmed
  (`docs/HANDOFF-CHATGPT-TRADING-LOOP.md` Part 4C).

With execution attached, the 09-01 and 09-24 runs would have tried to place
0DTE orders on contracts that had already expired, priced off a close that had
already printed. **A late run with an executor behind it is not a missed
email; it is a bad order.**

Gate to leave Phase 1 (measured, not asserted):

- 20 consecutive trading sessions with a run starting between 9:00 and 9:20 ET
  (on-time rate ≥ 95%, and zero runs after 10:00 ET that produced a signal).
- Exactly one publisher, confirmed by name and repo path.
- Ledger and `dashboard/data/performance.json` updating from the live run
  itself, not by hand.
- Staleness guard live: any run starting after 10:00 ET emits the late-run
  form and writes `"executable": false`. (The 09-24 email recommended this
  itself.)

---

## 2. Architecture: signal file first, email second, executor third

The single most important design decision: **the executor never reads the
email.** The email is rendered *from* a structured signal file, and the
executor reads the *same* file. One source of truth, no parsing prose.

```
 09:00 ET   morning run ──▶ signals/YYYY-MM-DD.json ──▶ email (rendered)
                                     │
 09:45 ET   executor  ◀──────────────┘  reads, validates 12 gates, places order
                                     │
 09:45–15:45  executor manages exit (target / stop / time)
                                     │
 16:05 ET   close job ◀── fills/YYYY-MM-DD.json ──▶ ledger row with REAL pnl
```

### 2.1 Signal file — `signals/YYYY-MM-DD.json` (public-safe, committed)

```json
{
  "schema": "spx-signal/1",
  "date": "2026-09-24",
  "generated_at": "2026-09-24T13:12:41Z",
  "publisher": "morning-bias-v5",
  "composite": -0.50,
  "label": "LEAN BEARISH",
  "executable": true,
  "size_multiplier": 0.5,
  "size_reason": "binary_event_day",
  "structure": {
    "type": "bear_call_spread",
    "short_strike": 7775,
    "long_strike": 7810,
    "width": 35,
    "credit_target": 7.0,
    "credit_floor": 5.5,
    "max_loss_per_lot": 28
  },
  "invalidation": { "spx_above": 7775 },
  "gates": {
    "trading_day": true,
    "on_time": true,
    "binary_event": "trump_xi_summit",
    "buckets_partial": ["international"],
    "data_quality_discards": 2
  },
  "evidence": { "spx_ref": 7706.03, "vix_ref": 14.21, "sigma": 69.0 }
}
```

Every field the executor decides on is here. Nothing is inferred from text.
A stand-down writes `"executable": false` with `"structure": null`.

### 2.2 Executor — separate process, separate machine, private

Runs on hardware the owner controls with the broker credentials. **Never in
this repo.** Reads the signal file (via git pull or a pushed copy), and refuses
to trade unless *all twelve* gates pass:

| # | Gate | Rejects when |
|---|---|---|
| 1 | Kill switch | file `EXECUTION_DISABLED` exists — checked first, every cycle |
| 2 | Signal date | `date` ≠ today (ET) |
| 3 | Signal freshness | `generated_at` after 10:00 ET, or older than 90 minutes |
| 4 | Executable flag | `executable` is false (stand-down, late run, data failure) |
| 5 | Trading day | market holiday or weekend |
| 6 | Composite magnitude | `abs(composite)` < 0.30 (neutral band — belt and braces) |
| 7 | Data quality | `buckets_partial` ≥ 2 or `data_quality_discards` ≥ 3 |
| 8 | Position cap | any open SPX position already exists |
| 9 | Daily loss cap | realized loss today ≥ configured cap |
| 10 | Weekly loss cap | realized loss this week ≥ configured cap |
| 11 | Credit floor | live mid-price credit < `credit_floor` (structure has decayed) |
| 12 | Strike sanity | short strike within 0.5σ of the signal's `spx_ref` ± 1σ band; otherwise the tape moved and the strikes are stale |

Order logic, per the structure already defined in `SKILL.md` §5:

- **Entry 09:45 ET.** Vertical credit spread, `quantity = base_lots ×
  size_multiplier` (rounded down; minimum 1), limit at `credit_target`,
  walk down to `credit_floor` in 0.25 steps over 3 minutes, then cancel.
- **Profit target.** Close at 50% of credit received (GTC limit placed on fill).
- **Stop.** Close if SPX trades through the short strike (the published
  invalidation level), or if spread mark ≥ 2× credit received.
- **Time exit.** Flat by 15:45 ET regardless — never hold into settlement.
- **Logging.** Every order, fill, cancel, and reject written to
  `fills/YYYY-MM-DD.json` (private) with timestamps and the gate results.

### 2.3 Close job — consumes real fills

`close_track.py` reads `fills/` and appends the ledger row with
`disciplined_pnl` = actual realized P&L per lot. This is the part that fixes
the accountability layer's biggest defect: today 7 of 9 directional trades in
the ledger have **no dollar figure** because no fill was ever published. A paper
executor produces real fills. Even Phase 2 answers the "$1,500" question
properly — with sizing you chose, on prices that actually printed.

---

## 3. Phases and promotion gates

**Phase 1 — Reliability.** Section 1. No executor exists yet. Exit: the four
measured criteria above.

**Phase 2 — Automated paper execution.** Executor live against a broker paper
account. Base size 1 lot. Run for the longer of **40 sessions or 20 executed
trades**. Promotion criteria are fixed *now*, before the data exists, so they
cannot be tuned to fit:

- Executor on-time and gate-correct on 100% of sessions (no order ever placed
  when a gate should have rejected).
- ≥ 20 verified fills with real entry and exit prices.
- Expectancy per executed trade > 0 after modeled commissions.
- Max drawdown ≤ 3× average win.
- Direction hit rate on executed trades ≥ the ledger's current 66.7% is *not*
  required — structure P&L is what matters. Fewer than 20 trades → stay in
  Phase 2.

**Phase 3 — Live, minimum size, human-armed.** Separate capped sub-account.
1 lot. For the first 20 live sessions the executor requires a daily *arm*
(the owner drops a file `ARMED-YYYY-MM-DD` before 09:40 ET or nothing trades).
Daily loss cap = one max loss. Weekly cap = two.

**Phase 4 — Hands-off.** Only after Phase 3 clears the same criteria again on
live fills. Size increases stepwise and never more than 2× per 20 sessions.

Any hard failure — a bad order, a late signal that slipped past a gate, a
reconciliation mismatch — drops the system one phase and restarts that
phase's clock.

---

## 4. What the evidence supports today

Being direct, because `AGENTS.md` #6 says never present research as further
along than it is:

- 19 audited days. **Only 2 have a real dollar fill** (+$300, −$180).
- Win rate 50% on those 2. Expectancy +$30. Sample far too small to size on.
- Direction hit rate 66.7% (9 scored), structure 85.7% (7 scored) — encouraging,
  but every one of those days is a *verdict without a dollar*.
- The live publisher's own 09-24 email: calibration stale, treat composites as
  lower-confidence.

That is exactly what Phase 2 is for. The paper executor is the thing that turns
"66.7% direction, dollars unknown" into a number that can justify — or rule
out — live capital. Skipping to Phase 3 would be sizing real money on two
observations.

---

## 5. Immediate next steps (in order)

1. **Owner:** record the three decisions in §0 in Notion. Nothing else starts
   until "paper first" and the distribution question are written down.
2. **Owner:** confirm the actual publisher and repo path (Part 4C of the
   handoff). The staleness guard goes into *that* pipeline.
3. **Pipeline:** emit `signals/YYYY-MM-DD.json` from the morning run. The
   email becomes a render of it. This session can build the schema, the
   validator, and the render step in this repo.
4. **Pipeline:** add the staleness guard and start the 20-session clock.
5. **Owner:** open a paper account at a broker with SPX options API access;
   keep credentials off this repo entirely.
6. **Executor:** build against the paper sandbox on the owner's machine. This
   session can write the executor and its 12-gate validator with a simulated
   broker adapter; the real broker adapter is written and tested where the
   credentials live.
7. **Phase 2 begins** only when step 4's clock has cleared.

## 6. What this session will not do

- Hold broker credentials or place orders from this environment.
- Put account numbers, API keys, fills, or position data into this public repo
  (`AGENTS.md` #3; `SKILL-accountability.md` §5 — private book only).
- Switch execution on. That is a decision only the owner makes, and only after
  Phase 1 is measured, not assumed.
