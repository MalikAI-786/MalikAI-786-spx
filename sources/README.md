# MalikAI-786 SPX v5.0 — AI Peer Cross-Check Sources

> **Status:** PLACEHOLDER WIRING (v5.0). All three sources currently return
> `NOT_WIRED_YET`. The morning skill is tolerant of that — it just treats
> them as abstentions until the sentinel env vars are flipped on.
>
> **Educational / non-advisory.** This system does not provide investment
> advice. Outputs are synthetic signals used only for self-study against a
> calibrated ledger.

---

## Why this directory exists

The v4.x system carried two **human peer** inputs — "Angelo" and "Omeir" —
that were polled informally each morning and used to nudge the composite
bias score. The v5.0 audit memo (Finding **F-05**, "Unvalidated human
peer inputs lack reproducibility, model cards, or version control") called
that pattern out as the single largest validation gap in the system.

To close F-05 we replaced the two human peers with **three independent AI
peers**, each governed under the same SR 11-7-style model-risk discipline
that the primary 5-bucket model is. The three peers are deliberately
chosen from different vendors with different training corpora, different
RLHF lineages, and different real-time-search behaviors, so that their
agreement is informative rather than three echoes of the same model.

| Slot | Vendor      | Adapter                  | Card                          |
| ---- | ----------- | ------------------------ | ----------------------------- |
| 1    | OpenAI      | `codex_adapter.py`       | `cards/codex-card.md`         |
| 2    | Google      | `gemini_adapter.py`      | `cards/gemini-card.md`        |
| 3    | Perplexity  | `perplexity_adapter.py`  | `cards/perplexity-card.md`    |

All three are called by the morning skill with the **same shared prompt
template** (`prompt_template.md`) so we are comparing apples to apples.

---

## What each adapter does

Each adapter exposes one importable function:

```python
def get_<vendor>_bias(date_iso: str, market_context: dict) -> dict: ...
```

When live, the returned dict conforms to the schema in
`prompt_template.md`:

```jsonc
{
  "status": "OK",
  "source": "codex" | "gemini" | "perplexity",
  "as_of": "2026-05-28T13:25:00Z",
  "buckets": {
    "futures":       {"score": -3, "rationale": "ES -0.4% overnight ..."},
    "macro":         {"score":  1, "rationale": "..."},
    "news":          {"score":  0, "rationale": "..."},
    "international": {"score": -2, "rationale": "..."},
    "sentiment":     {"score":  4, "rationale": "..."}
  },
  "composite": 0,
  "bias_label": "Neutral",
  "confidence": "Med",
  "citations": ["..."],
  "disclaimer": "Educational only. Not investment advice."
}
```

Until the sentinel env var for that adapter is set to `1`, the adapter
short-circuits and returns:

```jsonc
{ "status": "NOT_WIRED_YET", "source": "<vendor>",
  "note": "placeholder for v5.0 — wire to <vendor> via API" }
```

Sentinels:
- `MALIKAI_CODEX_LIVE=1`
- `MALIKAI_GEMINI_LIVE=1`
- `MALIKAI_PERPLEXITY_LIVE=1`

This means today, **with no API keys configured**, the morning skill is
still safe to run — it just sees three abstentions and applies no
confidence adjustment.

---

## How disagreement is computed

`agreement.py` exposes:

```python
def compute_agreement(primary_score: float,
                      source_responses: list[dict]) -> dict
```

Logic (see `agreement.py` for the canonical implementation):

1. Drop any source whose `status != "OK"` (abstain).
2. Among the remaining live sources, count those whose composite has the
   **opposite sign** from `primary_score` ("disagreers").
3. Decision table:

   | Live sources | Disagreers | `confidence_adjustment` |
   | ------------ | ---------- | ----------------------- |
   | 3            | 0          | **+1** (full consensus) |
   | 3            | 1          |  0                      |
   | 3            | 2 or 3     | **-1**                  |
   | 2            | 2          | **-1**                  |
   | 2            | 0 or 1     |  0                      |
   | 0 or 1       | any        |  0 (insufficient panel) |

4. `agreement_index` is `(live_agree - live_disagree) / live_total`,
   range `[-1.0, +1.0]`.
5. Zero-sign primary (`primary_score == 0`) is treated as Neutral; any
   non-zero AI source is counted as a "disagreer" only if it crosses +/-2
   (we don't penalize Neutral primary for a peer reporting +1).

The morning skill takes the `confidence_adjustment` and bumps the
calibration-overlay confidence one notch — Low to Very Low, Med to Low,
High to Med, or upward when full consensus.

---

## How to wire each one in (production checklist)

For each adapter:

1. Obtain an API key from the vendor and store it in the OS keychain
   (never commit). Surface it to the process via env var:
   - `OPENAI_API_KEY`
   - `GOOGLE_API_KEY`
   - `PERPLEXITY_API_KEY`
2. Flip the corresponding `MALIKAI_*_LIVE=1` sentinel.
3. Replace the body of the `# === WIRE HERE ===` block inside the
   adapter with the SDK call shown in the comments.
4. Confirm the returned JSON validates against `_validate_response()`.
5. Add a smoke-test run to `responses/` (one JSON per day per source,
   so each adapter's behavior is auditable post-hoc).
6. Update the model card's `version_date` and re-attest.

> Treat each vendor swap as a **change-controlled event** under F-05:
> open a ledger entry, re-run the last 10 days of backtests against the
> new responses, and only then promote to "live in morning skill."

---

## Audit trail back to F-05

The v5.0 audit memo's Finding **F-05** required:

- Documented model lineage for every non-primary signal source — cards
- Reproducible call interface — adapters with shared prompt template
- Versioned prompts — `prompt_template.md` is the single source of truth
- Per-source response logs — `responses/` directory
- Governance owner per source — each card lists owner-as-validator

Sign-off: this directory closes F-05 **structurally** for v5.0. Each
adapter remains in placeholder state until the corresponding sentinel
flips. The first live wiring is targeted for v5.1 (Codex), with Gemini
and Perplexity to follow on a staggered cadence so we can isolate the
effect of each addition on the calibration ledger.
