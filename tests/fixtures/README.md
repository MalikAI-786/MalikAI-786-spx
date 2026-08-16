# Test fixtures

## `prices.json`

**This is not market data.** It is a deterministic synthetic price series
(seeded PRNG, geometric random walk) used to exercise
`scripts/portfolio_track.py` offline, where no market-data host is reachable.

It exists because the bucket scorers, the composite, the append-only ledger
invariant, and the projection all need to be testable without a network — and
because a fixture is reproducible in a way a live feed is not.

Nothing derived from this file may be committed as a scored week. Runs against
a fixture must use `--dry-run` (writes nothing) or `--example` (writes only
`dashboard/data/portfolio.example.json`, which is stamped `"example": true`
and never touches `ledger/portfolio-signals.csv`).

Regenerate:

```bash
python3 - <<'PY'
import json, random
rng = random.Random(786)
def series(start, drift, vol, n=260):
    lv, s = start, []
    for _ in range(n):
        lv *= (1 + rng.gauss(drift, vol)); s.append(round(lv, 2))
    return s
out = {}
for t, px, dr in [("AAPL",190,.0006),("MSFT",420,.0007),("NVDA",120,.0015),
                  ("GOOGL",175,.0005),("AMZN",185,.0006),("META",520,.0008),
                  ("AVGO",165,.0011),("AMD",140,.0004),("XLK",235,.0006)]:
    out[t] = series(px, dr, .015)
out["^TNX"] = series(42.0, .0000, .006)   # yield x10 -> 4.20%
out["^VIX"] = series(17.0, -.0004, .045)
out["earnings_revision_breadth"] = 0.625   # scalar bucket input, not a series
json.dump(out, open("tests/fixtures/prices.json", "w"), indent=1)
PY
```

Smoke test:

```bash
python3 scripts/portfolio_track.py --fixture tests/fixtures/prices.json \
        --week-ending 2026-08-14 --dry-run
python3 scripts/portfolio_track.py --fixture tests/fixtures/prices.json \
        --week-ending 2026-08-14 --example
```
