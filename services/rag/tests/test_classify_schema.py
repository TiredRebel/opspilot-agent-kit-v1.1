from decimal import Decimal
from unittest.mock import AsyncMock

from app import main
from app.llm import LLMResult
from fastapi.testclient import TestClient


def _result(parsed: dict) -> LLMResult:
    return LLMResult(
        provider="fake",
        model="fake",
        tokens_in=1,
        tokens_out=1,
        cost_usd=Decimal("0"),
        latency_ms=1,
        success=True,
        text=str(parsed),
        parsed=parsed,
    )


def test_valid_json_passes(monkeypatch):
    monkeypatch.setattr(
        main,
        "complete",
        AsyncMock(
            return_value=_result(
                {"category": "billing", "priority": "high", "sentiment": "negative", "lang": "en"}
            )
        ),
    )
    with TestClient(main.app) as client:
        response = client.post(
            "/classify",
            json={
                "ticket_id": "11111111-1111-1111-1111-111111111111",
                "subject": "Invoice question",
                "body": "Why?",
            },
        )
    assert response.status_code == 200
    assert response.json() == {
        "category": "billing",
        "priority": "high",
        "sentiment": "negative",
        "lang": "en",
    }


def test_invalid_json_retries_exactly_once_then_422(monkeypatch):
    mock = AsyncMock(return_value=_result({"not": "a valid classification"}))
    monkeypatch.setattr(main, "complete", mock)
    with TestClient(main.app) as client:
        response = client.post(
            "/classify",
            json={"ticket_id": "22222222-2222-2222-2222-222222222222", "subject": "s", "body": "b"},
        )
    assert response.status_code == 422
    assert mock.await_count == 2
