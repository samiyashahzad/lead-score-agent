"""
FastAPI endpoint to qualify a lead.
Structurally valid request  → full pipeline → QualifyResponse (always)
Structurally invalid request → FastAPI validation catches it → distinct error response, never reaches the pipeline

"""


from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.status import HTTP_422_UNPROCESSABLE_CONTENT

from app.schemas import LeadInput, QualifyResponse
from app.scoring import score_lead
from app.signal_extraction import signal_extraction, ProviderRateLimitError
from app.explanation import generate_explanation

app = FastAPI(
    title="leadscout",
    description="AI-powered B2B lead scoring agent. Extracts signals from raw inquiry text, scores leads 0–100, classifies them as Distributor or End Customer, and recommends next actions.",
    version="1.0.0",
)

@app.post("/qualify", response_model=QualifyResponse)
def qualify(lead:LeadInput):
    """
    Qualify a lead by extracting signals, scoring, and generating explanations
    """

    signals = signal_extraction(lead.inquiry)
    score, priority, classification, confidence = score_lead(signals)
    reasoning, next_action = generate_explanation(signals, score, priority, classification, confidence)
    return QualifyResponse(
        score=score,
        priority=priority,
        classification=classification,
        confidence=confidence,
        reasoning=reasoning,
        next_action=next_action
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request, exc):
    """
      returns error gracefully 
    """
    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "error": "validation_failed",
            "detail": _make_serializable(exc.errors())
        }
    )


def _make_serializable(obj):
    """Recursively convert non-JSON-serializable values (like bytes) to strings."""
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_serializable(item) for item in obj]
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    return obj

@app.exception_handler(ProviderRateLimitError)
async def handle_provider_rate_limit(request, exc):
    return JSONResponse(
        status_code=503,
        content={"detail": "Upstream AI provider rate limit exceeded. Please try again later."}
    )