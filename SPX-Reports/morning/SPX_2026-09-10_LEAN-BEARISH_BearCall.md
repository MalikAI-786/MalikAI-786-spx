---
source: gmail
message_id: 1a08b6d5cfe40838
thread_id: 1a08b6d5cfe40838
date: 2026-09-10
bias: LEAN-BEARISH
action: BearCall
composite: -0.42
subject: "SPX 0DTE — 2026-09-10 — LEAN BEARISH (-0.42) — Bear Call 7715/7750, enter 9:45 ET"
sender: yasiramalik@gmail.com
---

# SPX 0DTE — 2026-09-10 — LEAN BEARISH (-0.42)

## Trade plan
- **Bias:** LEAN BEARISH (composite -0.42, moderate conviction)
- **Structure:** Bear Call Spread (defined risk)
- **Strikes:** Short 7715 / Long 7750 (width 35)
- **Credit:** target ~7.0 | **Max loss:** ~28 | **Size:** 1/2 unit (lean)
- **Entry:** 09:45 ET, after the open settles
- **Profit target:** ~50% of credit (~3.5) → close / GTC
- **Stop/invalidation:** SPX sustained above ~7,715 → close the trade

## How to place it
**Option Alpha (primary):**
1. Open Option Alpha → Bots → SPX 0DTE defined-risk bot.
2. New position → SPX → today's expiration (0DTE).
3. Bear Call = sell the 7715 call, buy the 7750 call.
4. Enter both strikes; set limit ≈ 7.0 credit.
5. Quantity = ½ unit. Set profit-taking ≈ 50% and the stop at SPX > 7,715.
6. Confirm max loss ≈ 28/contract, submit at 09:45 ET.

**tastytrade (backup, manual):**
1. Watchlist → SPX → Trade → today's 0DTE expiration.
2. Sell the 7715 call, buy the 7750 call (vertical).
3. Net credit limit ≈ 7.0; defined risk only.
4. Quantity = ½ unit; confirm buying-power reduction ≈ max loss; send.

Defined-risk only. Place at your own discretion.

## Why
- Macro headwind intensifying: 10Y yield ~4.85% (3-year high); CME FedWatch ~60% odds of a Sept hike (not a cut) ahead of the Sept 15-16 FOMC.
- Today's PPI (8:30 ET) is expected hot: consensus +0.4% MoM (prior 0.0%) / +5.3% YoY (prior +4.7%) — a beat hardens hike bets right into the open.
- Oil keeps climbing on the Iran/Hormuz conflict: Brent >$102, a third session of elevated crude adding to inflation pressure.
- International tape leans negative: Asia mostly lower (Nikkei -0.26%, Topix -0.65%), Europe soft premarket after Wednesday's steep selloff (FTSE -1.38%, DAX -1.6%, CAC -2%) on ECB hike expectations.
- Partial offset: futures only mildly mixed (S&P flat, Dow +0.2%, Nasdaq -0.3%) after Trump's overnight $5,000-per-adult "dividend" pledge tied to a GOP midterm win, plus Oracle's AI-signaling earnings today could swing tech sentiment either way — keeps this a LEAN, not a full BEARISH.

## Bucket scores
| Bucket | Score | Tag | Rationale |
|--------|-------|-----|-----------|
| Futures | +0.2 | TRUSTED | S&P futures flat (+0.04%) at 7,646.50; Dow +0.2%; Nasdaq -0.3% (7:42 ET) |
| Macro | -1.3 | TRUSTED | 10Y ~4.85% (3-yr high); ~60% Sept hike odds; hot PPI expected today |
| News | -0.8 | TRUSTED | Iran/Hormuz escalation + Oracle earnings risk outweigh the Trump dividend pledge |
| International | -0.5 | WEAK | Asia mixed-lower; Europe soft premarket after Wednesday's rout |
| Sentiment | -0.3 | TRUSTED | VIX ~14.5, +1.5% on the day, still a low absolute level |

## Composite & calibration
| Bucket | Final weight | Contribution |
|--------|--------------|--------------|
| Futures | 31.1% | +0.062 |
| Macro | 20.7% | -0.249 |
| News | 15.5% | -0.109 |
| International | 12.0% | -0.060 |
| Sentiment | 20.7% | -0.062 |
| **Composite** | **100%** | **-0.42 → LEAN BEARISH** |

Calibration: yesterday's LEAN BEARISH call (-0.68) was correct — SPX closed -0.58%. Futures/Macro/News/Sentiment stay TRUSTED; International's raw also matched the down day, promoted one notch WRONG-WAY → WEAK. No lessons re-weighting needed.

## Yesterday's recap
Predicted (9/9): LEAN BEARISH -0.68, Bear Call 7725/7765.
Actual: SPX closed 7,629.00, -0.58%. Direction matched — correct call, and the short strike (7725) stayed well OTM (full credit kept). Second straight correct call.

## SPX levels
- Prior close (9/9): 7,629.00
- Premarket-implied open: ~7,646 (+0.22%)
- 1-sigma range: 7,576 - 7,716
- Support: 7,629 (pivot), 7,600 (round #), 7,576 (1-sigma low)
- Resistance: 7,650 (near-term), 7,700 (psych), 7,716 (1-sigma high, near short strike)

## Catalysts today
- 8:30 ET — PPI (Aug): consensus +0.4% MoM / +5.3% YoY — binary risk into FOMC
- 8:30 ET — Initial jobless claims
- 10:00 ET — Wholesale trade, NAR existing home sales
- 11:30 ET — Weekly Economic Index
- Today — Oracle (ORCL) earnings, AI-signaling results
- Ongoing — US-Iran/Strait of Hormuz conflict, Brent >$102
- Fri 9/11 — CPI + core CPI — size down into it
- Sept 15-16 — FOMC decision (quiet period since 9/5), ~60% hike odds

## Rolling synthetic P&L
| Window | W/L/SD | Win rate (decided) |
|--------|--------|--------------------|
| Aug 14 – Sep 9 | 6W / 1L / 2SD of 9 scored | ~86% |

Synthetic/illustrative paper-trading journal, not a real tracked record.

## Notes
Educational paper-trading journal. Not investment advice. Defined-risk only; you are responsible for your own trades. 0DTE options are high-risk.

System notes: Dashboard/git still broken (fatal: not a git repository) — report saved directly via file tools, not through git. Needs repair on your Mac (see FIX-DASHBOARD-GIT.md).

## Sidecar
`SPX 0DTE — 2026-09-10 — LEAN BEARISH (-0.42) — Bear Call 7715/7750, enter 9:45 ET` → `SPX_2026-09-10_LEAN-BEARISH_BearCall.md` → thread `1a08b6d5cfe40838`
