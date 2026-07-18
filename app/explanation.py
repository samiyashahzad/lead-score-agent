import json
import logging
from typing import Any, List

from app.schemas import Signals
from app.signal_extraction import call_llm

logger = logging.getLogger(__name__)

"""
generate explanation for the lead qualification process
call llm to generate explanation
"""


def generate_explanation(
    signals: Signals,
    score: int,
    priority: str,
    classification: str,
    confidence: float,
) -> tuple[List[str], str]:
    """Generate explanation for the lead qualification process."""

    system_prompt = """\
You are an expert lead-qualification explainer.

You will receive a set of already-decided lead signals and scoring results.
Your job is to produce two things:

1. "reasoning" — a JSON array of short sentences explaining WHY this lead
   received the score and classification it did.
   Rules for reasoning:
   - One sentence per signal.
   - For signals that have a real value (not "unknown", not false-by-default),
     write a clear sentence explaining what that signal contributed.
     Example tone:
       "Inquiry explicitly expresses interest in distributing the product."
       "High urgency language detected in the request."
       "Company operates in a directly relevant industry for this product."
   - For signals set to "unknown" or boolean signals that are false:
     state plainly that the information was not available. Do NOT escalate,
     do NOT recommend "human review," do NOT speculate.
     Example tone:
       "Geographic scope could not be determined from the inquiry."
       "No decision-maker language was detected."
       "Company scale information was not provided."

2. "next_action" — a single sentence recommending what to do with this lead.
   The tone and urgency of this sentence MUST match the priority bucket below.
   Do NOT contradict the priority — it is already a hard fact.

   Priority-to-tone mapping (mandatory):
   - "Hot"  → suggest immediate, urgent follow-up.
             Example: "Assign to sales representative immediately for direct outreach."
   - "Warm" → suggest near-term, scheduled follow-up.
             Example: "Schedule a follow-up call within the next few business days."
   - "Cold" → suggest low-priority, log-only handling.
             Example: "Log inquiry for future reference; no immediate action required."

   You may incorporate specific signals to make the sentence more useful
   (e.g. "Assign to distribution team immediately given explicit distributor intent"),
   but the urgency level must stay anchored to the priority.

Return ONLY valid JSON matching this exact schema — no prose, no markdown:
{
  "reasoning": ["string", "..."],
  "next_action": "string"
}"""

    user_message = f"""\
Lead scoring results (already decided — do not override):
- Score: {score}/100
- Priority: {priority}
- Classification: {classification}
- Confidence: {confidence}

Extracted signals:
- Distributor intent: {signals.distributor_intent}
- Commercial intent: {signals.commercial_intent}
- Decision maker: {signals.decision_maker}
- Urgency: {signals.urgency}
- Industry relevance: {signals.industry_relevance}
- Geographic scope: {signals.geographic_scope}
- Company scale: {signals.company_scale}"""

    max_attempts = 2

    for attempt in range(1, max_attempts + 1):
        logger.info("Explanation generation attempt %d/%d", attempt, max_attempts)
        raw = call_llm(system_prompt, user_message)

        result = _validate_explanation(raw)

        if result is not None:
            logger.info("Attempt %d: valid explanation generated.", attempt)
            return result

        if attempt < max_attempts:
            logger.warning("Attempt %d: explanation validation failed — retrying.", attempt)
            continue

        # Second attempt still failed — fall back using data already in memory
        logger.warning(
            "Attempt %d: explanation still failing — using priority-aware fallbacks.",
            attempt,
        )
        return (
            _fallback_reasoning(score, confidence),
            _fallback_next_action(priority),
        )

    # Defensive: unreachable, satisfies type checker
    return (
        _fallback_reasoning(score, confidence),
        _fallback_next_action(priority),
    )


# ── Validation ─────────────────────────────────────────────────────

def _validate_explanation(raw: str) -> tuple[List[str], str] | None:
    """Parse and validate LLM response into (reasoning, next_action).

    Returns the tuple if both fields are valid, None otherwise.
    The caller decides whether to retry or fall back.
    """
    parsed = _try_parse_json(raw)

    if parsed is None:
        return None

    reasoning = parsed.get("reasoning")
    next_action = parsed.get("next_action")

    # reasoning must be a non-empty list of non-empty strings
    if (
        not isinstance(reasoning, list)
        or len(reasoning) == 0
        or not all(isinstance(r, str) and r.strip() for r in reasoning)
    ):
        return None

    # next_action must be a non-empty string
    if not isinstance(next_action, str) or not next_action.strip():
        return None

    return reasoning, next_action


# ── Priority-aware fallbacks (no LLM needed) ──────────────────────

_NEXT_ACTION_BY_PRIORITY = {
    "Hot": "Assign to sales representative immediately for direct outreach.",
    "Warm": "Schedule a follow-up call within the next few business days.",
    "Cold": "Log inquiry for future reference; no immediate action required.",
}


def _fallback_next_action(priority: str) -> str:
    """Deterministic next_action from the priority bucket — no LLM."""
    return _NEXT_ACTION_BY_PRIORITY.get(
        priority,
        "Review lead based on the assigned score and priority.",
    )


def _fallback_reasoning(score: int, confidence: float) -> List[str]:
    """Honest generic reasoning from data already in memory — no invented detail."""
    resolved_count = round(confidence * 4)  # confidence = resolved_enums / 4
    return [
        (
            f"Automated explanation generation failed. "
            f"Lead scored {score}/100 based on "
            f"{resolved_count} of 4 categorical signals successfully extracted "
            f"(confidence: {confidence})."
        ),
    ]


# ── JSON parser ────────────────────────────────────────────────────

def _try_parse_json(raw: str) -> dict[str, Any] | None:
    """Try to parse raw LLM output as JSON."""
    stripped = raw.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        lines = [l for l in lines[1:] if not l.strip().startswith("```")]
        stripped = "\n".join(lines)
    try:
        data = json.loads(stripped)
        if isinstance(data, dict):
            return data
        return None
    except (json.JSONDecodeError, TypeError):
        return None

