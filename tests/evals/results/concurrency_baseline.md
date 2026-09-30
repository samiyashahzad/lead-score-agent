# Concurrency Evaluation — Observed Live Baseline

> **Status:** Live Load-to-Failure Evaluation Under Actual Provider Constraints
>
> This is not a provider-independent concurrency benchmark. Provider quota
> exhaustion (Groq 429) caused the majority of failures at C=5 and C=10.
> The data below is raw evidence preserved for the reliability report,
> not a causal measurement of concurrency behavior in isolation.

## Run Configuration

| Parameter              | Value                                    |
|------------------------|------------------------------------------|
| Date                   | 2026-09-30                               |
| Script                 | `tests/evals/eval_concurrency.py`        |
| Target                 | `http://127.0.0.1:8000/qualify`          |
| Server                 | `uvicorn app.api:app --port 8000`        |
| Server-side mitigation | `threading.Semaphore(5)` (production)    |
| Leads per run          | 20 (from `load_test_leads.json`)         |
| LLM calls per lead     | 2 (signal extraction + explanation)      |
| Provider               | Groq (`openai/gpt-oss-120b`)            |
| Provider tier          | `on_demand` (free)                       |
| Provider TPM limit     | 8,000 tokens/minute                      |
| Run method             | Each level run independently (`-c N`)    |

## Raw Results

Each concurrency level was run as an independent invocation against fresh
provider quota, not as a sequential 1→5→10 execution.

| Metric           |        C=1 |        C=5 |       C=10 |
|------------------|-----------:|-----------:|-----------:|
| Total requests   |         20 |         20 |         20 |
| Successful       |         20 |          7 |          8 |
| Failed           |          0 |         13 |         12 |
| Success rate     |     100.0% |      35.0% |      40.0% |
| p50 latency      |  15,585 ms |  15,166 ms |  34,234 ms |
| p95 latency      |  22,469 ms |  20,781 ms |  48,939 ms |
| Total duration   |     310.2s |      72.5s |      85.5s |
| 429 errors       |          0 |          0 |          0 |
| Timeout errors   |          0 |          0 |          0 |
| Other errors     |          0 |         13 |         12 |

## Error Propagation Finding

All failures were reported by the evaluator as **"Other errors"** rather
than **"429 errors"**. This is itself a finding about error observability:

```
Groq HTTP 429
  → openai.RateLimitError (raised inside call_llm())
    → no try/except in call_llm(), signal_extraction(), or qualify()
      → unhandled exception propagates to FastAPI
        → LeadScout returns HTTP 500 Internal Server Error
          → evaluator sees generic server failure, not rate-limit error
```

From the **client's** perspective, every failure was an HTTP 500 with a
non-JSON body. The 429 was an internal event between the server and the Groq
API, invisible to the external caller.

**Implication:** An external monitoring system or customer integration would
have no way to distinguish "provider temporarily rate-limited" from "server
crashed." The error is not propagated meaningfully.

Server log excerpt confirming the root cause:

```
openai.RateLimitError: Error code: 429 - {'error': {'message':
 'Rate limit reached for model `openai/gpt-oss-120b` in organization
  `org_01kyvk8g0sfdm97pdh0d9dq1nh` service tier `on_demand` on tokens
  per minute (TPM): Limit 8000, Used 7608, Requested 1865. Please try
  again in 11.0475s.'}}
```

## Interpretation

### Main Finding

The production `threading.Semaphore(5)` in `signal_extraction.py:45` limits
simultaneous LLM API calls to 5, but does not enforce the provider's
tokens-per-minute quota. Under this model/tier/workload, higher client
concurrency triggered substantial provider throttling:

- **C=1** completed with 100% success because requests were fully serialized —
  each lead's 2 LLM calls finished before the next lead started, giving the
  TPM quota time to recover between requests.
- **C=5 and C=10** both experienced ~60–65% failure rates because multiple
  leads sent LLM requests within the same minute window, exhausting the
  8,000 TPM limit.

### What Cannot Be Concluded

- **C=10's 40% success rate vs C=5's 35%** should not be interpreted as
  C=10 performing better. The experiment does not contain enough repeated
  controlled trials to establish that — the difference is within noise for
  a single run of 20 leads against a rate-limited provider.

- **p95 latency** (22.5s → 20.8s → 48.9s) includes both successful and
  failed requests. Failed requests may have had abnormal timing due to the
  provider error path. The C=5 p95 appearing lower than C=1 is likely an
  artifact of failed requests returning quickly with errors rather than
  completing full LLM round-trips.

- **Total duration** (310s → 72s → 86s) decreased at higher concurrency,
  but this comparison is confounded because many requests at C=5/C=10 failed
  early rather than completing full LLM round-trips.

### Findings Summary

| # | Finding | Status |
|---|---------|--------|
| 1 | `Semaphore(5)` bounds simultaneous LLM calls but does not enforce provider TPM quota | Confirmed |
| 2 | Provider rate limiting has no graceful handling — surfaces externally as HTTP 500 | Confirmed |
| 3 | p95 latency pattern is observed but confounded by provider failures | Observed, not causal |
| 4 | Throughput/duration pattern is observed but confounded by early failures | Observed, not causal |

### What This Baseline Enables

1. The **current system has no resilience to provider rate limits** — a single
   429 crashes the request.
2. The **error propagation path obscures the root cause** — external callers
   cannot distinguish provider throttling from server crashes.
3. A **clean concurrency benchmark** requires either solving the rate-limit
   problem first, or using a controlled mock/stub provider.
4. These findings confirm the priority of **Experiment 2 (Provider Rate
   Limiting)** from `EVAL_PLAN.md`.
