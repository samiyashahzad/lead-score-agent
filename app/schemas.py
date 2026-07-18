from typing import Literal, List
from pydantic import BaseModel


class LeadInput(BaseModel):
    name: str | None = None
    company: str
    industry: str | None = None
    source: str | None = None
    inquiry: str
    country: str | None = None
    email: str | None = None

class Signals(BaseModel):
    distributor_intent: bool
    commercial_intent: bool
    decision_maker: bool
    urgency: Literal["low", "medium", "high", "unknown"]
    industry_relevance: Literal["low", "medium", "high", "unknown"]
    geographic_scope: Literal["single_location", "national", "regional", "multi_country", "unknown"]
    company_scale: Literal["small", "large", "unknown"]

class QualifyResponse(BaseModel):
    score: int
    priority: Literal["Hot", "Warm", "Cold"]
    classification: Literal["Distributor", "End Customer"]
    confidence: float
    reasoning: List[str]
    next_action: str

