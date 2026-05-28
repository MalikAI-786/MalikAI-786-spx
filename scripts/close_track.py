#!/usr/bin/env python3
# SYNTHETIC PAPER-TRADE LEDGER. Real money never moved. Educational only. Not investment advice.
"""
close_track.py — SPX 0DTE v5.0 close-of-day tracker.

Runs at 4:15 PM ET on US trading days.

Pipeline:
  1. Read today's morning report from SPX-Reports/morning/{date}.md
  2. Extract score, structure, strikes, max_risk, max_reward, confidence
  3. Fetch actual SPX 9:45 ET open and 4:00 ET close
  4. Compute synthetic 'trusted-bot' P&L assuming 1-lot of recommended structure
     exited at 4:00 ET close
  5. Append atomically to ledger/paper-pnl.csv (idempotent: refuses duplicate dates)
  6. Write close report to SPX-Reports/close/{date}.md
  7. Update dashboard/data/{date}.json close fields
  8. Git commit with deterministic message format
  9. Verify ledger append-only invariant

Usage:
  python scripts/close_track.py                # process today (ET)
  python scripts/close_track.py --date 2026-05-28
  python scripts/close_track.py --dry-run      # no writes, no commit
  python scripts/close_track.py --no-commit    # write files but skip git

Conventions:
  - Times: America/New_York
  - Money: USD
  - 1 SPX option multiplier: $100
  - Stand-down rows record $0 P&L
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH = REPO_ROOT / "ledger" / "paper-pnl.csv"
MORNING_SIGNALS_PATH = REPO_ROOT / "ledger" / "morning-signals.csv"
MORNING_REPORTS_DIR = REPO_ROOT / "SPX-Reports" / "morning"
CLOSE_REPORTS_DIR = REPO_ROOT / "SPX-Reports" / "close"
DASHBOARD_DATA_DIR = REPO_ROOT / "dashboard" / "data"

OPTION_MULTIPLIER = 100  # 1 SPX/SPXW contract = $100 per $1 of premium

LEDGER_COLUMNS = [
    "date", "day_of_week", "bias_score", "bias_label", "confidence",
    "stand_down", "structure", "strike_short", "strike_long",
    "credit_or_debit", "max_risk", "max_reward",
    "spx_open_945", "spx_close", "exit_price",
    "trusted_bot_pnl", "trusted_bot_pnl_pct_of_max_risk",
    "running_total", "running_winrate",
    "morning_commit_hash", "close_commit_hash", "notes",
]

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MorningSnapshot:
    date: str
    day_of_week: str
    bias_score: float
    bias_label: str
    confidence: str
    stand_down: bool
    structure: str
    strike_short: Optional[float]
    strike_long: Optional[float]
    credit_or_debit: Optional[float]  # signed: + credit received, - debit paid
    max_risk: float
    max_reward: float
    morning_commit_hash: str
    bucket_contributions: dict  # {"futures": 1.0, "macro": 0.5, ...}


@dataclass
class CloseResult:
    spx_open_945: float
    spx_close: float
    exit_price: float
    trusted_bot_pnl: float
    trusted_bot_pnl_pct_of_max_risk: float


# ---------------------------------------------------------------------------
# Morning report parsing
# ---------------------------------------------------------------------------

def _parse_float(s: str) -> Optional[float]:
    try:
        return float(s.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def read_morning_report(date: str) -> MorningSnapshot:
    """Parse SPX-Reports/morning/{date}.md to extract the day's signal.

    Expected structure (loose key:value lines, robust to formatting drift):
      Score: 2.5
      Label: bullish
      Confidence: medium
      Stand-down: false
      Structure: put_credit_spread
      Strike short: 5275
      Strike long: 5270
      Credit: 0.85           (or 'Debit: 0.85')
      Max risk: 415.00
      Max reward: 85.00
      Bucket - futures: 1.0
      Bucket - macro: 0.5
      Bucket - news: 0.0
      Bucket - intl: 0.5
      Bucket - sentiment: 0.5
      Morning commit: a1b2c3d
    """
    path = MORNING_REPORTS_DIR / f"{date}.md"
    if not path.exists():
        raise FileNotFoundError(f"Morning report not found: {path}")

    text = path.read_text(encoding="utf-8")
    kv: dict = {}
    bucket: dict = {}
    for raw in text.splitlines():
        line = raw.strip().lstrip("-*# ").strip()
        m = re.match(r"^([A-Za-z][A-Za-z _-]+?)\s*[:=]\s*(.+?)\s*$", line)
        if not m:
            continue
        key = m.group(1).strip().lower()
        val = m.group(2).strip()
        if key.startswith("bucket"):
            bname = key.replace("bucket", "").strip(" -_").lower()
            if bname:
                bucket[bname] = _parse_float(val) or 0.0
        else:
            kv[key] = val

    stand_down_raw = kv.get("stand-down", kv.get("stand down", "false")).lower()
    stand_down = stand_down_raw in ("true", "yes", "1", "stand-down", "stand down")

    credit = _parse_float(kv.get("credit", ""))
    debit = _parse_float(kv.get("debit", ""))
    cod = credit if credit is not None else (-debit if debit is not None else None)

    day_of_week = dt.date.fromisoformat(date).strftime("%A")

    return MorningSnapshot(
        date=date,
        day_of_week=day_of_week,
        bias_score=_parse_float(kv.get("score", "0")) or 0.0,
        bias_label=kv.get("label", "neutral"),
        confidence=kv.get("confidence", "low"),
        stand_down=stand_down,
        structure=kv.get("structure", "stand_down" if stand_down else "unknown"),
        strike_short=_parse_float(kv.get("strike short", "")),
        strike_long=_parse_float(kv.get("strike long", "")),
        credit_or_debit=cod,
        max_risk=_parse_float(kv.get("max risk", "0")) or 0.0,
        max_reward=_parse_float(kv.get("max reward", "0")) or 0.0,
        morning_commit_hash=kv.get("morning commit", kv.get("commit", "unknown"))[:7],
        bucket_contributions=bucket,
    )


# ---------------------------------------------------------------------------
# Market data
# ---------------------------------------------------------------------------

def get_spx_intraday(date: str) -> tuple[float, float]:
    """Return (spx_open_945_ET, spx_close_400_ET) for the given date.

    TODO: Wire to a real free data source.
      Options (no API key required for SPX/^GSPC):
        - Stooq:   https://stooq.com/q/d/?s=^spx&i=d   (daily only — won't give 9:45 mark)
        - Yahoo:   https://query1.finance.yahoo.com/v8/finance/chart/^GSPC
                   ?interval=15m&range=5d                 (15-min bars; 9:45 bar = 9:30-9:45)
        - Polygon free tier: aggs/ticker/I:SPX/range/15/minute/{date}/{date}

    Until wired, returns a deterministic mock derived from the date string so
    tests are reproducible. The mock is CLEARLY NOT real data.
    """
    seed = int(hashlib.sha256(date.encode()).hexdigest()[:8], 16)
    base = 5300.0
    open_drift = ((seed % 1000) - 500) / 50.0       # ~+/- 10 pts
    close_drift = (((seed >> 8) % 1000) - 500) / 25.0  # ~+/- 20 pts
    spx_open = round(base + open_drift, 2)
    spx_close = round(spx_open + close_drift, 2)
    # Mark mock data with a banner via stderr (caller can see).
    print(
        f"[MOCK] get_spx_intraday({date}) -> open={spx_open}, close={spx_close} "
        f"(replace with real source before going live)",
        file=sys.stderr,
    )
    return spx_open, spx_close


# ---------------------------------------------------------------------------
# Synthetic P&L
# ---------------------------------------------------------------------------

def compute_trusted_bot_pnl(m: MorningSnapshot, spx_close: float) -> CloseResult:
    """Compute the synthetic 'trusted-bot' P&L for a 1-lot of the recommended
    defined-risk structure, exited at the 4:00 ET close.

    Supported structures:
      - stand_down              -> $0
      - put_credit_spread       -> short put / long lower put, credit received
      - call_credit_spread      -> short call / long higher call, credit received
      - put_debit_spread        -> long put / short lower put, debit paid
      - call_debit_spread       -> long call / short higher call, debit paid

    At 4:00 ET expiration, each leg is worth max(0, intrinsic). Exit_price is
    the spread's intrinsic value at close, in option points (one decimal).
    P&L per 1-lot = (credit_received - intrinsic_owed) * 100 for credit spreads,
                  = (intrinsic_owned - debit_paid)   * 100 for debit spreads.
    """
    spx_open_945, _ = get_spx_intraday(m.date)

    if m.stand_down or m.structure == "stand_down":
        return CloseResult(
            spx_open_945=spx_open_945,
            spx_close=spx_close,
            exit_price=0.0,
            trusted_bot_pnl=0.0,
            trusted_bot_pnl_pct_of_max_risk=0.0,
        )

    short = m.strike_short
    long_ = m.strike_long
    cod = m.credit_or_debit
    if short is None or long_ is None or cod is None:
        raise ValueError(
            f"Missing strikes/credit for non-stand-down structure: {m.structure}"
        )

    s = m.structure.lower()

    if s == "put_credit_spread":
        short_intrinsic = max(0.0, short - spx_close)
        long_intrinsic = max(0.0, long_ - spx_close)
        spread_value = short_intrinsic - long_intrinsic     # what we owe at close
        pnl_points = cod - spread_value                     # credit kept - owed
    elif s == "call_credit_spread":
        short_intrinsic = max(0.0, spx_close - short)
        long_intrinsic = max(0.0, spx_close - long_)
        spread_value = short_intrinsic - long_intrinsic
        pnl_points = cod - spread_value
    elif s == "put_debit_spread":
        long_intrinsic = max(0.0, long_ - spx_close)
        short_intrinsic = max(0.0, short - spx_close)
        spread_value = long_intrinsic - short_intrinsic
        pnl_points = spread_value - abs(cod)
    elif s == "call_debit_spread":
        long_intrinsic = max(0.0, spx_close - long_)
        short_intrinsic = max(0.0, spx_close - short)
        spread_value = long_intrinsic - short_intrinsic
        pnl_points = spread_value - abs(cod)
    else:
        raise ValueError(f"Unsupported structure: {m.structure}")

    pnl = round(pnl_points * OPTION_MULTIPLIER, 2)
    exit_price = round(spread_value, 2)
    pct = round(100.0 * pnl / m.max_risk, 2) if m.max_risk > 0 else 0.0

    return CloseResult(
        spx_open_945=spx_open_945,
        spx_close=spx_close,
        exit_price=exit_price,
        trusted_bot_pnl=pnl,
        trusted_bot_pnl_pct_of_max_risk=pct,
    )


# ---------------------------------------------------------------------------
# Ledger I/O — atomic, append-only, idempotent
# ---------------------------------------------------------------------------

def _read_ledger_rows() -> list[dict]:
    if not LEDGER_PATH.exists():
        return []
    with LEDGER_PATH.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _ledger_snapshot_hash(rows: list[dict]) -> str:
    """Stable hash of the ledger up to (and including) the last row.
    Used for the append-only invariant check after we write.
    """
    h = hashlib.sha256()
    for r in rows:
        line = "|".join(str(r.get(c, "")) for c in LEDGER_COLUMNS)
        h.update(line.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


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


def append_ledger_row(row: dict, dry_run: bool = False) -> tuple[float, float]:
    """Append a row to the ledger atomically. Refuses duplicate dates.

    Returns (running_total, running_winrate) *including* this new row.
    """
    rows = _read_ledger_rows()
    for r in rows:
        if r["date"] == row["date"]:
            raise RuntimeError(
                f"Ledger already has a row for {row['date']} — refusing duplicate append. "
                f"Delete or amend the existing row manually."
            )

    # Compute running stats including this row
    all_rows = rows + [row]
    pnls = [float(r["trusted_bot_pnl"]) for r in all_rows]
    running_total = round(sum(pnls), 2)

    # Win-rate excludes stand-downs
    traded = [r for r in all_rows if str(r.get("stand_down", "")).lower() != "true"]
    wins = [r for r in traded if float(r["trusted_bot_pnl"]) > 0]
    running_winrate = round(len(wins) / len(traded), 3) if traded else 0.0

    row["running_total"] = f"{running_total:.2f}"
    row["running_winrate"] = f"{running_winrate:.3f}"

    if dry_run:
        print(f"[dry-run] would append: {row}")
        return running_total, running_winrate

    # Snapshot prior rows for invariant check
    prior_hash = _ledger_snapshot_hash(rows)

    # Write the full file atomically (CSV doesn't safely allow O_APPEND with
    # quoted fields, so we rewrite + os.replace).
    buf = []
    buf.append(",".join(LEDGER_COLUMNS))
    for r in all_rows:
        buf.append(",".join(_csv_escape(str(r.get(c, ""))) for c in LEDGER_COLUMNS))
    _atomic_write(LEDGER_PATH, "\n".join(buf) + "\n")

    # INVARIANT: prior rows must be byte-identical after write
    rows_after = _read_ledger_rows()
    post_prior = rows_after[: len(rows)]
    if _ledger_snapshot_hash(post_prior) != prior_hash:
        raise RuntimeError(
            "APPEND-ONLY INVARIANT VIOLATED: prior ledger rows changed during write. "
            "Aborting; restore from git."
        )
    if len(rows_after) != len(rows) + 1:
        raise RuntimeError(
            f"APPEND-ONLY INVARIANT VIOLATED: expected {len(rows) + 1} rows, "
            f"got {len(rows_after)}."
        )
    if rows_after[-1]["date"] != row["date"]:
        raise RuntimeError("APPEND-ONLY INVARIANT VIOLATED: new row not last.")

    return running_total, running_winrate


def _csv_escape(v: str) -> str:
    if any(ch in v for ch in [",", '"', "\n", "\r"]):
        return '"' + v.replace('"', '""') + '"'
    return v


# ---------------------------------------------------------------------------
# Close report
# ---------------------------------------------------------------------------

def write_close_report(
    m: MorningSnapshot,
    c: CloseResult,
    running_total: float,
    running_winrate: float,
    dry_run: bool = False,
) -> Path:
    """Write the human-readable close report to SPX-Reports/close/{date}.md."""
    spx_move = c.spx_close - c.spx_open_945
    direction = "up" if spx_move > 0 else ("down" if spx_move < 0 else "flat")
    pred_dir = "up" if m.bias_score > 0 else ("down" if m.bias_score < 0 else "flat")
    predicted_correctly = pred_dir == direction or pred_dir == "flat"

    # Bucket attribution: largest absolute contribution
    if m.bucket_contributions:
        ranked = sorted(
            m.bucket_contributions.items(), key=lambda kv: abs(kv[1]), reverse=True
        )
        top_bucket, top_val = ranked[0]
        # Did the top bucket "drive the day"? Heuristic: its sign matches
        # actual SPX direction.
        top_sign = 1 if top_val > 0 else (-1 if top_val < 0 else 0)
        spx_sign = 1 if spx_move > 0 else (-1 if spx_move < 0 else 0)
        top_drove = (top_sign == spx_sign) and top_sign != 0
        bucket_lines = "\n".join(
            f"  - {name}: {val:+.2f}" for name, val in ranked
        )
    else:
        top_bucket, top_val, top_drove = "n/a", 0.0, False
        bucket_lines = "  (no bucket data)"

    # Lessons-learned candidates
    lessons = []
    if m.stand_down:
        if abs(spx_move) < 5:
            lessons.append(
                "Stand-down was correct: low-conviction call, SPX moved <5 pts."
            )
        else:
            lessons.append(
                f"Stand-down on day SPX moved {spx_move:+.2f} pts — was caution warranted "
                f"or did we leave money on the table?"
            )
    else:
        if c.trusted_bot_pnl > 0 and predicted_correctly:
            lessons.append(
                f"Clean win: bias_label='{m.bias_label}' aligned with SPX {direction} move."
            )
        elif c.trusted_bot_pnl < 0:
            lessons.append(
                f"Loss: predicted {pred_dir}, SPX went {direction}. "
                f"Review which bucket misled us."
            )
        if not top_drove and m.bucket_contributions:
            lessons.append(
                f"Top bucket '{top_bucket}' ({top_val:+.2f}) did NOT drive the day "
                f"(SPX moved {spx_move:+.2f}). Calibration candidate."
            )

    lines = [
        f"# SPX 0DTE Close Report — {m.date} ({m.day_of_week})",
        "",
        "**SYNTHETIC PAPER-TRADE LEDGER. Real money never moved. Educational only.**",
        "",
        "## Predicted vs actual",
        f"- Morning bias score: **{m.bias_score:+.2f}** ({m.bias_label}, conf={m.confidence})",
        f"- Predicted direction: **{pred_dir}**",
        f"- SPX 9:45 ET open: **{c.spx_open_945:.2f}**",
        f"- SPX 4:00 ET close: **{c.spx_close:.2f}**",
        f"- Actual move: **{spx_move:+.2f} pts** ({direction})",
        f"- Predicted correctly: **{predicted_correctly}**",
        "",
        "## Trade & P&L",
        f"- Structure: `{m.structure}`",
        f"- Strikes: short={m.strike_short}, long={m.strike_long}",
        f"- Credit/debit at open: {m.credit_or_debit}",
        f"- Max risk: ${m.max_risk:.2f} / Max reward: ${m.max_reward:.2f}",
        f"- Exit price (intrinsic at 4:00): {c.exit_price:.2f}",
        f"- **Trusted-bot P&L: ${c.trusted_bot_pnl:+.2f} "
        f"({c.trusted_bot_pnl_pct_of_max_risk:+.2f}% of max risk)**",
        f"- Stand-down: {m.stand_down}",
        "",
        "## P&L attribution by bucket",
        bucket_lines,
        "",
        f"- Largest-contribution bucket: **{top_bucket}** ({top_val:+.2f})",
        f"- Did it drive the day? **{top_drove}**",
        "",
        "## Running stats",
        f"- Cumulative trusted-bot P&L: **${running_total:+.2f}**",
        f"- Rolling win-rate (excludes stand-downs): **{running_winrate * 100:.1f}%**",
        "",
        "## Lessons-learned candidates",
    ]
    if lessons:
        lines.extend(f"- {x}" for x in lessons)
    else:
        lines.append("- (none flagged today)")
    lines.append("")
    lines.append("---")
    lines.append("Generated by `scripts/close_track.py`. Not investment advice.")

    out = CLOSE_REPORTS_DIR / f"{m.date}.md"
    content = "\n".join(lines)
    if dry_run:
        print(f"[dry-run] would write {out}")
        print(content)
    else:
        _atomic_write(out, content)
    return out


# ---------------------------------------------------------------------------
# Dashboard JSON update
# ---------------------------------------------------------------------------

def update_dashboard_json(
    m: MorningSnapshot,
    c: CloseResult,
    running_total: float,
    running_winrate: float,
    dry_run: bool = False,
) -> Path:
    path = DASHBOARD_DATA_DIR / f"{m.date}.json"
    existing = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    existing.setdefault("date", m.date)
    existing["close"] = {
        "spx_open_945": c.spx_open_945,
        "spx_close": c.spx_close,
        "exit_price": c.exit_price,
        "trusted_bot_pnl": c.trusted_bot_pnl,
        "trusted_bot_pnl_pct_of_max_risk": c.trusted_bot_pnl_pct_of_max_risk,
        "stand_down": m.stand_down,
        "structure": m.structure,
        "running_total": running_total,
        "running_winrate": running_winrate,
    }
    content = json.dumps(existing, indent=2, sort_keys=True) + "\n"
    if dry_run:
        print(f"[dry-run] would write {path}")
    else:
        _atomic_write(path, content)
    return path


# ---------------------------------------------------------------------------
# Git
# ---------------------------------------------------------------------------

def git_commit(date: str, dry_run: bool = False, no_commit: bool = False) -> str:
    """Commit ledger + report + dashboard JSON. Returns short commit hash."""
    if dry_run or no_commit:
        return "0000000"
    paths = [
        str(LEDGER_PATH.relative_to(REPO_ROOT)),
        str((CLOSE_REPORTS_DIR / f"{date}.md").relative_to(REPO_ROOT)),
        str((DASHBOARD_DATA_DIR / f"{date}.json").relative_to(REPO_ROOT)),
    ]
    try:
        subprocess.run(
            ["git", "add", "--", *paths], cwd=REPO_ROOT, check=True,
            capture_output=True,
        )
        msg = f"close({date}): trusted-bot P&L ledger update"
        subprocess.run(
            ["git", "commit", "-m", msg], cwd=REPO_ROOT, check=True,
            capture_output=True,
        )
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, check=True,
            capture_output=True, text=True,
        )
        return out.stdout.strip()
    except subprocess.CalledProcessError as e:
        sys.stderr.write(
            f"[warn] git commit failed (continuing): "
            f"{e.stderr.decode() if e.stderr else e}\n"
        )
        return "uncommitted"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", default=None, help="YYYY-MM-DD (default: today, ET)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-commit", action="store_true")
    args = p.parse_args(argv)

    if args.date:
        date = args.date
    else:
        # America/New_York "today"
        try:
            from zoneinfo import ZoneInfo
            date = dt.datetime.now(ZoneInfo("America/New_York")).date().isoformat()
        except Exception:
            date = dt.date.today().isoformat()

    print(f"[close_track] processing {date}")
    m = read_morning_report(date)

    _open, spx_close = get_spx_intraday(date)
    c = compute_trusted_bot_pnl(m, spx_close)

    row = {
        "date": m.date,
        "day_of_week": m.day_of_week,
        "bias_score": f"{m.bias_score:.2f}",
        "bias_label": m.bias_label,
        "confidence": m.confidence,
        "stand_down": "true" if m.stand_down else "false",
        "structure": m.structure,
        "strike_short": "" if m.strike_short is None else f"{m.strike_short:g}",
        "strike_long": "" if m.strike_long is None else f"{m.strike_long:g}",
        "credit_or_debit": "" if m.credit_or_debit is None else f"{m.credit_or_debit:g}",
        "max_risk": f"{m.max_risk:.2f}",
        "max_reward": f"{m.max_reward:.2f}",
        "spx_open_945": f"{c.spx_open_945:.2f}",
        "spx_close": f"{c.spx_close:.2f}",
        "exit_price": "" if m.stand_down else f"{c.exit_price:.2f}",
        "trusted_bot_pnl": f"{c.trusted_bot_pnl:.2f}",
        "trusted_bot_pnl_pct_of_max_risk": f"{c.trusted_bot_pnl_pct_of_max_risk:.2f}",
        "running_total": "",      # filled by append_ledger_row
        "running_winrate": "",    # filled by append_ledger_row
        "morning_commit_hash": m.morning_commit_hash,
        "close_commit_hash": "",  # filled after git commit
        "notes": "",
    }
    running_total, running_winrate = append_ledger_row(row, dry_run=args.dry_run)

    write_close_report(m, c, running_total, running_winrate, dry_run=args.dry_run)
    update_dashboard_json(m, c, running_total, running_winrate, dry_run=args.dry_run)

    close_hash = git_commit(date, dry_run=args.dry_run, no_commit=args.no_commit)
    # Post-commit, patch the close_commit_hash field in the just-written row.
    if not args.dry_run and close_hash not in ("0000000", "uncommitted"):
        _patch_close_hash(date, close_hash)

    print(
        f"[close_track] done: pnl=${c.trusted_bot_pnl:+.2f} "
        f"running=${running_total:+.2f} winrate={running_winrate * 100:.1f}% "
        f"commit={close_hash}"
    )
    return 0


def _patch_close_hash(date: str, close_hash: str) -> None:
    rows = _read_ledger_rows()
    for r in rows:
        if r["date"] == date:
            r["close_commit_hash"] = close_hash
    buf = [",".join(LEDGER_COLUMNS)]
    for r in rows:
        buf.append(",".join(_csv_escape(str(r.get(c, ""))) for c in LEDGER_COLUMNS))
    _atomic_write(LEDGER_PATH, "\n".join(buf) + "\n")


if __name__ == "__main__":
    sys.exit(main())
