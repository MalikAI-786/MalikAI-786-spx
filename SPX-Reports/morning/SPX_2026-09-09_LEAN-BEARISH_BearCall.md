---
source: gmail
message_id: 1a086458f15f062e
thread_id: 1a086458f15f062e
date: 2026-09-09
bias: LEAN-BEARISH
action: BearCall
composite: -0.68
subject: "SPX 0DTE — 2026-09-09 — LEAN BEARISH (-0.68) — Bear Call 7725/7765, enter 9:45 ET"
sender: yasiramalik@gmail.com
---

# SPX 0DTE — 2026-09-09 — LEAN BEARISH (-0.68)

## Trade plan
- **Bias:** LEAN BEARISH (composite -0.68, moderate conviction)
- **Structure:** Bear Call Spread (defined risk)
- **Strikes:** Short 7725 / Long 7765 (width 40)
- **Credit:** target ~8.0 | **Max loss:** ~32 | **Size:** 1/2 unit (lean)
- **Entry:** 09:45 ET, after the open settles
- **Profit target:** ~50% of credit (~4.0) → close / GTC
- **Stop/invalidation:** SPX sustained above ~7,725 → close the trade

## How to place it
**Option Alpha (primary, automated):**
1. Open Option Alpha → Bots → the SPX 0DTE defined-risk bot.
2. New position → SPX → today's expiration (0DTE).
3. Bear Call = sell the 7725 call, buy the 7765 call.
4. Enter both strikes; set limit ≈ 8.0 credit.
5. Quantity = ½ unit. Set profit-taking ≈ 50% and the stop at SPX > 7,725.
6. Confirm max loss ≈ 32/contract, submit at 09:45 ET.

**tastytrade (backup, manual):**
1. Watchlist → SPX → Trade → today's 0DTE expiration.
2. Sell the 7725 call, buy the 7765 call (vertical).
3. Net credit limit ≈ 8.0; defined risk only.
4. Quantity = ½ unit; confirm buying-power reduction ≈ max loss; send.

Defined-risk only. Place at your own discretion.

## Why
- Direct US-Iran military escalation overnight: the US destroyed five Iranian oil tankers; Iran retaliated with missile strikes on the US base at Al Azraq, Jordan, and reportedly targeted two US Navy destroyers — the Strait of Hormuz remains effectively closed (day 192).
- Oil holding near $100: Brent ~$99.3-100.7, WTI ~$94-95, up another 1%+ overnight on top of yesterday's surge — a direct hit to consumer/input costs ahead of Thursday's PPI and Friday's CPI.
- Futures broadly soft into the open: Dow -0.6%, S&P -0.3%, Nasdaq -0.4% — no mega-cap tech offset today, unlike yesterday.
- 10-year yield sitting at ~4.79-4.80%, highest since October 2023, as oil-driven inflation risk keeps the rate backdrop unfriendly.
- VIX up again to 15.72 (+2.75%) — sentiment continuing to deteriorate but still shy of a panic reading.

## Bucket scores
| Bucket | Score | Tag | Rationale |
|--------|-------|-----|-----------|
| Futures | -0.7 | TRUSTED | Dow -0.6%, S&P -0.3%, Nasdaq -0.4% — broad-based soft open, no tech offset |
| Macro | -0.3 | TRUSTED | No major US data today; mild negative from oil-driven inflation overhang into Thu PPI/Fri CPI |
| News | -1.4 | TRUSTED | US-Iran military escalation: tanker strikes, Jordan base hit, Hormuz still closed, oil >$99 |
| International | -0.3 | WRONG-WAY | Mixed/mild negative: Nikkei +0.04%, Hang Seng -0.15%, DAX -0.67% at open, FTSE flat |
| Sentiment | -0.6 | TRUSTED | VIX 15.72, +2.75% — rising fear, still below panic levels |

## Composite & calibration
| Bucket | Final weight | Contribution |
|--------|--------------|--------------|
| Futures | 32.7% | -0.229 |
| Macro | 21.8% | -0.065 |
| News | 16.3% | -0.229 |
| International | 7.4% | -0.022 |
| Sentiment | 21.8% | -0.131 |
| **Composite** | **100%** | **-0.68 → LEAN BEARISH** |

Independent recompute matched within tolerance. Yesterday's call was correct, so Futures/Macro/News/Sentiment moved WEAK → TRUSTED (×1.10); International stays WRONG-WAY (×0.50) after missing again. No lessons re-weighting needed (9/8 was a hit).

## Yesterday's recap
Predicted LEAN BEARISH (-0.58) on 9/8. Actual: SPX closed 7,673.52, -0.58% — direction matched. **Correct call.** Oil/Iran escalation and a soft rate backdrop played out as expected.

## SPX levels
- Prior close (9/8): 7,673.52 (-0.58%)
- Premarket-implied open (ES-based): ~7,650
- VIX: 15.72 (+2.75%)
- 1-sigma range: ~7,574 - 7,726
- Key resistance: 7,674 (prior close) / 7,725 (+1σ, short strike) / 7,765 (+1.5σ)
- Key support: 7,650 (implied open) / 7,600 / 7,574 (-1σ)

## Catalysts today
- All session — US-Iran military escalation: US struck five Iranian oil tankers; Iran hit the US base at Al Azraq, Jordan and reportedly targeted two US Navy destroyers; Strait of Hormuz remains closed.
- All session — Oil near $100 (Brent ~$99-101, WTI ~$94-95), continuing to pressure the rate/inflation backdrop.
- No major US economic release this morning — light calendar day.
- Thu 9/10: PPI. Fri 9/11: CPI — binary risk later this week; size down anything held into it.

## Rolling synthetic P&L
| Window | W/L/SD | Win rate (decided) |
|--------|--------|--------------------|
| Aug 14 – Sep 8 | 5W / 1L / 2SD of 8 scored | 83% |

Synthetic/illustrative paper-trading journal, not a real track record.

## Notes
Educational paper-trading journal. Not investment advice. Defined-risk only; you are responsible for your own trades. 0DTE options are high-risk.

System notes: Dashboard not refreshed today (local git repo needs repair — see FIX-DASHBOARD-GIT.md in the repo).

## Sidecar
`SPX 0DTE — 2026-09-09 — LEAN BEARISH (-0.68) — Bear Call 7725/7765, enter 9:45 ET` → `SPX_2026-09-09_LEAN-BEARISH_BearCall.md` → thread `1a086458f15f062e`
