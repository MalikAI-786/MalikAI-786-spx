#!/usr/bin/env python3
# EDUCATIONAL ANALYTICS. Real money never moved. Not investment advice.
"""
risk.py — portfolio risk metrics.

Ported from `A-Whale-Off-the-Port-folio/whale_analysis.ipynb` (Columbia
FinTech, 2021), which computed these against Soros / Paulson / Tiger Global /
Berkshire daily returns versus the S&P 500.

Two things changed in the port:

1. **pandas is gone.** The notebook leaned on `.rolling()`, `.ewm()` and
   `.corr()`. Nothing in this repository's daily pipeline imports a
   third-party package, the audit workflow only runs `compileall`, and the
   machine this executes on should not need a scientific stack to produce a
   morning email. Everything here is stdlib over `list[float]`.

2. **Ambiguity is an exception, not a NaN.** The notebook dropped NaNs and
   carried on. A metric computed from too few observations is not a small
   number, it is an unknown one, so these functions return None and let the
   caller decide what to say about it.

Conventions:
  - `returns` are simple period returns (0.01 == +1%), oldest first.
  - `periods` is the annualization factor: 252 daily, 52 weekly, 12 monthly.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence

TRADING_DAYS = 252


# ---------------------------------------------------------------------------
# Series helpers
# ---------------------------------------------------------------------------

def daily_returns(prices: Sequence[float]) -> list[float]:
    """Simple period-over-period returns. Mirrors `.pct_change().dropna()`."""
    return [
        prices[i] / prices[i - 1] - 1.0
        for i in range(1, len(prices))
        if prices[i - 1]
    ]


def cumulative_returns(returns: Sequence[float]) -> list[float]:
    """Growth of 1.0. Mirrors `(1 + returns).cumprod()`."""
    out, level = [], 1.0
    for r in returns:
        level *= (1.0 + r)
        out.append(level)
    return out


def mean(xs: Sequence[float]) -> Optional[float]:
    return sum(xs) / len(xs) if xs else None


def stdev(xs: Sequence[float]) -> Optional[float]:
    """Sample standard deviation (n-1), matching pandas `.std()`."""
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


# ---------------------------------------------------------------------------
# Headline metrics
# ---------------------------------------------------------------------------

def annualized_vol(returns: Sequence[float], periods: int = TRADING_DAYS) -> Optional[float]:
    """`std * sqrt(periods)`. Returned as a fraction, not a percent."""
    sd = stdev(returns)
    return sd * math.sqrt(periods) if sd is not None else None


def sharpe(
    returns: Sequence[float], periods: int = TRADING_DAYS, risk_free: float = 0.0
) -> Optional[float]:
    """Annualized Sharpe: `(mean * periods - rf) / (std * sqrt(periods))`.

    The notebook used the zero-risk-free form, which was defensible at 2021
    short rates and is not at current ones. `risk_free` is an annual rate;
    pass it explicitly rather than accepting the zero default when the number
    is going to be shown to anyone.
    """
    sd = stdev(returns)
    m = mean(returns)
    if sd is None or m is None or sd == 0:
        return None
    return (m * periods - risk_free) / (sd * math.sqrt(periods))


def max_drawdown(levels: Sequence[float]) -> Optional[float]:
    """Largest peak-to-trough decline, as a negative fraction.

    Takes an index level series, not returns -- drawdown is path-dependent
    and cannot be recovered from summary statistics.
    """
    if len(levels) < 2:
        return None
    peak, worst = levels[0], 0.0
    for lv in levels:
        peak = max(peak, lv)
        if peak > 0:
            worst = min(worst, lv / peak - 1.0)
    return worst


def covariance(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    n = min(len(a), len(b))
    if n < 2:
        return None
    a, b = a[-n:], b[-n:]
    ma, mb = sum(a) / n, sum(b) / n
    return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / (n - 1)


def correlation(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    cov = covariance(a, b)
    sa, sb = stdev(a[-min(len(a), len(b)):]), stdev(b[-min(len(a), len(b)):])
    if cov is None or not sa or not sb:
        return None
    return max(-1.0, min(1.0, cov / (sa * sb)))


def beta(asset: Sequence[float], benchmark: Sequence[float]) -> Optional[float]:
    """`cov(asset, benchmark) / var(benchmark)`."""
    n = min(len(asset), len(benchmark))
    if n < 2:
        return None
    cov = covariance(asset[-n:], benchmark[-n:])
    sb = stdev(benchmark[-n:])
    if cov is None or not sb:
        return None
    return cov / (sb ** 2)


def rolling_beta(
    asset: Sequence[float], benchmark: Sequence[float], window: int = 60
) -> list[Optional[float]]:
    """Rolling beta, one value per window-length slice. Window 60 matches the
    source notebook. Returns [] when there is not one full window."""
    n = min(len(asset), len(benchmark))
    if n < window:
        return []
    a, b = asset[-n:], benchmark[-n:]
    return [beta(a[i - window:i], b[i - window:i]) for i in range(window, n + 1)]


def correlation_matrix(series: dict) -> dict:
    """Pairwise correlations. Mirrors `df.corr()`, as a nested dict."""
    keys = list(series)
    return {
        a: {b: correlation(series[a], series[b]) for b in keys}
        for a in keys
    }


# ---------------------------------------------------------------------------
# Conditional volatility
# ---------------------------------------------------------------------------

def ewma_vol(
    returns: Sequence[float], lam: float = 0.94, periods: int = TRADING_DAYS
) -> Optional[float]:
    """Exponentially-weighted annualized volatility (RiskMetrics).

    The whale notebook used `ewm(halflife=21)` on returns; this applies the
    same idea to squared returns, which is what a volatility estimate needs.
    lam=0.94 is the RiskMetrics daily default -- roughly an 11-day half-life.

    This stands in for the GARCH(1,1) fit in `Time_Series/
    time_series_analysis.ipynb`. EWMA is GARCH(1,1) with the parameters
    pinned instead of estimated: no `arch` dependency, no convergence to
    babysit, and it reacts to a vol shock the same way. It gives up
    mean-reversion in variance, so it will run hot for longer than a fitted
    GARCH after a spike. When `arch` is available, fitting properly is the
    upgrade -- keep this as the fallback rather than replacing it.
    """
    if len(returns) < 2:
        return None
    var = returns[0] ** 2
    for r in returns[1:]:
        var = lam * var + (1.0 - lam) * r * r
    return math.sqrt(var * periods)


def summarize(
    returns: Sequence[float],
    benchmark_returns: Optional[Sequence[float]] = None,
    periods: int = TRADING_DAYS,
    risk_free: float = 0.0,
) -> dict:
    """The whale notebook's headline panel, as one dict.

    Any metric that cannot be computed from the data supplied comes back as
    None rather than being silently dropped, so a caller rendering this can
    say which numbers are missing.
    """
    levels = cumulative_returns(returns)
    out = {
        "observations": len(returns),
        "annualized_vol": annualized_vol(returns, periods),
        "ewma_vol": ewma_vol(returns, periods=periods),
        "sharpe": sharpe(returns, periods, risk_free),
        "max_drawdown": max_drawdown(levels),
        "cumulative_return": (levels[-1] - 1.0) if levels else None,
        "beta": None,
        "correlation_to_benchmark": None,
    }
    if benchmark_returns:
        out["beta"] = beta(returns, benchmark_returns)
        out["correlation_to_benchmark"] = correlation(returns, benchmark_returns)
    return out
