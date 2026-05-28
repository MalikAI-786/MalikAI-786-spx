# Model Card — Gemini (Google) AI Peer

> **Format:** SR 11-7-style model card, per v5.0 audit memo Finding F-05.
> **Status (v5.0):** PLACEHOLDER. Adapter returns `NOT_WIRED_YET` until
> `MALIKAI_GEMINI_LIVE=1` and `GOOGLE_API_KEY` are both set.

## 1. Identity

| Field                | Value                                                          |
| -------------------- | -------------------------------------------------------------- |
| Source slot          | Peer 2 of 3                                                    |
| Vendor               | Google                                                         |
| Model family         | Gemini 2.5 Pro                                                 |
| Model version pinned | `gemini-2.5-pro-2026-02`                                       |
| Knowledge cutoff     | February 2026 (per Google's published cutoff)                  |
| Vendor card          | https://ai.google.dev/gemini-api/docs/models/gemini            |
| Vendor usage policy  | https://policies.google.com/terms/generative-ai/use-policy     |
| Adapter file         | `sources/gemini_adapter.py`                                    |
| Prompt template      | `sources/prompt_template.md` (v1.0)                            |
| Version date         | 2026-05-28                                                     |
| Card version         | 1.0                                                            |

## 2. Owner-as-validator note

Per the v5.0 audit memo F-05 interim governance posture, the system owner
(**Yasir Amalik**) acts as his own model validator until an independent
reviewer is engaged. This is a documented control weakness, not a
denial of the role. Owner-as-validator attestations:

- I have read Google's published Gemini model documentation and
  generative-AI use policy as of the version date above.
- I have confirmed the pinned model version is in Google's currently
  supported list.
- I have reviewed the response schema in `prompt_template.md` against
  what this model is known to be able to emit (Gemini's JSON mode is
  generally reliable when `response_mime_type="application/json"`).
- I accept the limitations enumerated in section 4 below.

## 3. Intended use

- **In scope:** Producing one structured, JSON-schema-conformant
  bias-assessment payload per US trading day for the SPX 0DTE
  educational research system, scoring 5 buckets (futures, macro, news,
  international, sentiment) on a -10..+10 scale plus a composite.
- **Operating window:** Called once per trading day between approximately
  09:00 and 09:25 ET by the morning skill, with a 30-second timeout.
- **Consumer:** `agreement.py` aggregates this peer's response with the
  Codex and Perplexity peers' responses into a single
  `confidence_adjustment` integer in `{-1, 0, +1}`.

## 4. Known limitations

- **No live retrieval (default).** Without explicit grounding tools,
  Gemini 2.5 Pro operates from its training corpus through the February
  2026 cutoff. Same-day macro releases, headlines, and overnight
  futures behavior must be passed in via `market_context`.
- **Grounding-tool option.** Gemini supports a `tools` parameter for
  Google Search grounding; v5.0 deliberately leaves this OFF so that
  Codex and Gemini remain comparable as pure-LLM peers, with Perplexity
  as the dedicated retrieval-augmented peer. Turning Search grounding
  on is a future change-control decision.
- **JSON adherence.** Gemini's JSON mode is strong but not perfect;
  `_validate_response()` enforces the schema and treats failures as
  abstentions.
- **Safety-filter false positives.** Gemini's safety filters can flag
  financial-language outputs unexpectedly. The adapter logs raw
  responses; a `BLOCK_REASON_*` payload is treated as a non-OK status.
- **Determinism.** `temperature=0.2` with same input produces small
  variance run-to-run (composite +/- 1 typical).
- **Vendor outage risk.** Single point of failure if Google API is down.
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

- Sentinel env var:  `MALIKAI_GEMINI_LIVE`
- API key env var:   `GOOGLE_API_KEY`
- Live target version: `v5.2` (after Codex live in v5.1)
- Today's behavior: returns `{"status":"NOT_WIRED_YET", "source":"gemini", ...}`

## 8. Change log

| Card version | Date       | Change                       | Validator     |
| ------------ | ---------- | ---------------------------- | ------------- |
| 1.0          | 2026-05-28 | Initial v5.0 placeholder card| Y. Amalik     |
