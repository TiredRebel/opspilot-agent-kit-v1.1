"""Pydantic request/response models and JSON-schema constants for structured LLM output."""

from datetime import datetime
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
    """POST /classify request body."""

    # Typed as UUID, not str, so a malformed ticket_id is rejected here with a clean 422 —
    # otherwise it reaches asyncpg and crashes with a raw 500 (wiki/gotchas.md #13).
    ticket_id: UUID
    subject: str
    body: str


class ClassifyResponse(BaseModel):
    """POST /classify response body — the parsed structured-output fields."""

    category: str
    priority: str
    sentiment: str
    lang: str


class QueryRequest(BaseModel):
    """POST /query request body."""

    question: str
    ticket_id: UUID | None = None


class QueryResponse(BaseModel):
    """POST /query response body — grounded answer, cited sources, and blended confidence."""

    answer: str
    sources: list[str]
    confidence: float


class IngestResponse(BaseModel):
    """POST /kb/ingest response body — counts of documents/chunks written this run."""

    documents: int
    chunks: int


class SummarizeRequest(BaseModel):
    """POST /summarize request body — the stats payload to turn into a digest."""

    stats: dict


class SummarizeResponse(BaseModel):
    """POST /summarize response body."""

    text: str


class TicketEvent(BaseModel):
    """One ticket_events row — type, trigger-built payload, and when it happened."""

    type: str
    payload: dict
    created_at: datetime


class TicketEventsResponse(BaseModel):
    """GET /tickets/{ticket_id}/events response body — the ticket's audit trail, oldest first."""

    ticket_id: UUID
    events: list[TicketEvent]


class StatsResponse(BaseModel):
    """GET /stats response body — ticket/cost/latency aggregates, optionally time-scoped."""

    tickets_by_status: dict[str, int]
    tickets_by_category: dict[str, int]
    tickets_by_priority: dict[str, int]
    auto_resolution_rate: float
    avg_confidence: float | None
    total_cost_usd: float
    p95_latency_ms: float | None
