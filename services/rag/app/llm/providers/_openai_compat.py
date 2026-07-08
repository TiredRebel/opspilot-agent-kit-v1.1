"""Shared response-parsing for providers whose calls return OpenAI-shaped ChatCompletions."""

import time
from uuid import UUID

from app.llm.base import LLMResult, Purpose, _parse_json
from app.llm.ledger import Ledger
from app.llm.pricing import _cost


async def _complete_openai_compatible(
    call_fn,
    provider: str,
    model: str,
    purpose: Purpose,
    messages: list[dict[str, str]],
    schema: dict | None,
    system: str | None,
    ticket_id: str | UUID | None,
    ledger: Ledger,
) -> LLMResult:
    """Shared response-parsing for any provider whose call returns an OpenAI-shaped
    ChatCompletion object — OpenAI itself, and Ollama via its OpenAI-compatible endpoint."""
    start = time.monotonic()
    response = await call_fn(messages, schema, system)
    latency_ms = int((time.monotonic() - start) * 1000)
    tokens_in = response.usage.prompt_tokens
    tokens_out = response.usage.completion_tokens
    cost = _cost(model, tokens_in, tokens_out)
    text = response.choices[0].message.content
    parsed = _parse_json(text, schema)
    await ledger.record(
        ticket_id, purpose, provider, model, tokens_in, tokens_out, cost, latency_ms, True
    )
    return LLMResult(
        provider=provider,
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost,
        latency_ms=latency_ms,
        success=True,
        text=text,
        parsed=parsed,
    )
