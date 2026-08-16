#!/usr/bin/env python3
# EDUCATIONAL ANALYTICS. Real money never moved. Not investment advice.
"""
montecarlo.py — correlated Monte Carlo for a weighted portfolio.

Ported from `API/MCForecastTools.py` (Columbia FinTech, 2021), the
`MCSimulation` class used by `financial-planner.ipynb` to project a
retirement balance.

Three changes from the original, in order of how much they matter:

1. **Correlated draws instead of independent ones.**
   The original simulated each holding on its own:

       simvals[s].append(simvals[s][-1] * (1 + np.random.normal(mean[s], std[s])))

   Every stock drew its own independent shock, so the simulated portfolio
   diversified away risk that a real one does not have. In a drawdown, eight
   large-cap technology names do not move independently -- they move together,
   which is the entire reason a concentrated tech sleeve is concentrated. The
   original therefore reports a tighter band than the portfolio deserves, and
   it is tightest exactly where the error is most expensive: the lower tail.

   This version estimates the empirical covariance across holdings, takes its
   Cholesky factor, and draws correlated shocks, so a bad week for one name is
   a bad week for its neighbours. Everything else about the model -- Gaussian
   shocks, drift from the trailing sample mean -- is unchanged.

2. **No Alpaca, no pandas.** The original imported `alpaca_trade_api` at module
   scope and required Alpaca's MultiIndex DataFrame layout, so it could not be
   imported without both installed. This takes `{ticker: [prices]}` and depends
   only on the standard library.

3. **Seeded.** The original used the global numpy RNG, so no two runs matched.
   A projection that lands in a public artifact has to be reproducible from the
   committed inputs, or the artifact cannot be audited.

What did NOT change, and remains the model's weakest assumption: returns are
drawn from a Gaussian fitted to a trailing window. Real equity returns have
fatter tails and cluster their volatility. The 10th percentile here is not a
worst case, and should never be described as one.
"""
from __future__ import annotations

import math
import random
from typing import Optional, Sequence

TRADING_DAYS = 252


# ---------------------------------------------------------------------------
# Linear algebra (small matrices, stdlib only)
# ---------------------------------------------------------------------------

def cholesky(matrix: list[list[float]], jitter: float = 1e-10) -> Optional[list[list[float]]]:
    """Lower-triangular Cholesky factor L with L @ L.T == matrix.

    An empirical covariance matrix can come back very slightly non-positive-
    definite through floating-point error, or genuinely singular if two
    holdings have identical price histories. Ridge jitter is retried a few
    times; past that we return None and the caller falls back to an
    uncorrelated path rather than silently producing a wrong factorization.
    """
    n = len(matrix)
    for attempt in range(6):
        ridge = jitter * (10 ** attempt) if attempt else 0.0
        L = [[0.0] * n for _ in range(n)]
        ok = True
        for i in range(n):
            for j in range(i + 1):
                s = sum(L[i][k] * L[j][k] for k in range(j))
                if i == j:
                    d = matrix[i][i] + ridge - s
                    if d <= 0:
                        ok = False
                        break
                    L[i][j] = math.sqrt(d)
                else:
                    if L[j][j] == 0:
                        ok = False
                        break
                    L[i][j] = (matrix[i][j] - s) / L[j][j]
            if not ok:
                break
        if ok:
            return L
    return None


def covariance_matrix(returns_by_ticker: dict, tickers: list[str]) -> list[list[float]]:
    n = min(len(returns_by_ticker[t]) for t in tickers)
    cols = [returns_by_ticker[t][-n:] for t in tickers]
    means = [sum(c) / n for c in cols]
    k = len(tickers)
    return [
        [
            sum((cols[i][x] - means[i]) * (cols[j][x] - means[j]) for x in range(n))
            / (n - 1)
            for j in range(k)
        ]
        for i in range(k)
    ]


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

class MCSimulation:
    """Monte Carlo over a weighted portfolio of correlated holdings.

    Parameters
    ----------
    returns_by_ticker : {ticker: [simple period returns, oldest first]}
    weights : {ticker: fraction}. Renormalized over the tickers that have
        data, so a holding whose price series failed to load is dropped
        rather than silently treated as cash.
    num_simulation : paths to draw.
    num_periods : periods to project (252 = one trading year of days).
    seed : fixed so a published projection reproduces from committed inputs.
    """

    def __init__(
        self,
        returns_by_ticker: dict,
        weights: Optional[dict] = None,
        num_simulation: int = 1000,
        num_periods: int = TRADING_DAYS,
        seed: int = 786,
    ):
        self.tickers = [t for t, r in returns_by_ticker.items() if r and len(r) >= 30]
        if not self.tickers:
            raise ValueError("No ticker has enough return history to simulate.")

        self.returns = {t: list(returns_by_ticker[t]) for t in self.tickers}

        if weights:
            w = {t: float(weights.get(t, 0.0)) for t in self.tickers}
            total = sum(w.values())
            if total <= 0:
                raise ValueError("Portfolio weights sum to zero over available tickers.")
            self.weights = {t: v / total for t, v in w.items()}
        else:
            self.weights = {t: 1.0 / len(self.tickers) for t in self.tickers}

        self.nSim = int(num_simulation)
        self.nPeriods = int(num_periods)
        self.seed = int(seed)

        n = min(len(self.returns[t]) for t in self.tickers)
        self.means = [sum(self.returns[t][-n:]) / n for t in self.tickers]
        self.cov = covariance_matrix(self.returns, self.tickers)
        self.chol = cholesky(self.cov)
        self.correlated = self.chol is not None
        self.simulated_final: list[float] = []

    def _draw_period(self, rng: random.Random) -> list[float]:
        """One period's return for each holding, correlated where possible."""
        k = len(self.tickers)
        z = [rng.gauss(0.0, 1.0) for _ in range(k)]
        if self.correlated:
            return [
                self.means[i] + sum(self.chol[i][j] * z[j] for j in range(i + 1))
                for i in range(k)
            ]
        # Degenerate covariance: fall back to independent draws and say so
        # via `.correlated`, so the caller can disclose the weaker assumption.
        sds = [math.sqrt(max(self.cov[i][i], 0.0)) for i in range(k)]
        return [self.means[i] + sds[i] * z[i] for i in range(k)]

    def run(self, contribution_per_period: float = 0.0) -> list[list[float]]:
        """Project `nSim` paths of a base-100 portfolio index.

        `contribution_per_period` is expressed in index points, not currency,
        so the output stays publishable without disclosing a balance.
        """
        rng = random.Random(self.seed)
        w = [self.weights[t] for t in self.tickers]
        paths = []
        for _ in range(self.nSim):
            level = 100.0
            row = [level]
            for _p in range(self.nPeriods):
                draws = self._draw_period(rng)
                port_return = sum(w[i] * draws[i] for i in range(len(w)))
                level *= (1.0 + port_return)
                level += contribution_per_period
                row.append(level)
            paths.append(row)
        self.simulated_final = sorted(p[-1] for p in paths)
        return paths

    def percentile_path(
        self, paths: list[list[float]], quantiles: Sequence[float] = (0.10, 0.50, 0.90)
    ) -> list[dict]:
        """Cross-sectional quantiles at each step, for a fan chart."""
        out = []
        for step in range(len(paths[0])):
            col = sorted(p[step] for p in paths)
            row = {"period": step}
            for q in quantiles:
                row[f"p{int(q * 100)}"] = round(col[int(q * (len(col) - 1))], 2)
            out.append(row)
        return out

    def summarize(self) -> dict:
        """Final-value summary. The original returned a 95% CI from the 2.5th
        and 97.5th percentiles; that is kept, alongside the decile band the
        dashboard draws."""
        if not self.simulated_final:
            raise RuntimeError("Call run() before summarize().")
        f = self.simulated_final
        last = len(f) - 1

        def q(p: float) -> float:
            return round(f[int(p * last)], 2)

        return {
            "simulations": self.nSim,
            "periods": self.nPeriods,
            "correlated": self.correlated,
            "tickers": list(self.tickers),
            "mean": round(sum(f) / len(f), 2),
            "median": q(0.50),
            "p10": q(0.10),
            "p90": q(0.90),
            "ci95_lower": q(0.025),
            "ci95_upper": q(0.975),
            "basis": "index, base 100",
        }
