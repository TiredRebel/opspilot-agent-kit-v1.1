from types import SimpleNamespace

import anthropic
import httpx
import pytest
from app import llm
from app.settings import settings


@pytest.fixture(autouse=True)
def _non_fake_provider(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(settings, "daily_budget_usd", 1000.0)


async def test_primary_5xx_falls_back_once_and_logs_both_attempts(pool, monkeypatch):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status_code=529, request=request)
    error = anthropic.APIStatusError("overloaded", response=response, body=None)

    async def failing_anthropic(*args, **kwargs):
        raise error

    openai_response = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=12, completion_tokens=8),
        choices=[SimpleNamespace(message=SimpleNamespace(content="fallback answer"))],
    )
    openai_calls = 0

    async def fake_openai(*args, **kwargs):
        nonlocal openai_calls
        openai_calls += 1
        return openai_response

    monkeypatch.setattr(llm, "_call_anthropic", failing_anthropic)
    monkeypatch.setattr(llm, "_call_openai", fake_openai)

    result = await llm.complete("answer", [{"role": "user", "content": "hi"}])

    assert openai_calls == 1
    assert result.provider == "openai"
    assert result.text == "fallback answer"

    rows = await pool.fetch("SELECT provider, success FROM llm_calls ORDER BY created_at, provider")
    assert [dict(row) for row in rows] == [
        {"provider": "anthropic", "success": False},
        {"provider": "openai", "success": True},
    ]


async def test_primary_4xx_does_not_fall_back(monkeypatch):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status_code=400, request=request)
    error = anthropic.APIStatusError("bad request", response=response, body=None)

    async def failing_anthropic(*args, **kwargs):
        raise error

    async def should_not_be_called(*args, **kwargs):
        raise AssertionError("OpenAI fallback should not be called on a non-retryable 4xx")

    monkeypatch.setattr(llm, "_call_anthropic", failing_anthropic)
    monkeypatch.setattr(llm, "_call_openai", should_not_be_called)

    with pytest.raises(anthropic.APIStatusError):
        await llm.complete("answer", [{"role": "user", "content": "hi"}])
