"""FastAPI app: /health, /kb/ingest, /classify, /query, /summarize, /stats.

This is the only service allowed to call an LLM (ADR-001) — n8n workflows call these endpoints
over HTTP rather than reaching an LLM API directly.
"""

import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from app import db
from app.llm import BudgetExceeded, complete, load_prompt
from app.retrieval import blend_confidence, chunk_text, to_vector_literal, top_k_chunks
from app.schemas import (
    CLASSIFY_SCHEMA,
    ClassifyRequest,
    ClassifyResponse,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    StatsResponse,
    SummarizeRequest,
    SummarizeResponse,
)
from app.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await db.close_pool()


app = FastAPI(title="OpsPilot RAG service", lifespan=lifespan)
router = APIRouter()


@app.exception_handler(BudgetExceeded)
async def budget_exceeded_handler(request: Request, exc: BudgetExceeded):
    return JSONResponse(status_code=429, content={"detail": str(exc)})


@router.get("/health")
async def health(response: Response):
    """Liveness probe — 503 (not just a false field) so container orchestration/compose
    healthchecks can act on it without parsing the body."""
    db_ok = await db.check_db()
    if not db_ok:
        response.status_code = 503
    return {"status": "ok" if db_ok else "unavailable", "db": db_ok}


@router.post("/kb/ingest", response_model=IngestResponse)
async def kb_ingest(seed_dir: str | None = None) -> IngestResponse:
    """Idempotent by document title: re-ingesting a doc deletes its old chunks/row first, so
    `make seed` is safe to rerun after editing kb/seed/*.md without creating duplicates."""
    directory = Path(seed_dir or settings.kb_seed_dir)
    pool = await db.get_pool()
    documents = 0
    chunks = 0
    for path in sorted(directory.glob("*.md")):
        title = path.stem
        text = path.read_text(encoding="utf-8")

        # Idempotent re-ingest: replace any existing document with the same title.
        existing = await pool.fetch("SELECT id FROM kb_documents WHERE title = $1", title)
        for row in existing:
            await pool.execute("DELETE FROM kb_chunks WHERE document_id = $1", row["id"])
            await pool.execute("DELETE FROM kb_documents WHERE id = $1", row["id"])

        document_id = await pool.fetchval(
            "INSERT INTO kb_documents (title, source) VALUES ($1, $2) RETURNING id",
            title,
            str(path),
        )
        documents += 1
        for index, chunk in enumerate(chunk_text(text)):
            result = await complete("embed", embed_text=chunk)
            await pool.execute(
                """
                INSERT INTO kb_chunks (document_id, chunk_index, content, embedding)
                VALUES ($1, $2, $3, $4::vector)
                """,
                document_id,
                index,
                chunk,
                to_vector_literal(result.embedding),
            )
            chunks += 1
    return IngestResponse(documents=documents, chunks=chunks)


def _classify_valid(parsed: dict | None) -> bool:
    """A schema-constrained LLM call can still come back malformed (e.g. a provider that ignores
    the schema) — this is the actual validation gate, not just a truthiness check."""
    if not isinstance(parsed, dict):
        return False
    required = {"category", "priority", "sentiment", "lang"}
    return required.issubset(parsed.keys())


@router.post("/classify", response_model=ClassifyResponse)
async def classify(payload: ClassifyRequest) -> ClassifyResponse:
    """One retry on invalid structured output, then a clean 422 (docs/TESTPLAN.md
    test_classify_schema.py) rather than surfacing a confusing downstream error."""
    system = load_prompt("classify")
    messages = [{"role": "user", "content": f"Subject: {payload.subject}\n\nBody: {payload.body}"}]

    for _attempt in range(2):
        result = await complete(
            "classify",
            messages,
            schema=CLASSIFY_SCHEMA,
            system=system,
            ticket_id=payload.ticket_id,
        )
        if _classify_valid(result.parsed):
            return ClassifyResponse(**result.parsed)

    raise HTTPException(status_code=422, detail="classification failed validation after retry")


def _parse_score(text: str | None) -> float:
    """The self-check prompt asks for a bare 0-1 number but LLMs sometimes wrap it in a
    sentence — extract the first numeric substring rather than requiring exact-float parsing,
    and clamp defensively in case the model returns something outside [0, 1]."""
    if not text:
        return 0.0
    match = re.search(r"[-+]?\d*\.?\d+", text)
    if not match:
        return 0.0
    return max(0.0, min(1.0, float(match.group())))


@router.post("/query", response_model=QueryResponse)
async def query(payload: QueryRequest) -> QueryResponse:
    """RAG pipeline: embed the question, retrieve top-k chunks, draft an answer grounded in
    them, then a separate self-check call scores how well-supported that answer actually is.
    Confidence blends retrieval similarity with the self-check score (SPEC §3.1) rather than
    trusting either signal alone — a good retrieval match with a hallucinated answer, or a poor
    match the model still fabricated confidently, should both score low."""
    pool = await db.get_pool()
    embed_result = await complete("embed", embed_text=payload.question)
    rows = await top_k_chunks(pool, embed_result.embedding)

    mean_similarity = sum(row["similarity"] for row in rows) / len(rows) if rows else 0.0
    context = "\n\n".join(
        f"[source: {row['title']}#{row['chunk_index']}]\n{row['content']}" for row in rows
    )

    answer_result = await complete(
        "answer",
        [
            {
                "role": "user",
                "content": f"Knowledge base excerpts:\n{context}\n\nQuestion: {payload.question}",
            }
        ],
        system=load_prompt("answer"),
        ticket_id=payload.ticket_id,
    )
    answer_text = answer_result.text or ""

    self_check_result = await complete(
        "self_check",
        [{"role": "user", "content": f"Excerpts:\n{context}\n\nDrafted answer:\n{answer_text}"}],
        system=load_prompt("self_check"),
        ticket_id=payload.ticket_id,
    )
    self_check_score = _parse_score(self_check_result.text)

    confidence = blend_confidence(mean_similarity, self_check_score)
    sources = [f"{row['title']}#{row['chunk_index']}" for row in rows]
    return QueryResponse(answer=answer_text, sources=sources, confidence=confidence)


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize(payload: SummarizeRequest) -> SummarizeResponse:
    result = await complete(
        "summarize",
        [{"role": "user", "content": f"Stats: {payload.stats}"}],
        system=load_prompt("digest"),
    )
    return SummarizeResponse(text=result.text or "")


@router.get("/stats", response_model=StatsResponse)
async def stats(hours: int | None = None) -> StatsResponse:
    """All-time aggregates by default; `?hours=N` scopes every aggregate to `created_at >= now()
    - N hours` instead (used by WF-5's daily digest, e.g. `?hours=24`). The WHERE clause is built
    conditionally — `tickets_where` is either empty or a full `WHERE ...` clause, and each
    per-column query below appends `AND <col> IS NOT NULL` after it, or starts its own `WHERE`
    if `tickets_where` was empty — so the same code path serves both the filtered and
    unfiltered case without duplicating every query."""
    pool = await db.get_pool()

    tickets_since = "created_at >= now() - ($1 * interval '1 hour')"
    calls_since = "created_at >= now() - ($1 * interval '1 hour')"
    ticket_args = [hours] if hours is not None else []
    call_args = [hours] if hours is not None else []
    tickets_where = f"WHERE {tickets_since}" if hours is not None else ""
    calls_where = f"WHERE {calls_since}" if hours is not None else ""

    status_rows = await pool.fetch(
        f"SELECT status, COUNT(*) AS count FROM tickets {tickets_where} GROUP BY status",
        *ticket_args,
    )
    tickets_by_status = {row["status"]: row["count"] for row in status_rows}
    total_tickets = sum(tickets_by_status.values())

    category_rows = await pool.fetch(
        f"""
        SELECT category, COUNT(*) AS count FROM tickets
        {tickets_where}{" AND" if tickets_where else "WHERE"} category IS NOT NULL
        GROUP BY category
        """,
        *ticket_args,
    )
    tickets_by_category = {row["category"]: row["count"] for row in category_rows}

    priority_rows = await pool.fetch(
        f"""
        SELECT priority, COUNT(*) AS count FROM tickets
        {tickets_where}{" AND" if tickets_where else "WHERE"} priority IS NOT NULL
        GROUP BY priority
        """,
        *ticket_args,
    )
    tickets_by_priority = {row["priority"]: row["count"] for row in priority_rows}

    auto_resolved = await pool.fetchval(
        f"SELECT COUNT(*) FROM tickets {tickets_where}"
        f"{' AND' if tickets_where else 'WHERE'} auto_resolved IS TRUE",
        *ticket_args,
    )
    auto_resolution_rate = (auto_resolved / total_tickets) if total_tickets else 0.0

    avg_confidence = await pool.fetchval(
        f"SELECT AVG(confidence) FROM tickets {tickets_where}"
        f"{' AND' if tickets_where else 'WHERE'} confidence IS NOT NULL",
        *ticket_args,
    )
    total_cost_usd = await pool.fetchval(
        f"SELECT COALESCE(SUM(cost_usd), 0) FROM llm_calls {calls_where}", *call_args
    )
    p95_latency_ms = await pool.fetchval(
        f"""
        SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)
        FROM llm_calls {calls_where}
        """,
        *call_args,
    )

    return StatsResponse(
        tickets_by_status=tickets_by_status,
        tickets_by_category=tickets_by_category,
        tickets_by_priority=tickets_by_priority,
        auto_resolution_rate=auto_resolution_rate,
        avg_confidence=float(avg_confidence) if avg_confidence is not None else None,
        total_cost_usd=float(total_cost_usd),
        p95_latency_ms=float(p95_latency_ms) if p95_latency_ms is not None else None,
    )


app.include_router(router)
