#!/usr/bin/env python3
# EDUCATIONAL OUTLOOK MODEL. Real money never moved. Not investment advice.
"""
portfolio_track.py — Tech-sleeve weekly outlook, v1.0.

Runs Friday after the close on US trading weeks.

Pipeline:
  1. Load portfolio/basket.json (tickers + percentage weights ONLY)
  2. Fetch trailing daily closes for the constituents, benchmark, 10Y, VIX
  3. Score five buckets in [-2, +2]; a bucket with no data ABSTAINS (null)
  4. Renormalize weights over the scored buckets, compute composite + label
  5. Append one row to ledger/portfolio-signals.csv (append-only, idempotent)
  6. Write dashboard/data/portfolio.json for the Tech Outlook tab
  7. Write the email section fragment(s)

Usage:
  python scripts/portfolio_track.py                     # score this week
  python scripts/portfolio_track.py --score-prior       # fill last week's outcome
  python scripts/portfolio_track.py --dry-run
  python scripts/portfolio_track.py --fixture tests/fixtures/prices.json
  python scripts/portfolio_track.py --week-ending 2026-08-14

The privacy line (docs/PORTFOLIO-SCHEMA.md):
  Nothing read from private/holdings.json is ever written to dashboard/,
  ledger/, or portfolio/. Private figures reach exactly one destination --
  private/portfolio-email-private.html, which is gitignored. If you extend
  this file, preserve that property. It is the whole control.

Conventions:
  - Dates: America/New_York
  - Bucket scores: [-2.0, +2.0]; sign = direction, magnitude = conviction
  - Abstention is null, never 0.0
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analytics import montecarlo, risk  # noqa: E402

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
BASKET_PATH = REPO_ROOT / "portfolio" / "basket.json"
LEDGER_PATH = REPO_ROOT / "ledger" / "portfolio-signals.csv"
DASHBOARD_DATA_DIR = REPO_ROOT / "dashboard" / "data"
PRIVATE_DIR = REPO_ROOT / "private"

SCHEMA_VERSION = "1.0.0"

LEDGER_COLUMNS = [
    "week_ending", "basket_id", "owner_confirmed", "composite", "label",
    "confidence", "momentum", "breadth", "rates", "earnings", "volatility",
    "abstained", "bucket_span", "basket_index", "benchmark_index",
    "fwd_1w_basket_pct", "was_directionally_right", "commit_hash", "notes",
]

BASE_WEIGHTS = {
    "momentum": 0.30,
    "breadth": 0.20,
    "rates": 0.20,
    "earnings": 0.15,
    "volatility": 0.15,
}

# Auxiliary series the buckets need beyond the basket constituents.
BENCHMARK_DEFAULT = "XLK"
TNX_TICKER = "^TNX"   # CBOE 10-year Treasury yield index (yield x 10)
VIX_TICKER = "^VIX"

REFERENCE_BANNER = "REFERENCE BASKET — not the owner's holdings"

DISCLAIMER = (
    "Educational only. Not investment advice, not a recommendation, and not "
    "an instruction to buy, sell, hold, or reallocate. Past performance does "
    "not indicate future results."
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Bucket:
    name: str
    score: Optional[float]        # None == abstained. Never coerce to 0.0.
    rationale: str

    @property
    def abstained(self) -> bool:
        return self.score is None


@dataclass
class Call:
    composite: float
    label: str
    confidence: str
    bucket_span: float
    buckets: list[Bucket]
    weights: dict                 # renormalized, scored buckets only

    @property
    def abstained_names(self) -> list[str]:
        return [b.name for b in self.buckets if b.abstained]


@dataclass
class Basket:
    basket_id: str
    display_name: str
    owner_confirmed: bool
    source: str
    as_of: Optional[str]
    benchmark: str
    tickers: list[str]
    weights_pct: dict
    cadence: str
    assumed_continuing: bool
    raw: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Basket loading
# ---------------------------------------------------------------------------

def load_basket(path: Path = BASKET_PATH) -> Basket:
    if not path.exists():
        raise FileNotFoundError(
            f"Basket definition not found: {path}. See docs/PORTFOLIO-SCHEMA.md."
        )
    d = json.loads(path.read_text(encoding="utf-8"))

    constituents = d.get("constituents") or []
    if not constituents:
        raise ValueError(f"{path} has no constituents.")

    weights = {c["ticker"]: float(c["weight_pct"]) for c in constituents}
    total = sum(weights.values())
    if total <= 0:
        raise ValueError(f"{path}: constituent weights sum to {total}.")
    if abs(total - 100.0) > 1.0:
        sys.stderr.write(
            f"[warn] basket weights sum to {total:.2f}%, not ~100%. "
            f"Normalizing anyway.\n"
        )

    contribution = d.get("contribution") or {}
    return Basket(
        basket_id=d.get("basket_id", "basket"),
        display_name=d.get("display_name", d.get("basket_id", "Basket")),
        owner_confirmed=bool(d.get("owner_confirmed", False)),
        source=d.get("source", "unknown"),
        as_of=d.get("as_of"),
        benchmark=d.get("benchmark", BENCHMARK_DEFAULT),
        tickers=[c["ticker"] for c in constituents],
        weights_pct=weights,
        cadence=contribution.get("cadence", "none"),
        assumed_continuing=bool(contribution.get("assumed_continuing", False)),
        raw=d,
    )


# ---------------------------------------------------------------------------
# Market data
# ---------------------------------------------------------------------------
# Two keyless sources, tried in order, then give up and let buckets abstain.
# This environment's egress policy blocks both, which is exactly why every
# bucket must tolerate a missing series rather than assume zero.

def _http_get(url: str, timeout: int = 20) -> Optional[bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "malikai-786-spx/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError) as e:
        sys.stderr.write(f"[data] {url.split('?')[0]} unavailable: {e}\n")
        return None


def _fetch_stooq(ticker: str) -> Optional[list[float]]:
    """Stooq daily CSV. Keyless. US equities take a .us suffix; index symbols
    keep their ^ prefix and take none."""
    t = ticker.lower()
    sym = t if t.startswith("^") else f"{t}.us"
    raw = _http_get(f"https://stooq.com/q/d/l/?s={urllib.parse.quote(sym)}&i=d")
    if not raw:
        return None
    closes = []
    for line in raw.decode("utf-8", "replace").splitlines()[1:]:
        parts = line.split(",")
        if len(parts) >= 5:
            try:
                closes.append(float(parts[4]))
            except ValueError:
                continue
    return closes or None


def _fetch_yahoo(ticker: str) -> Optional[list[float]]:
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(ticker)}?range=1y&interval=1d"
    )
    raw = _http_get(url)
    if not raw:
        return None
    try:
        d = json.loads(raw)
        quotes = d["chart"]["result"][0]["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return None
    closes = [c for c in quotes if c is not None]
    return closes or None


def fetch_series(tickers: list[str], fixture: Optional[Path] = None) -> dict:
    """Return {ticker: [daily closes, oldest first]}. Missing tickers are absent.

    A fixture is a plain JSON object of the same shape, used for offline runs
    and tests. It is not a mock of a live source -- it IS the source when
    supplied, so a fixture-backed run is fully reproducible.
    """
    if fixture:
        d = json.loads(Path(fixture).read_text(encoding="utf-8"))
        # Scalar keys in a fixture are bucket inputs (e.g. earnings revision
        # breadth), not price series -- they are read separately.
        return {k: [float(x) for x in v]
                for k, v in d.items() if isinstance(v, list) and v}

    out: dict = {}
    for t in tickers:
        series = _fetch_stooq(t) or _fetch_yahoo(t)
        if series and len(series) >= 60:
            out[t] = series
        else:
            sys.stderr.write(f"[data] no usable series for {t}\n")
    return out


# ---------------------------------------------------------------------------
# Bucket scoring
# ---------------------------------------------------------------------------

def _clamp(x: float, lo: float = -2.0, hi: float = 2.0) -> float:
    return max(lo, min(hi, x))


def _sma(series: list[float], n: int) -> Optional[float]:
    return sum(series[-n:]) / n if len(series) >= n else None


def basket_index_series(series: dict, b: Basket) -> Optional[list[float]]:
    """Weighted index of the basket, base 100 at the start of the window.

    Uses only the constituents that actually returned data, renormalizing
    their weights. If fewer than half the sleeve resolved, returns None --
    an index built from two of eight names is not the sleeve.
    """
    present = [t for t in b.tickers if t in series]
    if len(present) < max(2, len(b.tickers) // 2):
        return None

    n = min(len(series[t]) for t in present)
    if n < 60:
        return None

    wsum = sum(b.weights_pct[t] for t in present)
    idx = []
    for i in range(n):
        level = 0.0
        for t in present:
            s = series[t][-n:]
            level += (b.weights_pct[t] / wsum) * (s[i] / s[0])
        idx.append(level * 100.0)
    return idx


def score_momentum(idx: Optional[list[float]]) -> Bucket:
    if not idx or len(idx) < 50:
        return Bucket("momentum", None, "No basket index — constituents unavailable.")
    last = idx[-1]
    sma20, sma50 = _sma(idx, 20), _sma(idx, 50)
    if sma20 is None or sma50 is None:
        return Bucket("momentum", None, "Insufficient history for 20/50-day trend.")

    above20 = (last / sma20 - 1.0) * 100.0
    above50 = (last / sma50 - 1.0) * 100.0
    blended = 0.6 * above20 + 0.4 * above50
    # +/-2.5% above blended trend saturates the bucket.
    score = _clamp(blended / 2.5 * 2.0)
    return Bucket(
        "momentum", round(score, 2),
        f"Basket {above20:+.2f}% vs 20-day, {above50:+.2f}% vs 50-day.",
    )


def score_breadth(series: dict, b: Basket) -> Bucket:
    present = [t for t in b.tickers if t in series and len(series[t]) >= 50]
    if len(present) < max(2, len(b.tickers) // 2):
        return Bucket("breadth", None, "Too few constituents resolved to measure breadth.")

    above = 0
    for t in present:
        s = series[t]
        sma50 = _sma(s, 50)
        if sma50 and s[-1] > sma50:
            above += 1
    frac = above / len(present)
    score = _clamp((frac - 0.5) * 4.0)
    return Bucket(
        "breadth", round(score, 2),
        f"{above}/{len(present)} constituents above their own 50-day average.",
    )


def score_rates(series: dict) -> Bucket:
    s = series.get(TNX_TICKER)
    if not s or len(s) < 6:
        return Bucket("rates", None, "10-year yield series unavailable.")
    # ^TNX quotes yield x10, so a 1.0 move is 100bp.
    chg_bp = (s[-1] - s[-6]) * 10.0
    # Sign-inverted: rising long rates discount long-duration tech.
    score = _clamp(-chg_bp / 15.0 * 2.0)
    return Bucket(
        "rates", round(score, 2),
        f"US 10-year {chg_bp:+.1f}bp over the week; long-duration tech scores inverse.",
    )


def score_earnings(series: dict, fixture_extra: Optional[dict]) -> Bucket:
    """Forward-EPS revision breadth.

    Deliberately abstains. There is no keyless source for consensus forward
    estimates, and inventing one would put a fabricated number into a ledger
    whose entire purpose is that its numbers are not fabricated. Supply
    `earnings_revision_breadth` in a fixture (fraction of the sleeve with
    upward 4-week revisions, 0..1) to activate it.
    """
    frac = (fixture_extra or {}).get("earnings_revision_breadth")
    if frac is None:
        return Bucket(
            "earnings", None,
            "Abstained — no keyless source for forward-EPS revisions.",
        )
    score = _clamp((float(frac) - 0.5) * 4.0)
    return Bucket(
        "earnings", round(score, 2),
        f"{float(frac) * 100:.0f}% of the sleeve carrying upward 4-week EPS revisions.",
    )


def score_volatility(series: dict) -> Bucket:
    s = series.get(VIX_TICKER)
    if not s or len(s) < 6:
        return Bucket("volatility", None, "VIX series unavailable.")
    level, prior = s[-1], s[-6]
    chg_pct = (level / prior - 1.0) * 100.0
    # Falling vol is constructive; a 10% weekly move saturates.
    score = -chg_pct / 10.0 * 2.0
    # An elevated absolute level caps how constructive falling vol can read.
    if level > 25.0:
        score = min(score, 0.5)
    return Bucket(
        "volatility", round(_clamp(score), 2),
        f"VIX {level:.2f}, {chg_pct:+.1f}% on the week.",
    )


# ---------------------------------------------------------------------------
# Composite
# ---------------------------------------------------------------------------

def label_for(composite: float) -> str:
    if composite >= 1.0:
        return "CONSTRUCTIVE"
    if composite >= 0.3:
        return "LEAN CONSTRUCTIVE"
    if composite > -0.3:
        return "NEUTRAL"
    if composite > -1.0:
        return "LEAN DEFENSIVE"
    return "DEFENSIVE"


def build_call(buckets: list[Bucket]) -> Call:
    """Composite over scored buckets only, with weights renormalized.

    An abstaining bucket is dropped, not zeroed. Zeroing would drag the
    composite toward the neutral band and manufacture a false NEUTRAL --
    the same failure control C-06 guards against in the SPX morning model.
    """
    scored = [b for b in buckets if not b.abstained]
    if not scored:
        return Call(0.0, "NEUTRAL", "low", 0.0, buckets, {})

    wsum = sum(BASE_WEIGHTS[b.name] for b in scored)
    weights = {b.name: BASE_WEIGHTS[b.name] / wsum for b in scored}
    composite = _clamp(sum(weights[b.name] * b.score for b in scored))

    vals = [b.score for b in scored]
    span = max(vals) - min(vals)

    n_abstained = len(buckets) - len(scored)
    if n_abstained >= 2:
        confidence = "low"
    elif span < 1.5 and len(scored) >= 4:
        confidence = "high"
    elif span < 2.5 and len(scored) >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    return Call(
        composite=round(composite, 2),
        label=label_for(composite),
        confidence=confidence,
        bucket_span=round(span, 2),
        buckets=buckets,
        weights={k: round(v, 4) for k, v in weights.items()},
    )


# ---------------------------------------------------------------------------
# Projection — a scenario, not a forecast
# ---------------------------------------------------------------------------

def weekly_returns_by_ticker(series: dict, b: Basket) -> dict:
    """Non-overlapping weekly simple returns per holding, aligned across the
    sleeve so the covariance estimate compares the same weeks."""
    present = [t for t in b.tickers if t in series and len(series[t]) >= 120]
    if not present:
        return {}
    n = min(len(series[t]) for t in present)
    out = {}
    for t in present:
        s = series[t][-n:]
        out[t] = [s[i] / s[i - 5] - 1.0 for i in range(5, n, 5) if s[i - 5]]
    return out


def build_projection(
    series: dict, b: Basket, horizon_weeks: int = 52, seed: int = 786,
) -> dict:
    """Correlated Monte Carlo forward from the sleeve's trailing weekly returns.

    Normalized to base 100 so it publishes without disclosing a balance. The
    composite call is deliberately NOT an input: folding a one-week
    directional score into a 52-week path would imply the model forecasts a
    year out. It does not.

    Uses analytics.montecarlo, which draws CORRELATED shocks across holdings.
    This matters more than it sounds: on a fixture with the ~0.5 pairwise
    correlation large-cap tech actually shows, independent draws understate
    the decile band by roughly half and put the 10th percentile ~20 index
    points too high. A concentrated sleeve does not diversify its own risk
    away, and a projection that says otherwise is flattering, not useful.
    """
    base = {
        "basis": "normalized index, base 100",
        "cadence": b.cadence,
        "assumed_continuing": b.assumed_continuing,
        "horizon_weeks": horizon_weeks,
        "method": ("correlated Monte Carlo over trailing weekly returns "
                   "(analytics.montecarlo); composite call excluded"),
        "path": [],
        "available": False,
        "note": "Insufficient history to draw a band.",
    }

    weekly = weekly_returns_by_ticker(series, b)
    weekly = {t: r for t, r in weekly.items() if len(r) >= 30}
    if len(weekly) < max(2, len(b.tickers) // 2):
        return base

    # Contribution in index points per week, never currency, so the output
    # stays publishable. A monthly cadence adds ~1 point a month.
    per_week = {"weekly": 1.0, "biweekly": 0.5, "monthly": 0.25}.get(b.cadence, 0.0)
    if not b.assumed_continuing:
        per_week = 0.0

    try:
        mc = montecarlo.MCSimulation(
            weekly,
            weights={t: b.weights_pct[t] for t in weekly},
            num_simulation=2000,
            num_periods=horizon_weeks,
            seed=seed,
        )
        paths = mc.run(contribution_per_period=per_week)
    except ValueError as e:
        base["note"] = f"Projection unavailable: {e}"
        return base

    path = [
        {"week": row["period"], "p10": row["p10"], "p50": row["p50"], "p90": row["p90"]}
        for row in mc.percentile_path(paths)
    ]

    port = portfolio_return_series(weekly, b)
    ann_vol = risk.annualized_vol(port, periods=52) if port else None

    base.update({
        "path": path,
        "available": True,
        "summary": mc.summarize(),
        "correlated": mc.correlated,
        "holdings_simulated": len(weekly),
        "trailing_weeks_sampled": min(len(r) for r in weekly.values()),
        "annualized_vol_pct": round(ann_vol * 100, 1) if ann_vol else None,
        "note": (
            "Band is drawn from trailing volatility and breaks in a regime "
            "change. p10/p90 are not worst and best cases — roughly one year "
            "in ten finishes outside each edge, and real equity tails are "
            "fatter than the Gaussian this draws from. Management fees are "
            "not netted out."
        ),
    })
    if not mc.correlated:
        base["note"] = ("Covariance across holdings was degenerate, so shocks "
                        "were drawn independently — this band is too narrow. "
                        + base["note"])
    return base


def portfolio_return_series(returns_by_ticker: dict, b: Basket) -> list[float]:
    """Weight-blended return series across the holdings that resolved."""
    if not returns_by_ticker:
        return []
    tickers = list(returns_by_ticker)
    wsum = sum(b.weights_pct[t] for t in tickers)
    n = min(len(returns_by_ticker[t]) for t in tickers)
    return [
        sum(b.weights_pct[t] / wsum * returns_by_ticker[t][-n:][i] for t in tickers)
        for i in range(n)
    ]


def build_risk_panel(series: dict, b: Basket) -> dict:
    """Sharpe, vol, beta, drawdown and correlation for the sleeve.

    Ported from A-Whale-Off-the-Port-folio/whale_analysis.ipynb via
    analytics.risk. Computed on DAILY returns (periods=252) because beta and
    drawdown both degrade badly on a weekly sample this short.

    risk_free is left at 0.0 and labelled as such. The source notebook used
    the zero form, which was defensible at 2021 short rates and is not now --
    the Sharpe here is therefore flattering and is published with that stated
    rather than quietly corrected to a rate nobody chose.
    """
    daily = {
        t: risk.daily_returns(series[t])
        for t in b.tickers if t in series and len(series[t]) >= 60
    }
    if len(daily) < max(2, len(b.tickers) // 2):
        return {"available": False,
                "note": "Too few constituents resolved to compute risk metrics."}

    port = portfolio_return_series(daily, b)
    bench_daily = (risk.daily_returns(series[b.benchmark])
                   if b.benchmark in series else None)
    panel = risk.summarize(port, bench_daily, periods=risk.TRADING_DAYS,
                           risk_free=0.0)

    pairs = [
        risk.correlation(daily[a], daily[c])
        for i, a in enumerate(daily) for c in list(daily)[i + 1:]
    ]
    pairs = [p for p in pairs if p is not None]

    rb = risk.rolling_beta(port, bench_daily, window=60) if bench_daily else []
    rb = [x for x in rb if x is not None]

    return {
        "available": True,
        "benchmark": b.benchmark,
        "risk_free_rate": 0.0,
        "holdings_measured": len(daily),
        "annualized_vol": panel["annualized_vol"],
        "ewma_vol": panel["ewma_vol"],
        "sharpe": panel["sharpe"],
        "max_drawdown": panel["max_drawdown"],
        "beta": panel["beta"],
        "correlation_to_benchmark": panel["correlation_to_benchmark"],
        "mean_pairwise_correlation": (
            round(sum(pairs) / len(pairs), 3) if pairs else None
        ),
        "rolling_beta_60d": {
            "latest": round(rb[-1], 3) if rb else None,
            "min": round(min(rb), 3) if rb else None,
            "max": round(max(rb), 3) if rb else None,
        },
        "note": ("Sharpe assumes a 0% risk-free rate, as in the source "
                 "notebook. At current short rates that overstates it."),
    }


# ---------------------------------------------------------------------------
# Ledger I/O — atomic, append-only, idempotent
# ---------------------------------------------------------------------------

def _read_ledger_rows() -> list[dict]:
    if not LEDGER_PATH.exists():
        return []
    with LEDGER_PATH.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _csv_escape(v: str) -> str:
    if any(ch in v for ch in [",", '"', "\n", "\r"]):
        return '"' + v.replace('"', '""') + '"'
    return v


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


def _write_ledger(rows: list[dict]) -> None:
    buf = [",".join(LEDGER_COLUMNS)]
    for r in rows:
        buf.append(",".join(_csv_escape(str(r.get(c, ""))) for c in LEDGER_COLUMNS))
    _atomic_write(LEDGER_PATH, "\n".join(buf) + "\n")


def append_ledger_row(row: dict, dry_run: bool = False) -> None:
    """Append one week. Refuses duplicates. Verifies prior rows are untouched."""
    rows = _read_ledger_rows()
    for r in rows:
        if r["week_ending"] == row["week_ending"]:
            raise RuntimeError(
                f"Ledger already has a row for {row['week_ending']} — refusing "
                f"duplicate append. Amend deliberately per docs/PORTFOLIO-SCHEMA.md."
            )
    if dry_run:
        print(f"[dry-run] would append: {row['week_ending']} "
              f"{row['label']} ({row['composite']})")
        return

    before = [dict(r) for r in rows]
    _write_ledger(rows + [row])

    after = _read_ledger_rows()
    if len(after) != len(before) + 1:
        raise RuntimeError(
            f"APPEND-ONLY INVARIANT VIOLATED: expected {len(before) + 1} rows, "
            f"got {len(after)}."
        )
    for i, r in enumerate(before):
        if after[i] != r:
            raise RuntimeError(
                f"APPEND-ONLY INVARIANT VIOLATED: row {i} "
                f"({r['week_ending']}) changed during write. Restore from git."
            )
    if after[-1]["week_ending"] != row["week_ending"]:
        raise RuntimeError("APPEND-ONLY INVARIANT VIOLATED: new row is not last.")


def score_prior_week(idx: Optional[list[float]], dry_run: bool = False) -> Optional[str]:
    """Fill the outcome columns on the most recent row that lacks them.

    Touches `fwd_1w_basket_pct` and `was_directionally_right` and nothing
    else. The call in columns 4-6 was recorded before this outcome existed
    and must stay exactly as written -- that is what makes it a prediction.
    """
    rows = _read_ledger_rows()
    target = None
    for r in reversed(rows):
        if not r.get("fwd_1w_basket_pct"):
            target = r
            break
    if target is None:
        print("[score-prior] no unscored row.")
        return None
    if not idx or len(idx) < 6:
        print("[score-prior] no basket index available — leaving row unscored.")
        return None

    fwd_pct = (idx[-1] / idx[-6] - 1.0) * 100.0
    composite = float(target["composite"] or 0.0)
    right = (composite > 0 and fwd_pct > 0) or (composite < 0 and fwd_pct < 0)

    frozen = {k: v for k, v in target.items()
              if k not in ("fwd_1w_basket_pct", "was_directionally_right")}
    target["fwd_1w_basket_pct"] = f"{fwd_pct:.2f}"
    target["was_directionally_right"] = "" if composite == 0 else str(right).lower()

    for k, v in frozen.items():
        if target[k] != v:
            raise RuntimeError(
                f"REFUSING WRITE: --score-prior altered '{k}' on "
                f"{target['week_ending']}. Only outcome columns may change."
            )

    if dry_run:
        print(f"[dry-run] would score {target['week_ending']}: "
              f"fwd={fwd_pct:+.2f}% right={target['was_directionally_right']}")
        return target["week_ending"]

    _write_ledger(rows)
    print(f"[score-prior] {target['week_ending']}: fwd={fwd_pct:+.2f}% "
          f"right={target['was_directionally_right']}")
    return target["week_ending"]


def track_record() -> dict:
    rows = _read_ledger_rows()
    scored = [r for r in rows if r.get("was_directionally_right") in ("true", "false")]
    if not scored:
        return {"weeks_recorded": len(rows), "weeks_scored": 0,
                "directional_hit_rate": None}
    hits = sum(1 for r in scored if r["was_directionally_right"] == "true")
    return {
        "weeks_recorded": len(rows),
        "weeks_scored": len(scored),
        "directional_hit_rate": round(hits / len(scored), 3),
    }


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

def git_short_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT,
            check=True, capture_output=True, text=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def write_dashboard_json(
    b: Basket, call: Call, projection: dict, week_ending: str,
    basket_idx: Optional[list[float]], bench_idx: Optional[float],
    risk_panel: Optional[dict] = None,
    dry_run: bool = False, example: bool = False,
) -> Path:
    """Public-safe by construction: every value here derives from public market
    data plus tickers and percentage weights. Nothing from private/."""
    payload = {
        "schema_version": SCHEMA_VERSION,
        "example": example or None,
        "week_ending": week_ending,
        "generated_at": _now_et().isoformat(timespec="seconds"),
        "owner_confirmed": b.owner_confirmed,
        "banner": None if b.owner_confirmed else REFERENCE_BANNER,
        "basket": {
            "id": b.basket_id,
            "display_name": b.display_name,
            "source": b.source,
            "as_of": b.as_of,
            "benchmark": b.benchmark,
            "constituents": [
                {"ticker": t, "weight_pct": b.weights_pct[t]} for t in b.tickers
            ],
        },
        "call": {
            "composite": call.composite,
            "label": call.label,
            "confidence": call.confidence,
            "bucket_span": call.bucket_span,
            "abstained": call.abstained_names,
        },
        "buckets": [
            {
                "name": bk.name,
                "score": bk.score,
                "weight": call.weights.get(bk.name),
                "base_weight": BASE_WEIGHTS[bk.name],
                "rationale": bk.rationale,
                "abstained": bk.abstained,
            }
            for bk in call.buckets
        ],
        "levels": {
            "basket_index": round(basket_idx[-1], 2) if basket_idx else None,
            "benchmark_index": round(bench_idx, 2) if bench_idx else None,
        },
        "risk": risk_panel or {"available": False},
        "projection": projection,
        "track_record": track_record(),
        "disclaimer": DISCLAIMER,
    }
    path = DASHBOARD_DATA_DIR / (
        "portfolio.example.json" if example else "portfolio.json"
    )
    content = json.dumps(payload, indent=2, sort_keys=False) + "\n"
    if dry_run:
        print(f"[dry-run] would write {path}")
    else:
        _atomic_write(path, content)
    return path


def _bucket_rows_html(call: Call) -> str:
    out = []
    for bk in call.buckets:
        if bk.abstained:
            score, cls = "abstained", "muted"
        else:
            score, cls = f"{bk.score:+.2f}", ("pos" if bk.score > 0 else
                                              "neg" if bk.score < 0 else "muted")
        out.append(
            f'<tr><td style="padding:6px 10px;text-transform:capitalize">{bk.name}</td>'
            f'<td style="padding:6px 10px;text-align:right" class="{cls}">{score}</td>'
            f'<td style="padding:6px 10px;color:#5A646E">{bk.rationale}</td></tr>'
        )
    return "\n".join(out)


def write_email_fragment(
    b: Basket, call: Call, week_ending: str, dry_run: bool = False,
) -> Path:
    """The PUBLIC email section. Tickers, weights, scores. No dollars."""
    banner = "" if b.owner_confirmed else (
        f'<p style="margin:0 0 10px;padding:8px 10px;background:#FDF4EF;'
        f'border-left:3px solid #E0662E;color:#AD4317;font-size:13px">'
        f'<b>{REFERENCE_BANNER}</b></p>'
    )
    abstained = call.abstained_names
    abstain_line = (
        f'<p style="margin:8px 0 0;color:#5A646E;font-size:13px">'
        f'Abstained this week: <b>{", ".join(abstained)}</b>. '
        f'Weights renormalized over the buckets that scored; an absent input '
        f'is not a neutral one.</p>' if abstained else ""
    )
    tr = track_record()
    hit = tr["directional_hit_rate"]
    record_line = (
        f'{tr["weeks_scored"]} weeks scored, '
        f'{hit * 100:.0f}% directionally right'
        if hit is not None else
        f'{tr["weeks_recorded"]} week(s) recorded, none scored yet'
    )

    html = f"""<!-- BEGIN tech-outlook (generated by scripts/portfolio_track.py) -->
<section style="margin:24px 0;font-family:system-ui,-apple-system,sans-serif">
  <h2 style="margin:0 0 4px;font-size:19px;color:#171A1D">
    {b.display_name} — Weekly Outlook</h2>
  <div style="font-size:11px;letter-spacing:.14em;text-transform:uppercase;
              color:#AD4317;margin-bottom:12px">Week ending {week_ending}</div>
  {banner}
  <div style="padding:14px;border:1px solid #E2DAD3;border-radius:6px;background:#fff">
    <div style="font-size:28px;font-weight:800;color:#171A1D">
      {call.label} <span style="font-size:19px;color:#5A646E">
      ({call.composite:+.2f})</span></div>
    <div style="font-size:13px;color:#5A646E;margin-top:2px">
      Confidence {call.confidence} · bucket span {call.bucket_span:.2f} ·
      track record: {record_line}</div>
    <table style="width:100%;border-collapse:collapse;margin-top:12px;font-size:13px">
      <thead><tr style="text-align:left;border-bottom:1px solid #E2DAD3">
        <th style="padding:6px 10px">Bucket</th>
        <th style="padding:6px 10px;text-align:right">Score</th>
        <th style="padding:6px 10px">Rationale</th></tr></thead>
      <tbody>
{_bucket_rows_html(call)}
      </tbody>
    </table>
    {abstain_line}
  </div>
  <p style="margin:10px 0 0;font-size:12px;color:#5A646E">
    This is a weekly <b>outlook</b> on a long-horizon sleeve, not a trade
    instruction, and not a suggestion to change contributions. {DISCLAIMER}</p>
</section>
<!-- END tech-outlook -->
"""
    path = DASHBOARD_DATA_DIR / "portfolio-email.html"
    if dry_run:
        print(f"[dry-run] would write {path}")
    else:
        _atomic_write(path, html)
    return path


def write_private_email_fragment(
    b: Basket, call: Call, week_ending: str, dry_run: bool = False,
) -> Optional[Path]:
    """The owner-only addendum, with dollars. Written under private/, which is
    gitignored. This is the ONLY sink for values read from private/holdings.json.
    """
    src = PRIVATE_DIR / "holdings.json"
    if not src.exists():
        return None
    try:
        h = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.stderr.write(f"[warn] private/holdings.json is not valid JSON: {e}\n")
        return None

    value = h.get("sleeve_value_usd")
    contrib = h.get("contribution_amount_usd")
    rows = "".join(
        f'<tr><td style="padding:4px 8px">{k}</td>'
        f'<td style="padding:4px 8px;text-align:right">{v}</td></tr>'
        for k, v in (
            ("Sleeve value", f"${value:,.2f}" if isinstance(value, (int, float)) else "—"),
            ("Contribution", f"${contrib:,.2f} / {b.cadence}"
             if isinstance(contrib, (int, float)) else "—"),
        )
    )
    html = f"""<!-- OWNER-ONLY. Contains private figures. NEVER COMMIT. -->
<section style="margin:16px 0;font-family:system-ui,sans-serif">
  <h3 style="margin:0 0 6px;font-size:15px">Owner addendum — {week_ending}</h3>
  <table style="border-collapse:collapse;font-size:13px;border:1px solid #E2DAD3">
    {rows}
  </table>
  <p style="font-size:12px;color:#5A646E;margin:8px 0 0">
    Call this week: {call.label} ({call.composite:+.2f}).
    Figures above are read from private/holdings.json and appear in no
    committed file. {DISCLAIMER}</p>
</section>
"""
    path = PRIVATE_DIR / "portfolio-email-private.html"
    if dry_run:
        print(f"[dry-run] would write {path} (gitignored)")
        return path
    _atomic_write(path, html)
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _now_et() -> dt.datetime:
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return dt.datetime.now()


def _last_friday(d: dt.date) -> dt.date:
    return d - dt.timedelta(days=(d.weekday() - 4) % 7)


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--week-ending", default=None, help="YYYY-MM-DD Friday")
    p.add_argument("--fixture", default=None, help="JSON price series for offline runs")
    p.add_argument("--score-prior", action="store_true",
                   help="fill the previous row's outcome columns and exit")
    p.add_argument("--example", action="store_true",
                   help="write dashboard/data/portfolio.example.json and touch "
                        "nothing else; never appends to the ledger")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    week_ending = args.week_ending or _last_friday(_now_et().date()).isoformat()
    b = load_basket()

    fixture = Path(args.fixture) if args.fixture else None
    wanted = b.tickers + [b.benchmark, TNX_TICKER, VIX_TICKER]
    series = fetch_series(wanted, fixture=fixture)
    fixture_extra = None
    if fixture:
        raw = json.loads(fixture.read_text(encoding="utf-8"))
        fixture_extra = {k: v for k, v in raw.items() if not isinstance(v, list)}

    idx = basket_index_series(series, b)

    if args.score_prior:
        score_prior_week(idx, dry_run=args.dry_run)
        return 0

    buckets = [
        score_momentum(idx),
        score_breadth(series, b),
        score_rates(series),
        score_earnings(series, fixture_extra),
        score_volatility(series),
    ]
    call = build_call(buckets)

    bench_series = series.get(b.benchmark)
    bench_idx = (bench_series[-1] / bench_series[-len(idx)] * 100.0
                 if bench_series and idx and len(bench_series) >= len(idx) else None)

    projection = build_projection(series, b)
    risk_panel = build_risk_panel(series, b)

    row = {
        "week_ending": week_ending,
        "basket_id": b.basket_id,
        "owner_confirmed": "true" if b.owner_confirmed else "false",
        "composite": f"{call.composite:.2f}",
        "label": call.label,
        "confidence": call.confidence,
        "momentum": "", "breadth": "", "rates": "", "earnings": "", "volatility": "",
        "abstained": ";".join(call.abstained_names),
        "bucket_span": f"{call.bucket_span:.2f}",
        "basket_index": f"{idx[-1]:.2f}" if idx else "",
        "benchmark_index": f"{bench_idx:.2f}" if bench_idx else "",
        "fwd_1w_basket_pct": "",
        "was_directionally_right": "",
        "commit_hash": git_short_sha(),
        "notes": "" if b.owner_confirmed else "reference basket; not owner holdings",
    }
    for bk in call.buckets:
        row[bk.name] = "" if bk.abstained else f"{bk.score:.2f}"

    if args.example:
        # Example mode exists so the tab can be smoke-tested from a fixture
        # without a fabricated week ever entering the append-only ledger.
        out = write_dashboard_json(b, call, projection, week_ending, idx,
                                   bench_idx, risk_panel=risk_panel,
                                   dry_run=args.dry_run, example=True)
        print(f"[portfolio_track] example written to {out}; ledger untouched.")
        return 0

    append_ledger_row(row, dry_run=args.dry_run)
    write_dashboard_json(b, call, projection, week_ending, idx, bench_idx,
                         risk_panel=risk_panel, dry_run=args.dry_run)
    write_email_fragment(b, call, week_ending, dry_run=args.dry_run)
    priv = write_private_email_fragment(b, call, week_ending, dry_run=args.dry_run)

    scored = [bk.name for bk in call.buckets if not bk.abstained]
    print(
        f"[portfolio_track] {week_ending}: {call.label} ({call.composite:+.2f}) "
        f"confidence={call.confidence} scored={len(scored)}/5 "
        f"abstained={','.join(call.abstained_names) or 'none'}"
    )
    if not b.owner_confirmed:
        print(f"[portfolio_track] {REFERENCE_BANNER} — "
              f"set owner_confirmed=true in portfolio/basket.json after upload.")
    if priv:
        print(f"[portfolio_track] owner addendum written to {priv} (gitignored)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
