# =============================================================================
#  MalikAI-786 SPX v5.0  -  AI-Peer Agreement Index
# -----------------------------------------------------------------------------
#  EDUCATIONAL / NON-ADVISORY
#
#  Pure-Python module. Computes how much the three AI peers
#  (Codex, Gemini, Perplexity) agree with the primary 5-bucket model's
#  composite bias, and how that agreement should adjust the calibration-
#  overlay confidence by exactly one notch.
#
#  Key design decision (see CRITICAL DESIGN NOTE below):
#  -----------------------------------------------------------------
#  NOT_WIRED_YET responses are treated as ABSTENTIONS, not as votes.
#  A panel of 0 or 1 live source NEVER moves the confidence dial in
#  either direction. This guarantees that the v5.0 placeholder state
#  is a true no-op on the primary model, satisfying the audit memo
#  F-05 requirement that the peer layer be additive-only.
# =============================================================================

from __future__ import annotations

from typing import Any, Iterable

_NEUTRAL_BAND = 2.0  # |score| <= 2 is "Neutral" for disagreement purposes


def _sign(x: float) -> int:
    """Return -1 / 0 / +1 according to the sign of x (Neutral if |x| <= NEUTRAL_BAND)."""
    if x > _NEUTRAL_BAND:
        return 1
    if x < -_NEUTRAL_BAND:
        return -1
    return 0


def _is_live(resp: dict[str, Any]) -> bool:
    """A response counts as 'live' only if status == 'OK' and composite is numeric."""
    if not isinstance(resp, dict):
        return False
    if resp.get("status") != "OK":
        return False
    comp = resp.get("composite")
    return isinstance(comp, (int, float))


def compute_agreement(
    primary_score: float,
    source_responses: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """
    Compute the AI-peer agreement index and confidence adjustment.

    Parameters
    ----------
    primary_score : float
        The composite -10..+10 score from the primary 5-bucket model.
    source_responses : iterable of dict
        Iterable of adapter responses (from codex_adapter.get_codex_bias,
        gemini_adapter.get_gemini_bias, perplexity_adapter.get_perplexity_bias,
        or any future peer). Each is either a NOT_WIRED_YET / error dict or a
        valid OK payload with a numeric "composite".

    Returns
    -------
    dict with keys:
        "agreement_index"       float in [-1.0, +1.0]
        "disagreers"            list[str]   - source names voting opposite
        "consensus_direction"   str         - "Bullish" / "Bearish" / "Neutral"
                                              / "Mixed" / "Insufficient"
        "confidence_adjustment" int         - one of {-1, 0, +1}

    Logic
    -----
    1. Drop any response whose status != "OK" (abstain).
    2. Compute sign(primary) and sign(composite) for each live response,
       using NEUTRAL_BAND so small |score| values count as Neutral.
    3. Tally agreers (same sign as primary) and disagreers (opposite sign).
       Neutral-vs-non-Neutral pairings count as neither.
    4. Apply the decision table from sources/README.md:

       live=3, disagree=0           -> +1 (full consensus boost)
       live=3, disagree>=2          -> -1 (majority disagreement)
       live=2, disagree=2           -> -1 (both live peers disagree)
       live<=1                      ->  0 (insufficient panel - NO-OP)
       all other cases              ->  0 (mixed signal, no adjustment)

    5. agreement_index = (agreers - disagreers) / live_total, or 0.0 when
       live_total == 0.

    CRITICAL DESIGN NOTE
    --------------------
    A panel of 0 or 1 live source ALWAYS returns confidence_adjustment=0.
    This is the single most important rule in this module. Because v5.0
    ships with all three adapters in NOT_WIRED_YET state, this rule
    guarantees that v5.0 is operationally identical to v4.x on the
    confidence dial - the peer layer is structurally present (closing
    audit F-05) but behaviorally inert until live wiring lands. Without
    this rule, a single noisy live source could swing the confidence
    overlay; that would violate the "additive-only" invariant the
    calibration ledger relies on.
    """
    responses = list(source_responses)
    live = [r for r in responses if _is_live(r)]
    live_total = len(live)

    primary_sign = _sign(float(primary_score))

    agreers: list[str] = []
    disagreers: list[str] = []
    neutrals: list[str] = []

    for r in live:
        name = str(r.get("source", "unknown"))
        s = _sign(float(r["composite"]))
        if primary_sign == 0 or s == 0:
            # Either primary or peer is Neutral - count as neither.
            neutrals.append(name)
        elif s == primary_sign:
            agreers.append(name)
        else:
            disagreers.append(name)

    # ---- Confidence adjustment (the gate) ---------------------------------
    if live_total <= 1:
        confidence_adjustment = 0  # insufficient panel - NO-OP, always.
    elif live_total == 3 and len(disagreers) == 0 and len(agreers) >= 2:
        # Full consensus (allows one Neutral peer alongside two agreers).
        confidence_adjustment = +1
    elif live_total == 3 and len(disagreers) >= 2:
        confidence_adjustment = -1
    elif live_total == 2 and len(disagreers) == 2:
        confidence_adjustment = -1
    else:
        confidence_adjustment = 0

    # ---- Agreement index --------------------------------------------------
    if live_total == 0:
        agreement_index = 0.0
    else:
        agreement_index = (len(agreers) - len(disagreers)) / live_total

    # ---- Consensus direction label ---------------------------------------
    if live_total == 0:
        consensus_direction = "Insufficient"
    else:
        live_signs = [_sign(float(r["composite"])) for r in live]
        pos = sum(1 for s in live_signs if s > 0)
        neg = sum(1 for s in live_signs if s < 0)
        if pos >= 2 and neg == 0:
            consensus_direction = "Bullish"
        elif neg >= 2 and pos == 0:
            consensus_direction = "Bearish"
        elif pos == 0 and neg == 0:
            consensus_direction = "Neutral"
        else:
            consensus_direction = "Mixed"

    return {
        "agreement_index": round(agreement_index, 3),
        "disagreers": disagreers,
        "consensus_direction": consensus_direction,
        "confidence_adjustment": confidence_adjustment,
        # Extra diagnostics - not required by spec but useful for the ledger:
        "_diag": {
            "primary_sign": primary_sign,
            "live_total": live_total,
            "agreers": agreers,
            "neutrals": neutrals,
            "abstained": [
                str(r.get("source", "unknown"))
                for r in responses if not _is_live(r)
            ],
        },
    }


__all__ = ["compute_agreement"]
