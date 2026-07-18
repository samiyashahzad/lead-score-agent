"""Lead scoring engine.

Converts extracted Signals into a numeric score, priority label,
lead classification, and confidence value.
"""

from .schemas import Signals


# ── Weight configuration ────────────────────────────────────────────
# Each weight represents the maximum points a signal can contribute.
# Total possible points = 100.
WEIGHTS = {
    "distributor_intent": 30,
    "commercial_intent": 25,
    "urgency": 15,
    "industry_relevance": 10,
    "geographic_scope": 10,
    "company_scale": 5,
    "decision_maker": 5,
}

# Ratio tables — each ratio × its weight must produce a clean int().
# Urgency (weight 15):  high→15, medium→10, low→5
_URGENCY_SCORES = {"high": 1.0, "medium": 0.67, "low": 0.34, "unknown": 0.0}
# Industry relevance (weight 10):  high→10, medium→6, low→3
_RELEVANCE_SCORES = {"high": 1.0, "medium": 0.6, "low": 0.3, "unknown": 0.0}
# Geographic scope (weight 10):  multi→10, regional→7, national→5, single→3
_GEO_SCORES = {
    "multi_country": 1.0,
    "regional": 0.7,
    "national": 0.5,
    "single_location": 0.3,
    "unknown": 0.0,
}
# Company scale (weight 5):  large→5, small→3
_SCALE_SCORES = {"large": 1.0, "small": 0.6, "unknown": 0.0}


# ── Priority thresholds ────────────────────────────────────────────
HOT_THRESHOLD = 80
WARM_THRESHOLD = 50


def _calculate_points(signals: Signals) -> int:
    """Return the total earned points (0-100) for the given signals."""
    earned = 0

    # --- Boolean signals -------------------------------------------------
    if signals.distributor_intent:
        earned += WEIGHTS["distributor_intent"]

    if signals.commercial_intent:
        earned += WEIGHTS["commercial_intent"]

    if signals.decision_maker:
        earned += WEIGHTS["decision_maker"]

    # --- Tiered / categorical signals ------------------------------------
    earned += int(WEIGHTS["urgency"] * _URGENCY_SCORES[signals.urgency])
    earned += int(WEIGHTS["industry_relevance"] * _RELEVANCE_SCORES[signals.industry_relevance])
    earned += int(WEIGHTS["geographic_scope"] * _GEO_SCORES[signals.geographic_scope])
    earned += int(WEIGHTS["company_scale"] * _SCALE_SCORES[signals.company_scale])

    return earned


def _classify(signals: Signals) -> str:
    """Classify the lead as 'Distributor' or 'End Customer'."""
    if signals.distributor_intent:
        return "Distributor"
    return "End Customer"


def _priority_label(score: int) -> str:
    """Map a 0-100 score to a priority bucket."""
    if score >= HOT_THRESHOLD:
        return "Hot"
    if score >= WARM_THRESHOLD:
        return "Warm"
    return "Cold"


# The 4 enum fields that can structurally fall back to "unknown".
_ENUM_FIELDS = ("urgency", "industry_relevance", "geographic_scope", "company_scale")


def _confidence(signals: Signals) -> float:
    """Compute a 0.0-1.0 confidence value.

    Only the 4 enum fields (urgency, industry_relevance,
    geographic_scope, company_scale) can fall back to "unknown".
    Booleans always resolve to True/False and therefore carry no
    extraction uncertainty — including them would artificially
    inflate confidence.

    confidence = (enum fields with a real value) / 4
    """
    resolved = sum(
        1 for field in _ENUM_FIELDS
        if getattr(signals, field) != "unknown"
    )
    return round(resolved / len(_ENUM_FIELDS), 2)


# ── Public API ──────────────────────────────────────────────────────

def score_lead(signals: Signals) -> tuple[int, str, str, float]:
    """Score a lead based on extracted signals.

    Parameters
    ----------
    signals : Signals
        The structured signals extracted from the lead inquiry.

    Returns
    -------
    tuple[int, str, str, float]
        score        – numeric score  (0-100)
        priority     – "Hot" | "Warm" | "Cold"
        classification – "Distributor" | "End Customer"
        confidence   – 0.0-1.0 indicating data completeness
    """
    earned = _calculate_points(signals)

    score = min(earned, 100)
    priority = _priority_label(score)
    classification = _classify(signals)
    confidence = _confidence(signals)

    return score, priority, classification, confidence
