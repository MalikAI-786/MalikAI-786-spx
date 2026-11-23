#!/usr/bin/env python3
"""Render the SPX morning email as a newspaper-style HTML page.

Usage:
  python3 scripts/render_paper.py CONTENT.json OUT_DIR

CONTENT.json holds the day's editorial content (see the example in the
`__main__` docstring below). Every money-to-date and scorecard number is
read from dashboard/data/performance.json; it is never typed into the
content file, so the email cannot drift from the ledger.

Writes OUT_DIR/email.html (inline-CSS, table layout, safe for Gmail/Outlook)
and OUT_DIR/email.txt (the plain-text alternative). The logo is referenced
as cid:att0, so send the logo as the first inline attachment.
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PERF = ROOT / "dashboard" / "data" / "performance.json"

INK = "#1b1b1b"
PAPER = "#f7f3ea"
RULE = "#2b2b2b"
MUTED = "#5c5a55"
NAVY = "#0f1b2d"
GOLD = "#E0662E"  # Malik brand orange
RED = "#9b2c2c"
GREEN = "#2f6b3a"
SERIF = "Georgia, Times, serif"
SANS = "Arial, Helvetica, sans-serif"

OWNER = "yasiramalik@gmail.com"
UNSUB = f"mailto:{OWNER}?subject=UNSUBSCRIBE%20SPX%20Morning%20Paper&body=Please%20remove%20me%20from%20the%20SPX%20Morning%20Paper."

PAPER_TRADING_STEPS = [
    ("Pick a practice platform.",
     "Most large US brokers and many charting sites offer a free <b>paper trading</b> "
     "(simulated trading) mode. Search the provider's help center for \"paper trading\"."),
    ("Open the practice account.",
     "It usually takes only an email address. Some providers ask you to open a regular "
     "account first. <b>You never need to deposit money to practice.</b>"),
    ("Confirm you are in paper mode.",
     "Practice accounts show a \"Paper\" or \"Simulated\" label and a pretend balance. "
     "Check for it every time you log in."),
    ("Turn on options in the simulator.",
     "Some simulators need options or spread trading switched on in their settings before "
     "you can practice a defined-risk spread."),
    ("Practice one contract and keep a journal.",
     "Copy the morning example, if there is one, at a single contract. Write down the credit, "
     "the max loss, the exit and the result, then compare it with the next morning's scorecard."),
    ("Practice long before risking anything real.",
     "Aim for 30 or more practice trades, losses included. Then talk to a licensed "
     "professional before considering real money."),
]


def money(v: float | None) -> str:
    if v is None:
        return "N/A"
    sign = "-" if v < 0 else "+"
    return f"{sign}${abs(v):,.0f}"


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def load_perf() -> dict:
    try:
        return json.loads(PERF.read_text(encoding="utf-8"))
    except Exception:
        return {}


def money_block(perf: dict) -> tuple[str, str, str]:
    """Return (headline, html_body, text_body) for the MONEY TO DATE lead."""
    pr = perf.get("published_record") or {}
    s = perf.get("summary") or {}
    if not pr:
        na = "N/A — ledger unavailable this run"
        return "Money to date: N/A", f"<p>{na}</p>", na
    scratches = pr["setups"] - pr["wins"] - pr["losses"]
    head = (f"{money(pr['net_synthetic_pnl_1lot'])} to date: {pr['wins']} wins, "
            f"{pr['losses']} loss{'es' if pr['losses'] != 1 else ''}"
            + (f", {scratches} scratch" if scratches else ""))
    losses = pr.get("loss_days") or []
    loss_html = "".join(
        f"<li><b style='color:{RED}'>{esc(l['date'])}: {money(l['synthetic_pnl_1lot'])}</b></li>" for l in losses
    ) or "<li>No losing setups on record.</li>"
    loss_txt = "; ".join(f"{l['date']} {money(l['synthetic_pnl_1lot'])}" for l in losses) or "none"
    body = (
        f"<p style='margin:0 0 8px'>Following <b>every published setup</b> since {esc(pr['first_date'])} "
        f"(1 lot each, held to the close, credit = published target; <i>synthetic, not real fills</i>): "
        f"<b>{pr['setups']} setups, {pr['wins']} wins, {pr['losses']} loss{'es' if pr['losses'] != 1 else ''}"
        + (f", {scratches} scratch" if scratches else "")
        + f"</b>. Net <b>{money(pr['net_synthetic_pnl_1lot'])}</b>. "
        f"Max drawdown <b>{money(-pr['max_drawdown'])}</b>.</p>"
        f"<p style='margin:0 0 4px'><b>Every loss, listed:</b></p><ul style='margin:0 0 8px 18px;padding:0'>{loss_html}</ul>"
        f"<p style='margin:0;color:{MUTED};font-size:13px'>Verified with real evidence: "
        f"<b>{money(s.get('verified_cumulative_pnl'))}</b> over {s.get('wins', 0) + s.get('losses', 0)} scored trades "
        f"({s.get('wins', 0)} W / {s.get('losses', 0)} L), {s.get('stand_downs', 0)} stand-down days. "
        f"\"Verified\" needs a real fill or close report, which is why it is much smaller than the synthetic record.</p>"
    )
    text = (
        f"MONEY TO DATE\nFollowing every published setup since {pr['first_date']} (1 lot each, held to the close, "
        f"credit = published target; synthetic, not real fills): {pr['setups']} setups, {pr['wins']} wins, "
        f"{pr['losses']} losses" + (f", {scratches} scratch" if scratches else "")
        + f". Net {money(pr['net_synthetic_pnl_1lot'])}. Max drawdown {money(-pr['max_drawdown'])}.\n"
        f"Every loss: {loss_txt}.\n"
        f"Verified with real evidence: {money(s.get('verified_cumulative_pnl'))} over "
        f"{s.get('wins', 0) + s.get('losses', 0)} scored trades ({s.get('wins', 0)} W / {s.get('losses', 0)} L), "
        f"{s.get('stand_downs', 0)} stand-downs. Verified needs a real fill or close report."
    )
    return head, body, text


def section(title: str, inner: str, kicker: str = "") -> str:
    k = (f"<div style='font:bold 11px {SANS};letter-spacing:2px;color:{GOLD};text-transform:uppercase;"
         f"margin:0 0 4px'>{esc(kicker)}</div>") if kicker else ""
    return (
        f"<tr><td style='padding:18px 28px 6px'>{k}"
        f"<h2 style='font:bold 22px/1.2 {SERIF};color:{INK};margin:0 0 8px'>{esc(title)}</h2>"
        f"<div style='font:15px/1.55 {SERIF};color:{INK}'>{inner}</div></td></tr>"
        f"<tr><td style='padding:0 28px'><div style='border-top:1px solid #cfc8b8'></div></td></tr>"
    )


def render(c: dict, out: Path) -> None:
    perf = load_perf()
    head, money_html, money_txt = money_block(perf)
    s = perf.get("summary") or {}

    # Yesterday
    y = c.get("yesterday") or {}
    y_html = (
        f"<p style='margin:0 0 6px'><b>Published:</b> {esc(y.get('setup', 'N/A'))}</p>"
        f"<p style='margin:0 0 6px'><b>What happened:</b> {esc(y.get('close_line', 'N/A'))}</p>"
        "<table role='presentation' cellpadding='0' cellspacing='0' style='margin:4px 0 6px'><tr>"
        f"<td style='padding:4px 10px;border:1px solid {RULE};font:bold 13px {SANS}'>Direction: {esc(y.get('direction', 'N/A'))}</td>"
        f"<td style='width:8px'></td>"
        f"<td style='padding:4px 10px;border:1px solid {RULE};font:bold 13px {SANS}'>Structure: {esc(y.get('structure', 'N/A'))}</td>"
        "</tr></table>"
        f"<p style='margin:0'>{esc(y.get('result_line', ''))}</p>"
    )

    # Buckets
    rows = "".join(
        f"<tr><td style='padding:6px 8px;border-bottom:1px solid #ddd6c6;font:bold 14px {SERIF}'>{esc(b['name'])}"
        f"<div style='font:12px {SANS};color:{MUTED}'>weight {b['weight']}</div></td>"
        f"<td style='padding:6px 8px;border-bottom:1px solid #ddd6c6;font:bold 15px {SANS};"
        f"color:{GREEN if b['score'] > 0 else RED if b['score'] < 0 else MUTED};text-align:right;white-space:nowrap'>{b['score']:+.2f}</td>"
        f"<td style='padding:6px 8px;border-bottom:1px solid #ddd6c6;font:14px/1.45 {SERIF}'>{esc(b['evidence'])}</td></tr>"
        for b in c["buckets"]
    )
    buckets_html = (
        f"<p style='margin:0 0 8px;color:{MUTED};font-size:13px'>{esc(c.get('gates', ''))}</p>"
        f"<table role='presentation' width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse'>{rows}</table>"
        f"<p style='margin:10px 0 0'><b>Composite {c['composite']:+.2f} &rarr; {esc(c['label'])}</b>"
        f" ({esc(c.get('conviction', ''))}).</p>"
        + (f"<p style='margin:8px 0 0;padding:8px 10px;background:#efe7d6;border-left:3px solid {GOLD}'>"
           f"<b>Honest caution:</b> {esc(c['caution'])}</p>" if c.get("caution") else "")
    )

    st = c.get("structure")
    if st:
        st_html = "<ul style='margin:0 0 0 18px;padding:0'>" + "".join(f"<li style='margin:0 0 4px'>{esc(x)}</li>" for x in st) + "</ul>"
        st_title = "The Example Setup (educational)"
    else:
        st_html = f"<p style='margin:0'><b>No trade today.</b> {esc(c.get('standdown_reason', ''))}</p>"
        st_title = "Today: Stand Down"

    levels_html = "<ul style='margin:0 0 0 18px;padding:0'>" + "".join(f"<li>{esc(x)}</li>" for x in c.get("levels", [])) + "</ul>"
    if c.get("catalysts"):
        levels_html += f"<p style='margin:8px 0 0'><b>Calendar:</b> {esc(c['catalysts'])}</p>"

    steps_html = "<ol style='margin:0 0 0 20px;padding:0'>" + "".join(
        f"<li style='margin:0 0 6px'><b>{esc(t)}</b> {d}</li>" for t, d in PAPER_TRADING_STEPS) + "</ol>"
    steps_html += (f"<p style='margin:8px 0 0;color:{MUTED};font-size:13px'>No provider is recommended or endorsed "
                   f"here. This newsletter never tells anyone how to place a real order.</p>")

    html_doc = f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(c['subject'])}</title></head>
<body style="margin:0;padding:0;background:#e9e4d8">
<div style="display:none;max-height:0;overflow:hidden">{esc(head)} · {esc(c['label'])} ({c['composite']:+.2f})</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#e9e4d8"><tr><td align="center" style="padding:16px 8px">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="width:100%;max-width:640px;background:{PAPER};border:1px solid #cfc8b8">
<tr><td style="background:{NAVY};padding:16px 28px" align="center">
  <img src="cid:att0" width="72" height="77" alt="Malik Marketplace" style="display:block;border:0;margin:0 auto 6px">
  <div style="font:bold 12px {SANS};letter-spacing:4px;color:{GOLD}">MALIK MARKETPLACE</div>
</td></tr>
<tr><td style="padding:14px 28px 0" align="center">
  <div style="font:bold 40px/1.05 {SERIF};color:{INK};letter-spacing:1px">The SPX Morning Paper</div>
  <div style="border-top:3px double {RULE};border-bottom:1px solid {RULE};margin:10px 0 0;padding:5px 0;font:12px {SANS};color:{MUTED};letter-spacing:1px">
    {esc(c['date_long'])} &nbsp;·&nbsp; {esc(c.get('run_time', ''))} &nbsp;·&nbsp; EDUCATIONAL EDITION &nbsp;·&nbsp; FREE
  </div>
</td></tr>
<tr><td style="padding:18px 28px 6px">
  <div style="font:bold 11px {SANS};letter-spacing:2px;color:{GOLD};text-transform:uppercase;margin:0 0 4px">Money to date</div>
  <h1 style="font:bold 28px/1.15 {SERIF};color:{INK};margin:0 0 10px">{esc(head)}</h1>
  <div style="font:15px/1.55 {SERIF};color:{INK}">{money_html}</div>
</td></tr>
<tr><td style="padding:8px 28px">
  <div style="border:2px solid {RULE};padding:10px 12px;font:13px/1.5 {SANS};color:{INK}">
    <b>NOT INVESTMENT ADVICE — EDUCATIONAL CONTENT ONLY.</b> The author is not a registered investment adviser.
    This is a personal paper-trading journal shared with family and friends for learning. Nothing here is a
    recommendation to buy or sell any security. All results are simulated unless marked verified.
  </div>
</td></tr>
{section("If We Had Followed Yesterday's Setup", y_html, "Scorecard · " + y.get('date', ''))}
{section(f"Today's Read: {c['label']} ({c['composite']:+.2f})", buckets_html, "Five-bucket model")}
{section(st_title, st_html, "Defined risk only")}
{section("Levels & Calendar", levels_html, "Reference")}
{section("Learn It Safely: Open a Free Paper-Trading Account", steps_html, "Classroom")}
<tr><td style="padding:16px 28px 4px;font:italic 16px/1.5 {SERIF};color:{INK}" align="center">&ldquo;{esc(c['quote'])}&rdquo;<br><span style="font:12px {SANS};color:{MUTED};font-style:normal">— Hazrat Ali (RA)</span></td></tr>
<tr><td style="padding:14px 28px 22px;font:12px/1.6 {SANS};color:{MUTED}">
  <div style="border-top:3px double {RULE};padding-top:10px">
  Educational paper-trading journal. Not investment advice. Defined-risk only; you are responsible for your own decisions.
  0DTE options are high-risk and can lose their full defined risk in minutes. Past simulated results do not predict future results.<br>
  Questions or something look off? Reply to this email.<br>
  You receive this because Yasir A. Malik added you to the list.
  <a href="{UNSUB}" style="color:{NAVY};font-weight:bold">Unsubscribe with one click</a>
  (or reply with the word UNSUBSCRIBE) and you will be removed before the next edition.
  </div>
</td></tr>
</table></td></tr></table></body></html>"""

    text = "\n".join([
        f"THE SPX MORNING PAPER — MALIK MARKETPLACE — {c['date_long']} — EDUCATIONAL EDITION",
        "",
        money_txt,
        "",
        "NOT INVESTMENT ADVICE — EDUCATIONAL CONTENT ONLY. The author is not a registered investment adviser.",
        "",
        f"IF WE HAD FOLLOWED YESTERDAY'S PUBLISHED MODEL SETUP ({y.get('date', '')})",
        f"Published: {y.get('setup', 'N/A')}",
        f"What happened: {y.get('close_line', 'N/A')}",
        f"Direction: {y.get('direction', 'N/A')} | Structure: {y.get('structure', 'N/A')}",
        y.get("result_line", ""),
        "",
        f"TODAY'S READ: {c['label']} ({c['composite']:+.2f}) — {c.get('conviction', '')}",
        c.get("gates", ""),
        *[f"- {b['name']} ({b['weight']}): {b['score']:+.2f}. {b['evidence']}" for b in c["buckets"]],
        (f"Honest caution: {c['caution']}" if c.get("caution") else ""),
        "",
        ("THE EXAMPLE SETUP (educational)" if st else "TODAY: STAND DOWN"),
        *([f"- {x}" for x in st] if st else [c.get("standdown_reason", "")]),
        "",
        "LEVELS & CALENDAR",
        *[f"- {x}" for x in c.get("levels", [])],
        (f"Calendar: {c['catalysts']}" if c.get("catalysts") else ""),
        "",
        "LEARN IT SAFELY: OPEN A FREE PAPER-TRADING ACCOUNT",
        *[f"{i}. {t} {html.unescape(d).replace('<b>', '').replace('</b>', '')}" for i, (t, d) in enumerate(PAPER_TRADING_STEPS, 1)],
        "No provider is recommended or endorsed here.",
        "",
        f"\"{c['quote']}\" — Hazrat Ali (RA)",
        "",
        "Educational paper-trading journal. Not investment advice. Defined-risk only. 0DTE options are high-risk.",
        "Questions or something look off? Reply to this email.",
        f"Unsubscribe: reply with the word UNSUBSCRIBE, or email {OWNER} with the subject UNSUBSCRIBE SPX Morning Paper.",
    ])

    out.mkdir(parents=True, exist_ok=True)
    (out / "email.html").write_text(html_doc, encoding="utf-8")
    (out / "email.txt").write_text(text, encoding="utf-8")
    print(f"wrote {out / 'email.html'} and {out / 'email.txt'}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    render(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")), Path(sys.argv[2]))
