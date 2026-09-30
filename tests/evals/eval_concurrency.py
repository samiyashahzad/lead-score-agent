# -*- coding: utf-8 -*-
"""
Concurrency Evaluation — Baseline

Runs all 20 leads from load_test_leads.json at client-side concurrency
levels 1, 5, and 10 against the live server, which uses the production
threading.Semaphore(5) for LLM call gating.

This establishes the baseline behavior of the existing concurrency
mitigation.  The unbounded comparison (no semaphore) is a separate,
future experiment.

Two distinct bottlenecks are at play:

  Client-side semaphore (this script)
    Controls how many HTTP requests are simultaneously in-flight from
    this process to the server.

  Server-side semaphore (signal_extraction.py, threading.Semaphore(5))
    Controls how many concurrent call_llm() invocations hit Groq.
    Each /qualify request makes 2 sequential LLM calls (signal
    extraction + explanation), so 10 concurrent requests can queue
    up to 20 LLM calls behind this semaphore.

Requires:
    1. Server running:  uvicorn app.api:app --port 8000
    2. httpx installed: pip install httpx

Usage:
    python tests/evals/eval_concurrency.py
"""

import argparse
import asyncio
import json
import math
import os
import sys
import io
import time
import pathlib

# ── Path setup ─────────────────────────────────────────────────────
# Add tests/ to sys.path so we can import from load_test_concurrent.
_TESTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_TESTS_DIR))

from load_test_concurrent import LeadResult, send_lead, BASE_URL  # noqa: E402

# ── Configuration ──────────────────────────────────────────────────
LEADS_FILE = _TESTS_DIR / "load_test_leads.json"
DEFAULT_CONCURRENCY_LEVELS = [1, 5, 10]


# ── Helpers ────────────────────────────────────────────────────────

def _percentile(sorted_values: list[float], p: float) -> float:
    """Return the p-th percentile from a pre-sorted list (linear interpolation)."""
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    return sorted_values[f] * (c - k) + sorted_values[c] * (k - f)


def _categorize_errors(results: list[LeadResult]) -> tuple[int, int, int]:
    """Categorize failures into (count_429, count_timeout, count_other).

    Reuses the same detection logic as load_test_concurrent.py lines 177-191.
    """
    n_429 = n_timeout = n_other = 0
    for r in results:
        if r.success:
            continue
        err = (r.error or "").lower()
        status = str(r.status_code or "")
        if "429" in err or "429" in status or "rate" in err:
            n_429 += 1
        elif "timeout" in err or "timed out" in err:
            n_timeout += 1
        else:
            n_other += 1
    return n_429, n_timeout, n_other


# ── Data container for one concurrency run ─────────────────────────

class ConcurrencyRunResult:
    """Aggregated metrics for a single concurrency-level run."""

    def __init__(
        self,
        concurrency: int,
        results: list[LeadResult],
        total_ms: float,
    ):
        self.concurrency = concurrency
        self.results = sorted(results, key=lambda r: r.lead_id)
        self.total_ms = total_ms

        durations = sorted(r.duration_ms for r in results)
        successes = [r for r in results if r.success]

        self.total_requests = len(results)
        self.successful = len(successes)
        self.failed = self.total_requests - self.successful
        self.success_rate = (
            (self.successful / self.total_requests * 100)
            if self.total_requests
            else 0.0
        )
        self.p50 = _percentile(durations, 50)
        self.p95 = _percentile(durations, 95)
        self.n_429, self.n_timeout, self.n_other = _categorize_errors(results)


# ── Runner ─────────────────────────────────────────────────────────

async def run_at_concurrency(
    leads: list[dict], concurrency: int,
) -> ConcurrencyRunResult:
    """Run all leads at the given client-side concurrency level.

    Reuses send_lead() from load_test_concurrent.py unchanged — only
    the asyncio.Semaphore value differs.
    """
    try:
        import httpx  # noqa: F401 — just verifying availability
    except ImportError:
        print("ERROR: httpx not installed.  Run: pip install httpx")
        sys.exit(1)

    import httpx

    semaphore = asyncio.Semaphore(concurrency)
    start = time.perf_counter()

    async with httpx.AsyncClient() as client:
        tasks = [send_lead(client, lead, semaphore) for lead in leads]
        results: list[LeadResult] = await asyncio.gather(*tasks)

    total_ms = (time.perf_counter() - start) * 1000
    return ConcurrencyRunResult(concurrency, results, total_ms)


# ── Reporting ──────────────────────────────────────────────────────

def _print_level_detail(run: ConcurrencyRunResult) -> None:
    """Print per-lead results for one concurrency level."""
    print(f"\n{'─'*80}")
    print(f"  CONCURRENCY = {run.concurrency}  ({run.total_requests} leads)")
    print(f"{'─'*80}")

    for r in run.results:
        print(r.summary_line())

    print(
        f"\n  Duration: {run.total_ms:,.0f}ms  |  "
        f"OK: {run.successful}/{run.total_requests}  |  "
        f"p50: {run.p50:,.0f}ms  |  p95: {run.p95:,.0f}ms"
    )
    if run.failed:
        print(
            f"  Errors — 429: {run.n_429}  |  "
            f"Timeout: {run.n_timeout}  |  Other: {run.n_other}"
        )


def _print_comparison_table(runs: list[ConcurrencyRunResult]) -> None:
    """Print the final side-by-side comparison table."""
    label_w = 22
    col_w = 16

    print(f"\n{'='*80}")
    print("  CONCURRENCY COMPARISON  (server-side Semaphore = 5)")
    print(f"{'='*80}\n")

    # Column headers
    header = f"  {'Metric':<{label_w}}"
    for run in runs:
        header += f" {'C=' + str(run.concurrency):>{col_w}}"
    print(header)
    print(f"  {'─' * label_w}" + f" {'─' * col_w}" * len(runs))

    # Rows
    rows: list[tuple[str, list[str]]] = [
        ("Total requests",  [str(r.total_requests) for r in runs]),
        ("Successful",      [str(r.successful) for r in runs]),
        ("Failed",          [str(r.failed) for r in runs]),
        ("Success rate",    [f"{r.success_rate:.1f}%" for r in runs]),
        ("p50 latency",     [f"{r.p50:,.0f}ms" for r in runs]),
        ("p95 latency",     [f"{r.p95:,.0f}ms" for r in runs]),
        ("Total duration",  [f"{r.total_ms / 1000:.1f}s" for r in runs]),
        ("429 errors",      [str(r.n_429) for r in runs]),
        ("Timeout errors",  [str(r.n_timeout) for r in runs]),
        ("Other errors",    [str(r.n_other) for r in runs]),
    ]

    for label, values in rows:
        line = f"  {label:<{label_w}}"
        for v in values:
            line += f" {v:>{col_w}}"
        print(line)

    print(f"\n{'='*80}\n")


# ── CLI ────────────────────────────────────────────────────────────

def _parse_args() -> list[int]:
    """Parse CLI arguments and return the concurrency levels to run.

    Usage:
        python tests/evals/eval_concurrency.py                 # all three (1, 5, 10)
        python tests/evals/eval_concurrency.py -c 5            # single level
        python tests/evals/eval_concurrency.py -c 1 -c 5       # specific levels
    """
    parser = argparse.ArgumentParser(
        description=(
            "LeadScout concurrency evaluation.  Run each level "
            "independently with --concurrency to isolate provider quota."
        ),
    )
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        action="append",
        dest="levels",
        metavar="N",
        help=(
            "Client concurrency level to test (repeatable). "
            f"Default: {DEFAULT_CONCURRENCY_LEVELS}"
        ),
    )
    args = parser.parse_args()
    return args.levels or DEFAULT_CONCURRENCY_LEVELS


# ── Main ───────────────────────────────────────────────────────────

async def main() -> int:
    # Force UTF-8 on Windows
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace",
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace",
        )

    levels = _parse_args()

    # Load leads
    with open(LEADS_FILE, "r", encoding="utf-8") as f:
        leads: list[dict] = json.load(f)

    print(f"\n{'='*80}")
    print("  LEADSCOUT — CONCURRENCY EVALUATION (BASELINE)")
    print(f"{'='*80}")
    print(f"  Target:          {BASE_URL}/qualify")
    print(f"  Leads per run:   {len(leads)}")
    print(f"  Concurrency:     {levels}")
    print(f"  Server-side:     threading.Semaphore(5)  (production default)")
    print(f"  Note:            Each /qualify makes 2 sequential LLM calls")
    print(f"{'='*80}")

    runs: list[ConcurrencyRunResult] = []

    for level in levels:
        print(f"\n>>> Running {len(leads)} leads at concurrency = {level} ...")
        run = await run_at_concurrency(leads, level)
        runs.append(run)
        _print_level_detail(run)

    # Comparison table only when multiple levels were run
    if len(runs) > 1:
        _print_comparison_table(runs)

    # Exit code: fail if ANY run had failures
    any_failures = any(r.failed > 0 for r in runs)
    return 1 if any_failures else 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
