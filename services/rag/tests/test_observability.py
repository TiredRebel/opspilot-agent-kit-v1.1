"""Tests for the structured-logging / meaningful-messages pass (service-observability spec).

The app logger has propagate=False (so uvicorn/root handlers can't double-print), which means
pytest's root-attached caplog handler won't see its records — the autouse fixture below attaches
caplog's handler to the `app` logger directly."""

import logging
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from app import db, llm, main
from app.llm import LLMResult
from app.logging_setup import setup_logging
from app.settings import settings
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _capture_app_logs(caplog):
    # setup_logging first (idempotent): it sets propagate=False, without which a record would
    # be captured twice when this file runs before any TestClient has triggered the lifespan
    # (once via this handler, once via propagation to caplog's root handler).
    setup_logging("INFO")
    logger = logging.getLogger("app")
    logger.addHandler(caplog.handler)
    yield
    logger.removeHandler(caplog.handler)


def _invalid_result() -> LLMResult:
    return LLMResult(
        provider="ollama",
        model="test-model",
        tokens_in=1,
        tokens_out=1,
        cost_usd=Decimal("0"),
        latency_ms=1,
        success=True,
        text="{}",
        parsed={"category": "billing", "sentiment": "neutral"},  # missing priority, lang
    )


async def test_empty_kb_query_short_circuits(pool, caplog):
    with TestClient(main.app) as client:
        response = client.post("/query", json={"question": "What is the refund policy?"})

    assert response.status_code == 200
    body = response.json()
    assert body["sources"] == []
    assert body["confidence"] == 0.0
    assert "kb/ingest" in body["answer"]

    # Only the embed call ran — no answer/self_check drafting from an empty context.
    purposes = [row["purpose"] for row in await pool.fetch("SELECT purpose FROM llm_calls")]
    assert "answer" not in purposes
    assert "self_check" not in purposes
    assert any("zero KB chunks" in record.message for record in caplog.records)


def test_classify_422_detail_names_what_failed(monkeypatch):
    mock = AsyncMock(return_value=_invalid_result())
    monkeypatch.setattr(main, "complete", mock)
    with TestClient(main.app) as client:
        response = client.post(
            "/classify",
            json={"ticket_id": "33333333-3333-3333-3333-333333333333", "subject": "s", "body": "b"},
        )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "2 attempts" in detail
    assert "provider=ollama" in detail
    assert "model=test-model" in detail
    assert "lang" in detail and "priority" in detail
    assert mock.await_count == 2


def test_health_db_down_names_error_class(monkeypatch):
    async def broken_pool():
        raise RuntimeError("boom")

    monkeypatch.setattr(db, "get_pool", broken_pool)
    with TestClient(main.app) as client:
        response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["db"] is False
    assert body["error"] == "RuntimeError"


async def test_llm_attempt_emits_info_record(pool, caplog):
    await llm.complete("classify", [{"role": "user", "content": "hi"}])
    attempt_records = [r.message for r in caplog.records if "llm attempt" in r.message]
    assert len(attempt_records) == 1
    assert "provider=fake" in attempt_records[0]
    assert "purpose=classify" in attempt_records[0]
    assert "success=True" in attempt_records[0]


async def test_unknown_provider_lists_valid_options(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "nope")
    with pytest.raises(ValueError, match="anthropic, fake, gemini, ollama, openai"):
        await llm.complete("classify", [{"role": "user", "content": "hi"}])
