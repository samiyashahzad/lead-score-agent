"""
Eval Stage 2 — Scoring Math Correctness

Takes expected_signals from the eval dataset, feeds them directly into
score_lead(), and checks that the rule engine produces the correct
score, priority, classification, and confidence.

No LLM calls. No network. Pure deterministic logic.
Skips cases where expected_signals is null (e.g. validation-error cases).

Run with:
    .venv\Scripts\python.exe -m pytest tests/test_eval_stage2_scoring.py -v -s

    -v  = show each test name
    -s  = show print output (so you can see the math)
"""

import json
import pathlib

import pytest

from app.schemas import Signals
from app.scoring import score_lead, WEIGHTS, _URGENCY_SCORES, _RELEVANCE_SCORES, _GEO_SCORES, _SCALE_SCORES

# ── Load eval dataset ──────────────────────────────────────────────

_DATASET_PATH = pathlib.Path(__file__).parent / "eval_dataset_v1.json"

with open(_DATASET_PATH, encoding="utf-8") as f:
    _ALL_CASES = json.load(f)["cases"]

# Filter out cases that have no expected_signals (like validation-error cases)
_SCORING_CASES = [c for c in _ALL_CASES if c["expected_signals"] is not None]


# ── Helper: show the math breakdown ────────────────────────────────

def _print_math_breakdown(case_id, signals, score, priority, classification, confidence, case):
    """Print a human-readable breakdown of how the score was calculated."""
    print(f"\n{'='*60}")
    print(f"  CASE: {case_id}")
    print(f"{'='*60}")

    # Show each signal's contribution
    print(f"\n  Signal Breakdown:")
    print(f"  {'Signal':<25} {'Value':<18} {'Weight':>6} {'Ratio':>6} {'Points':>7}")
    print(f"  {'-'*62}")

    total = 0

    # Boolean signals
    for field in ["distributor_intent", "commercial_intent", "decision_maker"]:
        val = getattr(signals, field)
        pts = WEIGHTS[field] if val else 0
        total += pts
        print(f"  {field:<25} {str(val):<18} {WEIGHTS[field]:>6} {'1.0' if val else '0.0':>6} {pts:>7}")

    # Tiered signals
    tiered = [
        ("urgency",            signals.urgency,            _URGENCY_SCORES),
        ("industry_relevance", signals.industry_relevance, _RELEVANCE_SCORES),
        ("geographic_scope",   signals.geographic_scope,   _GEO_SCORES),
        ("company_scale",      signals.company_scale,      _SCALE_SCORES),
    ]
    for field, val, lookup in tiered:
        ratio = lookup[val]
        pts = int(WEIGHTS[field] * ratio)
        total += pts
        print(f"  {field:<25} {val:<18} {WEIGHTS[field]:>6} {ratio:>6} {pts:>7}")

    print(f"  {'-'*62}")
    print(f"  {'TOTAL':<25} {'':<18} {'':<6} {'':<6} {total:>7}")

    # Show the final results vs expected
    print(f"\n  Results vs Expected:")
    print(f"  {'Field':<20} {'Got':<15} {'Expected':<15} {'Match'}")
    print(f"  {'-'*55}")

    checks = [
        ("score",          score,          case["expected_score"]),
        ("priority",       priority,       case["expected_priority"]),
        ("classification", classification, case["expected_classification"]),
        ("confidence",     confidence,     case["expected_confidence"]),
    ]
    for field, got, expected in checks:
        match = "PASS" if got == expected else "FAIL <<<"
        print(f"  {field:<20} {str(got):<15} {str(expected):<15} {match}")

    print()


# ── Parametrized test ──────────────────────────────────────────────

@pytest.mark.parametrize(
    "case",
    _SCORING_CASES,
    ids=[c["id"] for c in _SCORING_CASES],
)
class TestScoringMath:
    """Given the expected signals, does the rule engine produce the right outputs?"""

    def _run(self, case):
        """Build Signals from expected values and run through score_lead."""
        signals = Signals(**case["expected_signals"])
        score, priority, classification, confidence = score_lead(signals)

        # Print the full breakdown so you can see exactly what happened
        _print_math_breakdown(case["id"], signals, score, priority, classification, confidence, case)

        return score, priority, classification, confidence

    def test_score(self, case):
        score, _, _, _ = self._run(case)
        assert score == case["expected_score"], (
            f"[{case['id']}] score: got {score}, expected {case['expected_score']}"
        )

    def test_priority(self, case):
        _, priority, _, _ = self._run(case)
        assert priority == case["expected_priority"], (
            f"[{case['id']}] priority: got {priority}, expected {case['expected_priority']}"
        )

    def test_classification(self, case):
        _, _, classification, _ = self._run(case)
        assert classification == case["expected_classification"], (
            f"[{case['id']}] classification: got {classification}, expected {case['expected_classification']}"
        )

    def test_confidence(self, case):
        _, _, _, confidence = self._run(case)
        assert confidence == pytest.approx(case["expected_confidence"], abs=0.01), (
            f"[{case['id']}] confidence: got {confidence}, expected {case['expected_confidence']}"
        )
