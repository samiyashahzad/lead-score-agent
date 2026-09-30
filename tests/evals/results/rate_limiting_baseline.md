# Rate Limiting Evaluation — Observed Baseline

> **Status:** Baseline evaluation before implementing retries
>
> Evaluated `app.signal_extraction.call_llm` under controlled HTTP 429 fault injection using a mocked provider to isolate rate-limiting behavior from the live server/concurrency constraints.

## Run Configuration
- **Date:** 2026-09-30
- **Script:** `tests/evals/eval_rate_limiting.py`
- **Target:** `app.signal_extraction.call_llm`
- **Mitigation Present:** None (0 retries, no backoff, no exception handling)
- **Constraint:** Maximum 3 provider attempts allowed

## Results

| Scenario | Injected Sequence | Attempts Made | Outcome | Exception | Recovery |
|----------|------------------|---------------|---------|-----------|----------|
| 1 | 1x HTTP 429 → Success | 1 | Raised | RateLimitError | False |
| 2 | 2x HTTP 429 → Success | 1 | Raised | RateLimitError | False |
| 3 | Persistent HTTP 429s | 1 | Raised | RateLimitError | False |

## Findings

1. **Zero Fault Tolerance:** The current implementation of `call_llm` is completely brittle. A single HTTP 429 exception from the provider immediately propagates upward.
2. **No Recovery:** Scenarios 1 and 2 demonstrate that transient faults, which could be resolved with a simple retry, currently crash the request entirely.
3. **HTTP 500 Propagation:** Because the `RateLimitError` is unhandled, it propagates to the FastAPI routing layer resulting in a generic 500 Internal Server Error, masking the provider limit from the client.
