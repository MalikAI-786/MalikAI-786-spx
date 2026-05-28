# Crypto Signal Execution Module — v1 Specification

**Skill Name:** `crypto-signal-execution`
**Version:** 0.1.0 (design / pre-implementation)
**Sibling Skill:** `morning-bias` (SPX 0DTE) — same risk-discipline lineage, independent runtime
**Author:** Yasir A.
**Status:** Draft — pending compliance review
**Last Updated:** 2026-05-28

---

## 1. Purpose & Scope

The Crypto Signal Execution Module is a manually-invoked Claude skill that turns
freeform third-party trading signals (e.g. a Telegram or Discord post the owner
follows as a subscriber) into a validated, structured **manual-execution trade
ticket** for the owner's own broker. The owner reads the card, decides, and
clicks the trade himself.

This skill is **not** an automated trading system. It is a structured
note-taking + risk-check assistant for a single human operator.

### 1.1 What this skill IS
- A paste-in normalizer for crypto trading signals authored by a third party
- A defined-risk validator (7-point pre-trade check)
- A manual-execution checklist generator with broker-specific click steps
- A logger for every signal seen and every owner decision taken
- An end-of-day P&L tracker for paper-trade outcomes

### 1.2 What this skill IS NOT
- Not an order router. It will never call a broker trading API.
- Not a wallet. It will never hold keys, sign transactions, or move assets.
- Not investment advice. It will never tell the owner to take a trade.
- Not a republisher. It will never forward the source channel's signals to anyone.
- Not a compensation engine. No money flows in or out based on signal outcomes.

---

## 2. Operating Context

- **Owner:** single individual (Yasir), currently on unemployment benefits.
- **Capital at risk:** paper-trade only by default, $1,000 nominal per-signal
  risk budget for sizing math. Live capital usage requires explicit per-signal
  owner confirmation and is logged separately.
- **Signal origin:** third-party Telegram/Discord channels the owner subscribes
  to as a follower. The owner is not the signal author and does not redistribute.
- **Invocation:** manual. The owner pastes signal text into Claude and asks
  the skill to validate. No cron, no webhook, no auto-poll.
- **Broker:** configurable. v1 targets retail spot/perp venues with browser
  trade tickets — Coinbase Advanced, Kraken Pro, Binance.US (where lawful for
  owner's jurisdiction). The skill never authenticates to the broker.

---

## 3. Architecture (Text Diagram)

```
+--------------------------------------------------------------------+
|                       OWNER (human-in-the-loop)                    |
|  - Receives signal from third-party channel                        |
|  - Pastes raw text into Claude conversation                        |
|  - Reads execution card, makes final decision                      |
|  - Clicks trade in broker UI (or skips)                            |
+----------------------------+---------------------------------------+
                             | paste
                             v
+--------------------------------------------------------------------+
|              CRYPTO-SIGNAL-EXECUTION  (this skill)                 |
|                                                                    |
|   [ 1. PARSER ]                                                    |
|     - regex + LLM normalization of freeform text                   |
|     - extracts: asset, side, entry, SL, TP, leverage hint          |
|                                                                    |
|   [ 2. ENRICHER ]   --read-only-->  Coingecko / CoinAPI public     |
|     - current spot price                                           |
|     - 24h vol, funding rate (perp), liquidity flag                 |
|                                                                    |
|   [ 3. RISK CHECK ENGINE ]  (7-point — see Sec 6)                  |
|     - returns PASS / WARN / FAIL per rule                          |
|                                                                    |
|   [ 4. SIZER ]                                                     |
|     - position size from $1000 risk budget and SL distance         |
|                                                                    |
|   [ 5. CARD RENDERER ]                                             |
|     - human-readable execution card                                |
|     - broker-specific click steps                                  |
|     - copy-paste log line                                          |
|                                                                    |
|   [ 6. LEDGER WRITER ]  --append-->  crypto/ledger/signals.csv     |
|     - every paste logged, regardless of outcome                    |
|                                                                    |
|   [ 7. EOD P&L TRACKER ]  (separate invocation)                    |
|     - mark-to-market open paper trades                             |
|     - append --> crypto/ledger/paper-pnl-crypto.csv                |
+--------------------------------------------------------------------+
                             |
                             v
                  No outbound order. No wallet write.
                  Only file writes (local) + read-only HTTP.
```

---

## 4. File Layout

```
crypto/
  supported.yaml              # whitelisted assets + tick/lot rules
  channels.yaml               # approved signal-source channels
  brokers.yaml                # broker UI click-step templates
  config.yaml                 # global risk caps, budgets, env keys
  ledger/
    signals.csv               # every signal seen + owner decision
    paper-pnl-crypto.csv      # EOD mark-to-market for open paper trades
    closed-trades.csv         # archived realized P&L
  cards/
    YYYY-MM-DD-HHMMSS.md      # rendered execution cards (audit trail)
  audit/
    CRYPTO-AUDIT-MEMO.md      # FUTURE — controls memo, see Sec 12
```

---

## 5. Signal Parser — Input Formats

The parser must handle freeform paste. Examples it must normalize:

| Raw paste | Normalized fields |
|---|---|
| `Long BTC at 67k SL 65k TP 70k` | asset=BTC, side=LONG, entry=67000, sl=65000, tp=70000 |
| `Short ETH-PERP entry 3450 exit 3380` | asset=ETH, side=SHORT, venue=PERP, entry=3450, tp=3380, sl=MISSING |
| `SOL long 145-148 zone, stop 140, targets 155/162` | asset=SOL, side=LONG, entry_low=145, entry_high=148, sl=140, tp1=155, tp2=162 |
| `BTC scalp 67.2k SL 66.8 TP 68 RR ~2` | asset=BTC, side=LONG (inferred), entry=67200, sl=66800, tp=68000 |

**Parser rules:**
- Side defaulted to LONG only if direction words ("long", "buy", "bull",
  upward arrow emoji) appear. Otherwise the field is `UNKNOWN` and the signal
  fails Rule 1.
- Numbers ending in `k` expand to ×1000; `m` to ×1_000_000.
- Multi-target signals (TP1/TP2) keep all targets; RR is computed against TP1.
- Entry zones become a midpoint for sizing; both bounds preserved in ledger.
- If SL is missing, the signal is rejected at parse time. No synthetic stops.

---

## 6. The 7-Point Risk Check

Each rule returns `PASS`, `WARN`, or `FAIL`. Any `FAIL` blocks the execution
card from rendering (the skill still renders a "REJECTED — reason" summary).
Two or more `WARN` results downgrade the card to "REVIEW ONLY — do not click."

### Rule 1 — Asset Allow-List
- **Check:** parsed asset symbol is in `crypto/supported.yaml`.
- **Rationale:** keeps the surface narrow. Penny-cap tokens, memecoins, and
  newly-listed assets carry liquidation and rug-pull risk disproportionate to
  retail edge. The allow-list is owner-curated and version-controlled.
- **Default list:** BTC, ETH, SOL, AVAX, LINK, MATIC, ARB, OP.
- **FAIL action:** card not rendered. Signal logged with reason
  `asset-not-supported`.

### Rule 2 — Risk:Reward Ratio ≥ 1.5
- **Check:** `RR = |TP - entry| / |entry - SL| >= 1.5`.
- **Rationale:** defined-risk discipline. A trader with 50% hit rate needs
  RR > 1.0 to break even after fees and slippage; 1.5 is a sane minimum cushion.
- **FAIL action:** card not rendered. Logged as `rr-too-low`.

### Rule 3 — Stop-Loss Within 5% of Entry
- **Check:** `|entry - SL| / entry <= 0.05`.
- **Rationale:** caps tail-risk per trade. Wider stops on volatile crypto
  invite blowup positions where one bad fill consumes the daily budget.
  This rule is the single biggest defense against revenge-sizing.
- **FAIL action:** card not rendered. Logged as `stop-too-wide`.

### Rule 4 — Position Size ≤ 5% of Stated Portfolio
- **Check:** computed notional from $1000 risk budget and SL distance is
  ≤ 5% of `config.portfolio_notional`.
- **Rationale:** concentration cap. Even a perfectly-priced signal should not
  put more than a small fraction of net worth on a single ticket.
- **FAIL action:** card downgraded to REVIEW ONLY. Logged as `size-cap-hit`.

### Rule 5 — Funding Rate Not Extreme (perps only)
- **Check:** absolute funding rate < 0.05% per 8h window (placeholder
  threshold — to be tuned per asset). Source: read-only public exchange API.
  v1 stub returns `UNKNOWN` and emits a WARN.
- **Rationale:** extreme funding signals crowded directional positioning.
  Entering with the crowd at peak funding is a known liquidation trap.
- **FAIL action:** WARN by default in v1. Becomes FAIL once data wiring is live.

### Rule 6 — Source Channel Approved
- **Check:** the channel the signal came from is listed in
  `crypto/channels.yaml` with `status: approved`. Owner must state the source
  channel when pasting; the skill prompts if missing.
- **Rationale:** prevents random forwarded screenshots, scam channels, and
  pump-coordinator rooms from entering the pipeline. Ethical hygiene: only
  signals from sources the owner has independently evaluated.
- **FAIL action:** card not rendered. Logged as `channel-not-approved`.

### Rule 7 — Daily Trade Count Within Limit
- **Check:** count of signals with action ∈ {`paper-executed`, `live-executed`}
  in `signals.csv` for today's date < 3.
- **Rationale:** behavioral guardrail. Overtrading is the dominant
  P&L destroyer for discretionary retail. Hard cap protects the owner from
  himself, especially on a tilt day.
- **FAIL action:** card not rendered, signal still logged with action
  `daily-limit-hit`.

---

## 7. Manual Execution Card — Output Format

```
================ CRYPTO MANUAL EXECUTION CARD ================
Signal ID    : CRY-20260528-001
Source       : @cryptodesk_alpha (Telegram, approved)
Received     : 2026-05-28 14:22:07 ET
Asset        : ETH        Side: LONG       Venue: SPOT
Entry zone   : 3,450 - 3,460      (mid 3,455)
Stop loss    : 3,380              (-2.17% from mid)
Take profit  : 3,580              (+3.62% from mid)
Risk:reward  : 1.67  [PASS]
Spot now     : 3,452              (Coingecko, 14:21:55 ET)

Sizing (paper, $1000 risk):
  Risk per unit : $75 (entry-mid - SL)
  Units        : 13.33 ETH-notional → rounded 13.3
  Notional     : ~$45,952
  % of portfolio: 4.6%   [PASS]

7-POINT RISK CHECK
  1. Asset allow-list .......... PASS
  2. RR >= 1.5 ................. PASS (1.67)
  3. SL within 5% .............. PASS (2.17%)
  4. Size <= 5% portfolio ...... PASS (4.6%)
  5. Funding not extreme ....... WARN (data stub)
  6. Channel approved .......... PASS
  7. Daily count (1/3) ......... PASS

OVERALL: REVIEW & EXECUTE (1 WARN)

------- MANUAL CLICK STEPS (Coinbase Advanced) -------
1. Open https://www.coinbase.com/advanced-trade/spot/ETH-USD
2. Order panel → BUY tab
3. Order type → LIMIT
4. Limit price: 3,455.00
5. Amount (ETH): 13.3
6. Time in force: GTC
7. Review → confirm price and total
8. Place order
9. Open Orders tab → confirm working
10. Set TP exit: SELL LIMIT 3,580.00 for 13.3 ETH
11. Set SL exit: SELL STOP 3,380.00 trigger, MARKET fill

------- COPY-PASTE LOG LINE -------
2026-05-28,ETH,LONG,3455,3380,3580,13.3,paper,CRY-20260528-001

REMINDERS
- This is a manual checklist, not advice.
- You are the decision-maker; do not click if anything looks wrong.
- After execution, run `/crypto-log CRY-20260528-001 executed` so the
  ledger is updated.
==================================================================
```

---

## 8. Ledger Schemas

### 8.1 `crypto/ledger/signals.csv`

| Column | Type | Notes |
|---|---|---|
| signal_id | string | `CRY-YYYYMMDD-NNN` |
| received_ts | ISO8601 | when the paste landed |
| source_channel | string | matches `channels.yaml` key |
| raw_text | string | exact paste, quote-escaped |
| asset | string | parsed |
| side | enum | LONG / SHORT / UNKNOWN |
| entry_low | float | nullable |
| entry_high | float | nullable |
| stop_loss | float | |
| take_profit | float | TP1 |
| extra_targets | string | JSON array of TP2..TPn |
| rr | float | computed |
| size_units | float | from sizer |
| size_notional_usd | float | |
| rule_1..rule_7 | enum | PASS / WARN / FAIL |
| overall | enum | RENDERED / REVIEW-ONLY / REJECTED |
| owner_action | enum | paper-executed / live-executed / skipped-rule-violation / skipped-owner-judgment / queued |
| owner_note | string | freeform |

### 8.2 `crypto/ledger/paper-pnl-crypto.csv`

| Column | Type | Notes |
|---|---|---|
| eod_date | date | trading day close ET |
| signal_id | string | FK to signals.csv |
| asset | string | |
| side | enum | |
| entry_fill | float | mid of entry zone for paper |
| mark_price | float | spot at 16:00 ET |
| units | float | |
| unrealized_pnl_usd | float | |
| days_open | int | |
| status | enum | OPEN / TP-HIT / SL-HIT / EXPIRED |

---

## 9. Configuration Files

### 9.1 `crypto/supported.yaml`
```yaml
assets:
  BTC: { name: Bitcoin, venues: [spot, perp], tick: 0.01, min_size: 0.0001 }
  ETH: { name: Ether,   venues: [spot, perp], tick: 0.01, min_size: 0.001 }
  SOL: { name: Solana,  venues: [spot, perp], tick: 0.01, min_size: 0.01 }
  # ... owner-curated
```

### 9.2 `crypto/channels.yaml` (approved-channels schema)
```yaml
channels:
  - key: cryptodesk_alpha
    platform: telegram
    handle: "@cryptodesk_alpha"
    operator: "anonymized handle / no PII"
    status: approved        # approved | trial | revoked
    added_on: 2026-04-01
    track_record_window_days: 60
    track_record_winrate: 0.58
    notes: |
      Owner subscribed since Apr 2026. No paid relationship.
      Owner does not redistribute their signals.
    paid_subscription: false
    affiliate_relationship: false
  - key: eth_swings_room
    platform: discord
    handle: "eth-swings#general"
    status: trial
    added_on: 2026-05-10
    notes: "On probation; signals run paper-only until 30 paper trades complete."
```

**Channel onboarding requirement:** before a channel reaches `approved`, the
owner must record 30 paper trades from it and review hit-rate.

### 9.3 `crypto/config.yaml`
```yaml
portfolio_notional: 25000        # owner-declared, self-attested
per_signal_risk_budget: 1000     # paper default
max_size_pct: 0.05
min_rr: 1.5
max_sl_pct: 0.05
max_daily_trades: 3
max_leverage: 3                  # hard ceiling; perp signals above this are rejected
default_broker: coinbase_advanced
price_data:
  provider: coingecko
  endpoint: https://api.coingecko.com/api/v3
  api_key_env: COINGECKO_API_KEY   # read-only; absent ok for free tier
```

---

## 10. Glossary (for non-traders)

- **Entry:** the price at which you intend to open the position.
- **Stop-Loss (SL):** the price at which you exit at a loss to cap downside.
  Pre-committed, not negotiable mid-trade.
- **Take-Profit (TP):** the price at which you exit at a gain.
- **Risk:Reward (RR):** ratio of potential gain to potential loss. RR=2 means
  you stand to make twice what you risk if the trade reaches TP and the SL
  holds.
- **Funding Rate:** on perpetual futures, the periodic payment between long
  and short holders that pulls the perp price toward spot. Positive funding
  means longs pay shorts; extreme values flag crowded positioning.
- **Perps / Perpetual:** futures contracts with no expiry. Common on crypto
  venues. Carry liquidation risk, especially with leverage.
- **Notional:** total dollar size of the position, not the margin posted.
- **Tilt:** the emotional state after a loss where the next trade is taken
  for revenge rather than reason. The daily-count cap exists for this.

---

## 11. Safety Boundaries — What the Skill Will NEVER Do

The following are hard rules. Any future PR that loosens them must update the
audit memo (Sec 12) and require an explicit out-of-band owner sign-off.

1. **No wallet operations.** The skill does not generate, hold, import,
   reference, or sign with any private key, seed phrase, or wallet file.
2. **No trading API keys.** The skill never stores or uses a broker API key
   with order-placement scope. Read-only price keys only.
3. **No order routing.** No code path may construct or POST an order payload
   to any exchange, DEX, aggregator, or bridge.
4. **No leverage above 3x.** Signals implying >3x leverage are rejected at
   parse time. The skill will not render execution cards that require margin
   beyond `config.max_leverage`.
5. **No unapproved channels.** Signals from a channel not in `channels.yaml`
   with `status: approved` are rejected. The owner cannot inline-override.
6. **No signal redistribution.** The skill does not post, forward, share, or
   syndicate the source channel's signals to any third party or surface
   outside the owner's local environment.
7. **No advice framing.** Output never uses imperative language ("buy now",
   "go long here"). Output uses descriptive language ("the signal proposes
   a long at X; if you choose to execute, the steps are...").
8. **No compensation flows.** The skill takes no fee, kickback, affiliate
   commission, or referral payment tied to whether the owner trades.
9. **No automation.** The skill is invoked manually. It does not subscribe
   to channels, scrape feeds, or run on a timer for signal ingestion.
10. **No retention of third-party PII.** The `channels.yaml` `operator`
    field stores only the public handle; no real names, emails, or contact
    info for the channel author.

---

## 12. Audit Memo Controls Mapping

The skill inherits the control framework from the SPX 0DTE audit memo
(C-01..C-10). The future `crypto/audit/CRYPTO-AUDIT-MEMO.md` will own the
authoritative mapping; v1 placement below.

| Control | SPX Origin | Crypto Application |
|---|---|---|
| **C-01 No Autonomous Execution** | Skill never places SPX orders | Skill never places crypto orders. Sec 11.3 enforces. |
| **C-02 Defined-Risk Only** | SPX strategy defined-risk verticals | Crypto SL is mandatory; signals without SL rejected (Sec 5). |
| **C-03 Daily Loss / Count Cap** | SPX 1 trade/day | Crypto max 3 trades/day (Rule 7). |
| **C-04 Source Disclosure** | Bias model inputs documented | Source channel logged per signal; `channels.yaml` versioned. |
| **C-05 No Advice to Third Parties** | SPX dashboard non-advice disclaimer | Same disclaimer on every rendered card (Sec 13). |
| **C-06 Ledger Immutability** | SPX P&L ledger append-only | `signals.csv` and `paper-pnl-crypto.csv` append-only; row updates write a new row with `correction_of` field. |
| **C-07 Read-Only Data Access** | SPX market data read-only | Crypto price/funding data via read-only public endpoints. No write scopes. |
| **C-08 No PII Retention** | SPX has no user data | Channel operator field stores public handle only (Sec 11.10). |
| **C-09 Manual Invocation Only** | SPX morning skill is human-triggered | Crypto skill manual-only; no cron, no webhook (Sec 11.9). |
| **C-10 Audit Memo Co-Located** | SPX memo in repo | Crypto memo at `crypto/audit/CRYPTO-AUDIT-MEMO.md` (TBD). |

The future audit memo must also document: (a) data-provider terms of service
compliance, (b) the owner's jurisdiction and applicable retail trading rules,
(c) the unemployment-benefits posture — paper trading is not earned income but
the owner should consult state guidance before treating any realized crypto
gains as taxable trading activity that could affect benefits eligibility.

---

## 13. Ethical-Use Clause

This skill is built for a single owner-operator. It is not licensed, sold, or
shared. If the owner shows output to a friend, posts a screenshot, or
otherwise exposes a rendered card:

- The card is **not** advice. It is the owner's personal pre-trade checklist.
- No reader should act on it. Anyone acting on a forwarded card does so
  without the owner's recommendation and without any duty of care from the
  owner or from this software.
- No compensation may be solicited or accepted in exchange for showing the
  card, the channel sources, or the ledger.
- If the owner ever wants to share systematically (newsletter, paid group,
  etc.), this skill is the wrong tool — that use case requires a separate
  compliance review including investment-adviser registration analysis.

Every rendered card carries the footer:

> *This card is a personal pre-trade checklist for the owner. It is not
> investment advice. Past signal performance does not predict future results.
> Crypto markets carry total-loss risk.*

---

## 14. End-of-Day P&L Tracker

Separate manual invocation: `/crypto-eod`. Steps:

1. Read all `signals.csv` rows with `owner_action ∈ {paper-executed, live-executed}`
   and no row in `closed-trades.csv` for that signal_id.
2. For each open position, fetch spot at 16:00 ET (or owner-specified
   cutoff for 24/7 markets).
3. Compute unrealized P&L: `(mark - entry_fill) * units * side_sign`.
4. Detect TP / SL hits using intraday OHLC for the asset (read-only API).
5. Append a row to `paper-pnl-crypto.csv` per open position.
6. Move TP-HIT and SL-HIT positions to `closed-trades.csv` with realized P&L.
7. Print weekly summary: net P&L, win-rate by source channel, drawdown.

---

## 15. Failure Modes & Owner Prompts

| Failure | Skill response |
|---|---|
| Source channel not specified | Prompt: "Which channel did this come from? Type the key from `channels.yaml`." |
| Asset not on allow-list | Print rejection, log, suggest the owner review `supported.yaml`. |
| SL missing | Reject; explain that synthetic stops are forbidden (Sec 6 Rule 3 rationale). |
| Price API down | Render card with `spot_now=UNAVAILABLE` and force REVIEW-ONLY status. |
| Daily cap hit | Reject with cooling-off note; do not allow override. |
| Owner says "execute" but Rule 4 was WARN | Confirm twice; require typed "I accept" before logging as executed. |

---

## 16. v1 Open Items (Non-Blocking)

- Funding-rate data wiring (currently stub).
- Multi-broker click templates (v1 ships Coinbase Advanced + Kraken Pro).
- Owner-portfolio attestation refresh cadence (currently static in config).
- Per-channel auto-revocation if rolling 30-trade hit rate falls below 0.40.
- TradingView chart link auto-embed in the card.

---

## 17. References

- Sibling skill: `morning-bias` (SPX 0DTE) — same risk lineage.
- Audit memo (SPX): `spx/v5/repo/audit/AUDIT-MEMO.md`.
- Future audit memo (crypto): `crypto/audit/CRYPTO-AUDIT-MEMO.md`.

---

*End of v1 specification.*
