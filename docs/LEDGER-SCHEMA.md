# Ledger Schema — SPX 0DTE v5.0

**This entire system is a SYNTHETIC PAPER-TRADE LEDGER. Real money is never moved. Educational only. Not investment advice.**

This document describes every column in the two CSV ledger files, the invariants the system enforces, and how to read the rolling statistics.

- All timestamps are **America/New_York**.
- All money is **USD**.
- One SPX option contract has a $100 multiplier (1.00 of premium = $100).

---

## Files

| File | Purpose | Written by | Read by |
|---|---|---|---|
| `ledger/paper-pnl.csv` | One row per trading day with the day's recommended structure and the synthetic close-of-day P&L. | `scripts/close_track.py` | `scripts/lessons_learned.py`, dashboard, morning.py step 1 |
| `ledger/morning-signals.csv` | One row per trading day with the morning bias score, bucket contributions, and calibration pattern. | `scripts/morning.py` (step 4) | `scripts/lessons_learned.py`, dashboard |
| `ledger/lessons-{date}.md` | Rolling 10-day digest fed back into tomorrow's morning bias step 1. | `scripts/lessons_learned.py` | `scripts/morning.py` |

---

## `ledger/paper-pnl.csv` columns

| # | Column | Type | Units | Description |
|---|---|---|---|---|
| 1 | `date` | `YYYY-MM-DD` | ET trading date | Primary key. One row per date. |
| 2 | `day_of_week` | string | — | `Monday`..`Friday`. Derived from `date`. |
| 3 | `bias_score` | float | — | Composite bias score from morning.py. Negative = bearish, positive = bullish, magnitude = conviction (~0..5). |
| 4 | `bias_label` | enum | — | `bullish` / `neutral_bull` / `neutral` / `neutral_bear` / `bearish`. |
| 5 | `confidence` | enum | — | `low` / `medium` / `high`. Derived from bucket alignment + calibration overlay. |
| 6 | `stand_down` | bool | `true`/`false` | `true` means no trade was recommended. P&L will be `0`. |
| 7 | `structure` | enum | — | `put_credit_spread` / `call_credit_spread` / `put_debit_spread` / `call_debit_spread` / `stand_down`. |
| 8 | `strike_short` | float or empty | SPX points | Short leg strike. Empty on stand-down. |
| 9 | `strike_long` | float or empty | SPX points | Long leg strike. Empty on stand-down. |
| 10 | `credit_or_debit` | float or empty | option points | Signed: `+` = net credit received at open, `-` = net debit paid. Multiply by $100 for dollars. |
| 11 | `max_risk` | float | USD | Worst-case dollar loss for a 1-lot of the structure. `0` on stand-down. |
| 12 | `max_reward` | float | USD | Best-case dollar gain for a 1-lot. `0` on stand-down. |
| 13 | `spx_open_945` | float | SPX points | SPX cash index at 9:45 ET (the moment the bot would have entered). |
| 14 | `spx_close` | float | SPX points | SPX cash index at 4:00 ET. |
| 15 | `exit_price` | float or empty | option points | Intrinsic value of the spread at 4:00 ET. Empty on stand-down. |
| 16 | `trusted_bot_pnl` | float | USD | The headline number. SYNTHETIC. See "P&L formula" below. |
| 17 | `trusted_bot_pnl_pct_of_max_risk` | float | percent | `100 * trusted_bot_pnl / max_risk`. `0` on stand-down. |
| 18 | `running_total` | float | USD | Cumulative `trusted_bot_pnl` from the first row through this row. Recomputed every append; never edited in place. |
| 19 | `running_winrate` | float | 0.0..1.0 | Wins / active-trade count. **Excludes stand-downs.** |
| 20 | `morning_commit_hash` | string | 7-char git sha | Commit hash of the morning report this row came from. Provenance. |
| 21 | `close_commit_hash` | string | 7-char git sha | Commit hash from `close_track.py`. Empty until the close commit lands. |
| 22 | `notes` | string | free text | Optional human commentary. Commas/newlines auto-quoted. |

### P&L formula — what `trusted_bot_pnl` actually means

`trusted_bot_pnl` is what a **fully-trusted, perfectly-disciplined automated bot** would have realized **IF** it had executed the recommended structure as a 1-lot, sized at the morning's stated max risk, and exited at the 4:00 ET cash close. Stand-down days are `$0` (the bot does nothing — neither makes nor loses money).

Per-structure formula (each leg's value at 4:00 = max(0, intrinsic)):

| Structure | P&L (option points) |
|---|---|
| `put_credit_spread` | `credit_received - max(0, short_strike - spx_close) + max(0, long_strike - spx_close)` |
| `call_credit_spread` | `credit_received - max(0, spx_close - short_strike) + max(0, spx_close - long_strike)` |
| `put_debit_spread` | `max(0, long_strike - spx_close) - max(0, short_strike - spx_close) - debit_paid` |
| `call_debit_spread` | `max(0, spx_close - long_strike) - max(0, spx_close - short_strike) - debit_paid` |

Then `trusted_bot_pnl = pnl_points * 100`.

**The ledger does not account for** slippage, commissions, assignment risk, gap risk overnight, partial fills, or behavioral slippage from a human operator. This is deliberate: the ledger measures **signal quality**, not execution quality. Real-world results will be worse.

---

## `ledger/morning-signals.csv` columns

| # | Column | Type | Description |
|---|---|---|---|
| 1 | `date` | `YYYY-MM-DD` | Trading date. |
| 2 | `score` | float | Composite bias score (matches `bias_score` in paper-pnl). |
| 3 | `futures` | float | Futures bucket contribution to score. Sign = direction, magnitude = strength. |
| 4 | `macro` | float | Macro bucket contribution. |
| 5 | `news` | float | News bucket contribution. |
| 6 | `intl` | float | International session bucket contribution. |
| 7 | `sentiment` | float | Sentiment bucket contribution. |
| 8 | `confidence` | enum | `low` / `medium` / `high`. |
| 9 | `bucket_span` | float | `max(bucket) - min(bucket)`. High span = disagreement among buckets. |
| 10 | `calibration_pattern` | string | Tag for the recurring pattern this morning matched (e.g. `futures_led_quiet_macro`, `mixed_signals_low_conviction`, `broad_alignment_high_conviction`). Free-form but should be stable across days. |
| 11 | `stand_down` | bool | Matches paper-pnl. |
| 12 | `morning_commit_hash` | string | 7-char git sha. |

The five buckets sum (with weights) to `score`. `lessons_learned.py` joins `morning-signals.csv` to `paper-pnl.csv` on `date` to compute per-bucket hit-rates.

---

## Invariants

The system enforces the following invariants. Violations abort the run.

1. **Append-only.** `close_track.py` reads the existing ledger, snapshots its SHA-256, writes the new file with the prior rows + one new row, then re-reads and re-snapshots the prior-rows prefix. The prefix hash MUST equal the pre-write snapshot. If not, the script aborts and instructs the operator to restore from git. Implemented in `scripts/close_track.py::append_ledger_row`.
2. **Idempotent.** `close_track.py` refuses to append if a row already exists for the target date. Re-running the same day requires manual deletion of the prior row (and a documented reason in `notes`).
3. **Atomic writes.** All file writes use `tempfile.mkstemp` + `os.replace` so a crashed run never produces a half-written CSV.
4. **One row per date.** The `date` column is the primary key. `preflight.sh` check #2 enforces this from the morning side too — morning.py cannot start if today already has a row.
5. **Running stats recomputed, never amended.** `running_total` and `running_winrate` are recomputed from the full ledger on every append. They are derived columns, not inputs. If you back-edit an old row, the next append will silently correct downstream totals (this is why back-editing requires a `notes` entry and a new git commit).
6. **Stand-downs are `$0`, not blank.** A stand-down day still gets a row. It contributes `0` to `running_total` and is excluded from `running_winrate`.
7. **Commit hashes are provenance.** Every row references the morning commit and the close commit that produced it. To audit "why did the bot recommend X on date Y", `git show <morning_commit_hash>` retrieves the exact morning report.
8. **Real money never moved.** Every Python file in this system starts with the banner `# SYNTHETIC PAPER-TRADE LEDGER. Real money never moved. Educational only. Not investment advice.`

---

## Rolling statistics — how to read them

- **Cumulative P&L** is the sum of `trusted_bot_pnl` from row 1 to the row in question. Strictly synthetic. A real account with the same signals would underperform this number.
- **Win-rate** counts a "win" as `trusted_bot_pnl > 0`. Breakeven days (exactly `$0` on a non-stand-down) are losses. Stand-downs are excluded from the denominator.
- **Max drawdown** (in `lessons-{date}.md`) is the largest peak-to-trough decline in `running_total` across the window.
- **Longest losing streak** counts consecutive trading days with `trusted_bot_pnl < 0`. Stand-downs neither extend nor break the streak (they're `0`, not negative).
- **Bucket hit-rate** in `lessons-{date}.md` is `(days where sign(bucket) == sign(P&L)) / (days where bucket != 0 and not stand-down)`. <40% suggests the bucket is mis-calibrated or its sign is inverted; >70% suggests it's reliable and could be up-weighted.

---

## Day-in-the-life

```
06:30 ET   preflight.sh                      # token perms, no dup row, clean git
06:35 ET   morning.py                        # produces SPX-Reports/morning/{date}.md
                                             # + morning-signals.csv row
                                             # + dashboard/data/{date}.json (morning fields)
09:30 ET   email sent
16:15 ET   close_track.py                    # appends paper-pnl.csv row
                                             # + SPX-Reports/close/{date}.md
                                             # + dashboard/data/{date}.json (close fields)
16:20 ET   lessons_learned.py                # writes ledger/lessons-{date}.md
                                             #   - tomorrow's morning.py reads this first
```

---

## Backfilling and amendments

If you need to amend a historical row (e.g. you discovered the morning report had a typo'd strike), do it in a separate commit with `git commit -m "amend({date}): {one-line reason}"`. The next `close_track.py` run will recompute `running_total` and `running_winrate` downstream automatically. Do not silently edit; the morning_commit_hash / close_commit_hash columns lose provenance.

For backfilling new historical days, run `close_track.py --date YYYY-MM-DD` once per day in chronological order. The idempotency check prevents reprocessing.
