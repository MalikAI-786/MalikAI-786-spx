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
    pnl = _num(row.get("disciplined_pnl")) or 0.0
    if stand:
        return "Stand-down preserved the model's no-exposure rule. The ledger correctly records $0 rather than retrofitting a trade after the fact."
    if d == "HIT" and s == "HIT" and pnl > 0:
        return "Directional edge and structure both worked: the bias matched the realized move and the published defined-risk structure was profitable."
    if d == "HIT" and s in {"MISS", "MIXED"}:
        return "Direction was useful, but structure/strike selection or execution diluted the edge. This is a construction problem, not the same as a bad directional call."
    if d == "MISS" and pnl >= 0:
        return "Direction was wrong, but the discipline layer limited or avoided the loss. Risk controls worked even though the forecast did not."
    if d == "MISS":
        return "Directional inference failed and the synthetic setup lost money. The next calibration should focus first on the buckets that drove the wrong-way call."
    return "The result is recorded, but the available evidence is not sufficient to classify both direction and structure cleanly."


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
        "latest_effective_result": last,
        "diagnosis": diagnosis(last),
    }
    PERF_JSON.parent.mkdir(parents=True, exist_ok=True)
    PERF_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    cumulative = summary["verified_cumulative_pnl"]
    if last:
        last_pnl = _num(last.get("disciplined_pnl"))
        if _bool(last.get("stand_down", "false")):
            lead = (
                "IF WE HAD FOLLOWED YESTERDAY'S PUBLISHED MODEL SETUP: "
                "we would have stayed flat. Synthetic disciplined P&L: $0. "
                "The model took no exposure."
            )
        elif last_pnl is not None:
            action = "made" if last_pnl > 0 else "lost" if last_pnl < 0 else "finished flat at"
            lead = (
                "IF WE HAD FOLLOWED YESTERDAY'S PUBLISHED MODEL SETUP: "
                f"the standardized synthetic 1-lot result would have {action} {_money(last_pnl)}."
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
    return p


def main() -> None:
    args = parser().parse_args()
    if args.command == "build":
        payload = build_outputs()
        print(json.dumps(payload["summary"], indent=2))
    elif args.command == "append":
        append_row(args)


if __name__ == "__main__":
    main()
