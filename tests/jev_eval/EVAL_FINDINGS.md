# Jev Eval — Findings Log

> Comparing **Jev** (Vercel AI Gateway) against the existing Groq LLM on [`eval_dataset_v1.json`](file:///d:/lead%20score%20agent/tests/eval_dataset_v1.json).
> Same instructions, different engine. We only log what's interesting — the differences.

---

## Urgency — 7/9 passed

Two failures, same root cause: the system prompt says *"no time-related language → unknown"* but the eval labels expect the model to read beyond literal time words.

### F · `multi_branch_distributor_hot` — expected `low`, Jev said `unknown`

> *"...would like to **explore** stocking your product line..."*

"Explore" is pace/hedging language, not a time word. The original LLM guessed `low` because its training maps hedging → casual. Jev read the rule literally: no time word, no urgency. **The instruction is underspecified** — it says "time-related" but means "pace/hedging" too.

### I · `large_enterprise_end_customer` — expected `medium`, Jev said `unknown`

> *"...want to set up a regular supply contract... send pricing for national-level procurement."*

Zero time or pace words. The `medium` label comes from how *specific and business-ready* the inquiry is — that's lead seriousness, not urgency. Compare Case J (*"would like to add your product line"* → `unknown`): same zero time words, but J is vague so it got `unknown`. **The label is encoding the wrong concept.**

### What this means

The urgency field quietly carries two things: (1) actual time pressure and (2) how serious/concrete the lead sounds. Jev exposed it; the original model masked it by guessing right for the wrong reason. Whether to fix this (split the signal? rewrite the instruction? relabel?) is deferred until we've tested all signals — no point redesigning from a sample of one.

---

## Distributor Intent — *next up*

---

## Infrastructure

| What | Where |
|------|-------|
| Test module | [`tests/jev_eval/`](file:///d:/lead%20score%20agent/tests/jev_eval) |
| Jev endpoint | `POST https://ai-gateway.vercel.sh/v1/evaluate` |
| Jev model | `typesafe-ai/jev` |
| Original prompt | [`signal_extraction.py` L162–278](file:///d:/lead%20score%20agent/app/signal_extraction.py#L162-L278) |
