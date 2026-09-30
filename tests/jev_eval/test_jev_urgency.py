"""
Eval: Urgency extraction via Jev vs. eval dataset.

Sends each case's inquiry text to the Jev typesafe endpoint and compares
the returned urgency value against expected_signals.urgency.

Uses the SAME urgency instructions as the Groq-based pipeline
(see signal_questions.py) so the comparison is fair.

Requires AI_GATEWAY_API_KEY in .env or environment.

Run with:
    .venv\\Scripts\\python.exe -m pytest tests/jev_eval/test_jev_urgency.py -v -s
"""

import json
import pathlib

import pytest
from dotenv import load_dotenv

load_dotenv()

from .jev_client import JevClient
from .signal_questions import URGENCY_QUESTION

# ── Load eval dataset ──────────────────────────────────────────────

_DATASET_PATH = pathlib.Path(__file__).resolve().parent.parent / "eval_dataset_v1.json"

with open(_DATASET_PATH, encoding="utf-8") as f:
    _ALL_CASES = json.load(f)["cases"]

# Only cases that have expected_signals (skip Case E — validation error)
_SIGNAL_CASES = [c for c in _ALL_CASES if c["expected_signals"] is not None]


# ── Jev client (module-level, shared across all tests) ─────────────

_client = JevClient()

# ── Cache: one Jev call per case, not per test method ──────────────
# Avoids the "7 LLM calls per case" problem the original tests had.

_RESULT_CACHE: dict[str, str] = {}


def _get_jev_urgency(case: dict) -> str:
    """Call Jev once per case and return the urgency value."""
    case_id = case["id"]

    if case_id not in _RESULT_CACHE:
        inquiry = case["input"]["inquiry"]
        response = _client.extract(
            state=inquiry,
            questions={"urgency": URGENCY_QUESTION},
        )
        # Jev nests answers under: response["answers"][field]["choice"]
        answers = response.get("answers", {})
        urgency_answer = answers.get("urgency", {})
        _RESULT_CACHE[case_id] = urgency_answer.get("choice", "<missing>")

    return _RESULT_CACHE[case_id]


# ── Helper: comparison output ─────────────────────────────────────

def _print_urgency_comparison(case_id: str, jev_value: str, expected: str):
    """Print a concise comparison line for this case."""
    match = "PASS" if jev_value == expected else "FAIL <<<"
    print(f"  {case_id:<40} Jev={jev_value:<10} Expected={expected:<10} {match}")


# ── Parametrised test ─────────────────────────────────────────────

@pytest.mark.parametrize(
    "case",
    _SIGNAL_CASES,
    ids=[c["id"] for c in _SIGNAL_CASES],
)
def test_jev_urgency(case):
    """Does Jev extract the correct urgency from the inquiry text?"""
    expected = case["expected_signals"]["urgency"]
    jev_value = _get_jev_urgency(case)

    _print_urgency_comparison(case["id"], jev_value, expected)

    assert jev_value == expected, (
        f"[{case['id']}] urgency: Jev returned {jev_value!r}, "
        f"expected {expected!r}"
    )


# ── Summary report (runs once after all parametrised tests) ───────

@pytest.fixture(scope="session", autouse=True)
def _print_summary(request):
    """After all tests finish, print a summary table."""
    yield

    if not _RESULT_CACHE:
        return

    print(f"\n{'=' * 72}")
    print("  JEV URGENCY EXTRACTION — SUMMARY")
    print(f"{'=' * 72}")
    print(f"  {'Case':<40} {'Jev':<10} {'Expected':<10} {'Result'}")
    print(f"  {'-' * 68}")

    passes = 0
    total = 0

    for case in _SIGNAL_CASES:
        case_id = case["id"]
        expected = case["expected_signals"]["urgency"]
        jev_value = _RESULT_CACHE.get(case_id, "<not run>")
        match = "PASS" if jev_value == expected else "FAIL"

        if match == "PASS":
            passes += 1
        total += 1

        print(f"  {case_id:<40} {jev_value:<10} {expected:<10} {match}")

    accuracy = passes / total if total else 0
    print(f"\n  Accuracy: {passes}/{total} ({accuracy:.0%})")
    print(f"{'=' * 72}\n")
