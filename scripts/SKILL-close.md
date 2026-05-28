---
name: eod-monitor
version: 5.0.0
owner: Yasir A. Malik
status: production
supersedes: v4.1 close-of-day cron
audit_reference: /repo/audits/AUDIT-MEMO-v5.0.md
companion_skill: morning-bias (v5.0.0)
description: >
  At 4:15 PM ET on US trading days, close out the day's SPX 0-DTE synthetic
  paper-trade journal: load this morning's published bias, fetch the actual
  SPX 9:45/16:00 print, compute the trusted-bot P&L of the recommended
  defined-risk structure, score per-bucket directional attribution against
  the actual move, append one immutable row to the ledger, write the close
  report, refresh the public dashboard's Exit tab, and at 4:15:00 ET send
  the **educational** close email to the owner only. This is research and
  education content — not investment advice, not a recommendation, not a
  solicitation, not a P&L statement of any real account.
distribution:
  to: yasiramalik@gmail.com
  cc: []
  bcc: []   # F-02 remediation — owner-only, no BCC fan-out
framing: EDUCATIONAL  # F-01 remediation — no "trade at X" / "buy" / "sell"
---

# SPX 0DTE Close-of-Day — v5.0 Scheduled Task

**Owner:** Yasir A. Malik
**Run window:** 4:00:00 ET start (market close) → 4:15:00 ET email sent
**Hard fallback:** at 4:18:00 ET, if not finished, send `[INCOMPLETE]` email
**Audit memo of record:** `$REPO/audits/AUDIT-MEMO-v5.0.md` — every step
referencing a finding (F-01..F-06) implements that memo. Read it before
changing this file.

Mirror of `morning-bias`, runs in 15 minutes from 4:00 ET close. Every path,
command, and JSON shape is spelled out. Morning skill commits to the day's
bias; this skill closes the loop with empirical evidence and feeds tomorrow's
calibration.

---

## 0. Pre-flight — load environment and verify guardrails (4:00:00 → 4:00:45)

0.1. Set `REPO` to the local clone of `malikai-786/malikai-spx-dashboard`
    (ledger + reports + skill code) and `PUB` to the clone of
    `malikai-786/malikai-spx-pages` (GitHub Pages dashboard). Defaults:
    `$REPO = ~/code/malikai-spx-dashboard`, `$PUB = ~/code/malikai-spx-pages`.
    Halt with `ENV_ERROR: <REPO|PUB> not found` if missing.

0.2. Set `TODAY` to today's US/Eastern date `YYYY-MM-DD`. Do **not** derive
    `YESTERDAY` — close skill operates on today only. Tomorrow's morning
    skill is the consumer of what we write.

0.3. Verify today is a US trading day. If not, exit cleanly with
    `NON_TRADING_DAY` — no email. (Defensive double-check; morning skill
    should not have run either.)

0.4. Run `$REPO/scripts/preflight.sh` (control C-08). Must verify:
    - `~/.gmail-mcp/token.json` exists, mode `600`
    - `git` on PATH; **both** `$REPO` and `$PUB` are clean trees
    - Python 3.11+
    - Network reachability for `query1.finance.yahoo.com`, `stooq.com`,
      `api.polygon.io` (see §2)
    - The morning report at `$REPO/SPX-Reports/morning/$TODAY.md` exists.
      If missing, halt with `NO_MORNING_REPORT` and send the
      `[INCOMPLETE]` email per §14 — nothing to close out.
    Other failures halt with `PREFLIGHT_FAIL: <reason>`.

0.5. Record `GIT_SHA_START = git -C $REPO rev-parse HEAD` and
    `PUB_SHA_START = git -C $PUB rev-parse HEAD` for the report header
    (control C-02).

0.6. Compute SHA-256 of `$REPO/ledger/paper-pnl.csv` **before** this run
    touches it; store as `LEDGER_SHA256_PRE`. Cold start →
    `"EMPTY_LEDGER"`. Locked against for the append-only invariant
    (C-03, C-04).

0.7. **Hard rules from the audit memo — any violation halts immediately:**
    No `"Trade at"` in subject/body/artifact (F-01); no `"Option Alpha"`
    or `"Tastytrade"` in body (F-01); `bcc == []` (F-02); `to` exactly
    `["yasiramalik@gmail.com"]` (F-02, C-09); no payment processor /
    donation / Patreon / Stripe / BMAC / affiliate anywhere (F-03, C-07);
    `"Not Investment Advice"` box MUST appear in body (F-01, C-01);
    ledger CSV append-only — historical-row edits are a hard failure
    with git rollback (F-04, C-03); synthetic-paper-trade footnote MUST
    accompany every `$` figure in body (F-05, C-10).

---

## 1. Load this morning's published bias report (4:00:45 → 4:02:00)

1.1. Open `$REPO/SPX-Reports/morning/$TODAY.md` — what the morning skill
    wrote and signed at ~9:24 ET. Missing or unreadable → route to
    `[INCOMPLETE]` per §14.

1.2. Parse with `read_morning_report()` from `$REPO/scripts/close_track.py`
    (robust to formatting drift; loose `key: value` extraction). Returns
    `MorningSnapshot` with: `bias_score` ∈ `[-2.0, +2.0]`; `bias_label`
    ∈ `{BULLISH, LEAN BULLISH, STAND-DOWN, LEAN BEARISH, BEARISH}`;
    `confidence` ∈ `{low, medium, high}`; `stand_down` (bool);
    `structure` ∈ `{put_credit_spread, call_credit_spread,
    put_debit_spread, call_debit_spread, stand_down}`; `strike_short`,
    `strike_long` (None on stand-down); `credit_or_debit` (signed:
    + credit received, − debit paid); `max_risk`, `max_reward` (1-lot
    dollars); `bucket_contributions` (5 buckets ∈ `[-2.0, +2.0]`);
    `morning_commit_hash` (short SHA from morning §7.4).

1.3. Sanity-check:
    - `stand_down=false` AND any of `strike_short/long/credit_or_debit`
      is None → route to `[INCOMPLETE]`, reason
      `MORNING_REPORT_MALFORMED — non-stand-down with missing strikes`.
    - Empty `bucket_contributions` → log warning, set per-bucket
      attribution to `"n/a"` in §5, continue (degraded mode).

1.4. Echo the snapshot to stderr so the run log captures what close
    **believes** morning said. Discrepancies are investigated post-hoc by
    diffing the echo against the morning report on disk.

---

## 2. Fetch today's SPX intraday print (4:02:00 → 4:04:30)

2.1. Call `get_spx_intraday($TODAY)` from `close_track.py`. Returns
    `(spx_open_945, spx_close_400)`. **v5.0 returns deterministic mock
    data** seeded by SHA-256 of date; stderr banner
    `[MOCK] get_spx_intraday(...)` fires on every call.

2.2. Wire-up candidates (TODO in code; do not silently default in v5.0):
    **Stooq** — `https://stooq.com/q/d/?s=^spx&i=d` — daily/close-only.
    **Yahoo** — `https://query1.finance.yahoo.com/v8/finance/chart/^GSPC
    ?interval=15m&range=5d` — 15-min bars; `09:30→09:45` bar close is
    `spx_open_945`; no API key. **Polygon free tier** —
    `aggs/ticker/I:SPX/range/15/minute/$TODAY/$TODAY` — needs
    `POLYGON_API_KEY`; most accurate. Prefer Polygon if key set → Yahoo
    → Stooq (close-only) → mock with `DATA_SOURCE=MOCK` flag.

2.3. Also derive: `day_high` = max of 9:30–16:00 ET bars; `day_low` = min
    of same; `day_move_pct = 100*(spx_close_400/prior_close - 1)` where
    `prior_close` comes from `$REPO/cache/spx_prior_close.json` (nightly
    cron) or first 15-min bar if stale. Store in `MarketSnapshot` for
    §3, §5, §7.

2.4. If actual close fetch fails AND wall clock is past 4:08 ET, fall
    back to mock and stamp `DATA_SOURCE=MOCK_FALLBACK`. Do not block
    4:15 send on flaky data. Synthetic P&L on mock data is explicitly
    disclosed in the report and email.

---

## 3. Compute synthetic trusted-bot P&L (4:04:30 → 4:06:00)

3.1. Call `compute_trusted_bot_pnl(snapshot, spx_close)` from
    `close_track.py` — formula is fixed, do not re-implement. Summary:
    `stand_down` → `$0.00` (F-05). Credit spreads:
    `spread_value = short_intrinsic - long_intrinsic`,
    `pnl_pts = credit - spread_value`. Debit spreads:
    `pnl_pts = spread_value - |debit|`. Dollars: `pnl_pts × $100` (1-lot).

3.2. Returned `CloseResult`: `spx_open_945`, `spx_close`, `exit_price`
    (intrinsic at 4:00 ET in option points), `trusted_bot_pnl` (signed
    dollars), `trusted_bot_pnl_pct_of_max_risk = 100*pnl/max_risk`.

3.3. **Outcome classification** (subject line, hero chip, Exit tab):
    - **HIT** iff `pnl > 0`; OR `stand_down=true AND
      abs(day_move_pct) <= 0.30` (quiet day); OR `stand_down=true AND
      sign(bias_score) != sign(day_move_pct)` (model would have been wrong).
    - **MISS** iff `pnl < 0`; OR `stand_down=true AND
      abs(day_move_pct) > 0.30 AND sign(pre-clip composite) ==
      sign(day_move_pct)` (left a real call on the table).
    - **STAND-DOWN** iff `stand_down=true` and neither HIT nor MISS
      fired (neutral chip).
    - **FLAT** iff `pnl == 0.00 AND stand_down=false` — rare; classified
      as HIT by convention (defined-risk preserved capital).

3.4. Stand-down rows MUST hit the ledger with `pnl=$0.00` regardless of
    chip — chip is reporting-layer, ledger is immutable record. F-05
    anti-survivorship: never silently drop a stand-down day.

---

## 4. Bucket attribution against the actual move (4:06:00 → 4:07:00)

4.1. For each bucket `b ∈ {futures, macro, news, international, sentiment}`:
    `bucket_sign = sign(score_b)`, `actual_sign = sign(day_move_pct)`.
    **bucket_hit** iff signs equal and `actual_sign != 0`; **bucket_miss**
    iff both nonzero and unequal; **bucket_na** otherwise.

4.2. Aggregate `bucket_attribution: dict[str,str]` with values
    `"hit"|"miss"|"n/a"`. Tomorrow's morning skill consumes via §1.5
    (calibration overlay) and §1.6 (lessons learned).

4.3. Identify **top-contributing bucket**: `top_bucket = argmax_b
    |score_b|`. Record hit/miss. If model lost today, this is the prime
    suspect for tomorrow's "OVER-WEIGHTED yesterday — discount 25%" tag.

4.4. **Tomorrow's calibration preview** (1–3 lines, surfaced in email §11):
    bucket whose 10d rolling correlation just dropped `< 0.0` → "→
    WRONG-WAY watch"; bucket that just hit twice after a cold streak →
    "→ trending back to TRUSTED"; over-weighted bucket from §4.3 if MISS
    → "→ ×0.75 weight tomorrow". Forecasts only — application happens
    in morning.

---

## 5. Lessons-learned candidates (4:07:00 → 4:07:45)

5.1. Up to **three bullets**, deterministic:
    - **Bullet 1 — directional**: predicted vs actual in plain English.
      Ex: "Clean win: `LEAN BULLISH (+0.47)` aligned with SPX `+0.42%`."
      / "Loss: predicted `BEARISH (-1.20)`, SPX closed `+0.18%`. Review
      `news`." / "Stand-down correct: SPX moved `+0.11%`."
    - **Bullet 2 — bucket attribution**: top bucket and drove-day flag
      (§4.3). Ex: "`futures` (+1.20) drove the day." / "`sentiment`
      (-1.50) did NOT drive the day: VIX-derived fear was a head-fake."
    - **Bullet 3 — calibration tag**: one bucket to re-weight tomorrow.
      Ex: "`news` flagged WRONG-WAY: 3/10d negatively correlated.
      Tomorrow: ×0.50 clip." / "No re-weighting — direction correct."

5.2. Text generated by `close_track.write_close_report()` and re-rendered
    verbatim into the email body. Do not regenerate.

---

## 6. Append to the ledger — atomic, idempotent, append-only (4:07:45 → 4:09:00)

6.1. Build the row dict per `LEDGER_COLUMNS` in close_track.py:
    ```
    date, day_of_week, bias_score, bias_label, confidence, stand_down,
    structure, strike_short, strike_long, credit_or_debit,
    max_risk, max_reward, spx_open_945, spx_close, exit_price,
    trusted_bot_pnl, trusted_bot_pnl_pct_of_max_risk,
    running_total, running_winrate,
    morning_commit_hash, close_commit_hash, notes
    ```
    `running_total` and `running_winrate` filled by `append_ledger_row`;
    `close_commit_hash` patched in §9 after commit.

6.2. Call `append_ledger_row(row, dry_run=False)`. Invariants (any
    failure → hard abort): refuses duplicate `date` (idempotent);
    computes prior-rows SHA-256 (`_ledger_snapshot_hash`); atomic write
    via `tempfile.mkstemp` + `os.replace`; re-reads, verifies prior rows
    byte-identical (C-03, F-04); row count grew by exactly 1; new row is
    last. Violation raises `RuntimeError("APPEND-ONLY INVARIANT
    VIOLATED…")`, skill aborts. Recovery: `git checkout --
    ledger/paper-pnl.csv` + re-run.

6.3. Capture `(running_total, running_winrate)` for the report and email
    rolling-stats table.

6.4. Compute post-write SHA-256 of `paper-pnl.csv` as
    `LEDGER_SHA256_POST`. Published to `$PUB/integrity/$TODAY.txt` and
    embedded in email footer (C-04). MUST differ from `LEDGER_SHA256_PRE`
    unless this was a replay where row already existed (which 6.2
    would have caught — defense in depth).

---

## 7. Write the close report (4:09:00 → 4:10:30)

7.1. Path: `$REPO/SPX-Reports/close/$TODAY.md`. Overwrite forbidden — if
    file exists, halt with `DUPLICATE_RUN: $TODAY close report already
    on disk` (mirrors morning §7.1).

7.2. **Header block** (control C-02):
    ```
    ---
    title: SPX 0DTE Close Report — $TODAY
    framing: Educational analysis — synthetic paper-trade
    git_sha_start: $GIT_SHA_START
    pub_sha_start: $PUB_SHA_START
    ledger_sha256_pre:  $LEDGER_SHA256_PRE
    ledger_sha256_post: $LEDGER_SHA256_POST
    morning_commit:     $MORNING_COMMIT_HASH
    skill_version: 5.0.0
    audit_memo: /audits/AUDIT-MEMO-v5.0.md
    distribution: yasiramalik@gmail.com (owner only)
    data_source: $DATA_SOURCE   # polygon|yahoo|stooq|mock|mock_fallback
    ---
    ```

7.3. Body sections in order (generated by `write_close_report()`):
    (1) Hero — outcome chip, $ P&L, running cumulative, SPX close vs.
    open. (2) Predicted vs Actual table — `| Field | Morning | Actual |`
    rows for bias label, composite, direction, SPX 9:45 open, SPX 4:00
    close, day Δ (pts), day Δ (%), predicted-right? (T/F). (3) Bucket
    attribution (§4.2) — `| Bucket | Score | Sign | Day sign | Hit/Miss |`
    × 5 rows + top contributor + drove-day boolean. (4) Trusted-bot P&L
    breakdown — structure, strikes, credit/debit, max risk/reward, entry
    (9:45), exit (16:00 intrinsic), **P&L**, % of max risk. Synthetic
    footnote (§11.3) immediately under. (5) Rolling 10-day stats — window,
    wins, losses, stand-downs (=$0), total P&L, win rate, avg win, avg
    loss, largest drawdown (last 10 ledger rows; stand-downs as $0).
    (6) Lessons learned — 3 bullets from §5.1. (7) Tomorrow's calibration
    preview — §4.4. (8) AI peer sources (close-side) — placeholder table
    `| Source | Today's call (AM) | Actual | Hit/Miss | Status |` × 3
    (Codex/Gemini/Perplexity, all `NOT_WIRED_YET`). Caption: "PENDING
    WIRING; abstaining for v5.0." (9) Morning recap link —
    `$REPO/SPX-Reports/morning/$TODAY.md` + message-id from
    `$REPO/ledger/sent-emails.csv` row for `$TODAY`. (10) Dashboard Exit
    tab: `https://malikai-786.github.io/malikai-spx-dashboard/#/exit/$TODAY`.
    (11) Audit-memo: `/audits/AUDIT-MEMO-v5.0.md`. (12)
    NOT-INVESTMENT-ADVICE box (§8). (13) Hazrat Ali quote (§12).
    (14) Provenance footer — `git_sha_close`, `ledger_sha256_post`,
    `data_source`, `skill_version=5.0.0` (filled after §9).

7.4. Save report. Staging deferred to §9 because `close_commit_hash` is
    the result of that commit and must be patched back into row + header
    before push.

---

## 8. The NOT-INVESTMENT-ADVICE box (mandatory, exact text)

Top of email body, immediately after subject-line preview banner, before
hero. Styled block-quote (HTML `<blockquote>` or markdown `>`). Verbatim
identical to morning §8 — do **not** drift wording:

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

Implements control C-01. Pre-send lint diffs the rendered block against
the canonical string at `$REPO/scripts/not-investment-advice.txt`; aborts
on any diff.

---

## 9. Commit and push in BOTH repos (4:10:30 → 4:12:30)

9.1. **`$REPO`** — ledger + close report + AI-source-abstain logs:
    ```
    git -C "$REPO" add ledger/paper-pnl.csv \
                       SPX-Reports/close/$TODAY.md \
                       sources/responses/$TODAY-close-*.md \
                       dashboard/integrity/$TODAY.txt
    git -C "$REPO" commit -S -m "close($TODAY): trusted-bot P&L ledger update (v5.0)"
    ```
    Capture hash as `GIT_SHA_CLOSE`. No GPG key → unsigned + record
    `signed: false` in report metadata.

9.2. Call `_patch_close_hash($TODAY, GIT_SHA_CLOSE[:7])` from
    `close_track.py`: reads ledger, finds today's row, patches empty
    `close_commit_hash`, atomic rewrite. **Re-runs append-only invariant**
    — only last row's `close_commit_hash` field may change; any other
    byte diff → hard abort + `git reset --hard HEAD~1` rollback. Amend
    commit (`git commit --amend --no-edit -S`) so committed ledger
    contains the close hash.

9.3. Write `$PUB/data/$TODAY.json` and `$PUB/data/latest.json` per §10.
    Stage + commit in `$PUB`:
    ```
    git -C "$PUB" add data/$TODAY.json data/latest.json \
                      exit/$TODAY.html integrity/$TODAY.txt
    git -C "$PUB" commit -S -m "close($TODAY): dashboard Exit tab update (v5.0)"
    git -C "$PUB" push origin main
    ```
    Capture `PUB_SHA_CLOSE` for email footer.

9.4. Push `$REPO`:
    ```
    git -C "$REPO" push origin main
    git -C "$REPO" tag close/$TODAY $GIT_SHA_CLOSE
    git -C "$REPO" push origin close/$TODAY
    ```

9.5. Recompute ledger SHA-256 after patched commit; write
    `$REPO/dashboard/integrity/$TODAY.txt`. Copy to
    `$PUB/integrity/$TODAY.txt` and re-commit dashboard if differs from
    §9.3 (defensive — patch in 9.2 only touches `close_commit_hash`).

---

## 10. Update the dashboard JSON — Exit tab (4:09:30 → 4:11:00, parallel with §7)

10.1. Call `update_dashboard_json(snapshot, close_result, running_total,
    running_winrate)` from `close_track.py`. Writes
    `$REPO/dashboard/data/$TODAY.json` (source); agent mirrors to
    `$PUB/data/$TODAY.json` and updates `$PUB/data/latest.json` to point
    at `$TODAY`.

10.2. `close` block — Exit tab consumes every field. Required keys:
    `status` (`HIT|MISS|STAND-DOWN|INCOMPLETE`), `spx_open_945`,
    `spx_close`, `day_high`, `day_low`, `day_move_pct`, `exit_price`,
    `stand_down`, `structure`, `strike_short`, `strike_long`,
    `credit_or_debit`, `max_risk`, `max_reward`, `trusted_bot_pnl`,
    `trusted_bot_pnl_pct_of_max_risk`, `running_total`, `running_winrate`,
    `rolling_10d` (object: `wins`, `losses`, `stand_downs`, `total_pnl`,
    `win_rate`, `avg_win`, `avg_loss`, `largest_drawdown`),
    `bucket_attribution` (5 buckets → `"hit"|"miss"|"n/a"`),
    `lessons` (array of 3 strings), `tomorrow_calibration_preview`
    (array), `morning_commit_hash`, `close_commit_hash`, `pub_commit_hash`,
    `ledger_sha256`, `data_source`
    (`polygon|yahoo|stooq|mock|mock_fallback`), `skill_version` (`5.0.0`).
    Morning skill wrote the sibling `morning` block earlier; close MUST
    NOT mutate it. Read-modify-write only the `close` key.

10.3. `latest.json`:
    ```json
    {"latest_date": "$TODAY", "morning_published": true, "close_published": true}
    ```
    Atomic write via `_atomic_write`.

10.4. Render static Exit tab HTML at `$PUB/exit/$TODAY.html` via
    `$PUB/scripts/render_exit.py --date $TODAY`. Page reads the JSON
    above; renders same tables as email body. MUST NOT contain
    click-by-click broker variant (lives behind self-directed-trader
    gate on morning page).

---

## 11. Compose the close email payload (4:12:30 → 4:14:00)

11.1. **Subject line** (F-01 — no "Trade at" / "buy"):
    ```
    SPX 0DTE Close — Thu Mon DD, YYYY — {HIT|MISS|STAND-DOWN} $${SYNTH_PNL} — Educational
    ```
    Examples: `SPX 0DTE Close — Thu May 28, 2026 — HIT $+85.00 —
    Educational` / `… — MISS $-120.00 — Educational` / `… — STAND-DOWN
    $0.00 — Educational`. Date is `strftime("%a %b %d, %Y")` in
    America/New_York. `$${PNL}` is `$+85.00` (signed, 2 decimals);
    stand-down → `$0.00` (sign-less zero).

11.2. **JSON payload** for `gmail_send.py` (F-02 distribution lock):
    ```json
    {
      "to":  ["yasiramalik@gmail.com"],
      "cc":  [], "bcc": [],
      "subject": "<from 11.1>",
      "body_markdown": "<rendered from §11.4>",
      "body_html": "<cmarkgfm pass>",
      "headers": {
        "X-MalikAI-Version": "5.0.0", "X-MalikAI-Skill": "eod-monitor",
        "X-MalikAI-Git-Sha": "<GIT_SHA_CLOSE>",
        "X-MalikAI-Pub-Sha": "<PUB_SHA_CLOSE>",
        "X-MalikAI-Ledger-Sha256": "<LEDGER_SHA256_POST>",
        "X-MalikAI-Morning-Sha": "<MORNING_COMMIT_HASH>",
        "X-MalikAI-Framing": "EDUCATIONAL",
        "X-MalikAI-Outcome": "<HIT|MISS|STAND-DOWN>"
      }
    }
    ```
    **Hard assertion before send** (DISTRIBUTION_GUARD):
    `payload["to"] == ["yasiramalik@gmail.com"]`,
    `payload["cc"] == []`, `payload["bcc"] == []`. Failure → abort with
    `DISTRIBUTION_GUARD_VIOLATION`; do **not** invoke gmail_send.py. Same
    guard runs again inside gmail_send.py (defense in depth).

11.3. **Synthetic-paper-trade footnote** (verbatim — must accompany every
    `$` figure in body):
    ```
    > Synthetic paper-trade. Every dollar figure on this page is the
    > hypothetical outcome of a 1-lot of the recommended defined-risk
    > structure exited at the 4:00 ET cash-index close. No fees, no
    > slippage, no broker, no real money. Stand-down days counted as
    > $0 (anti-survivorship). This is the author's research journal,
    > not a P&L statement of any real account.
    ```

11.4. **Body section ordering** (mandatory):
    (1) NOT-INVESTMENT-ADVICE box (§8). (2) Hero — outcome chip, big $
    P&L number, "View Exit tab →" link to
    `https://malikai-786.github.io/malikai-spx-dashboard/#/exit/$TODAY`.
    (3) Predicted vs Actual table (§7.3 #2). (4) Bucket attribution
    (§7.3 #3). (5) Trusted-bot P&L breakdown (§7.3 #4) + synthetic
    footnote (§11.3). (6) Rolling 10-day stats (§7.3 #5) + one-line
    "Same caveat — synthetic." (7) Lessons learned (§5.1). (8) Tomorrow's
    calibration preview (§4.4). (9) AI peer sources actual hit/miss
    (§7.3 #8 placeholder + body: "Codex / Gemini / Perplexity not wired
    in v5.0; this section abstains until v5.1+."). (10) Morning recap —
    one sentence + gmail deeplink (`https://mail.google.com/mail/u/0/#all/$MID`)
    and dashboard morning-report link. (11) Dashboard Exit tab button.
    (12) Audit-memo link. (13) Provenance footer — single mono line:
    `git: $GIT_SHA_CLOSE_SHORT  pub: $PUB_SHA_CLOSE_SHORT  ledger-sha256:
    $LEDGER_SHA256_POST  morning: $MORNING_HASH  data: $DATA_SOURCE
    skill: 5.0.0`. (14) Hazrat Ali quote — final line, italicized.

11.5. **Banned-phrases lint** before send (F-01 — same ban-list as
    morning): `"Trade at"`, `"buy "`, `"sell "`, `"recommendation"`,
    `"signal to enter"`, `"Option Alpha"`, `"Tastytrade"`, `"click "`
    (case-insensitive). On hit, substitute via
    `$REPO/scripts/banned_phrases.json` and re-render; uncovered hit →
    `BANNED_PHRASE: <phrase>` abort. Runs on **both** markdown and
    rendered HTML (HTML escaping can re-introduce phrases markdown hid).

11.6. **Payload write** — serialize to `/tmp/spx-close-$TODAY.json` mode
    `600` for inspection/replay. §13 reads from this path.

---

## 12. Hazrat Ali (RA) quote — rotating pool

Same pool as morning (`$REPO/scripts/quotes.txt`). Morning picks via
`hash($TODAY + "morning")`; close picks via `hash($TODAY + "close")` — a
different deterministic draw so morning and close don't always share a
quote. v5.0 default pool (5 entries):

1. *"Do not let your difficulty in finding the right path stop you from walking it."*
2. *"The strongest among you is the one who controls his anger."*
3. *"Patience is of two kinds: patience over what pains you, and patience against what you covet."*
4. *"He who knows himself knows his Lord."*
5. *"The best wealth is the abandoning of desires."*

Attribution: `— Hazrat Ali (RA)`.

---

## 13. Send the email at 4:15:00 ET sharp (4:14:00 → 4:15:00)

13.1. Block-sleep until wall clock reaches
    `$TODAY 16:15:00 America/New_York`. Monotonic, sub-second precision.
    Never sleep past 16:15:00; if somehow at 16:15:01 without firing,
    send immediately + log `LATE_SEND` warning.

13.2. Re-assert distribution guard at T-1s (same 3 asserts as §11.2).
    Send:
    - **Primary:** `python $REPO/scripts/gmail_send.py <
      /tmp/spx-close-$TODAY.json` (uses `~/.gmail-mcp/token.json`).
    - **Fallback:** gmail_send.py non-zero → macOS osascript driver
      `$REPO/scripts/mail_send.scpt`, same payload path. osascript path
      enforces same distribution guard before composing.

13.3. Capture `message_id` (stdout of gmail_send.py:
    `{"id": "...", "threadId": "..."}`).

13.4. **Append `$REPO/ledger/email-log.csv`** (control C-09). Schema:
    `timestamp_iso_et,date,event,message_id,recipient_count,git_sha,ledger_sha256`.
    Row: `$NOW_ET_ISO,$TODAY,close-sent,$MESSAGE_ID,1,$GIT_SHA_CLOSE,
    $LEDGER_SHA256_POST`. Same atomic append-only pattern as P&L ledger
    (`_atomic_write` + invariant check). Hard fail on `recipient_count != 1`.

13.5. Hard fallback: at **4:18:00 ET** with no message_id captured →
    invoke `[INCOMPLETE]` per §14 with best-known state and send
    immediately. Do NOT block on retries past 4:18.

---

## 14. INCOMPLETE fallback at 4:18:00 ET (hard rule)

If at 16:18:00 ET §13.3 has not captured a message_id, abandon the full
pipeline and send a minimal email:

```
Subject: SPX 0DTE Close — Thu Mon DD, YYYY — [INCOMPLETE] — Educational

NOT INVESTMENT ADVICE — EDUCATIONAL CONTENT ONLY.

Today's close pipeline did not complete by 16:18 ET. No final P&L is
being published in this message.

Best-known partial state at cutoff:
- Morning bias:     $BIAS_LABEL  ($BIAS_SCORE)
- SPX 4:00 close:   $SPX_CLOSE (or "UNAVAILABLE")
- Synthetic P&L:    $TRUSTED_BOT_PNL (or "UNCOMPUTED")
- Ledger appended:  yes / no
- Reason: <last_error_message>

Git sha start/close: $GIT_SHA_START / $GIT_SHA_CLOSE (or "uncommitted")
Ledger sha256 pre/post: $LEDGER_SHA256_PRE / $LEDGER_SHA256_POST (or n/a)
Audit memo: /audits/AUDIT-MEMO-v5.0.md
Dashboard Exit: https://malikai-786.github.io/malikai-spx-dashboard/#/exit/$TODAY

— Hazrat Ali (RA): "Do not let your difficulty in finding the right path
stop you from walking it."

> Synthetic paper-trade. No real money moved. Educational only.
```

Same distribution guard + banned-phrases lint. INCOMPLETE event logged to
`$REPO/ledger/incomplete-runs.csv` (append-only, `event=close-incomplete`).
Dashboard Exit tab patched: `close.status → INCOMPLETE` in
`$PUB/data/$TODAY.json`.

---

## 15. Post-send (4:15:00 → 4:17:00)

15.1. **Log AI peer source responses** (placeholders in v5.0). For each
    of `{codex, gemini, perplexity}`, write a verbatim file at
    `$REPO/sources/responses/$TODAY-close-<model>.md` containing the
    literal `NOT_WIRED_YET — placeholder for v5.0 close-side source:
    <name>` followed by the prompt template that would have been sent
    (SPX 9:45 open, 4:00 close, morning composite, ask for independent
    `[-2.0, +2.0]` bias + one-sentence rationale) and the line
    `Response was abstained — wiring deferred to v5.1+.` Saved verbatim
    (C-05). Files staged in §9.1 + committed with ledger so the audit
    log captures *intentional* abstain, not silent skip.

15.2. **Commit + push email log:**
    ```
    git -C "$REPO" add ledger/email-log.csv sources/responses/$TODAY-close-*.md
    git -C "$REPO" commit -S -m "close($TODAY): email log + AI source abstain"
    git -C "$REPO" push origin main
    ```

15.3. **Dashboard Exit tab final touch.** After email lands, re-render
    `$PUB/exit/$TODAY.html` with `message_id` embedded as "View sent
    email" gmail deeplink (`https://mail.google.com/mail/u/0/#all/$MID`):
    ```
    git -C "$PUB" add exit/$TODAY.html
    git -C "$PUB" commit -S -m "close($TODAY): backfill sent message_id"
    git -C "$PUB" push origin main
    ```

15.4. Verify live URL returns Exit tab with today's data. Hit
    `https://malikai-786.github.io/malikai-spx-dashboard/data/latest.json`
    and confirm `"close_published": true` and `"latest_date": $TODAY`.
    GitHub Pages CDN can lag up to 60s — retry until 4:17:00 ET, then
    stop; tomorrow's morning §1 ingestion will notice.

---

## 16. Time budget — STRICT (mirror morning)

```
4:00 — Market closes. Skill starts.
4:00–4:05 — Pre-flight, load morning report, fetch SPX close. (§0,§1,§2)
4:05–4:10 — Compute P&L, bucket attribution, lessons,
            append ledger row. (§3,§4,§5,§6)
4:10–4:13 — Write close report, update dashboard JSON,
            commit + push both repos. (§7,§9,§10)
4:13–4:14 — Compose email body, run banned-phrases lint,
            write payload to /tmp/spx-close-$TODAY.json. (§11)
4:14 — HARD CUT: compose final email from what's ready.
            No new computation past this minute.
4:14:30 — Invoke gmail_send.py.
4:15:00 — SENT. Capture message_id, append email-log.csv.
4:15:00–4:17:00 — Post-send: AI source abstain logs,
                  dashboard message_id backfill, verify live URL. (§15)
4:18 — Abort and send [INCOMPLETE] if §13.3 did not capture a
       message_id. (§14)
```

Discipline mirrors morning: the wall-clock 4:15 ET send is the contract.
Everything else is best-effort.

---

## 17. Guardrails (mirror morning §15)

17.1. **Distribution guard violation** — hard abort, no fallback. F-02.
17.2. **Banned phrase** in body — hard abort if not auto-substitutable. F-01.
17.3. **Missing audit-memo link or NOT-INVESTMENT-ADVICE box** — hard abort. C-01.
17.4. **Ledger mutation** — any non-tail write, or any byte change in a
     prior row other than the documented `close_commit_hash` patch in
     §9.2 — hard abort, pre-commit hook rejects, `git reset --hard HEAD~1`.
     C-03, F-04.
17.5. **Git working tree dirty** in `$REPO` or `$PUB` — preflight fails. C-02.
17.6. **OAuth token mode not 600** — preflight fails. C-08.
17.7. **Payment processor string anywhere** — pre-commit hook rejects. C-07, F-03.
17.8. **AI peer sources non-placeholder, ≥2/3 disagree with morning
     composite** (future v5.1+) — close email gets "AM/PM disagreement"
     callout; morning is the gate for downgrades. C-06.
17.9. **Duplicate-run guard** — ledger §6.2, report §7.1, email-log §13.4
     all idempotent up to but not including the gmail send.
17.10. **Stand-down rows MUST hit ledger as $0** — anti-survivorship. F-05.
17.11. **Synthetic-paper-trade footnote** — positive lint: body MUST
      contain the canonical footnote string at least once. Hard abort if not.
17.12. **Educational framing only** — defined-risk structure is descriptive,
      not a recommendation. No broker steps in body; click-by-click variant
      stays behind the self-directed-trader gate on the dashboard.

---

## 18. Failure recovery — partial-state restart

Crashes between §6 (ledger appended) and §13 (email sent) restart safely:
- §6 idempotent — re-run raises `Ledger already has a row for $TODAY`;
  catch, skip, continue at §7.
- §7 refuses overwrite — re-run raises `DUPLICATE_RUN`; catch, skip,
  continue at §9.
- §9 commit/push idempotent — `git commit` on clean tree is no-op;
  `git push` idempotent.
- §10 dashboard JSON read-modify-write idempotent.
- §13 is the only non-idempotent step. Email-log duplicate guard in 13.4
  makes double-send detectable: existing `(date, close-sent)` row →
  abort `DUPLICATE_SEND_PREVENTED` + critical alert.

Restart contract: any re-run on the same `$TODAY` MUST either reproduce
identical ledger/report/dashboard state and skip sending, OR send exactly
once if no prior send is logged.

---

## 19. Version log

**v4.1** → **v5.0** close-of-day deltas (May 28, 2026):
- Renamed `close-of-day.sh` → skill `eod-monitor` (mirrors morning shape).
- Two-repo commit + push (`$REPO` for ledger/report, `$PUB` for
  dashboard JSON / Exit tab).
- Distribution locked to owner-only; BCC removed (F-02).
- Subject reframed: `HIT|MISS|STAND-DOWN $${PNL}` chip + `— Educational`
  (F-01).
- Synthetic-paper-trade footnote mandatory on every `$` figure (F-05, C-10).
- Stand-down rows confirmed as `$0.00` (anti-survivorship) — explicit
  in §3.4, §17.10 (F-05).
- AI peer sources mirrored as placeholder close-side calls; 3-row
  "abstaining for v5.0" table; abstain reason logged per model per day
  (F-05, C-05).
- Append-only ledger invariant tightened: §9.2 carves out
  `close_commit_hash` patch as the **only** permitted post-append
  mutation, with re-check (C-03, F-04).
- Outcome classification (§3.3) explicit: HIT/MISS/STAND-DOWN/FLAT —
  chip drives subject + Exit tab state.
- Bucket attribution (§4) + tomorrow's calibration preview (§4.4)
  formalized; feed morning §1.5/§1.6 for next session.
- INCOMPLETE fallback moved 4:25 → 4:18 ET (15-min total budget vs.
  morning's 30-min).
- Dashboard Exit tab message_id backfill is post-send — deeplink only
  exists after message lands; dashboard re-rendered + pushed once we
  have the id (§15.3).

---

*End of SKILL-close.md v5.0. Owner: Yasir A. Malik. Audit memo of record:
`/audits/AUDIT-MEMO-v5.0.md`. Companion to `SKILL.md` (morning-bias).
The loop closes here; tomorrow morning it opens again.*
