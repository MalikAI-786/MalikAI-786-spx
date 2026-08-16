# Analytics Provenance — what came from where

**Educational research only. Not investment advice.**

The `analytics/` package is not new work. It is the reusable maths from the
2021 Columbia FinTech coursework repositories, ported into versioned modules
that both live models consume. This file records what was taken, what was
changed, and what was deliberately left behind — so a reader can audit a
number back to the notebook it came from.

The order of authority in `AGENTS.md` applies here too: if this file and a
module docstring disagree, the module wins, because the module is what runs.

---

## Ported

| Source repository | File | Landed in | What it gave us |
|---|---|---|---|
| [`A-Whale-Off-the-Port-folio`](https://github.com/MalikAI-786/A-Whale-Off-the-Port-folio) | `whale_analysis.ipynb` | `analytics/risk.py` | Sharpe, annualized σ, rolling 21-day σ, EWM, rolling 60-day beta, correlation matrix, weighted portfolio returns |
| [`API`](https://github.com/MalikAI-786/API) | `MCForecastTools.py` | `analytics/montecarlo.py` | `MCSimulation` — Monte Carlo over a weighted portfolio with a 95% confidence interval |
| [`Time_Series`](https://github.com/MalikAI-786/Time_Series) | `time_series_analysis.ipynb` | `analytics/risk.ewma_vol` | Conditional volatility, as EWMA rather than fitted GARCH — see below |

Both consumers — `scripts/portfolio_track.py` today, the SPX model when its
buckets are wired — import from `analytics/`, so a correction lands in one
place instead of being re-derived per model.

---

## What changed, and why it mattered

### 1. The Monte Carlo drew each holding independently

This is the substantive finding of the port, not a style note.

`MCForecastTools.py` simulated every holding on its own:

```python
simvals[s].append(simvals[s][-1] * (1 + np.random.normal(mean_returns[s], std_returns[s])))
```

Each stock drew an independent shock, so the simulated portfolio diversified
away risk a real one does not have. Eight large-cap technology names do not
move independently in a drawdown — moving together is the whole reason a
concentrated sleeve is concentrated.

`analytics/montecarlo.py` estimates the empirical covariance across holdings,
takes its Cholesky factor, and draws correlated shocks. Measured on the test
fixture, which carries the ~0.53 mean pairwise correlation large-cap tech
actually shows:

| 52-week projection, base 100 | p10 | median | p90 | decile band |
|---|---|---|---|---|
| Correlated (current) | 103.0 | 136.4 | 184.3 | 81.3 |
| Independent (original) | 122.7 | 139.6 | 160.0 | 37.3 |

The original understates the band by **54%**, and its 10th percentile lands
**~20 index points too high**. The error is largest in the lower tail, which
is the part of the distribution anyone actually needs.

An uncorrelated fixture cannot detect this — the first version of
`tests/fixtures/prices.json` generated independent random walks and showed the
two methods agreeing to within 1%. The fixture was rebuilt around a common
market factor specifically so the correlated path is exercised. A fixture that
cannot fail is not a test.

### 2. pandas, numpy, Keras and Alpaca are gone

The notebooks assume a full scientific stack; `MCForecastTools` imported
`alpaca_trade_api` at module scope, so it could not even be imported without
an Alpaca account configured.

`analytics/` is standard library only, over `list[float]`. The daily pipeline
has to run on a laptop at 9:00 AM without a conda environment, the integrity
audit only runs `compileall`, and every dependency added is a dependency that
can break a morning email. Where a port genuinely gave up capability, the
module says so rather than implying equivalence.

### 3. GARCH became EWMA

`Time_Series/time_series_analysis.ipynb` fits GARCH(1,1) with `arch`.
`analytics/risk.ewma_vol` uses RiskMetrics EWMA (λ=0.94) instead: GARCH(1,1)
with the parameters pinned rather than estimated. No dependency, no
convergence to babysit, and it reacts to a volatility shock the same way.

What it gives up: variance mean-reversion. After a spike, EWMA runs hot longer
than a fitted GARCH would. When `arch` is available, fitting properly is a
genuine upgrade — keep EWMA as the fallback rather than deleting it.

### 4. Missing data raises or returns None, instead of becoming NaN

The notebooks dropped NaNs and carried on. A metric computed from too few
observations is not a small number, it is an unknown one. Every function in
`analytics/risk.py` returns `None` in that case, and callers disclose it.
This is the same discipline as bucket abstention in `docs/PORTFOLIO-SCHEMA.md`.

### 5. The simulation is seeded

The original used the global numpy RNG, so no two runs matched. A projection
that lands in a public artifact has to reproduce from committed inputs or the
artifact cannot be audited. `seed=786`, fixed.

---

## Carried forward unchanged — the model's real weaknesses

Stated here so nobody has to rediscover them:

- **Gaussian shocks.** Returns are drawn from a normal fitted to a trailing
  window. Real equity returns have fatter tails and cluster their volatility.
  `p10` is not a worst case and must never be labelled one.
- **Drift from the trailing sample mean.** A sleeve that has run hot projects
  forward hot. This is the single most flattering assumption in the model.
- **Correlation is static.** Estimated once over the window. In a real
  drawdown correlations converge toward 1, so even the corrected band is
  optimistic exactly when it matters.
- **Sharpe at a 0% risk-free rate.** Inherited from the notebook, defensible
  at 2021 short rates and not at current ones. Published with the assumption
  labelled rather than quietly changed to a rate nobody chose.
- **No fees.** The sleeve this describes sits behind roughly 165 bps of annual
  management cost, which compounds against every path drawn and is not netted
  out of the index.

---

## Reviewed and not ported

Not every repository has something the daily pipeline needs. Recording the
rejects matters as much as the ports — otherwise they get re-evaluated
from scratch every time someone browses the account.

| Repository | Contains | Why not ported |
|---|---|---|
| [`DeepLearning`](https://github.com/MalikAI-786/DeepLearning) | Keras LSTM price predictor (closing vs Fear & Greed) | Needs TensorFlow, and an LSTM on ~500 daily observations overfits far more readily than it forecasts. The honest version is a research question, not a pipeline component. Revisit as a study, not a bucket |
| [`Natural_Language_Processing`](https://github.com/MalikAI-786/Natural_Language_Processing) | VADER sentiment, NewsAPI, tokenization, NER | **The strongest remaining candidate.** Maps directly onto the SPX model's `news` and `sentiment` buckets, which are specified in `SKILL.md` §2.3/2.5 but not implemented. Needs `nltk` + a NewsAPI key, so it is a deliberate dependency decision rather than a free win |
| [`Machine_Learning_Classification`](https://github.com/MalikAI-786/Machine_Learning_Classification) | `imbalanced-learn` ensembles on credit risk | No role in either market model. Its real value is as portfolio evidence for the audit/risk-governance narrative — a worked example of imbalanced-class evaluation |
| [`Time_Series`](https://github.com/MalikAI-786/Time_Series) | ARMA/ARIMA forecasting, linear regression | The GARCH half was ported. ARIMA on daily equity prices is a well-documented way to fit noise; the regression notebook's in/out-of-sample RMSE discipline is worth more than its model |
| [`AWS`](https://github.com/MalikAI-786/AWS) | Lex robo-advisor Lambda, unsupervised crypto clustering | Retirement-recommendation dialogue. Directly conflicts with `AGENTS.md` framing — the models here publish outlooks, they do not recommend allocations to anyone |
| [`PyViz`](https://github.com/MalikAI-786/PyViz) | Panel/hvPlot dashboards, SF housing | The dashboard is already static HTML on Pages. Panel needs a live Python server |
| [`Apple_Card`](https://github.com/MalikAI-786/Apple_Card), [`Python`](https://github.com/MalikAI-786/Python), [`Columbia-FinTech`](https://github.com/MalikAI-786/Columbia-FinTech) | Write-ups, PyBank/PyRamen exercises, program overview | No reusable analytics |
| `BlockChain*`, `Decentralized-Apps`, `music-on-the-blockchain` | Solidity and web3 coursework | Unrelated to either model |

---

## Testing

`tests/fixtures/prices.json` is synthetic and seeded — a common market factor
plus idiosyncratic noise per holding, sized to produce roughly the volatility
and correlation large-cap tech exhibits. It is not market data and nothing
derived from it may be committed as a scored week.

```bash
python3 scripts/portfolio_track.py --fixture tests/fixtures/prices.json --dry-run
python3 scripts/portfolio_track.py --fixture tests/fixtures/prices.json --example
```

`--dry-run` writes nothing. `--example` writes only
`dashboard/data/portfolio.example.json`, stamped `"example": true`, and never
touches `ledger/portfolio-signals.csv`.
