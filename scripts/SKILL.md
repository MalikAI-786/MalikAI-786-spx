---
name: morning-bias
version: 5.0.0
owner: Yasir A. Malik
status: production
supersedes: v4.1
audit_reference: /repo/audits/AUDIT-MEMO-v5.0.md
description: >
  At 9:00 AM ET on US trading days, run the 5-bucket SPX 0-DTE bias model
  (futures, macro, news, international, sentiment), cross-check the composite
  against three AI peer sources (Codex, Gemini, Perplexity — placeholder calls
  in v5.0), ingest yesterday's close-report to compute a self-improving
  calibration overlay and rolling 10-day trusted-bot synthetic P&L, write the
  morning report committed to git with provenance hashes, refresh the public
  dashboard, and at 9:30:00 ET send the **educational** market-analysis email
  to the owner only. This is research and education content — not investment
  advice, not a recommendation, not a solicitation.
distribution:
  to: yasiramalik@gmail.com
  cc: []
  bcc: []   # F-02 remediation — BCC list removed in v5.0
framing: EDUCATIONAL  # F-01 remediation — no "trade at X" language anywhere
---

# SPX 0DTE Morning Bias — v5.0 Scheduled Task

**Owner:** Yasir A. Malik
**Run window:** 9:00:00 ET start → 9:30:00 ET email sent
**Hard fallback:** at 9:25:00 ET, if not finished, send an `INCOMPLETE` email
**Audit memo of record:** `$REPO/audits/AUDIT-MEMO-v5.0.md` — every step below
that references a finding (F-01 through F-06) is implementing a recommendation
from that memo. Read the memo before changing this file.

This task is designed to be executable by a fresh agent with **no prior
context**. Every required path, command, and JSON shape is spelled out. When
you find yourself wanting to "infer" something, stop and re-read the
referenced step.

---

## 0. Pre-flight — load environment and verify guardrails (9:00:00 → 9:01:30)

0.1. Set the environment variable `REPO` to the absolute path of the local
    clone of `malikai-786/malikai-spx-dashboard`. The agent's working
    assumption is `$REPO = ~/code/malikai-spx-dashboard`. If that path does
    not exist, halt and emit `ENV_ERROR: REPO not found`.

0.2. Set `TODAY` to today's US/Eastern date in `YYYY-MM-DD` form. Set
    `YESTERDAY` to the most recent prior **trading day** in `YYYY-MM-DD` form
    (skip Sat/Sun and NYSE holidays — use the holiday list at
    `$REPO/scripts/nyse_holidays.txt`).

0.3. Verify today is a US trading day. If not, exit cleanly with
    `NON_TRADING_DAY` and do not send any email.

0.4. Run `$REPO/scripts/preflight.sh`. It must verify (control C-08):
    - `~/.gmail-mcp/token.json` exists and is mode `600`
    - `git` is on PATH and `$REPO` is a clean working tree
    - Python 3.11+ is available
    - Network reachability for `api.polygon.io`, `query1.finance.yahoo.com`,
      `www.cmegroup.com`
    If any check fails, halt and emit `PREFLIGHT_FAIL: <reason>`.

0.5. Compute and record the **starting git commit hash** of `$REPO`
    (`git rev-parse HEAD`) into a variable `GIT_SHA_START`. This will be
    embedded in the report header (control C-02).

0.6. Compute the **SHA-256** of `$REPO/ledger/paper-pnl.csv` and store as
    `LEDGER_SHA256`. If the file does not yet exist (cold start), set
    `LEDGER_SHA256 = "EMPTY_LEDGER"`. This will also be embedded in the
    header and published to `/integrity` (control C-04).

0.7. **Hard rules from the audit memo — enforce on every run.** Any
    violation of these halts the task immediately:
    - The string `"Trade at"` MUST NOT appear in any subject line, body,
      or report artifact. (F-01)
    - The strings `"Option Alpha"` and `"Tastytrade"` MUST NOT appear in
      the email body. Click-by-click broker instructions are dashboard-
      gated only. (F-01)
    - The `bcc` field in the gmail send payload MUST be the empty list.
      (F-02)
    - The `to` field MUST equal exactly `"yasiramalik@gmail.com"` and
      nothing else. (F-02, C-09)
    - No payment processor, donation link, Patreon, Stripe, Buy-Me-A-
      Coffee, or affiliate link may appear anywhere. (F-03, C-07)
    - The phrase `"Not Investment Advice"` and the educational-disclaimer
      box MUST appear in the email body. (F-01, C-01)
    - The ledger CSV MUST be opened in append-only mode. Editing any
      historical row is a hard failure. (F-04, C-03)

---

## 1. Ingest yesterday's close report — the self-improving loop (9:01:30 → 9:04:00)

1.1. Open `$REPO/SPX-Reports/close/$YESTERDAY.md`. If it does not exist,
    set `YESTERDAY_PRESENT = false` and skip to step 1.7. (Cold start, or
    yesterday was a stand-down with no close run.)

1.2. Parse the close report. Extract:
    - `predicted_bias` — bullish / bearish / neutral / stand-down
    - `predicted_score` — the composite score from yesterday's morning run
    - `actual_spx_close_change_pct` — yesterday's SPX cash-index close
      change vs. prior close (signed percent)
    - `bucket_scores` — dict of `{futures, macro, news, international,
      sentiment}` each in `[-2, +2]`
    - `was_signal_correct` — true if the sign of `predicted_score` matched
      the sign of `actual_spx_close_change_pct`; false if it did not;
      `n/a` for stand-down days

1.3. Open `$REPO/ledger/paper-pnl.csv` (append-only — control C-03). Schema:
    ```
    date,predicted_bias,predicted_score,actual_close_change_pct,
    structure,strike_short,strike_long,entry_credit_or_debit,
    exit_value,pnl_dollars,was_correct,git_sha,notes
    ```

1.4. Read the last 10 rows (most recent trading days). If fewer than 10
    exist, use what is available — the rolling P&L just covers the
    window that exists.

1.5. Compute **calibration overlay**: for each of the 5 buckets, compute
    the rolling 10-day correlation between that bucket's score and the
    next-day actual SPX close change. Store as
    `calibration[bucket] ∈ [-1.0, +1.0]`. Buckets with correlation
    `< 0.0` are flagged "WRONG-WAY" and the morning report must say so.
    Buckets with `|corr| < 0.15` are flagged "WEAK". Buckets with
    `corr ≥ 0.40` are flagged "TRUSTED".

1.6. Compute **lessons learned** for yesterday: identify the bucket whose
    score was most directionally **wrong** relative to actual outcome
    (`bucket_score · sign(actual_change) < 0` and largest magnitude).
    That bucket becomes today's "OVER-WEIGHTED yesterday — discount by
    25%" tag. Identify the bucket whose score was most directionally
    **right** and call it "UNDER-WEIGHTED yesterday — keep weight". If
    yesterday was correct overall, the lessons section reads "No
    re-weighting required — model called direction correctly."

1.7. Compute **rolling 10-day trusted-bot synthetic P&L**. Assumption:
    a hypothetical fully-trusted bot took every non-stand-down signal at
    09:45 ET via the recommended defined-risk structure (see §7) and
    closed at 16:00 ET. For each row in the last 10 trading days:
    - Stand-down → `pnl = $0` (F-05 anti-survivorship, control C-10)
    - Otherwise → use the recorded `pnl_dollars` from the close report
    Aggregate:
    - `wins`, `losses`, `stand_downs`
    - `total_pnl`, `win_rate`, `avg_win`, `avg_loss`, `largest_drawdown`
    Record into a dict `rolling_pnl` for use in §10.

---

## 2. Pull the 5 bucket scores (9:04:00 → 9:12:00)

For each bucket, run the existing v4.1 ingestion module and store a score in
the closed interval `[-2.0, +2.0]` plus a short text rationale (≤ 280 chars).

2.1. **Futures.** Pull ES/NQ/YM front-month overnight session change from CME.
    Run `$REPO/scripts/buckets/futures.py --asof "$NOW_ET"`. Output:
    `score_futures`, `rationale_futures`.

2.2. **Macro.** Pull the day's scheduled US data releases from the BLS / BEA /
    Fed calendar cache at `$REPO/cache/macro_calendar.json` (refreshed by
    the nightly cron). Pre-market releases already printed are scored on
    surprise vs. consensus. Releases scheduled intraday are scored on
    expected directional impact only. Run
    `$REPO/scripts/buckets/macro.py`. Output: `score_macro`, `rationale_macro`.

2.3. **News.** Pull the last 16 hours of headlines from Reuters, Bloomberg
    Terminal RSS, and the WSJ markets feed. Filter for SPX-relevant
    keywords. Run `$REPO/scripts/buckets/news.py`. Output: `score_news`,
    `rationale_news`.

2.4. **International.** Pull overnight closes for Nikkei 225, Hang Seng,
    DAX, FTSE 100, Euro Stoxx 50. Score the unweighted mean change.
    Run `$REPO/scripts/buckets/international.py`. Output:
    `score_international`, `rationale_international`.

2.5. **Sentiment.** Pull VIX front-month, VVIX, put/call ratio (CBOE total),
    and AAII bull/bear if Wednesday close was published this week. Run
    `$REPO/scripts/buckets/sentiment.py`. Output: `score_sentiment`,
    `rationale_sentiment`.

2.6. Bundle the five scores plus calibration tags into a single dict
    `bucket_scores`:
    ```python
    {
      "futures":       {"score": ..., "rationale": ..., "calibration": "TRUSTED|WEAK|WRONG-WAY"},
      "macro":         {...},
      "news":          {...},
      "international": {...},
      "sentiment":     {...}
    }
    ```

---

## 3. Compute the composite score (9:12:00 → 9:13:00)

3.1. **Base weights** (unchanged from v4.1):
    - futures: 0.30
    - macro: 0.20
    - news: 0.15
    - international: 0.15
    - sentiment: 0.20

3.2. **Apply calibration overlay (new in v5.0):**
    - If bucket is "TRUSTED", multiply its base weight by 1.10
    - If "WEAK", multiply by 0.85
    - If "WRONG-WAY", multiply by 0.50 (do not flip sign — discount
      magnitude instead, the bucket is noisy not necessarily inverted)
    Re-normalize weights so they sum to 1.0.

3.3. **Apply lessons-learned tag:** the bucket flagged "OVER-WEIGHTED
    yesterday" gets an additional ×0.75 multiplier for today only. The
    bucket flagged "UNDER-WEIGHTED yesterday" keeps its weight.

3.4. Compute `composite_score = Σ (weight_i · score_i)`, clipped to
    `[-2.0, +2.0]`.

3.5. Map to bias label:
    - `composite_score ≥ +1.0` → `BULLISH`
    - `+0.3 ≤ composite_score < +1.0` → `LEAN BULLISH`
    - `-0.3 < composite_score < +0.3` → `STAND-DOWN`
    - `-1.0 < composite_score ≤ -0.3` → `LEAN BEARISH`
    - `composite_score ≤ -1.0` → `BEARISH`

---

## 4. Cross-check with three AI peer sources — Codex, Gemini, Perplexity (9:13:00 → 9:18:00)

These three calls REPLACE the v4.1 human peer models (Angelo and Omeir).
**In v5.0 they are placeholder calls** — each returns the literal string
`"NOT_WIRED_YET — placeholder for v5.0 source: <name>"`. The wiring will
be done incrementally in v5.1, v5.2, v5.3. The skill must already
structure for them today.

4.1. Construct the **shared prompt template** (pinned, control F-05.2):
    ```
    SPX 0DTE Morning Bias — peer cross-check.
    Today: {TODAY}. Spot SPX (last close): {SPX_LAST_CLOSE}.
    Implied 1-sigma move (front-month VIX-derived): {SIGMA_DOLLARS}.
    Our composite bias: {BIAS_LABEL} (score {COMPOSITE_SCORE:+.2f}).
    Bucket scores: {bucket_scores_json}.
    Question: independently, what is your directional bias for SPX cash
    today, by 4:00 PM ET, on a scale [-2.0, +2.0]? Give a one-sentence
    rationale. Do not anchor on our score.
    ```

4.2. **Call Codex.** Run `$REPO/scripts/sources/codex.py --prompt <prompt>`.
    In v5.0 the script returns:
    ```
    {"score": null, "rationale":
     "NOT_WIRED_YET — placeholder for v5.0 source: codex"}
    ```
    Save the verbatim response (control C-05) to
    `$REPO/sources/responses/$TODAY-codex.md`.

4.3. **Call Gemini.** Run `$REPO/scripts/sources/gemini.py --prompt <prompt>`.
    Same placeholder behavior. Save verbatim to
    `$REPO/sources/responses/$TODAY-gemini.md`.

4.4. **Call Perplexity.** Run
    `$REPO/scripts/sources/perplexity.py --prompt <prompt>`. Same
    placeholder behavior. Save verbatim to
    `$REPO/sources/responses/$TODAY-perplexity.md`.

4.5. **Agreement check (control C-06).** Once these sources are wired
    (v5.1+), if any score is non-null and `sign(score) != sign(composite)`,
    increment a counter `disagreement_count`. If `disagreement_count >= 2`,
    downgrade the `BIAS_LABEL` by one step toward `STAND-DOWN`. In v5.0
    while all three are placeholders, `disagreement_count = 0` always —
    record the AI-source-agreement section as "PENDING WIRING (3/3
    placeholders); confidence not adjusted." Do not silently treat
    placeholders as agreement.

4.6. Build the **AI source agreement** section for the email:
    ```
    | Source     | Score | Direction | Status               |
    |------------|-------|-----------|----------------------|
    | Codex      |  n/a  |   n/a     | NOT_WIRED_YET        |
    | Gemini     |  n/a  |   n/a     | NOT_WIRED_YET        |
    | Perplexity |  n/a  |   n/a     | NOT_WIRED_YET        |
    Composite confidence: as-is (no downgrade applied while wiring pending).
    ```

---

## 5. Pull spot, IV, and derive defined-risk structure (9:18:00 → 9:20:00)

5.1. Pull current SPX cash-index quote (or ES front-month if cash not yet
    printing) and store as `SPX_NOW`. Pull VIX front-month and store as
    `VIX_NOW`.

5.2. Compute the one-day 1-sigma dollar move:
    ```
    SIGMA_DOLLARS = SPX_NOW × (VIX_NOW / 100) × sqrt(1 / 252)
    ```
    Round to nearest dollar.

5.3. Derive **strikes** for a generic defined-risk structure based on
    `BIAS_LABEL`:
    - `BULLISH` / `LEAN BULLISH` → **Bull Put Spread**
       short put at `round_to_5(SPX_NOW - 1·SIGMA_DOLLARS)`
       long put at `round_to_5(SPX_NOW - 1.5·SIGMA_DOLLARS)`
    - `BEARISH` / `LEAN BEARISH` → **Bear Call Spread**
       short call at `round_to_5(SPX_NOW + 1·SIGMA_DOLLARS)`
       long call at `round_to_5(SPX_NOW + 1.5·SIGMA_DOLLARS)`
    - `STAND-DOWN` → **No structure.** The email says "no structure
      derived today — composite below conviction threshold."

5.4. The structure description in the email is **generic and educational**.
    F-01 remediation: no broker name, no click-by-click. Format:
    ```
    Defined-risk structure illustrated today: Bull Put Spread
      Short put strike: 5915  (≈ SPX − 1σ)
      Long put strike:  5895  (≈ SPX − 1.5σ)
      Net credit target: 0.20 × spread width
      Max defined loss:  spread width − credit
      Educational illustration only. See the dashboard for the
      execution variant the author uses for his own paper journal.
    ```

5.5. **Invalidation level.** Record `INVALIDATION_SPX = SPX_NOW − SIGMA_DOLLARS`
    for bullish biases or `SPX_NOW + SIGMA_DOLLARS` for bearish.
    Stand-down has no invalidation level.

---

## 6. Pull supporting evidence sections (9:20:00 → 9:22:30)

The model has already committed to a bias by §3. These sections are
**explanatory color**, not new inputs, and must not change the score.

6.1. **Bullish evidence (`bullish_bullets`)** — 3 to 5 short bullets from
    today's news and macro feeds that support the bullish case, regardless
    of which way the model leaned. Pulled by `$REPO/scripts/evidence/bullish.py`.

6.2. **Bearish evidence (`bearish_bullets`)** — same shape, bearish side.

6.3. **Vol & positioning (`vol_positioning_bullets`)** — 3 bullets covering
    VIX term structure (front vs. 2nd month), VVIX, total put/call, and
    dealer gamma estimate if available.

6.4. **Catalysts (`catalysts_bullets`)** — any scheduled FOMC speakers,
    earnings (mag-7), or data prints between now and 16:00 ET.

6.5. **SPX levels (`spx_levels`)** — overnight high, overnight low, prior
    close, 5-day VWAP, 20-day SMA, ES gamma flip if known.

---

## 7. Build the morning report markdown (9:22:30 → 9:24:00)

7.1. Path: `$REPO/SPX-Reports/morning/$TODAY.md`. Overwrite is forbidden —
    if the file already exists for today, halt with
    `DUPLICATE_RUN: $TODAY morning report already on disk`.

7.2. **Header block** (required, control C-02):
    ```
    ---
    title: SPX 0DTE Morning Bias — $TODAY
    framing: Educational analysis
    git_sha_start: $GIT_SHA_START
    ledger_sha256: $LEDGER_SHA256
    skill_version: 5.0.0
    audit_memo: /audits/AUDIT-MEMO-v5.0.md
    distribution: yasiramalik@gmail.com (owner only)
    ---
    ```

7.3. Body sections in order:
    1. **Hero** — one-paragraph summary: today's bias, score, structure name.
    2. **Bucket table** — table of 5 buckets, score, rationale, calibration tag.
    3. **Calibration overlay** — 10-day rolling correlation per bucket.
    4. **Yesterday's recap** — predicted vs actual, was-correct flag,
       reference link to `$REPO/SPX-Reports/close/$YESTERDAY.md`.
    5. **Lessons learned** — over-weighted bucket, under-weighted bucket,
       or "no re-weighting required."
    6. **AI source agreement** — the 3-row table from §4.6.
    7. **Bullish evidence**.
    8. **Bearish evidence**.
    9. **Vol & positioning**.
    10. **Catalysts today**.
    11. **SPX levels**.
    12. **Signal invalidation** — the level from §5.5.
    13. **Educational structure** — the §5.4 block. NOT click-by-click.
    14. **Pre-flight checklist** — generic checklist (review your size,
        review your stop, do not trade what you do not understand). NOT
        broker-specific.
    15. **Rolling 10-day trusted-bot synthetic P&L** — table:
        ```
        | Metric          | Value     |
        |-----------------|-----------|
        | Window          | last 10 td|
        | Wins            | n         |
        | Losses          | n         |
        | Stand-downs     | n (= $0)  |
        | Total P&L       | $...      |
        | Win rate        | xx%       |
        | Avg win         | $...      |
        | Avg loss        | $...      |
        | Largest drawdown| $...      |
        ```
        Followed by the disclaimer "Synthetic — assumes a hypothetical
        fully-trusted bot executed at 09:45 ET into 16:00 ET close per the
        defined-risk structure above. No fees, no slippage modeled.
        Stand-downs counted as $0 (anti-survivorship)."
    16. **Dashboard link** — `https://malikai-786.github.io/malikai-spx-dashboard/`
        with the note "Click-by-click execution variant and integrity
        hashes live on the dashboard, gated behind the
        self-directed-trader page."
    17. **Audit memo link** — `/audits/AUDIT-MEMO-v5.0.md`.
    18. **NOT-INVESTMENT-ADVICE box** — see §8 for exact text.
    19. **Questions line** — see §9.1.
    20. **Hazrat Ali quote** — see §9 for the rotating quote pool.

7.4. Save the report. Stage and commit:
    ```
    git -C "$REPO" add SPX-Reports/morning/$TODAY.md \
                       sources/responses/$TODAY-*.md
    git -C "$REPO" commit -S -m "morning bias $TODAY (v5.0)"
    ```
    Capture the resulting hash as `GIT_SHA_REPORT`. If the GPG signing
    key is not available, fall back to an unsigned commit but record
    `signed: false` in the report metadata.

7.5. Re-compute the ledger SHA-256 after any close-side updates and
    publish to `$REPO/dashboard/integrity/$TODAY.txt` (control C-04).

---

## 8. The NOT-INVESTMENT-ADVICE box (mandatory, exact text)

Place this prominently at the **top** of the email body, immediately after
the subject-line preview banner and before the hero paragraph. Render it
as a styled block-quote (HTML `<blockquote>` or markdown `>`).

```
> NOT INVESTMENT ADVICE — EDUCATIONAL CONTENT ONLY
>
> The author is **not** a registered investment adviser. This message is a
> personal trading-journal and learning artifact published for the author's
> own records and for any reader who has chosen to follow along. Nothing
> here is a recommendation to buy, sell, or hold any security. The figures,
> bias scores, and synthetic P&L are hypothetical and educational. Past
> simulated performance is not indicative of future results. You are
> responsible for your own decisions. If you need advice, consult a
> registered professional in your jurisdiction.
```

This implements control C-01. The exact words above must appear verbatim.
The styled-block requirement implements F-01 recommendation #4.

---

## 9. Hazrat Ali (RA) quote — rotating pool

Pick one quote at random from the pool, seeded by `hash($TODAY)` so the
choice is reproducible. Quotes are kept in `$REPO/scripts/quotes.txt`.
v5.0 default pool:

1. *"Do not let your difficulty in finding the right path stop you from walking it."*
2. *"The strongest among you is the one who controls his anger."*
3. *"Patience is of two kinds: patience over what pains you, and patience against what you covet."*
4. *"He who knows himself knows his Lord."*
5. *"The best wealth is the abandoning of desires."*

Format the chosen line as the final line of the email body, italicized,
with the attribution `— Hazrat Ali (RA)`.

### 9.1. Questions line (added v5.1)

Immediately after the educational disclaimer paragraph and any system
notes, and before the Hazrat Ali quote, add one plain line:

```
Questions or something look off? Reply to this email.
```

This is the only mechanism for a reader (cc/bcc'd recipients included) to
reach the owner about the content — not a calendar invite, not a
scheduling link, and not a Notion link (the control-center workspace is
private; recipients outside it cannot open a page there even if one were
linked). A reply lands in the same thread the owner already reads every
morning. Do not add any other contact channel without the owner's
explicit say-so.

---

## 10. Compose the email payload (9:24:00 → 9:25:00)

10.1. **Subject line.** Mandatory format (F-01 remediation — no "Trade at"):
    ```
    SPX 0DTE — Educational analysis — 9:30 ET publication — $TODAY — $BIAS_LABEL ($COMPOSITE_SCORE:+.2f)
    ```
    Example: `SPX 0DTE — Educational analysis — 9:30 ET publication — 2026-05-28 — LEAN BULLISH (+0.47)`.

10.2. **JSON payload** for `gmail_send.py` (exact shape — F-02 remediation):
    ```json
    {
      "to":  ["yasiramalik@gmail.com"],
      "cc":  [],
      "bcc": [],
      "subject": "<subject from 10.1>",
      "body_markdown": "<rendered from §7.3>",
      "body_html": "<rendered HTML — markdown → HTML via cmarkgfm>",
      "headers": {
        "X-MalikAI-Version": "5.0.0",
        "X-MalikAI-Git-Sha": "<GIT_SHA_REPORT>",
        "X-MalikAI-Ledger-Sha256": "<LEDGER_SHA256>",
        "X-MalikAI-Framing": "EDUCATIONAL"
      }
    }
    ```
    Hard assertion before sending: `payload["bcc"] == []` and
    `payload["to"] == ["yasiramalik@gmail.com"]`. If either fails, abort
    and emit `DISTRIBUTION_GUARD_VIOLATION` — do not send.

10.3. **Body section ordering** (mandatory, must match §7.3 exactly):
    hero → bucket table → calibration overlay → yesterday's recap →
    lessons learned → AI source agreement → bullish evidence →
    bearish evidence → vol/positioning → catalysts → SPX levels →
    signal invalidation → educational structure → pre-flight checklist →
    rolling 10-day trusted-bot P&L table → **tech-sleeve outlook + Monte Carlo
    band** (append `$REPO/dashboard/data/portfolio-email.html` when present;
    generated by `scripts/portfolio_track.py`, includes correlated MC p10/p50/p90
    on index base 100 — never dollars) → dashboard link →
    audit-memo link → NOT-INVESTMENT-ADVICE box → questions line → Hazrat Ali quote.

10.3.1. **Monte Carlo / tech outlook fragment.** If
    `$REPO/dashboard/data/portfolio-email.html` exists and was regenerated this
    week (or `--example` fixture), include it verbatim before the dashboard
    link. Do not invent a band; if the fragment is missing, omit the section
    rather than fabricating p10/p50/p90. p10 is a lower decile, never a
    "worst case."

10.4. **Banned phrases in the body** (lint pass before send — F-01):
    `"Trade at"`, `"buy "`, `"sell "`, `"recommendation"`, `"signal to enter"`,
    `"Option Alpha"`, `"Tastytrade"`, `"click "` (case-insensitive).
    If any banned phrase appears, replace via the substitution table at
    `$REPO/scripts/banned_phrases.json` and re-render. If the substitution
    table does not cover a hit, abort with `BANNED_PHRASE: <phrase>`.

---

## 11. Send the email at 9:30:00 ET sharp (9:25:00 → 9:30:00)

11.1. Block-sleep until the wall clock reaches `$TODAY 09:30:00 America/New_York`.
    Use a monotonic sleep with sub-second precision. Never sleep past
    09:30:00.

11.2. Send via the standard mechanism:
    - **Primary:** `python $REPO/scripts/gmail_send.py < payload.json`
      (uses the OAuth token at `~/.gmail-mcp/token.json`).
    - **Fallback:** if gmail_send.py exits non-zero, immediately fall
      back to the macOS `osascript` Mail-app driver at
      `$REPO/scripts/mail_send.scpt`, passing the same payload. The
      osascript path enforces the same distribution guard (to-only,
      no bcc) before composing the message.

11.3. Capture the resulting `message_id`. Append a row to
    `$REPO/ledger/sent-emails.csv`:
    ```
    date,message_id,subject,bias_label,composite_score,git_sha,ledger_sha256
    ```

11.4. Tag git: `git -C "$REPO" tag morning/$TODAY $GIT_SHA_REPORT`.

---

## 12. Refresh the public dashboard (9:30:00 → 9:32:00)

12.1. Run `$REPO/scripts/dashboard/refresh.py --date $TODAY`. This
    regenerates the static site:
    - `/index.html` — today's bias, bucket table, AI agreement table
    - `/integrity/$TODAY.txt` — published ledger SHA-256 (control C-04)
    - `/self-directed-trader/$TODAY.html` — the **gated** click-by-click
      execution variant (F-01: gated, not emailed). Page is published
      but the home page links to it only behind an explicit acknowledgment
      modal: *"I am a self-directed trader; show me the author's own
      execution notes."*
    - `/pnl/` — the rolling-10-day synthetic P&L tab, refreshed.

12.2. Commit and push:
    ```
    git -C "$REPO" add dashboard/
    git -C "$REPO" commit -m "dashboard refresh $TODAY (v5.0)"
    git -C "$REPO" push origin main
    ```

---

## 13. INCOMPLETE fallback at 9:25:00 ET (hard rule)

If at 09:25:00 ET the task has **not** reached step 10.2 (payload built and
validated), abandon the full pipeline and send a minimal email instead:

```
Subject: SPX 0DTE — Educational analysis — 9:30 ET publication — $TODAY — INCOMPLETE

NOT INVESTMENT ADVICE — EDUCATIONAL CONTENT ONLY.

Today's morning-bias pipeline did not complete by 09:25 ET.
No bias is being published. No structure is illustrated.
Reason (best-known at cutoff): <last_error_message>.

Git sha at cutoff: <GIT_SHA_START>
Ledger sha256:    <LEDGER_SHA256>
Audit memo:       /audits/AUDIT-MEMO-v5.0.md

— Hazrat Ali (RA): "Do not let your difficulty in finding the right path
stop you from walking it."
```

Same distribution guard (to=owner only, bcc=[]). The INCOMPLETE event is
logged to `$REPO/ledger/incomplete-runs.csv` and the dashboard front page
is set to the "no signal today — pipeline incomplete" state.

---

## 14. Close-of-day handoff (16:15 ET — out of scope for this skill)

The companion `eod-monitor` skill picks up at 16:15 ET, reads today's
morning report, fetches the actual SPX close, computes the synthetic P&L
for today's structure, appends to `paper-pnl.csv`, writes
`$REPO/SPX-Reports/close/$TODAY.md`, and commits. Tomorrow's morning
run consumes that file in §1. The loop closes.

---

## 15. Failure modes and operational invariants

15.1. **Distribution guard violation** (any deviation from to=owner-only,
     bcc=[]) — hard abort, no fallback. F-02.

15.2. **Banned phrase appearing in body** — hard abort if not auto-substitutable.
     F-01.

15.3. **Missing audit-memo link or NOT-INVESTMENT-ADVICE box** — hard abort.
     C-01.

15.4. **Ledger mutation attempt** (any write to a non-tail row) — hard abort,
     pre-commit hook rejects. C-03, F-04.

15.5. **Git working tree dirty at start** — preflight fails. C-02.

15.6. **OAuth token mode not 600** — preflight fails. C-08.

15.7. **Payment processor string found anywhere in repo** — pre-commit hook
     rejects. C-07, F-03.

15.8. **All three AI sources non-placeholder and 2/3 disagree with
     composite** (future state) — bias label auto-downgraded one step.
     C-06.

---

## 16. Version log

- **v4.1** → **v5.0** deltas (May 28, 2026):
  - Removed two human peer models (Angelo, Omeir).
  - Added three AI peer sources (Codex, Gemini, Perplexity) — all
    placeholder calls in v5.0, real wiring deferred to v5.1+.
  - Added self-improving loop: yesterday's close-report ingest →
    calibration overlay + lessons-learned + rolling 10-day synthetic P&L.
  - Distribution locked down to owner-only; BCC list removed (F-02).
  - Subject line and body language fully reframed as educational (F-01).
  - Click-by-click execution moved off email, behind dashboard gate (F-01).
  - Git commit hash + ledger SHA-256 embedded in report header (F-04, C-02).
  - AI source responses logged verbatim per model per day (F-05, C-05).
  - NOT-INVESTMENT-ADVICE box mandatory at top of body (C-01).
  - Hazrat Ali quote rotated from a pool of 5 (was single-quote in v4.1).

---

*End of SKILL.md v5.0. Owner: Yasir A. Malik. Audit memo of record:
`/audits/AUDIT-MEMO-v5.0.md`. The walk continues.*
