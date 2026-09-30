# -*- coding: utf-8 -*-
"""
Lab Exercise: Concurrency Failure Mode -- Load Test

Sends all 20 leads to the /qualify endpoint SIMULTANEOUSLY using asyncio
and httpx, then reports what broke (timeouts, rate limits, 500s, etc).

Usage:
    1. Start the server:   uvicorn app.api:app --port 8000
    2. Run this script:    python tests/load_test_concurrent.py

The script outputs a detailed results table + failure summary.
"""

import asyncio
import json
import time
import sys
import io
import os

# ── Configuration ──────────────────────────────────────────────────
BASE_URL = os.environ.get("LOAD_TEST_URL", "http://127.0.0.1:8000")
LEADS_FILE = os.path.join(os.path.dirname(__file__), "load_test_leads.json")
TIMEOUT_SECONDS = 120  # generous per-request timeout
CONCURRENCY = 20       # all 20 at once — the whole point


# ── Result container ───────────────────────────────────────────────
class LeadResult:
    def __init__(self, lead_id: int, label: str):
        self.lead_id = lead_id
        self.label = label
        self.status_code: int | None = None
        self.duration_ms: float = 0.0
        self.response_body: dict | str | None = None
        self.error: str | None = None
        self.priority: str | None = None
        self.score: int | None = None

    @property
    def success(self) -> bool:
        return self.status_code == 200 and self.error is None

    def summary_line(self) -> str:
        status = f"{self.status_code}" if self.status_code else "ERR"
        dur = f"{self.duration_ms:>8.0f}ms"
        flag = "[OK]" if self.success else "[FAIL]"
        score_str = f"score={self.score:<3}" if self.score is not None else "score=N/A"
        pri_str = f"pri={self.priority or 'N/A':<4}"
        err_str = f" | ERROR: {self.error}" if self.error else ""
        return f"  {flag} Lead {self.lead_id:>2} | {status} | {dur} | {score_str} | {pri_str} | {self.label}{err_str}"


# ── Send one lead ─────────────────────────────────────────────────
async def send_lead(client, lead: dict, semaphore: asyncio.Semaphore) -> LeadResult:
    """Fire one POST /qualify request and capture the outcome."""
    result = LeadResult(lead["id"], lead["label"])

    async with semaphore:
        start = time.perf_counter()
        try:
            resp = await client.post(
                f"{BASE_URL}/qualify",
                json=lead["request"],
                timeout=TIMEOUT_SECONDS,
            )
            elapsed = (time.perf_counter() - start) * 1000
            result.status_code = resp.status_code
            result.duration_ms = elapsed

            try:
                body = resp.json()
                result.response_body = body
                if resp.status_code == 200:
                    result.score = body.get("score")
                    result.priority = body.get("priority")
                else:
                    result.error = f"HTTP {resp.status_code}: {json.dumps(body)[:200]}"
            except Exception:
                result.response_body = resp.text
                result.error = f"HTTP {resp.status_code}: non-JSON body"

        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            result.duration_ms = elapsed
            result.error = f"{type(e).__name__}: {e}"

    return result


# ── Main load test ─────────────────────────────────────────────────
async def run_load_test():
    # Force UTF-8 stdout on Windows
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    # Dynamic import so the script only fails at runtime if httpx missing
    try:
        import httpx
    except ImportError:
        print("ERROR: httpx not installed. Run: pip install httpx")
        sys.exit(1)

    # Load leads
    with open(LEADS_FILE, "r", encoding="utf-8") as f:
        leads = json.load(f)

    print(f"\n{'='*80}")
    print(f"  LEADSCOUT -- CONCURRENCY LOAD TEST")
    print(f"  Target:      {BASE_URL}/qualify")
    print(f"  Leads:       {len(leads)}")
    print(f"  Concurrency: {CONCURRENCY} (all simultaneous)")
    print(f"  Timeout:     {TIMEOUT_SECONDS}s per request")
    print(f"{'='*80}\n")

    print(">>> Firing all 20 leads simultaneously...\n")

    semaphore = asyncio.Semaphore(CONCURRENCY)
    overall_start = time.perf_counter()

    async with httpx.AsyncClient() as client:
        tasks = [send_lead(client, lead, semaphore) for lead in leads]
        results: list[LeadResult] = await asyncio.gather(*tasks)

    overall_elapsed = (time.perf_counter() - overall_start) * 1000

    # ── Results table ──────────────────────────────────────────────
    print(f"\n{'='*80}")
    print(f"  RESULTS")
    print(f"{'='*80}")

    # Sort by lead_id for consistent display
    results.sort(key=lambda r: r.lead_id)

    for r in results:
        print(r.summary_line())

    # ── Summary stats ──────────────────────────────────────────────
    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]
    durations = [r.duration_ms for r in results]

    print(f"\n{'='*80}")
    print(f"  SUMMARY")
    print(f"{'='*80}")
    print(f"  Total time:      {overall_elapsed:,.0f}ms ({overall_elapsed/1000:.1f}s)")
    print(f"  Succeeded:       {len(successes)}/{len(results)}")
    print(f"  Failed:          {len(failures)}/{len(results)}")
    print(f"  Min latency:     {min(durations):,.0f}ms")
    print(f"  Max latency:     {max(durations):,.0f}ms")
    print(f"  Avg latency:     {sum(durations)/len(durations):,.0f}ms")
    print(f"  Median latency:  {sorted(durations)[len(durations)//2]:,.0f}ms")

    if failures:
        print(f"\n{'─'*80}")
        print(f"  ❌ FAILURE DETAILS")
        print(f"{'─'*80}")

        # Categorize failures
        error_categories: dict[str, list[LeadResult]] = {}
        for r in failures:
            # Extract error type
            err_type = r.error.split(":")[0] if r.error else "Unknown"
            error_categories.setdefault(err_type, []).append(r)

        for category, items in error_categories.items():
            print(f"\n  [{category}] — {len(items)} failure(s)")
            for r in items:
                print(f"    Lead {r.lead_id}: {r.error}")

        print(f"\n{'='*80}")
        print(f"  FAILURE ANALYSIS")
        print(f"{'─'*80}")

        if any("429" in (r.error or "") or "rate" in (r.error or "").lower() for r in failures):
            print("  [!] RATE LIMITING detected -- the LLM provider throttled concurrent requests.")
            print("      Fix: implement request queuing, retry with backoff, or reduce concurrency.")

        if any("Timeout" in (r.error or "") or "timed out" in (r.error or "").lower() for r in failures):
            print("  [!] TIMEOUTS detected -- some requests took too long under load.")
            print("      Fix: implement request timeouts, circuit breakers, or async processing.")

        if any("500" in str(r.status_code) for r in failures):
            print("  [!] SERVER ERRORS (500) detected -- unhandled exceptions in the pipeline.")
            print("      Fix: add try/catch around LLM calls, return graceful error responses.")

        if any("Connection" in (r.error or "") for r in failures):
            print("  [!] CONNECTION ERRORS detected -- server couldn't handle the connection load.")
            print("      Fix: increase worker count, implement connection pooling.")

    else:
        print(f"\n  [OK] All {len(results)} leads processed successfully!")
        print(f"     (But check latencies — even 'success' under 120s timeout may be degraded)")

    # Check for degraded performance even in success
    slow_threshold = 30_000  # 30 seconds
    slow_requests = [r for r in results if r.duration_ms > slow_threshold]
    if slow_requests:
        print(f"\n  [!] {len(slow_requests)} request(s) took > {slow_threshold/1000:.0f}s -- performance degradation under load:")
        for r in slow_requests:
            print(f"    Lead {r.lead_id}: {r.duration_ms/1000:.1f}s")

    print(f"\n{'='*80}\n")

    return results


if __name__ == "__main__":
    results = asyncio.run(run_load_test())

    # Exit code reflects whether any failures occurred
    sys.exit(1 if any(not r.success for r in results) else 0)
