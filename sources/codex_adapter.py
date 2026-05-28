# =============================================================================
#  MalikAI-786 SPX v5.0  -  Codex (OpenAI) AI-Peer Adapter
# -----------------------------------------------------------------------------
#  SYNTHETIC / NOT WIRED / EDUCATIONAL ONLY
#
#  This module is a v5.0 PLACEHOLDER. It is safe to import and call today
#  with NO API key configured: it short-circuits and returns a
#  NOT_WIRED_YET status object.
#
#  Live wiring is gated behind the sentinel env var:
#      MALIKAI_CODEX_LIVE=1
#  ... AND a valid OPENAI_API_KEY in the environment.
#
#  Nothing in this file constitutes investment advice. The system as a
#  whole is an educational research project governed by the model-risk
#  controls described in the v5.0 audit memo (Finding F-05).
# =============================================================================

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

# ---- Identity --------------------------------------------------------------
SOURCE_NAME = "codex"
VENDOR = "OpenAI"
MODEL_VERSION_PINNED = "gpt-4o-2026-03"   # update via model card change ctrl
PROMPT_TEMPLATE_PATH = "sources/prompt_template.md"
LIVE_SENTINEL_ENV = "MALIKAI_CODEX_LIVE"
API_KEY_ENV = "OPENAI_API_KEY"

# ---- Required response schema ---------------------------------------------
_REQUIRED_BUCKETS = ("futures", "macro", "news", "international", "sentiment")
_REQUIRED_TOP_KEYS = (
    "status", "source", "as_of", "buckets", "composite",
    "bias_label", "confidence", "citations", "disclaimer",
)
_VALID_CONFIDENCE = ("Low", "Med", "High")
_VALID_BIAS_LABELS = (
    "Strong Bearish", "Bearish", "Lean Bearish",
    "Neutral",
    "Lean Bullish", "Bullish", "Strong Bullish",
)


def _placeholder_response() -> dict[str, Any]:
    """The canonical NOT_WIRED_YET payload returned until v5.1 wiring."""
    return {
        "status": "NOT_WIRED_YET",
        "source": SOURCE_NAME,
        "note": "placeholder for v5.0 - wire to OpenAI Codex/GPT-4-class via API",
    }


def _validate_response(payload: dict[str, Any]) -> tuple[bool, str]:
    """
    Lightweight schema validator for live responses.

    Returns (ok, error_message). On ok=True, error_message is "".
    Used by the adapter before returning live data, and also exposed for
    unit tests in v5.1+.
    """
    if not isinstance(payload, dict):
        return False, "payload is not a dict"
    for k in _REQUIRED_TOP_KEYS:
        if k not in payload:
            return False, f"missing top-level key: {k}"
    if payload.get("source") != SOURCE_NAME:
        return False, f"source mismatch: {payload.get('source')!r}"
    buckets = payload.get("buckets")
    if not isinstance(buckets, dict):
        return False, "buckets is not a dict"
    for b in _REQUIRED_BUCKETS:
        if b not in buckets:
            return False, f"missing bucket: {b}"
        score = buckets[b].get("score") if isinstance(buckets[b], dict) else None
        if not isinstance(score, (int, float)) or not (-10 <= score <= 10):
            return False, f"bucket {b} score out of range or non-numeric"
    comp = payload.get("composite")
    if not isinstance(comp, (int, float)) or not (-10 <= comp <= 10):
        return False, "composite out of range"
    if payload.get("confidence") not in _VALID_CONFIDENCE:
        return False, "invalid confidence label"
    if payload.get("bias_label") not in _VALID_BIAS_LABELS:
        return False, "invalid bias_label"
    return True, ""


# ---- Prompt template (the EXACT prompt sent when wired) -------------------
# The shared canonical text lives in prompt_template.md. We inline a copy
# here so the adapter is self-contained for reproducibility in the response
# log. Any divergence between this constant and prompt_template.md is a
# change-control violation - the loader script in v5.1 will diff them.
PROMPT_TEMPLATE = """\
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
"""


def get_codex_bias(date_iso: str, market_context: dict[str, Any]) -> dict[str, Any]:
    """
    Return Codex's (OpenAI) bias read for the given trading date.

    Parameters
    ----------
    date_iso : str
        ISO-8601 calendar date for the session, e.g. "2026-05-28".
    market_context : dict
        Pre-market context bundle assembled by the morning skill:
        overnight futures levels, scheduled macro releases, top headlines,
        FX prints, VIX level, etc. Passed verbatim into the prompt.

    Returns
    -------
    dict
        Live mode:  payload conforming to the schema in prompt_template.md.
        Placeholder mode (default in v5.0):
            {"status": "NOT_WIRED_YET", "source": "codex", "note": "..."}

    Notes
    -----
    Safe to call without an API key. The function only attempts a live
    API call if BOTH:
      * env var MALIKAI_CODEX_LIVE == "1"
      * env var OPENAI_API_KEY is non-empty
    Otherwise the placeholder is returned and no network call is made.
    """
    live = os.environ.get(LIVE_SENTINEL_ENV) == "1"
    has_key = bool(os.environ.get(API_KEY_ENV))
    if not (live and has_key):
        return _placeholder_response()

    # === WIRE HERE (v5.1) ==================================================
    # Production wiring example, NOT executed in v5.0:
    #
    #   from openai import OpenAI
    #   client = OpenAI()  # picks up OPENAI_API_KEY
    #   prompt = PROMPT_TEMPLATE.format(
    #       date_iso=date_iso,
    #       market_context_json=json.dumps(market_context, sort_keys=True),
    #   )
    #   resp = client.chat.completions.create(
    #       model=MODEL_VERSION_PINNED,
    #       messages=[
    #           {"role": "system",
    #            "content": "You are an independent AI peer reviewer. "
    #                       "Respond with strict JSON only."},
    #           {"role": "user", "content": prompt},
    #       ],
    #       response_format={"type": "json_object"},
    #       temperature=0.2,
    #       max_tokens=900,
    #       timeout=30,
    #   )
    #   raw = resp.choices[0].message.content
    #   payload = json.loads(raw)
    #   payload.setdefault("source", SOURCE_NAME)
    #   payload.setdefault("as_of", datetime.now(timezone.utc).isoformat())
    #   ok, err = _validate_response(payload)
    #   if not ok:
    #       return {"status": "VALIDATION_FAILED", "source": SOURCE_NAME,
    #               "error": err, "raw": raw[:2000]}
    #   return payload
    # =======================================================================

    # Defensive: if someone forces the sentinel ON before the wire-here
    # block is replaced, fail loud and visible rather than silently lying.
    return {
        "status": "WIRE_NOT_IMPLEMENTED",
        "source": SOURCE_NAME,
        "note": "MALIKAI_CODEX_LIVE=1 but adapter body still placeholder; "
                "implement WIRE HERE block before flipping the sentinel.",
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


__all__ = [
    "SOURCE_NAME",
    "VENDOR",
    "MODEL_VERSION_PINNED",
    "PROMPT_TEMPLATE",
    "get_codex_bias",
    "_validate_response",
]
