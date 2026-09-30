# LeadScout Reliability Evaluation

## Goal

Evaluate how LeadScout behaves under four known failure conditions
and whether existing mitigations actually improve reliability.

## 1. Concurrency / Batch Load

Failure:
Multiple leads arriving simultaneously can overwhelm external LLM calls.

Experiment:
Run the same workload at:
- 1 concurrent request
- 5 concurrent requests
- 10 concurrent requests

Measure:
- success rate
- failed requests
- p50 latency
- p95 latency
- total execution time

Compare:
Unbounded concurrency vs bounded concurrency (semaphore).

Question:
Does bounding concurrency improve reliability, and what latency/
throughput trade-off does it introduce?


## 2. Provider Rate Limiting

Failure:
Groq may return HTTP 429 when request volume exceeds limits.

Experiment:
Inject controlled provider failures:
- normal response
- 429 → success
- 429 → 429 → success
- repeated 429 until retry exhaustion

Measure:
- recovery success
- retry count
- recovery latency

Compare:
No retry strategy vs backoff/retry.

Question:
Does retry/backoff recover safely from temporary provider failures?


## 3. Urgency Ambiguity

Failure:
LeadScout may classify vague or emphatic language as HIGH urgency
without sufficient evidence.

Test:
3 deliberately designed inquiries:
- clear urgency
- ambiguous urgency
- misleading/emphatic urgency

Measure:
Expected urgency vs actual urgency + supporting evidence.

Question:
Does LeadScout distinguish real urgency from linguistic intensity?


## 4. Unsupported Next Steps

Failure:
The LLM explanation may recommend actions not supported by the
original inquiry.

Test:
3 inquiries:
- explicit requested action
- ambiguous next step
- adversarial/unsupported requested output

Measure:
Whether the recommended next step is grounded in evidence
from the original inquiry.

Question:
Does LeadScout invent actions beyond what the lead actually supports?


# Output

Generate a reliability report containing:

- test/scenario
- expected behavior
- actual behavior
- PASS / FAIL
- evidence
- latency where applicable
- mitigation used
- remaining limitation

Show before/after results where a mitigation exists.