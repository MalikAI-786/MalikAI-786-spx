# Model Card — Codex (OpenAI) AI Peer

> **Format:** SR 11-7-style model card, per v5.0 audit memo Finding F-05.
> **Status (v5.0):** PLACEHOLDER. Adapter returns `NOT_WIRED_YET` until
> `MALIKAI_CODEX_LIVE=1` and `OPENAI_API_KEY` are both set.

## 1. Identity

| Field                | Value                                                 |
| -------------------- | ----------------------------------------------------- |
| Source slot          | Peer 1 of 3                                           |
| Vendor               | OpenAI                                                |
| Model family         | GPT-4-class (Codex lineage / Chat Completions)        |
| Model version pinned | `gpt-4o-2026-03`                                      |
| Knowledge cutoff     | March 2026 (per OpenAI's published cutoff)            |
| Vendor card          | https://openai.com/index/gpt-4o-system-card/          |
| Vendor usage policy  | https://openai.com/policies/usage-policies/           |
| Adapter file         | `sources/codex_adapter.py`                            |
| Prompt template      | `sources/prompt_template.md` (v1.0)                   |
| Version date         | 2026-05-28                                            |
| Card version         | 1.0                                                   |

## 2. Owner-as-validator note

Per the v5.0 audit memo F-05 interim governance posture, the system owner
(**Yasir Amalik**) acts as his own model validator until an independent
reviewer is engaged. This is a documented control weakness, not a
denial of the role. Owner-as-validator attestations:

- I have read OpenAI's published model card and usage policy as of the
  version date above.
- I have confirmed the pinned model version is in OpenAI's currently
  supported list.
- I have reviewed the response schema in `prompt_template.md` against
  what this model is known to be able to emit.
- I accept the limitations enumerated in section 4 below.

## 3. Intended use

- **In scope:** Producing one structured, JSON-schema-conformant
  bias-assessment payload per US trading day for the SPX 0DTE
  educational research system, scoring 5 buckets (futures, macro, news,
  international, sentiment) on a -10..+10 scale plus a composite.
- **Operating window:** Called once per trading day between approximately
  09:00 and 09:25 ET by the morning skill, with a 30-second timeout.
- **Consumer:** `agreement.py` aggregates this peer's response with the
  Gemini and Perplexity peers' responses into a single
  `confidence_adjustment` integer in `{-1, 0, +1}`.

## 4. Known limitations

- **No live retrieval (default).** GPT-4-class models have a training
  cutoff (March 2026). Same-day macro releases, headlines, and overnight
  futures behavior must be passed in via `market_context`; the model
  cannot fetch them itself unless function-calling tools are explicitly
  added in a later version.
- **JSON adherence is not 100%.** Even with `response_format={"type":
  "json_object"}`, occasional schema deviations occur (missing keys,
  out-of-range scores). The adapter's `_validate_response()` catches
  these and returns `VALIDATION_FAILED`, which `agreement.py` treats as
  an abstention.
- **Training-data bias toward US-equity bullish prior.** Internal
  back-testing in v4.x noted GPT-4-class models tilt mildly bullish on
  neutral days. The agreement gate uses sign + a Neutral band of |x|<=2
  to soften this; not eliminate it.
- **Determinism.** `temperature=0.2` reduces but does not eliminate
  run-to-run variance. Two calls minutes apart with identical context
  can produce composites that differ by +/- 1.
- **Vendor outage risk.** Single point of failure if OpenAI API is down.
  Adapter returns a non-OK status; `agreement.py` treats as abstention.

## 5. Out-of-scope use

- **Not investment advice.** Outputs are educational signals for
  self-study against a calibrated ledger. They MUST NOT be relayed to
  third parties as recommendations, redistributed, or used to solicit
  business.
- **Not real-time tick-by-tick.** One call per session, not intraday.
- **Not for non-SPX instruments** without re-baselining the prompt and
  re-running the agreement-index calibration.
- **Not for client-facing outputs** of any regulated activity.

## 6. Prompt template reference

The exact prompt sent live is the canonical text in
`sources/prompt_template.md` (v1.0). The adapter's inlined
`PROMPT_TEMPLATE` constant must match byte-for-byte; drift is a
change-control violation.

## 7. Wiring posture (v5.0)

- Sentinel env var:  `MALIKAI_CODEX_LIVE`
- API key env var:   `OPENAI_API_KEY`
- Live target version: `v5.1`
- Today's behavior: returns `{"status":"NOT_WIRED_YET", "source":"codex", ...}`

## 8. Change log

| Card version | Date       | Change                       | Validator     |
| ------------ | ---------- | ---------------------------- | ------------- |
| 1.0          | 2026-05-28 | Initial v5.0 placeholder card| Y. Amalik     |
