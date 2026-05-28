# MalikAI-786 SPX v5.0 — Shared AI-Peer Prompt Template

> **This is the single source of truth** for the prompt sent to every
> AI peer (Codex, Gemini, Perplexity). Each adapter inlines a copy of this
> text as its `PROMPT_TEMPLATE` constant for self-describing response
> logs. A v5.1 loader script will refuse to start if any adapter's inlined
> copy drifts from this file.
>
> **Version:** 1.0 (v5.0 ship)
> **Last modified:** 2026-05-28
> **Owner / validator:** Yasir Amalik (system owner, acting as own validator
> under the audit memo F-05 interim governance posture)

---

## Why one shared prompt

Three vendors with three training corpora are only an informative peer
panel if they are answering **the same question with the same framing**.
If we let each adapter drift its own prompt, the disagreement signal is
contaminated by prompt variance instead of model variance.

So: one prompt. One schema. Any change ships as a new version of this
file, gets a ledger entry, and triggers a re-baseline of the agreement
index against the last 10 sessions.

---

## The prompt (verbatim, used by all three adapters)

```
You are an independent AI peer reviewer for the MalikAI-786 SPX 0DTE
research system. This is an EDUCATIONAL exercise. Nothing you output is
investment advice.

For the given trading date and pre-market context, produce a structured
bias assessment for the S&P 500 cash index open, scoring each of five
buckets on an integer scale from -10 (strong bearish) to +10 (strong
bullish), and a composite on the same scale.

Buckets:
  1. futures      - overnight ES/NQ behavior, gap risk, key levels
  2. macro        - rates, USD, oil, scheduled data releases today
  3. news         - corporate / political / geopolitical headlines
  4. international - Asia + Europe sessions, FX, sovereign moves
  5. sentiment    - vol regime (VIX), put/call, breadth, positioning

Respond with STRICT JSON ONLY conforming to this schema:

{
  "status": "OK",
  "source": "<one of: codex | gemini | perplexity>",
  "as_of": "<RFC3339 timestamp UTC>",
  "buckets": {
    "futures":       {"score": <int -10..10>, "rationale": "<<=160 chars>"},
    "macro":         {"score": <int -10..10>, "rationale": "<<=160 chars>"},
    "news":          {"score": <int -10..10>, "rationale": "<<=160 chars>"},
    "international": {"score": <int -10..10>, "rationale": "<<=160 chars>"},
    "sentiment":     {"score": <int -10..10>, "rationale": "<<=160 chars>"}
  },
  "composite": <int -10..10>,
  "bias_label": "<Strong Bearish|Bearish|Lean Bearish|Neutral|Lean Bullish|Bullish|Strong Bullish>",
  "confidence": "<Low|Med|High>",
  "citations": ["<url or source descriptor>", "..."],
  "disclaimer": "Educational only. Not investment advice."
}

Trading date: {date_iso}
Market context (JSON): {market_context_json}
```

---

## JSON response schema (formal)

| Field                  | Type                  | Constraints                                                                                  |
| ---------------------- | --------------------- | -------------------------------------------------------------------------------------------- |
| `status`               | string                | Always `"OK"` on success                                                                     |
| `source`               | string                | Exactly one of `codex`, `gemini`, `perplexity`                                               |
| `as_of`                | string                | RFC3339 UTC timestamp                                                                        |
| `buckets`              | object                | Must contain all 5 keys: futures, macro, news, international, sentiment                      |
| `buckets.<b>.score`    | integer               | -10 .. +10 inclusive                                                                         |
| `buckets.<b>.rationale`| string                | <= 160 characters; plain text, no markdown                                                   |
| `composite`            | integer               | -10 .. +10 inclusive                                                                         |
| `bias_label`           | string (enum)         | One of: Strong Bearish, Bearish, Lean Bearish, Neutral, Lean Bullish, Bullish, Strong Bullish|
| `confidence`           | string (enum)         | One of: Low, Med, High                                                                       |
| `citations`            | array of string       | May be empty for pure-LLM peers; required non-empty for Perplexity                           |
| `disclaimer`           | string                | Must contain "Not investment advice" (case-insensitive)                                      |

### Suggested composite-to-label mapping

| Composite range | Bias label       |
| --------------- | ---------------- |
| -10 .. -7       | Strong Bearish   |
| -6 .. -4        | Bearish          |
| -3 .. -2        | Lean Bearish     |
| -1 .. +1        | Neutral          |
| +2 .. +3        | Lean Bullish     |
| +4 .. +6        | Bullish          |
| +7 .. +10       | Strong Bullish   |

This mapping is suggestive; if a model returns a label that disagrees
with its own composite, we log the inconsistency in `responses/` but do
not reject the response (vendors are allowed their own internal
calibration).

---

## What the morning skill passes in

`{date_iso}` — e.g. `"2026-05-28"`

`{market_context_json}` — a JSON object assembled by the morning skill,
typical keys:

```jsonc
{
  "overnight": {
    "es_pct": -0.42, "nq_pct": -0.51, "vix": 14.2,
    "key_levels": {"es_pivot": 5310, "es_overnight_high": 5325, "es_overnight_low": 5292}
  },
  "macro_today": [
    {"time_et": "08:30", "event": "Initial Jobless Claims", "consensus": 215000}
  ],
  "news_top": [
    {"headline": "...", "source": "Reuters", "ts_utc": "..."}
  ],
  "intl": {"hsi_pct": -0.8, "stoxx50_pct": 0.1, "dxy": 104.5, "wti": 78.4},
  "sentiment": {"put_call": 0.92, "spx_above_50dma": true, "advancers_pct_yday": 58}
}
```

---

## Non-advice / educational framing

Every prompt explicitly tells the model:

> *"This is an EDUCATIONAL exercise. Nothing you output is investment advice."*

and the response schema requires a `disclaimer` field whose contents are
preserved in the response log. This is a deliberate redundancy — both
the prompt and the response carry the educational framing, so that any
downstream consumer of the logs (auditor, future-Yasir, regulator) sees
the non-advice framing without needing context.

---

## Change control

| Version | Date       | Change                          | Validator   |
| ------- | ---------- | ------------------------------- | ----------- |
| 1.0     | 2026-05-28 | Initial v5.0 ship               | Y. Amalik   |

Any edit to the prompt body, schema, or mapping table requires:
1. Bump the version, add a row above.
2. Update `PROMPT_TEMPLATE` constant in all three adapters (they must
   match byte-for-byte aside from f-string interpolation markers).
3. Re-baseline the agreement index against the last 10 trading days of
   logged `responses/` (once we have 10 days of logs to baseline against).
4. Ledger entry under audit F-05 referencing the diff.
