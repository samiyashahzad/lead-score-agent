"""
Eval Stage 1 -- Signal Extraction Accuracy

Sends each case's inquiry text to the real LLM (signal_extraction),
then compares every extracted signal field against expected_signals.

This CALLS THE LLM -- requires GROQ_API_KEY in .env.

Run with:
    .venv\\Scripts\\python.exe -m pytest tests/test_eval_stage1_signals.py -v -s
"""

import json
import pathlib

import pytest

from app.signal_extraction import signal_extraction  # the function that calls the LLM

# ── Load eval dataset ──────────────────────────────────────────────

_DATASET_PATH = pathlib.Path(__file__).parent / "eval_dataset_v1.json"

with open(_DATASET_PATH, encoding="utf-8") as f:
    _ALL_CASES = json.load(f)["cases"]

# Only cases that have expected_signals (skip Case E -- validation error)
_SIGNAL_CASES = [c for c in _ALL_CASES if c["expected_signals"] is not None]

# The 7 signal fields we're checking
_SIGNAL_FIELDS = [
    "distributor_intent",
    "commercial_intent",
    "urgency",
    "industry_relevance",
    "geographic_scope",
    "company_scale",
    "decision_maker",
]


# ── Helper: print side-by-side comparison ──────────────────────────

def _print_signal_comparison(case_id, actual_signals, expected_signals):
    """Print what the LLM returned vs what we expected, field by field."""
    print(f"\n{'='*65}")
    print(f"  CASE: {case_id}")
    print(f"{'='*65}")
    print(f"\n  {'Signal':<25} {'LLM returned':<18} {'Expected':<18} {'Match'}")
    print(f"  {'-'*65}")

    mismatches = []
    for field in _SIGNAL_FIELDS:
        got = getattr(actual_signals, field)
        exp = expected_signals[field]
        match = "PASS" if got == exp else "FAIL <<<"
        if got != exp:
            mismatches.append(field)
        print(f"  {field:<25} {str(got):<18} {str(exp):<18} {match}")

    accuracy = (len(_SIGNAL_FIELDS) - len(mismatches)) / len(_SIGNAL_FIELDS)
    print(f"\n  Accuracy: {len(_SIGNAL_FIELDS) - len(mismatches)}/{len(_SIGNAL_FIELDS)} fields correct ({accuracy:.0%})")
    if mismatches:
        print(f"  Mismatched fields: {', '.join(mismatches)}")
    print()


# ── Parametrized test ──────────────────────────────────────────────

@pytest.mark.parametrize(
    "case",
    _SIGNAL_CASES,
    ids=[c["id"] for c in _SIGNAL_CASES],
)
class TestSignalExtraction:
    """Does the LLM extract the correct signals from the inquiry text?"""

    def _extract(self, case):
        """Call the real LLM with the inquiry text and return the Signals object."""
        inquiry = case["input"]["inquiry"]
        actual_signals = signal_extraction(inquiry)

        # Print the comparison so you can see what happened
        _print_signal_comparison(case["id"], actual_signals, case["expected_signals"])

        return actual_signals

    # ── One test per signal field ──────────────────────────────────

    def test_distributor_intent(self, case):
        actual = self._extract(case)
        assert actual.distributor_intent == case["expected_signals"]["distributor_intent"], (
            f"[{case['id']}] distributor_intent: LLM returned {actual.distributor_intent}, "
            f"expected {case['expected_signals']['distributor_intent']}"
        )

    def test_commercial_intent(self, case):
        actual = self._extract(case)
        assert actual.commercial_intent == case["expected_signals"]["commercial_intent"], (
            f"[{case['id']}] commercial_intent: LLM returned {actual.commercial_intent}, "
            f"expected {case['expected_signals']['commercial_intent']}"
        )

    def test_urgency(self, case):
        actual = self._extract(case)
        assert actual.urgency == case["expected_signals"]["urgency"], (
            f"[{case['id']}] urgency: LLM returned {actual.urgency}, "
            f"expected {case['expected_signals']['urgency']}"
        )

    def test_industry_relevance(self, case):
        actual = self._extract(case)
        assert actual.industry_relevance == case["expected_signals"]["industry_relevance"], (
            f"[{case['id']}] industry_relevance: LLM returned {actual.industry_relevance}, "
            f"expected {case['expected_signals']['industry_relevance']}"
        )

    def test_geographic_scope(self, case):
        actual = self._extract(case)
        assert actual.geographic_scope == case["expected_signals"]["geographic_scope"], (
            f"[{case['id']}] geographic_scope: LLM returned {actual.geographic_scope}, "
            f"expected {case['expected_signals']['geographic_scope']}"
        )

    def test_company_scale(self, case):
        actual = self._extract(case)
        assert actual.company_scale == case["expected_signals"]["company_scale"], (
            f"[{case['id']}] company_scale: LLM returned {actual.company_scale}, "
            f"expected {case['expected_signals']['company_scale']}"
        )

    def test_decision_maker(self, case):
        actual = self._extract(case)
        assert actual.decision_maker == case["expected_signals"]["decision_maker"], (
            f"[{case['id']}] decision_maker: LLM returned {actual.decision_maker}, "
            f"expected {case['expected_signals']['decision_maker']}"
        )
