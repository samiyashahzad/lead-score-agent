"""
Jev question definitions for each signal field.

Instructions are pulled verbatim from the main system prompt in
app/signal_extraction.py so the comparison is fair — same rules,
different extraction engine.

To add a new signal to the Jev eval, define a new question config
here and add a corresponding test in test_jev_<signal>.py.
"""

# ─────────────────────────────────────────────────────────────────
# Urgency
# ─────────────────────────────────────────────────────────────────
# Source: app/signal_extraction.py  lines 214-222

URGENCY_QUESTION = {
    "type": "choice",
    "instructions": (
        "Classify the urgency expressed in the inquiry, based on how "
        "time-sensitive it is. "
        "IMPORTANT: If the inquiry contains NO time-related language at all, "
        "return 'unknown'. Do NOT default to 'medium' — 'medium' requires "
        "some evidence of timeline interest. Absence of urgency language = "
        "'unknown', not 'medium'."
    ),
    "criteria": {
        "high": (
            "Explicit deadline, ASAP language (e.g. 'as soon as possible', "
            "'by tomorrow', 'urgently'), or emergency need."
        ),
        "medium": "Interested with implied but unstated timeline.",
        "low": "Casual inquiry, exploring options, no time pressure.",
        "unknown": "Cannot determine urgency from the text.",
    },
}


# ─────────────────────────────────────────────────────────────────
# Registry — easy lookup by field name
# ─────────────────────────────────────────────────────────────────

SIGNAL_QUESTIONS: dict[str, dict] = {
    "urgency": URGENCY_QUESTION,
    # Add more signals here as needed, e.g.:
    # "industry_relevance": INDUSTRY_RELEVANCE_QUESTION,
    # "company_scale": COMPANY_SCALE_QUESTION,
}
