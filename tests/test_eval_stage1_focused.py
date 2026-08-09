"""
Eval Stage 1 (Focused) -- Only the cases where the LLM still fails.

Runs just cases B, G, H to save API calls and avoid rate limits.
Use this to verify prompt fixes without burning through your full quota.

Run with:
    .venv\\Scripts\\python.exe -m pytest tests/test_eval_stage1_focused.py -v -s

Cases that already pass (A, C, D, F, I, J) are not included here.
Run the full test_eval_stage1_signals.py when you have fresh API quota.
"""

import json
import pathlib

import pytest

from app.signal_extraction import signal_extraction

# ── Load only the problem cases ────────────────────────────────────

_DATASET_PATH = pathlib.Path(__file__).parent / "eval_dataset_v1.json"

with open(_DATASET_PATH, encoding="utf-8") as f:
    _ALL_CASES = json.load(f)["cases"]

# Only the 3 cases the LLM still struggles with
_PROBLEM_IDS = {
    "B_clear_end_customer_warm",
    "G_urgent_end_customer_warm",
    "H_tentative_distributor_low_confidence",
}
_PROBLEM_CASES = [c for c in _ALL_CASES if c["id"] in _PROBLEM_IDS]

_SIGNAL_FIELDS = [
    "distributor_intent", "commercial_intent", "urgency",
    "industry_relevance", "geographic_scope", "company_scale", "decision_maker",
]


# ── Helper ─────────────────────────────────────────────────────────

def _print_comparison(case_id, actual_signals, expected_signals):
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
    print(f"\n  Accuracy: {len(_SIGNAL_FIELDS) - len(mismatches)}/{len(_SIGNAL_FIELDS)} ({accuracy:.0%})")
    if mismatches:
        print(f"  Mismatched: {', '.join(mismatches)}")
    print()


# ── Test ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "case",
    _PROBLEM_CASES,
    ids=[c["id"] for c in _PROBLEM_CASES],
)
class TestProblemCases:
    """Only the cases where the LLM still makes mistakes."""

    def _extract(self, case):
        actual = signal_extraction(case["input"]["inquiry"])
        _print_comparison(case["id"], actual, case["expected_signals"])
        return actual

    def test_distributor_intent(self, case):
        actual = self._extract(case)
        assert actual.distributor_intent == case["expected_signals"]["distributor_intent"]

    def test_commercial_intent(self, case):
        actual = self._extract(case)
        assert actual.commercial_intent == case["expected_signals"]["commercial_intent"]

    def test_urgency(self, case):
        actual = self._extract(case)
        assert actual.urgency == case["expected_signals"]["urgency"]

    def test_industry_relevance(self, case):
        actual = self._extract(case)
        assert actual.industry_relevance == case["expected_signals"]["industry_relevance"]

    def test_geographic_scope(self, case):
        actual = self._extract(case)
        assert actual.geographic_scope == case["expected_signals"]["geographic_scope"]

    def test_company_scale(self, case):
        actual = self._extract(case)
        assert actual.company_scale == case["expected_signals"]["company_scale"]

    def test_decision_maker(self, case):
        actual = self._extract(case)
        assert actual.decision_maker == case["expected_signals"]["decision_maker"]
