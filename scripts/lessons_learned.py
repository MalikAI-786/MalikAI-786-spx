#!/usr/bin/env python3
# SYNTHETIC PAPER-TRADE LEDGER. Real money never moved. Educational only. Not investment advice.
"""
lessons_learned.py — Roll up the trailing 10 trading days into a digest that
tomorrow's morning.py step 1 ingests.

Output: ledger/lessons-{YYYY-MM-DD}.md

Sections:
  - Rolling stats (win-rate, cumulative P&L, drawdown, avg win/loss)
  - Bucket calibration (which buckets are over/under-weighting)
  - Calibration patterns: which patterns are working
  - Day-of-week performance (best / worst day)
  - Stand-down quality (were stand-downs warranted)
  - Top 3 candidate adjustments for tomorrow

Inputs:
  - ledger/paper-pnl.csv          (full history)
  - ledger/morning-signals.csv    (per-day bucket contributions + patterns)
  - SPX-Reports/close/*.md        (free-form notes; lightly grepped)

Usage:
  python scripts/lessons_learned.py
  python scripts/lessons_learned.py --date 2026-05-28
  python scripts/lessons_learned.py --window 10
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import statistics
import sys
import tempfile
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH = REPO_ROOT / "ledger" / "paper-pnl.csv"
MORNING_SIGNALS_PATH = REPO_ROOT / "ledger" / "morning-signals.csv"
CLOSE_REPORTS_DIR = REPO_ROOT / "SPX-Reports" / "close"

BUCKETS = ["futures", "macro", "news", "intl", "sentiment"]


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _f(v, default=0.0) -> float:
    try:
        if v in ("", None):
            return default
        return float(v)
    except (ValueError, TypeError):
        return default


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _max_drawdown(pnls: list[float]) -> tuple[float, int]:
    """Return (max drawdown $, longest losing streak in days)."""
    if not pnls:
        return 0.0, 0
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    streak = 0
    longest = 0
    for p in pnls:
        cum += p
        if cum > peak:
            peak = cum
        dd = peak - cum
        if dd > max_dd:
            max_dd = dd
        if p < 0:
            streak += 1
            longest = max(longest, streak)
        else:
            streak = 0
    return round(max_dd, 2), longest


def build_digest(date: str, window: int) -> str:
    ledger = _read_csv(LEDGER_PATH)
    signals = {r["date"]: r for r in _read_csv(MORNING_SIGNALS_PATH)}

    # Take rows whose date <= cutoff, last `window` of them.
    rows = [r for r in ledger if r["date"] <= date]
    rows = rows[-window:]

    if not rows:
        return f"# Lessons Learned — {date}\n\n_No ledger rows yet._\n"

    # ---- Rolling stats
    pnls = [_f(r["trusted_bot_pnl"]) for r in rows]
    traded = [r for r in rows if str(r.get("stand_down", "")).lower() != "true"]
    wins = [r for r in traded if _f(r["trusted_bot_pnl"]) > 0]
    losses = [r for r in traded if _f(r["trusted_bot_pnl"]) < 0]
    win_rate = (len(wins) / len(traded)) if traded else 0.0
    cum_pnl = round(sum(pnls), 2)
    avg_win = round(statistics.mean(_f(r["trusted_bot_pnl"]) for r in wins), 2) if wins else 0.0
    avg_loss = round(statistics.mean(_f(r["trusted_bot_pnl"]) for r in losses), 2) if losses else 0.0
    max_dd, longest_losing = _max_drawdown(pnls)

    # ---- Bucket calibration: for each bucket, correlate sign of contribution
    # with sign of P&L. Positive correlation -> bucket is well-calibrated.
    bucket_score: dict = {b: {"hits": 0, "tot": 0, "weighted_pnl": 0.0} for b in BUCKETS}
    for r in rows:
        s = signals.get(r["date"])
        if not s:
            continue
        pnl = _f(r["trusted_bot_pnl"])
        if str(r.get("stand_down", "")).lower() == "true":
            continue
        for b in BUCKETS:
            v = _f(s.get(b))
            if v == 0:
                continue
            bucket_score[b]["tot"] += 1
            bucket_score[b]["weighted_pnl"] += v * pnl
            # Hit = bucket sign matched P&L sign
            if (v > 0 and pnl > 0) or (v < 0 and pnl < 0):
                bucket_score[b]["hits"] += 1

    bucket_lines = []
    over_under = []
    for b in BUCKETS:
        info = bucket_score[b]
        if info["tot"] == 0:
            bucket_lines.append(f"  - {b}: no signal in window")
            continue
        hit_rate = info["hits"] / info["tot"]
        wp = round(info["weighted_pnl"], 2)
        verdict = (
            "well-calibrated" if hit_rate >= 0.6
            else ("under-weighting" if hit_rate >= 0.4 else "over-weighting / inverted")
        )
        bucket_lines.append(
            f"  - {b}: hit-rate {hit_rate:.0%} over {info['tot']} active days, "
            f"weighted-pnl ${wp:+.2f} -> {verdict}"
        )
        if hit_rate < 0.4:
            over_under.append(f"down-weight `{b}` (hit-rate {hit_rate:.0%})")
        elif hit_rate >= 0.7:
            over_under.append(f"up-weight `{b}` (hit-rate {hit_rate:.0%})")

    # ---- Calibration patterns
    pattern_stats: dict = {}
    for r in rows:
        s = signals.get(r["date"])
        if not s:
            continue
        pat = s.get("calibration_pattern", "") or "unknown"
        d = pattern_stats.setdefault(pat, {"n": 0, "pnl": 0.0, "wins": 0, "traded": 0})
        d["n"] += 1
        d["pnl"] += _f(r["trusted_bot_pnl"])
        if str(r.get("stand_down", "")).lower() != "true":
            d["traded"] += 1
            if _f(r["trusted_bot_pnl"]) > 0:
                d["wins"] += 1
    pattern_lines = []
    for pat, d in sorted(pattern_stats.items(), key=lambda kv: -kv[1]["pnl"]):
        wr = (d["wins"] / d["traded"]) if d["traded"] else 0.0
        pattern_lines.append(
            f"  - `{pat}`: n={d['n']}, pnl=${d['pnl']:+.2f}, win-rate={wr:.0%}"
        )

    # ---- Day-of-week performance
    dow_stats: dict = {}
    for r in rows:
        dow = r.get("day_of_week", "?")
        d = dow_stats.setdefault(dow, {"n": 0, "pnl": 0.0, "wins": 0, "traded": 0})
        d["n"] += 1
        d["pnl"] += _f(r["trusted_bot_pnl"])
        if str(r.get("stand_down", "")).lower() != "true":
            d["traded"] += 1
            if _f(r["trusted_bot_pnl"]) > 0:
                d["wins"] += 1
    dow_sorted = sorted(dow_stats.items(), key=lambda kv: -kv[1]["pnl"])
    best_dow = dow_sorted[0][0] if dow_sorted else "n/a"
    worst_dow = dow_sorted[-1][0] if dow_sorted else "n/a"
    dow_lines = [
        f"  - {dow}: n={d['n']}, pnl=${d['pnl']:+.2f}, "
        f"win-rate={(d['wins'] / d['traded']) if d['traded'] else 0.0:.0%}"
        for dow, d in dow_sorted
    ]

    # ---- Stand-down quality
    sd_rows = [r for r in rows if str(r.get("stand_down", "")).lower() == "true"]
    sd_correct = 0
    sd_total = len(sd_rows)
    for r in sd_rows:
        try:
            move = abs(_f(r["spx_close"]) - _f(r["spx_open_945"]))
            if move < 5.0:
                sd_correct += 1
        except Exception:
            pass
    sd_quality = (sd_correct / sd_total) if sd_total else None

    # ---- Top adjustments for tomorrow
    adjustments = list(over_under)
    if pattern_stats:
        worst_pat = min(pattern_stats.items(), key=lambda kv: kv[1]["pnl"])
        if worst_pat[1]["pnl"] < 0:
            adjustments.append(
                f"flag pattern `{worst_pat[0]}` (cum pnl ${worst_pat[1]['pnl']:+.2f}) "
                f"as caution"
            )
    if longest_losing >= 3:
        adjustments.append(
            f"losing streak of {longest_losing} days hit — consider tighter "
            f"confidence threshold tomorrow"
        )
    if not adjustments:
        adjustments.append("no calibration changes recommended; system is in spec")
    adjustments = adjustments[:3]

    # ---- Render
    out = []
    out.append(f"# Lessons Learned — {date}")
    out.append("")
    out.append(
        "**Window:** trailing {n} trading days "
        "(synthetic paper-trade ledger; real money never moved).".format(n=len(rows))
    )
    out.append("")
    out.append("## Rolling stats")
    out.append(f"- Cumulative P&L: **${cum_pnl:+.2f}**")
    out.append(
        f"- Win-rate (active trades only): **{win_rate:.0%}** "
        f"({len(wins)}/{len(traded)})"
    )
    out.append(f"- Avg win: ${avg_win:+.2f}   avg loss: ${avg_loss:+.2f}")
    out.append(f"- Max drawdown: ${max_dd:.2f}")
    out.append(f"- Longest losing streak: {longest_losing} days")
    out.append("")
    out.append("## Bucket calibration")
    out.extend(bucket_lines)
    out.append("")
    out.append("## Calibration patterns")
    if pattern_lines:
        out.extend(pattern_lines)
    else:
        out.append("  (no pattern data)")
    out.append("")
    out.append("## Day-of-week performance")
    out.extend(dow_lines)
    out.append(f"  - **Best:** {best_dow}    **Worst:** {worst_dow}")
    out.append("")
    out.append("## Stand-down quality")
    if sd_quality is None:
        out.append("  - no stand-downs in window")
    else:
        out.append(
            f"  - {sd_correct}/{sd_total} stand-downs were warranted "
            f"(SPX moved <5 pts on those days) -> {sd_quality:.0%}"
        )
    out.append("")
    out.append("## Top adjustments for tomorrow (ingested by morning.py step 1)")
    for a in adjustments:
        out.append(f"- {a}")
    out.append("")
    out.append("---")
    out.append("_Generated by `scripts/lessons_learned.py`. Not investment advice._")
    return "\n".join(out) + "\n"


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", default=None, help="cutoff date YYYY-MM-DD (default: today ET)")
    p.add_argument("--window", type=int, default=10, help="trailing days to roll up")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    if args.date:
        date = args.date
    else:
        try:
            from zoneinfo import ZoneInfo
            date = dt.datetime.now(ZoneInfo("America/New_York")).date().isoformat()
        except Exception:
            date = dt.date.today().isoformat()

    content = build_digest(date, args.window)
    out = REPO_ROOT / "ledger" / f"lessons-{date}.md"
    if args.dry_run:
        print(content)
    else:
        _atomic_write(out, content)
        print(f"[lessons_learned] wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
