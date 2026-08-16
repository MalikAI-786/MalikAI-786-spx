# Test fixtures

## `prices.json`

**This is not market data.** It is a deterministic synthetic price series
(seeded PRNG) used to exercise `scripts/portfolio_track.py` and `analytics/`
offline, where no market-data host is reachable.

It exists because the bucket scorers, the composite, the append-only ledger
invariant, the risk panel and the Monte Carlo all need to be testable without
a network — and because a fixture is reproducible in a way a live feed is not.

### Why there is a market factor

Each holding is generated as `beta × market + idiosyncratic noise`, giving
~0.53 mean pairwise correlation and ~22% annualized portfolio volatility —
roughly what large-cap tech shows.

The first version of this fixture drew independent random walks. Under it,
`analytics/montecarlo.py`'s correlated draws and the original
`MCForecastTools` independent draws agreed to within 1%, so the fixture
would have validated an independent-draw bug as correct. With the market
factor, the same comparison shows the independent version understating the
decile band by 54%. **A fixture that cannot fail is not a test.**

Nothing derived from this file may be committed as a scored week. Runs against
a fixture must use `--dry-run` (writes nothing) or `--example` (writes only
`dashboard/data/portfolio.example.json`, which is stamped `"example": true`
and never touches `ledger/portfolio-signals.csv`).

Regenerate:

```bash
python3 - <<'EOF'
import json, random
rng = random.Random(786)
N = 260
mkt = [rng.gauss(0.0006, 0.011) for _ in range(N)]   # common market factor
spec = {  # ticker: (start price, beta to market, idiosyncratic vol)
    "AAPL": (190, 1.00, 0.009), "MSFT": (420, 0.95, 0.008),
    "NVDA": (120, 1.55, 0.017), "GOOGL": (175, 1.05, 0.010),
    "AMZN": (185, 1.10, 0.011), "META": (520, 1.15, 0.013),
    "AVGO": (165, 1.35, 0.014), "AMD":  (140, 1.60, 0.019),
    "XLK":  (235, 1.00, 0.002),
}
out = {}
for t, (px, b, iv) in spec.items():
    lv, s = px, []
    for i in range(N):
        lv *= (1 + b * mkt[i] + rng.gauss(0, iv)); s.append(round(lv, 2))
    out[t] = s
def walk(start, drift, vol):
    lv, s = start, []
    for _ in range(N):
        lv *= (1 + rng.gauss(drift, vol)); s.append(round(lv, 2))
    return s
out["^TNX"] = walk(42.0, 0.0, 0.006)      # yield x10 -> 4.20%
out["^VIX"] = walk(17.0, -0.0004, 0.045)
out["earnings_revision_breadth"] = 0.625  # scalar bucket input, not a series
json.dump(out, open("tests/fixtures/prices.json", "w"), indent=1)
EOF
```

Smoke test:

```bash
python3 scripts/portfolio_track.py --fixture tests/fixtures/prices.json \
        --week-ending 2026-08-14 --dry-run
python3 scripts/portfolio_track.py --fixture tests/fixtures/prices.json \
        --week-ending 2026-08-14 --example
```
