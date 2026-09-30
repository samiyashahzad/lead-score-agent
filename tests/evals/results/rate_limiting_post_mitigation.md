# Rate Limiting Evaluation — Results (Before vs After)

> **Status:** Post-Mitigation Validation Complete
>
> Evaluated `app.signal_extraction.call_llm` under controlled HTTP 429 fault injection using a mocked provider to isolate rate-limiting behavior from the live server/concurrency constraints.

## Run Configuration
- **Date:** 2026-09-30
- **Script:** `tests/evals/eval_rate_limiting.py`
- **Target:** `app.signal_extraction.call_llm`
- **Mitigation Present (Before):** None (0 retries, no backoff, no exception handling)
- **Mitigation Present (After):** Bounded retry loop (max 3 attempts, honors Retry-After header, fallback exponential backoff, raises `ProviderRateLimitError`)

## Results: Before Mitigation (Baseline)

| Scenario | Injected Sequence | Attempts Made | Outcome | Exception | Recovery |
|----------|------------------|---------------|---------|-----------|----------|
| 1 | 1x HTTP 429 → Success | 1 | Raised | RateLimitError | False |
| 2 | 2x HTTP 429 → Success | 1 | Raised | RateLimitError | False |
| 3 | Persistent HTTP 429s | 1 | Raised | RateLimitError | False |

## Results: After Mitigation

| Scenario | Injected Sequence | Attempts Made | Outcome | Exception | Recovery |
|----------|------------------|---------------|---------|-----------|----------|
| 1 | 1x HTTP 429 → Success | 2 | Returned | None | True |
| 2 | 2x HTTP 429 → Success | 3 | Returned | None | True |
| 3 | Persistent HTTP 429s | 3 | Raised | ProviderRateLimitError | False |

## Findings & Conclusions

1. **Successful Transient Fault Recovery:** Scenarios 1 and 2 now correctly recover from transient provider rate limits, successfully returning the response on attempts 2 and 3 respectively.
2. **Predictable Exhaustion:** Scenario 3 demonstrates that persistent rate limits correctly terminate after the configured 3 attempts, raising a domain-specific `ProviderRateLimitError` rather than hanging indefinitely.
3. **Structured API Response:** API-level tests confirmed that `ProviderRateLimitError` is successfully translated by FastAPI into a structured `503 Service Unavailable` response, isolating upstream infrastructure failures from the application's external contract.
