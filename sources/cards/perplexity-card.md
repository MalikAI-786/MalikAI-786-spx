# Model Card — Perplexity AI Peer

> **Format:** SR 11-7-style model card, per v5.0 audit memo Finding F-05.
> **Status (v5.0):** PLACEHOLDER. Adapter returns `NOT_WIRED_YET` until
> `MALIKAI_PERPLEXITY_LIVE=1` and `PERPLEXITY_API_KEY` are both set.

## 1. Identity

| Field                | Value                                                      |
| -------------------- | ---------------------------------------------------------- |
| Source slot          | Peer 3 of 3                                                |
| Vendor               | Perplexity AI                                              |
| Model family         | Sonar (online / retrieval-augmented)                       |
| Model version pinned | `sonar-large-online-2026-01`                               |
| Knowledge cutoff     | Rolling (online retrieval) + base LLM cutoff Jan 2026      |
| Vendor card          | https://docs.perplexity.ai/guides/model-cards              |
| Vendor usage policy  | https://www.perplexity.ai/hub/legal/usage-policy           |
| Adapter file         | `sources/perplexity_adapter.py`                            |
| API endpoint         | `https://api.perplexity.ai/chat/completions`               |
| Prompt template      | `sources/prompt_template.md` (v1.0)                        |
| Version date         | 2026-05-28                                                 |
| Card version         | 1.0                                                        |

## 2. Owner-as-validator note

Per the v5.0 audit memo F-05 interim governance posture, the system owner
(**Yasir Amalik**) acts as his own model validator until an independent
reviewer is engaged. This is a documented control weakness, not a
denial of the role. Owner-as-validator attestations:

- I have read Perplexity's published model documentation and usage
  policy as of the version date above.
- I have confirmed the pinned model version is in Perplexity's
  currently supported list.
- I have reviewed the response schema in `prompt_template.md` against
  what this model is known to be able to emit.
- I have noted Perplexity's status as a retrieval-augmented system and
  the implications enumerated in section 4 below.

## 3. Intended use

- **In scope:** Producing one structured, JSON-schema-conformant
  bias-assessment payload per US trading day for the SPX 0DTE
  educational research system, scoring 5 buckets (futures, macro, news,
  international, sentiment) on a -10..+10 scale plus a composite.
- **Role on the panel:** Perplexity is intentionally the
  retrieval-grounded peer. Codex and Gemini answer from their training
  corpora; Perplexity answers with live web retrieval. This is the
  whole reason it's slot 3.
- **Operating window:** Called once per trading day between approximately
  09:00 and 09:25 ET by the morning skill, with a 30-second timeout.
- **Consumer:** `agreement.py` aggregates this peer's response with the
  Codex and Gemini peers' responses into a single
  `confidence_adjustment` integer in `{-1, 0, +1}`.

## 4. Known limitations

- **Source-quality dependence.** Perplexity's answer is only as good as
  the sources it retrieves. Low-quality news sites, paywalled outlets
  it can't read, or stale cached articles all degrade output.
  Mitigation: the response schema REQUIRES non-empty `citations` for
  this peer (validator-enforced in v5.1+); a response with zero
  citations is treated as VALIDATION_FAILED -> abstain.
- **Latency.** Online retrieval is slower than pure LLM inference.
  Typical 5-15s response time; 30s timeout in adapter; if exceeded the
  adapter returns a non-OK status and `agreement.py` treats as
  abstention.
- **News-of-the-day overweighting.** Because Perplexity retrieves
  fresh headlines, it can swing harder on a single dramatic story than
  Codex or Gemini. This is the FEATURE we want from this peer, but it
  also means Perplexity is the most likely source of single-peer
  dissent. The agreement gate handles this by requiring 2 of 3
  disagreers before applying -1 (a lone Perplexity dissent never
  swings the dial alone).
- **JSON adherence.** Sonar models occasionally violate JSON mode.
  `_validate_response()` catches and abstains.
- **Source attribution accuracy.** Citation URLs are usually but not
  always the source actually used; this is a known industry issue with
  RAG systems.
- **Vendor outage risk.** Single point of failure if Perplexity API is
  down. Adapter returns a non-OK status; treated as abstention.

## 5. Out-of-scope use

- **Not investment advice.** Outputs are educational signals for
  self-study against a calibrated ledger. They MUST NOT be relayed to
  third parties as recommendations, redistributed, or used to solicit
  business.
- **Not real-time tick-by-tick.** One call per session, not intraday.
- **Not for non-SPX instruments** without re-baselining the prompt and
  re-running the agreement-index calibration.
- **Not for citation-laundering.** The fact that Perplexity returns
  citations does not make any downstream redistribution of those
  citations attributable to the cited outlets, nor does it confer
  research-publication status on the output.
- **Not for client-facing outputs** of any regulated activity.

## 6. Prompt template reference

The exact prompt sent live is the canonical text in
`sources/prompt_template.md` (v1.0). The adapter's inlined
`PROMPT_TEMPLATE` constant must match byte-for-byte; drift is a
change-control violation. Perplexity additionally receives the
`return_citations=True` request flag at the API layer.

## 7. Wiring posture (v5.0)

- Sentinel env var:  `MALIKAI_PERPLEXITY_LIVE`
- API key env var:   `PERPLEXITY_API_KEY`
- Live target version: `v5.3` (after Codex in v5.1 and Gemini in v5.2)
- Today's behavior: returns `{"status":"NOT_WIRED_YET", "source":"perplexity", ...}`

## 8. Change log

| Card version | Date       | Change                       | Validator     |
| ------------ | ---------- | ---------------------------- | ------------- |
| 1.0          | 2026-05-28 | Initial v5.0 placeholder card| Y. Amalik     |
