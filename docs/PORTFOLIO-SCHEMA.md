# Portfolio Outlook Schema — Tech Sleeve v1.0

**This is an educational outlook model. It is NOT investment advice, NOT a
recommendation, and NOT an instruction to buy, sell, hold, or reallocate
anything. No real money is moved by this system. Past performance does not
indicate future results.**

This document describes the weekly tech-sleeve outlook: what goes in, what
comes out, what is public, and what must never be committed.

- All dates are **America/New_York**.
- The weekly call is scored and recorded **Friday after the close**.
- The ledger is **append-only**, same discipline as `ledger/paper-pnl.csv`.

---

## The privacy line — read this first

`AGENTS.md` safeguard #1 says every file in this repository is public.
Safeguard #3 says personal records and account numbers are never committed.
The owner's JPMorgan holdings are exactly that. So the data is split in two,
and the split is enforced by code, not by care:

| Lives in git (public) | Lives in `private/` (gitignored, never committed) |
|---|---|
| Tickers | Dollar balances |
| Percentage weights | Share counts |
| Contribution **cadence** (`monthly`) | Contribution **amount** |
| Normalized index levels (base 100) | Account numbers, account nicknames |
| Bucket scores, composite, label | Cost basis, realized/unrealized gain |

`portfolio_track.py` never writes a value read from `private/` into any file
under `dashboard/`, `ledger/`, or `portfolio/`. Private figures reach exactly
one destination: the owner-only email draft, which is not committed. If you
extend this script, preserve that property — it is the whole control.

---

## Files

| File | Purpose | Written by | Read by |
|---|---|---|---|
| `portfolio/basket.json` | Basket definition — tickers, weights, benchmark, contribution cadence. | Human (from uploaded statement) | `portfolio_track.py` |
| `analytics/risk.py` | Sharpe, vol, beta, drawdown, correlation. Ported from `A-Whale-Off-the-Port-folio`. | — | `portfolio_track.py` |
| `analytics/montecarlo.py` | Correlated Monte Carlo. Ported from `API/MCForecastTools.py`. | — | `portfolio_track.py` |
| `private/holdings.json` | **Never committed.** Dollar balances and contribution amount. Optional. | Human | `portfolio_track.py` (email only) |
| `ledger/portfolio-signals.csv` | One row per scored week. Append-only. | `portfolio_track.py` | dashboard, calibration |
| `dashboard/data/portfolio.json` | What the Tech Outlook tab renders. Public-safe by construction. | `portfolio_track.py` | `spx_0dte_ai_signal_dashboard.html` |

---

## `portfolio/basket.json`

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Semver of this contract. |
| `basket_id` | string | Stable slug. Used as the ledger's `basket_id`. |
| `status` | enum | `PROVISIONAL_REFERENCE` or `OWNER_CONFIRMED`. |
| `owner_confirmed` | bool | `false` until the owner's real constituents are loaded. |
| `source` | string | Provenance, e.g. `PENDING_UPLOAD`, `jpm-statement-2026-07`. |
| `as_of` | date or null | Date the constituents were accurate. |
| `benchmark` | string | Ticker the basket is scored against. Default `XLK`. |
| `constituents[].ticker` | string | Exchange ticker. |
| `constituents[].weight_pct` | float | Percent of the sleeve. Should sum to ~100. |
| `contribution.cadence` | enum | `weekly` / `biweekly` / `monthly` / `none`. |
| `contribution.assumed_continuing` | bool | Whether the projection assumes contributions continue. |

**The `owner_confirmed` gate.** While `owner_confirmed` is `false`, every
artifact this pipeline writes is stamped `REFERENCE BASKET — not the owner's
holdings`, and the email section says so in its first line. This exists so a
half-configured run can never quietly imply that a generic tech basket is
Yasir's retirement account. Flipping the flag is a deliberate act taken after
loading real constituents.

---

## The five buckets

Each bucket scores to `[-2.0, +2.0]`, mirroring the SPX morning model so the
two systems read the same way. Sign = direction, magnitude = conviction.

| # | Bucket | Weight | What it measures |
|---|---|---|---|
| 1 | `momentum` | 0.30 | Basket's weighted return vs. its own 20-day and 50-day trend. |
| 2 | `breadth` | 0.20 | Share of constituents trading above their own 50-day average. |
| 3 | `rates` | 0.20 | 1-week change in the US 10-year yield, **sign-inverted** — long-duration tech is discounted by the long rate, so rising yields score negative. |
| 4 | `earnings` | 0.15 | Direction of forward-EPS revisions across the basket. |
| 5 | `volatility` | 0.15 | VIX / VXN level and 1-week change. Falling vol from an elevated base scores positive. |

### Abstention is explicit, never silent

A bucket with no usable data returns `null`, **not** `0.0`. A null bucket is
dropped from the composite and the remaining weights are renormalized to sum
to 1.0. The report and the tab both name which buckets abstained.

This mirrors control **C-06** in `scripts/SKILL.md`: a missing input is not
agreement, and it is not neutrality. Scoring an absent bucket as `0.0` would
drag the composite toward the neutral band and manufacture a false
STAND-DOWN — the exact failure the SPX model was audited for.

---

## Composite and label

```
composite = Σ (renormalized_weight_i × score_i)      clipped to [-2.0, +2.0]
```

| Composite | Label |
|---|---|
| `≥ +1.0` | `CONSTRUCTIVE` |
| `+0.3 … +1.0` | `LEAN CONSTRUCTIVE` |
| `-0.3 … +0.3` | `NEUTRAL` |
| `-1.0 … -0.3` | `LEAN DEFENSIVE` |
| `≤ -1.0` | `DEFENSIVE` |

**Confidence** is derived, not asserted:

- `bucket_span = max(scores) - min(scores)` across non-null buckets.
- `high` — span < 1.5 and ≥ 4 buckets scored.
- `medium` — span < 2.5 and ≥ 3 buckets scored.
- `low` — otherwise, or whenever ≥ 2 buckets abstained.

A `low`-confidence week is still recorded. Suppressing low-confidence calls
would bias the ledger toward the model's good weeks — the same
survivorship problem that stand-down rows solve in `paper-pnl.csv`.

---

## `ledger/portfolio-signals.csv` columns

| # | Column | Type | Description |
|---|---|---|---|
| 1 | `week_ending` | `YYYY-MM-DD` | The Friday scored. Primary key. |
| 2 | `basket_id` | string | From `basket.json`. |
| 3 | `owner_confirmed` | bool | Whether this row describes real holdings or the reference basket. |
| 4 | `composite` | float | Composite score, `[-2, +2]`. |
| 5 | `label` | enum | `CONSTRUCTIVE` … `DEFENSIVE`. |
| 6 | `confidence` | enum | `low` / `medium` / `high`. |
| 7 | `momentum` | float or empty | Bucket score. Empty = abstained. |
| 8 | `breadth` | float or empty | Bucket score. |
| 9 | `rates` | float or empty | Bucket score. |
| 10 | `earnings` | float or empty | Bucket score. |
| 11 | `volatility` | float or empty | Bucket score. |
| 12 | `abstained` | string | Semicolon-joined names of null buckets. |
| 13 | `bucket_span` | float | Disagreement measure across scored buckets. |
| 14 | `basket_index` | float | Basket level, base 100 at first ledger row. |
| 15 | `benchmark_index` | float | Benchmark level, base 100 at the same date. |
| 16 | `fwd_1w_basket_pct` | float or empty | **Outcome.** Basket's return the following week. Empty until scored. |
| 17 | `was_directionally_right` | bool or empty | `sign(composite) == sign(fwd_1w_basket_pct)`. Empty until the outcome lands. |
| 18 | `commit_hash` | string | 7-char git sha of the run that wrote this row. Provenance. |
| 19 | `notes` | string | Free text. Commas auto-quoted. |

### Columns 16–17 are the whole point

The call is recorded in columns 4–6 **before** the outcome exists. Columns
16–17 are filled in by the *next* week's run, which may not edit anything
else in the row. That is what makes this a prediction rather than a
description, and it is why the ledger is append-only with a `--score-prior`
path that touches only those two fields.

---

## `dashboard/data/portfolio.json`

```jsonc
{
  "schema_version": "1.0.0",
  "week_ending": "2026-08-14",
  "generated_at": "2026-08-14T16:30:00-04:00",
  "owner_confirmed": false,
  "banner": "REFERENCE BASKET — not the owner's holdings",
  "basket": { "id": "tech-sleeve", "display_name": "Tech Sleeve",
              "constituents": [{ "ticker": "AAPL", "weight_pct": 12.5 }] },
  "call": { "composite": -0.42, "label": "LEAN DEFENSIVE",
            "confidence": "medium", "bucket_span": 2.0 },
  "buckets": [{ "name": "momentum", "score": -1.0, "weight": 0.30,
                "rationale": "...", "abstained": false }],
  "projection": {
    "basis": "normalized index, base 100",
    "cadence": "monthly",
    "horizon_weeks": 52,
    "path": [{ "week": 0, "p10": 100.0, "p50": 100.0, "p90": 100.0 }]
  },
  "track_record": { "weeks_scored": 0, "directional_hit_rate": null },
  "disclaimer": "Educational only. Not investment advice."
}
```

Every field above is derived from public market data plus tickers and
percentage weights. **No field in this file may be computed from
`private/holdings.json`.** The projection is a normalized index precisely so
that it can be published without disclosing a balance.

---

## The risk panel

`risk` carries the metric set ported from `A-Whale-Off-the-Port-folio` via
`analytics/risk.py`: annualized and EWMA volatility, Sharpe, max drawdown,
beta and correlation against the benchmark, rolling 60-day beta range, and
mean pairwise correlation across holdings.

All of it is computed on **daily** returns (`periods=252`), not the weekly
returns the call is scored on. Beta and drawdown both degrade badly on a
weekly sample this short, and drawdown in particular is path-dependent —
sampling weekly hides the intra-week trough entirely.

`mean_pairwise_correlation` is on the panel because it is the number that
determines whether the projection band below is honest. See
`docs/ANALYTICS-PROVENANCE.md`.

Sharpe is published at a **0% risk-free rate**, inherited from the source
notebook, with `risk_free_rate` in the payload so the assumption travels with
the number. At current short rates that overstates it.

---

## The projection is a scenario, not a forecast

`projection.path` answers the question "if contributions continue at the
current cadence, what range of outcomes is consistent with this sleeve's own
realized volatility and co-movement?" It is a correlated Monte Carlo over
trailing weekly returns (`analytics/montecarlo.py`), not a view about the
future.

**Shocks are drawn correlated across holdings, and that is the point.** The
original `MCForecastTools` drew each holding independently, which on a sleeve
with the ~0.5 pairwise correlation large-cap tech shows understates the decile
band by roughly half and puts p10 about 20 index points too high. A
concentrated sleeve does not diversify its own risk away. If the covariance
matrix is degenerate the simulation falls back to independent draws, sets
`projection.correlated: false`, and says so in `projection.note` — it does not
silently publish the narrower band.

Four honest limits, stated on the tab itself:

1. The band is drawn from **trailing** volatility and **static** correlation.
   A regime change breaks it, and in a real drawdown correlations converge
   toward 1 — so even the corrected band is optimistic when it matters most.
2. `p10`/`p90` are not worst and best cases. Roughly one year in ten finishes
   outside each edge, and real equity tails are fatter than the Gaussian this
   draws from.
3. Drift comes from the trailing sample mean, so a sleeve that has run hot
   projects forward hot. This is the model's most flattering assumption.
4. The composite call does **not** feed the projection. Mixing a one-week
   directional score into a 52-week path would imply the model can forecast a
   year out. It cannot, and the ledger is the evidence either way.

Management fees are not netted out of any path.

---

## Day-in-the-life

```
Fri 16:30 ET   portfolio_track.py --score-prior   # fills last week's outcome
Fri 16:31 ET   portfolio_track.py                 # scores this week, appends row,
                                                  #   writes dashboard/data/portfolio.json
                                                  #   writes the email section fragment
Fri 16:35 ET   git commit + push                  # sync-dashboard copies to the tab
```

The morning email picks up the fragment on the next trading day. See
`scripts/SKILL-portfolio.md` §6 for where it slots into the email body.

---

## Amendments

Same rule as the P&L ledger: never silently edit a historical row. If a past
week is wrong, append a correction and record the reason in `notes`, in a
commit titled `amend({week_ending}): {one-line reason}`. The `commit_hash`
column is what lets `git show` retrieve the exact code that produced a call.
