import pytest
from app import llm, main
from app.llm.providers import anthropic as anthropic_provider
from app.llm.providers import openai as openai_provider
from app.settings import settings
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _non_fake_provider(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(settings, "daily_budget_usd", 1.0)


async def test_budget_exceeded_raises_without_calling_a_provider(pool, monkeypatch):
    await pool.execute(
        """
        INSERT INTO llm_calls
            (purpose, provider, model, tokens_in, tokens_out, cost_usd, latency_ms, success)
        VALUES ('classify', 'anthropic', 'claude-haiku-4-5', 0, 0, 1.50, 10, true)
        """
    )

    called = False

    async def should_not_be_called(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("provider must not be called once the daily budget is exceeded")

    monkeypatch.setattr(anthropic_provider, "_call_anthropic", should_not_be_called)
    monkeypatch.setattr(openai_provider, "_call_openai", should_not_be_called)

    with pytest.raises(llm.BudgetExceeded):
        await llm.complete("classify", [{"role": "user", "content": "hi"}])

    assert called is False


def test_endpoint_returns_429_on_budget_exceeded(monkeypatch):
    async def raise_budget_exceeded(*args, **kwargs):
        raise llm.BudgetExceeded("daily budget $1.00 exceeded (spent $1.50)")

    monkeypatch.setattr(main, "complete", raise_budget_exceeded)
    with TestClient(main.app) as client:
        response = client.post(
            "/classify",
            json={"ticket_id": "11111111-1111-1111-1111-111111111111", "subject": "s", "body": "b"},
        )
    assert response.status_code == 429
