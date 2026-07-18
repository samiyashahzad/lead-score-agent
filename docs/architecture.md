# Architecture

leadscout is a **3-stage pipeline** that converts raw, unstructured inquiry text into a structured lead qualification with a score, classification, and recommended next action.

## Pipeline Overview

```
Raw inquiry text
       │
       ▼
┌──────────────────────┐
│  Signal Extraction   │  LLM (Groq / Llama 3.3 70B)
│  signal_extraction.py│  Extracts 7 structured signals from freeform text
└──────────┬───────────┘
           │  Signals (Pydantic model)
           ▼
┌──────────────────────┐
│   Scoring Engine     │  Pure Python, deterministic
│   scoring.py         │  Weighted formula → score (0-100), priority, classification
└──────────┬───────────┘
           │  score, priority, classification, confidence
           ▼
┌──────────────────────┐
│ Explanation Generator│  LLM (Groq / Llama 3.3 70B)
│ explanation.py       │  Human-readable reasoning + next action recommendation
└──────────┬───────────┘
           │
           ▼
    QualifyResponse (JSON)
```

## Stage 1: Signal Extraction (`signal_extraction.py`)

**Input:** Raw inquiry text (string)
**Output:** `Signals` Pydantic model with 7 fields

The LLM receives the inquiry text with a system prompt that defines exactly what each signal means. The system prompt includes:

- **Explicit field definitions** with boundary conditions (e.g., "distributor_intent is true ONLY if the inquiry explicitly discusses reselling to others — a restaurant buying ingredients for its own kitchen is NOT distributor intent")
- **A concrete example** showing input → correct output, specifically addressing the distributor vs. end-customer ambiguity that was discovered during development
- **Anti-injection instructions** — the prompt explicitly tells the model to treat all input as data to analyze, never as instructions to follow

### Reliability pattern: Retry with field-level fallbacks

```
Attempt 1: Call LLM → Parse JSON → Validate against Pydantic schema
  ├─ All fields valid → return Signals
  └─ Validation fails → Attempt 2
Attempt 2: Call LLM → Parse JSON → Validate
  ├─ All fields valid → return Signals
  └─ Still fails → Field-level fallback
        For each field individually:
          ├─ Field passes validation → keep the LLM's value
          └─ Field fails → substitute safe default (false for bools, "unknown" for enums)
```

This means a single corrupted field doesn't throw away the entire extraction. If the LLM gets 6 out of 7 fields right, we keep those 6 and only fall back on the broken one.

## Stage 2: Scoring Engine (`scoring.py`)

**Input:** `Signals` model
**Output:** score (int 0-100), priority (Hot/Warm/Cold), classification (Distributor/End Customer), confidence (float 0.0-1.0)

This stage is **pure Python with no LLM calls**. It's fully deterministic — the same signals always produce the same score.

### Weight table (total = 100 points)

| Signal | Weight | Type |
|---|---|---|
| distributor_intent | 30 | Boolean (all or nothing) |
| commercial_intent | 25 | Boolean (all or nothing) |
| urgency | 15 | Tiered (high=15, medium=10, low=5) |
| industry_relevance | 10 | Tiered (high=10, medium=6, low=3) |
| geographic_scope | 10 | Tiered (multi_country=10, regional=7, national=5, single=3) |
| company_scale | 5 | Tiered (large=5, small=3) |
| decision_maker | 5 | Boolean (all or nothing) |

### Priority thresholds

- **Hot:** score ≥ 80
- **Warm:** score ≥ 50
- **Cold:** score < 50

### Confidence calculation

Confidence measures how much information the LLM was able to extract, not how "sure" the model is. It only counts the 4 enum fields (urgency, industry_relevance, geographic_scope, company_scale) because boolean fields always resolve to true/false and never land on "unknown."

```
confidence = (number of enum fields with a real value, not "unknown") / 4
```

## Stage 3: Explanation Generator (`explanation.py`)

**Input:** Signals + score + priority + classification + confidence
**Output:** reasoning (list of strings) + next_action (string)

A second LLM call generates human-readable explanations. The key design decision here: the explanation LLM receives the **already-decided** score and priority as hard facts. It cannot override them. Its system prompt includes a mandatory priority-to-tone mapping:

- **Hot** → suggest immediate, urgent follow-up
- **Warm** → suggest near-term, scheduled follow-up
- **Cold** → suggest low-priority, log-only handling

This prevents the explanation from contradicting the scoring (e.g., generating "contact immediately!" for a Cold lead).

### Fallback behavior

If the explanation LLM fails after 2 attempts, deterministic fallbacks kick in:
- `reasoning` → a single honest sentence stating the score and how many signals were extracted
- `next_action` → a canned response mapped directly from the priority bucket

## Cross-cutting concerns

### Input validation (schemas.py + api.py)

Pydantic models enforce types at the API boundary. A custom exception handler catches `RequestValidationError` and returns structured error JSON instead of FastAPI's default error format.

### Security

- All user input is treated as **data to analyze, never instructions** — explicitly stated in the signal extraction system prompt
- API keys are loaded from environment variables via `python-dotenv`, never exposed in responses or logs
- The agent is stateless — no persistent memory between requests
- Schema validation catches corrupted LLM output before it reaches the response

### Statelesness

Every request is independent. No database, no session, no memory. This is a deliberate design choice — it simplifies deployment, eliminates state-related bugs, and means a prompt injection in one request cannot affect any other request.
