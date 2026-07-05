"""Pydantic request/response models and JSON-schema constants for structured LLM output."""

from uuid import UUID

from pydantic import BaseModel

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": ["billing", "technical", "account", "other"]},
        "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"]},
        "sentiment": {"type": "string", "enum": ["positive", "neutral", "negative"]},
        "lang": {"type": "string"},
    },
    "required": ["category", "priority", "sentiment", "lang"],
    "additionalProperties": False,
}


class ClassifyRequest(BaseModel):
    ticket_id: UUID
    subject: str
    body: str


class ClassifyResponse(BaseModel):
    category: str
    priority: str
    sentiment: str
    lang: str


class QueryRequest(BaseModel):
    question: str
    ticket_id: UUID | None = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    confidence: float


class IngestResponse(BaseModel):
    documents: int
    chunks: int


class SummarizeRequest(BaseModel):
    stats: dict


class SummarizeResponse(BaseModel):
    text: str


class StatsResponse(BaseModel):
    tickets_by_status: dict[str, int]
    auto_resolution_rate: float
    avg_confidence: float | None
    total_cost_usd: float
    p95_latency_ms: float | None
