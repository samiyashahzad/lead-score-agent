"""
Eval Stage 3 -- End-to-End Pipeline Test

Sends the full lead payload as an HTTP POST to /qualify (via TestClient),
then compares the final response to expected values.

Also tests Case E (missing required field) -- expects HTTP 422.

This CALLS THE LLM -- requires GROQ_API_KEY in .env.

Run with:
    .venv\\Scripts\\python.exe -m pytest tests/test_eval_stage3_e2e.py -v -s
"""

import json
import pathlib

import pytest
from fastapi.testclient import TestClient

from app.api import app

client = TestClient(app)

# ── Load eval dataset ──────────────────────────────────────────────

_DATASET_PATH = pathlib.Path(__file__).parent / "eval_dataset_v1.json"

with open(_DATASET_PATH, encoding="utf-8") as f:
    _ALL_CASES = json.load(f)["cases"]

# Cases that go through the full pipeline (have expected_signals)
_PIPELINE_CASES = [c for c in _ALL_CASES if c["expected_signals"] is not None]

# Cases that should fail validation (e.g. missing required field)
_VALIDATION_CASES = [c for c in _ALL_CASES if c.get("expected_http_status") is not None]


# ── Helper: print end-to-end comparison ────────────────────────────

def _print_e2e_comparison(case_id, actual, case):
    """Print what the full pipeline returned vs what we expected."""
    print(f"\n{'='*65}")
    print(f"  CASE: {case_id}")
    print(f"{'='*65}")

    print(f"\n  {'Field':<20} {'API returned':<18} {'Expected':<18} {'Match'}")
    print(f"  {'-'*60}")

    checks = [
        ("score",          actual.get("score"),          case["expected_score"]),
        ("priority",       actual.get("priority"),       case["expected_priority"]),
        ("classification", actual.get("classification"), case["expected_classification"]),
        ("confidence",     actual.get("confidence"),     case["expected_confidence"]),
    ]

    for field, got, expected in checks:
        # For confidence, allow small floating point difference
        if field == "confidence" and got is not None and expected is not None:
            match = "PASS" if abs(got - expected) <= 0.01 else "FAIL <<<"
        else:
            match = "PASS" if got == expected else "FAIL <<<"
        print(f"  {field:<20} {str(got):<18} {str(expected):<18} {match}")

    # Also show reasoning and next_action (informational, not asserted)
    print(f"\n  Reasoning returned by API:")
    for i, r in enumerate(actual.get("reasoning", []), 1):
        print(f"    {i}. {r}")
    print(f"\n  Next action: {actual.get('next_action', 'N/A')}")
    print()


# ── Parametrized test: full pipeline ───────────────────────────────

@pytest.mark.parametrize(
    "case",
    _PIPELINE_CASES,
    ids=[c["id"] for c in _PIPELINE_CASES],
)
class TestEndToEnd:
    """Full pipeline: HTTP POST -> signal extraction -> scoring -> response."""

    def _call_api(self, case):
        """Send the full lead payload to /qualify and return the response data."""
        response = client.post("/qualify", json=case["input"])
        assert response.status_code == 200, (
            f"[{case['id']}] Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()

        # Print the comparison so you can see what happened
        _print_e2e_comparison(case["id"], data, case)

        return data

    def test_score(self, case):
        data = self._call_api(case)
        assert data["score"] == case["expected_score"], (
            f"[{case['id']}] score: API returned {data['score']}, expected {case['expected_score']}"
        )

    def test_priority(self, case):
        data = self._call_api(case)
        assert data["priority"] == case["expected_priority"], (
            f"[{case['id']}] priority: API returned {data['priority']}, expected {case['expected_priority']}"
        )

    def test_classification(self, case):
        data = self._call_api(case)
        assert data["classification"] == case["expected_classification"], (
            f"[{case['id']}] classification: API returned {data['classification']}, "
            f"expected {case['expected_classification']}"
        )

    def test_confidence(self, case):
        data = self._call_api(case)
        assert data["confidence"] == pytest.approx(case["expected_confidence"], abs=0.01), (
            f"[{case['id']}] confidence: API returned {data['confidence']}, "
            f"expected {case['expected_confidence']}"
        )

    def test_response_has_reasoning(self, case):
        """Reasoning should be a non-empty list of strings."""
        data = self._call_api(case)
        assert isinstance(data["reasoning"], list) and len(data["reasoning"]) > 0, (
            f"[{case['id']}] reasoning should be a non-empty list"
        )

    def test_response_has_next_action(self, case):
        """next_action should be a non-empty string."""
        data = self._call_api(case)
        assert isinstance(data["next_action"], str) and len(data["next_action"]) > 0, (
            f"[{case['id']}] next_action should be a non-empty string"
        )


# ── Validation error test (Case E) ────────────────────────────────

@pytest.mark.parametrize(
    "case",
    _VALIDATION_CASES,
    ids=[c["id"] for c in _VALIDATION_CASES],
)
class TestValidationErrors:
    """Structurally invalid requests should return an error, never reach the pipeline."""

    def test_returns_expected_status_code(self, case):
        """Missing required field should return HTTP 422."""
        response = client.post("/qualify", json=case["input"])

        print(f"\n{'='*65}")
        print(f"  CASE: {case['id']}")
        print(f"{'='*65}")
        print(f"\n  HTTP Status:  {response.status_code}  (expected {case['expected_http_status']})")
        print(f"  Response:     {response.json()}")
        print()

        assert response.status_code == case["expected_http_status"], (
            f"[{case['id']}] Expected HTTP {case['expected_http_status']}, "
            f"got {response.status_code}"
        )

    def test_returns_error_body(self, case):
        """Error response should have 'error' field, not a QualifyResponse."""
        response = client.post("/qualify", json=case["input"])
        data = response.json()

        # Should have 'error' key (not 'score', 'priority', etc.)
        assert "error" in data, (
            f"[{case['id']}] Expected error response, but got: {data}"
        )
        # Should NOT have pipeline output fields
        assert "score" not in data, (
            f"[{case['id']}] Invalid request should not produce a score"
        )
