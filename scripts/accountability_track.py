#!/usr/bin/env python3
"""SPX accountability ledger utilities.

Public-safe only. Real brokerage positions belong in the private Notion tracker,
not this repository.

Commands:
  python scripts/accountability_track.py build
  python scripts/accountability_track.py append --date ...

The ledger is append-only. Corrections append a new record with correction_of;
no historical row is edited by this script.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "ledger" / "accountability-v2.csv"
PERF_JSON = ROOT / "dashboard" / "data" / "performance.json"
EMAIL_HTML = ROOT / "dashboard" / "data" / "accountability-email.html"
SETUPS = ROOT / "ledger" / "published-setups.csv"
SETUP_FIELDS = [
    "date", "structure", "short_strike", "long_strike", "credit_target",
    "spx_close", "evidence_ref", "notes",
]

FIELDS = [
    "record_id", "date", "bias_score", "bias_label", "stand_down", "structure",
    "disciplined_pnl", "counterfactual_pnl", "model_verdict", "direction_verdict",
    "structure_verdict", "evidence_status", "evidence_ref", "correction_of", "notes",
]


def _money(value: float) -> str:
    sign = "+" if value > 0 else "−" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def _num(text: str | None) -> float | None:
    if text is None or str(text).strip() == "":
        return None
    return float(text)


def _bool(text: str | bool) -> bool:
    if isinstance(text, bool):
        return text
    return str(text).strip().lower() in {"1", "true", "yes", "y"}


def load_rows() -> list[dict[str, str]]:
    if not LEDGER.exists():
        return []
    with LEDGER.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    missing = set(FIELDS) - set(rows[0].keys() if rows else FIELDS)
    if missing:
        raise SystemExit(f"Ledger schema missing columns: {sorted(missing)}")
    return rows


def effective_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Return rows after append-only corrections are applied logically.

    A row is superseded when a later row's correction_of points at its record_id.
    The bytes remain in the ledger; only reporting selects the latest effective row.
    """
    superseded = {r.get("correction_of", "").strip() for r in rows if r.get("correction_of", "").strip()}
    eff = [r for r in rows if r.get("record_id", "").strip() not in superseded]
    return sorted(eff, key=lambda r: (r["date"], r["record_id"]))


def verified_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [r for r in effective_rows(rows) if r.get("evidence_status", "").upper() == "VERIFIED"]


def stats(rows: list[dict[str, str]]) -> dict:
    vr = verified_rows(rows)
    pnls = [_num(r.get("disciplined_pnl")) for r in vr]
    pnls = [p for p in pnls if p is not None]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    stand_downs = sum(_bool(r.get("stand_down", "false")) for r in vr)
    flats = sum((not _bool(r.get("stand_down", "false"))) and (_num(r.get("disciplined_pnl")) == 0) for r in vr)

    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    curve = []
    for r in vr:
        p = _num(r.get("disciplined_pnl"))
        if p is None:
            continue
        cumulative += p
        peak = max(peak, cumulative)
        max_drawdown = max(max_drawdown, peak - cumulative)
        curve.append({"date": r["date"], "pnl": p, "cumulative": cumulative, "record_id": r["record_id"]})

    directional = [r for r in vr if r.get("direction_verdict", "").upper() in {"HIT", "MISS"}]
    structure = [r for r in vr if r.get("structure_verdict", "").upper() in {"HIT", "MISS"}]
    direction_hits = sum(r["direction_verdict"].upper() == "HIT" for r in directional)
    structure_hits = sum(r["structure_verdict"].upper() == "HIT" for r in structure)

    # Per-day history for the calibration/deviation chart: every verified row's
    # published composite score against whether direction turned out to be
    # right. A stand-down carries no directional call (N/A), so it renders as
    # neutral rather than as a hit or a miss it never claimed to be.
    history = [
        {
            "date": r["date"],
            "bias_score": _num(r.get("bias_score")),
            "bias_label": r.get("bias_label", ""),
            "stand_down": _bool(r.get("stand_down", "false")),
            "direction_verdict": r.get("direction_verdict", "N/A").upper(),
            "structure_verdict": r.get("structure_verdict", "N/A").upper(),
            "disciplined_pnl": _num(r.get("disciplined_pnl")),
        }
        for r in vr
    ]

    non_stand_trade_pnls = [
        _num(r.get("disciplined_pnl")) for r in vr
        if not _bool(r.get("stand_down", "false")) and _num(r.get("disciplined_pnl")) is not None
    ]

    return {
        "verified_days": len(vr),
        "verified_cumulative_pnl": cumulative,
        "wins": len(wins),
        "losses": len(losses),
        "stand_downs": stand_downs,
        "flat_non_stand_downs": flats,
        "win_rate": (len(wins) / (len(wins) + len(losses))) if (wins or losses) else None,
        "avg_win": mean(wins) if wins else None,
        "avg_loss": mean(losses) if losses else None,
        "expectancy_per_non_stand_trade": mean(non_stand_trade_pnls) if non_stand_trade_pnls else None,
        "max_drawdown": max_drawdown,
        "direction_hit_rate": (direction_hits / len(directional)) if directional else None,
        "direction_scored_days": len(directional),
        "structure_hit_rate": (structure_hits / len(structure)) if structure else None,
        "structure_scored_days": len(structure),
        "curve": curve,
        "history": history,
        "coverage_note": "Historical backfill is incomplete; cumulative figures include VERIFIED evidence rows only and are not yet the full published-email history.",
    }


def latest_effective(rows: list[dict[str, str]]) -> dict[str, str] | None:
    eff = effective_rows(rows)
    return eff[-1] if eff else None


def diagnosis(row: dict[str, str] | None) -> str:
    if not row:
        return "No verified prior-day result is available yet."
    if row.get("evidence_status", "").upper() != "VERIFIED":
        return "Execution evidence is incomplete; the model result is not included in verified statistics."
    stand = _bool(row.get("stand_down", "false"))
    d = row.get("direction_verdict", "").upper()
    s = row.get("structure_verdict", "").upper()
    pnl_known = row.get("disciplined_pnl", "").strip() != ""
    pnl = _num(row.get("disciplined_pnl")) if pnl_known else None
    if stand:
        return "Stand-down preserved the model's no-exposure rule. The ledger correctly records $0 rather than retrofitting a trade after the fact."
    if d == "HIT" and s == "HIT" and pnl_known and pnl > 0:
        return "Directional edge and structure both worked: the bias matched the realized move and the published defined-risk structure was profitable."
    if d == "HIT" and s == "HIT" and not pnl_known:
        return "Direction and structure both confirmed correct from the sent email's own recap. The exact dollar fill was not stated, so disciplined_pnl is left blank rather than estimated -- this day is excluded from the P&L statistics but counted in the hit-rate ones."
    if d == "HIT" and s in {"MISS", "MIXED"}:
        return "Direction was useful, but structure/strike selection or execution diluted the edge. This is a construction problem, not the same as a bad directional call."
    if d == "MISS" and pnl_known and pnl >= 0:
        return "Direction was wrong, but the discipline layer limited or avoided the loss. Risk controls worked even though the forecast did not."
    if d == "MISS" and not pnl_known:
        return "Direction was wrong; the source email did not state whether the structure still avoided a loss, so no dollar claim is made."
    if d == "MISS":
        return "Directional inference failed and the synthetic setup lost money. The next calibration should focus first on the buckets that drove the wrong-way call."
    return "The result is recorded, but the available evidence is not sufficient to classify both direction and structure cleanly."


def load_setups() -> list[dict[str, str]]:
    if not SETUPS.exists():
        return []
    with SETUPS.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def setup_pnl(row: dict[str, str]) -> float | None:
    """Synthetic 1-lot P&L at expiry from the published strikes and the close.

    Rule (disclosed in every email): one lot of the published spread, credit =
    the published credit target (20 pct of width when none was stated), held to
    the 4:00 close, SPX multiplier 100. Not a real fill. Ignores intraday stops.
    """
    short, long_, close = _num(row.get("short_strike")), _num(row.get("long_strike")), _num(row.get("spx_close"))
    if short is None or long_ is None or close is None:
        return None
    width = abs(long_ - short)
    credit = _num(row.get("credit_target"))
    if credit is None:
        credit = round(0.2 * width, 2)
    if row.get("structure") == "bear_call_spread":
        intrinsic = min(max(close - short, 0.0), width)
    elif row.get("structure") == "bull_put_spread":
        intrinsic = min(max(short - close, 0.0), width)
    else:
        return None
    return round((credit - intrinsic) * 100, 2)


def published_record() -> dict:
    """Every published directional setup, wins AND losses, synthetic 1-lot."""
    items = []
    for r in load_setups():
        pnl = setup_pnl(r)
        if pnl is None:
            continue
        items.append({"date": r["date"], "structure": r["structure"],
                      "short_strike": _num(r["short_strike"]), "long_strike": _num(r["long_strike"]),
                      "spx_close": _num(r["spx_close"]), "synthetic_pnl_1lot": pnl,
                      "evidence_ref": r.get("evidence_ref", "")})
    items.sort(key=lambda x: x["date"])
    pnls = [i["synthetic_pnl_1lot"] for i in items]
    losses = [i for i in items if i["synthetic_pnl_1lot"] < 0]
    running, peak, mdd = 0.0, 0.0, 0.0
    for v in pnls:
        running += v
        peak = max(peak, running)
        mdd = max(mdd, peak - running)
    return {
        "basis": "SYNTHETIC — 1 lot of each published spread held to the close; credit = published target (20% of width if unstated); not real fills; intraday stops ignored",
        "first_date": items[0]["date"] if items else None,
        "last_date": items[-1]["date"] if items else None,
        "setups": len(items),
        "wins": sum(v > 0 for v in pnls),
        "losses": len(losses),
        "net_synthetic_pnl_1lot": round(sum(pnls), 2),
        "gross_wins": round(sum(v for v in pnls if v > 0), 2),
        "gross_losses": round(sum(v for v in pnls if v < 0), 2),
        "max_drawdown": round(mdd, 2),
        "loss_days": [{"date": i["date"], "synthetic_pnl_1lot": i["synthetic_pnl_1lot"]} for i in losses],
        "items": items,
    }


def build_outputs() -> dict:
    rows = load_rows()
    summary = stats(rows)
    last = latest_effective(rows)
    payload = {
        "schema_version": "2.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "public_safe": True,
        "actual_portfolio_disclosure": "PRIVATE_TRACKING_ACTIVE_NO_POSITION_LEVEL_PUBLICATION",
        "summary": summary,
        "published_record": published_record(),
        "latest_effective_result": last,
        "diagnosis": diagnosis(last),
    }
    PERF_JSON.parent.mkdir(parents=True, exist_ok=True)
    PERF_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    cumulative = summary["verified_cumulative_pnl"]
    if last:
        pnl_known = last.get("disciplined_pnl", "").strip() != ""
        last_pnl = _num(last.get("disciplined_pnl")) if pnl_known else None
        if _bool(last.get("stand_down", "false")):
            lead = (
                "IF WE HAD FOLLOWED YESTERDAY'S PUBLISHED MODEL SETUP: "
                "we would have stayed flat. Synthetic disciplined P&L: $0. "
                "The model took no exposure."
            )
        elif pnl_known:
            action = "made" if last_pnl > 0 else "lost" if last_pnl < 0 else "finished flat at"
            lead = (
                "IF WE HAD FOLLOWED YESTERDAY'S PUBLISHED MODEL SETUP: "
                f"the standardized synthetic 1-lot result would have {action} {_money(last_pnl)}."
            )
        else:
            # Direction/structure verdicts can be verified straight from the
            # sent email's own next-day recap even when the exact dollar fill
            # was never stated -- that is a confirmed result with an unknown
            # dollar amount, not an unverified one. Say which is true.
            d = last.get("direction_verdict", "N/A").upper()
            s = last.get("structure_verdict", "N/A").upper()
            if d in {"HIT", "MISS"}:
                lead = (
                    "IF WE HAD FOLLOWED YESTERDAY'S PUBLISHED MODEL SETUP: "
                    f"direction {d.lower()}, structure {s.lower() if s in {'HIT','MISS'} else 'unscored'} "
                    "-- the exact dollar P&L was not stated in the sent email, so no dollar figure is claimed."
                )
            else:
                lead = "IF WE HAD FOLLOWED YESTERDAY'S PUBLISHED MODEL SETUP: outcome not yet verified."
    else:
        lead = "IF WE HAD FOLLOWED YESTERDAY'S PUBLISHED MODEL SETUP: no verified prior-day row is available."

    def pct(v):
        return "N/A" if v is None else f"{100*v:.1f}%"

    html_out = f"""<section class=\"accountability-v2\">
  <h2>Yesterday first — model accountability</h2>
  <p><strong>{html.escape(lead)}</strong></p>
  <p>Verified cumulative synthetic P&amp;L: <strong>{html.escape(_money(cumulative))}</strong> across <strong>{summary['verified_days']}</strong> audited days.</p>
  <table>
    <tr><th>Wins</th><td>{summary['wins']}</td><th>Losses</th><td>{summary['losses']}</td><th>Stand-downs</th><td>{summary['stand_downs']}</td></tr>
    <tr><th>Win rate</th><td>{pct(summary['win_rate'])}</td><th>Max drawdown</th><td>{html.escape(_money(summary['max_drawdown']))}</td><th>Expectancy</th><td>{'N/A' if summary['expectancy_per_non_stand_trade'] is None else html.escape(_money(summary['expectancy_per_non_stand_trade']))}</td></tr>
    <tr><th>Direction hit rate</th><td>{pct(summary['direction_hit_rate'])}</td><th>Structure hit rate</th><td>{pct(summary['structure_hit_rate'])}</td><th>Evidence</th><td>VERIFIED rows only</td></tr>
  </table>
  <p><strong>Why it worked / failed:</strong> {html.escape(diagnosis(last))}</p>
  <p><em>{html.escape(summary['coverage_note'])}</em></p>
  <p><strong>Actual portfolio:</strong> private tracking active; no position-level figures published.</p>
  <p class=\"disclaimer\">Educational research only. Synthetic/paper results are not a real-account P&amp;L statement and are not investment advice.</p>
</section>\n"""
    EMAIL_HTML.write_text(html_out, encoding="utf-8")
    return payload


def append_row(args: argparse.Namespace) -> None:
    rows = load_rows()
    if not LEDGER.exists():
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()
        rows = []

    if args.correction_of:
        ids = {r["record_id"] for r in rows}
        if args.correction_of not in ids:
            raise SystemExit(f"correction_of not found: {args.correction_of}")
    else:
        effective_dates = {r["date"] for r in effective_rows(rows)}
        if args.date in effective_dates:
            raise SystemExit(f"Refusing duplicate effective date {args.date}; use --correction-of for an append-only correction.")

    rid = args.record_id or f"acct-{args.date.replace('-', '')}-{len(rows)+1:03d}"
    if any(r["record_id"] == rid for r in rows):
        raise SystemExit(f"Duplicate record_id: {rid}")

    row = {
        "record_id": rid,
        "date": args.date,
        "bias_score": args.bias_score if args.bias_score is not None else "",
        "bias_label": args.bias_label,
        "stand_down": str(args.stand_down).lower(),
        "structure": args.structure,
        "disciplined_pnl": args.disciplined_pnl if args.disciplined_pnl is not None else "",
        "counterfactual_pnl": args.counterfactual_pnl if args.counterfactual_pnl is not None else "",
        "model_verdict": args.model_verdict,
        "direction_verdict": args.direction_verdict,
        "structure_verdict": args.structure_verdict,
        "evidence_status": args.evidence_status,
        "evidence_ref": args.evidence_ref,
        "correction_of": args.correction_of or "",
        "notes": args.notes or "",
    }
    with LEDGER.open("a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=FIELDS).writerow(row)
    build_outputs()
    print(f"Appended {rid} and rebuilt public accountability outputs.")


def append_setup(args: argparse.Namespace) -> None:
    existing = load_setups()
    if any(r["date"] == args.date for r in existing):
        raise SystemExit(f"Refusing duplicate setup date {args.date}.")
    new = not SETUPS.exists()
    with SETUPS.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SETUP_FIELDS)
        if new:
            w.writeheader()
        w.writerow({"date": args.date, "structure": args.structure,
                    "short_strike": args.short, "long_strike": args.long,
                    "credit_target": "" if args.credit is None else args.credit,
                    "spx_close": args.close, "evidence_ref": args.evidence_ref,
                    "notes": args.notes or ""})
    build_outputs()
    print(f"Appended published setup {args.date} and rebuilt outputs.")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("build")
    a = sub.add_parser("append")
    a.add_argument("--record-id")
    a.add_argument("--date", required=True)
    a.add_argument("--bias-score", type=float)
    a.add_argument("--bias-label", required=True)
    a.add_argument("--stand-down", action="store_true")
    a.add_argument("--structure", required=True)
    a.add_argument("--disciplined-pnl", type=float)
    a.add_argument("--counterfactual-pnl", type=float)
    a.add_argument("--model-verdict", required=True)
    a.add_argument("--direction-verdict", default="N/A")
    a.add_argument("--structure-verdict", default="N/A")
    a.add_argument("--evidence-status", choices=["VERIFIED", "PARTIAL", "UNVERIFIED"], required=True)
    a.add_argument("--evidence-ref", required=True)
    a.add_argument("--correction-of")
    a.add_argument("--notes")
    s_ = sub.add_parser("append-setup", help="log a published directional setup for the money-to-date tally")
    s_.add_argument("--date", required=True)
    s_.add_argument("--structure", choices=["bear_call_spread", "bull_put_spread"], required=True)
    s_.add_argument("--short", type=float, required=True)
    s_.add_argument("--long", type=float, required=True)
    s_.add_argument("--credit", type=float, help="published credit target in points; omit to use 20%% of width")
    s_.add_argument("--close", type=float, required=True, help="SPX 4:00 close that day")
    s_.add_argument("--evidence-ref", required=True)
    s_.add_argument("--notes")
    return p


def main() -> None:
    args = parser().parse_args()
    if args.command == "build":
        payload = build_outputs()
        print(json.dumps(payload["summary"], indent=2))
    elif args.command == "append":
        append_row(args)
    elif args.command == "append-setup":
        append_setup(args)


if __name__ == "__main__":
    main()
