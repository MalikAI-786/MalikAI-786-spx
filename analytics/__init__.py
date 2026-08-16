# EDUCATIONAL ANALYTICS. Real money never moved. Not investment advice.
"""
analytics — shared quantitative library for the MalikAI-786 models.

Consolidates the reusable maths from the 2021 Columbia FinTech coursework
repositories into versioned, stdlib-only modules that both the SPX 0DTE model
and the tech-sleeve outlook consume. Provenance for each port is recorded in
the module it lives in, and in docs/ANALYTICS-PROVENANCE.md.

| Module | Ported from | Provides |
|---|---|---|
| `risk` | `A-Whale-Off-the-Port-folio` | Sharpe, annualized and EWMA vol, beta, rolling beta, correlation, max drawdown |
| `montecarlo` | `API/MCForecastTools.py` | Correlated Monte Carlo over a weighted portfolio |

Every module here is stdlib-only on purpose. The daily pipeline has to run on
a laptop at 9:00 AM without a scientific stack installed, and the integrity
audit only runs `compileall`. Where a port gave up a technique that genuinely
needs numpy or `arch`, the module says so and names the upgrade path rather
than pretending the simpler estimator is equivalent.
"""

__version__ = "1.0.0"
