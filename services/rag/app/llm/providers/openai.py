"""OpenAI provider — chat completions and the shared 1536-dim embedding path.

The embed path here also serves `anthropic` mode (no native Anthropic embeddings API — the
anthropic provider delegates to it, unchanged from the original ADR-001 design)."""

import time
from uuid import UUID

import openai

from app.llm.base import LLMResult, Purpose, _check_embed_dim
from app.llm.ledger import Ledger
from app.llm.pricing import OPENAI_EMBED_MODEL, OPENAI_MODEL, _cost
from app.llm.providers._openai_compat import _complete_openai_compatible
from app.settings import settings


def _openai_client() -> openai.AsyncOpenAI:
    """Build an OpenAI client using the configured API key."""
    return openai.AsyncOpenAI(api_key=settings.openai_api_key)


async def _call_openai(messages: list[dict[str, str]], schema: dict | None, system: str | None):
    """Raw call, isolated so tests can monkeypatch it."""
    kwargs: dict = {}
    if schema is not None:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "response", "schema": schema, "strict": True},
        }
    full_messages = ([{"role": "system", "content": system}] if system else []) + messages
    return await _openai_client().chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=1024,
        messages=full_messages,
        **kwargs,
    )


async def _call_openai_embed(text: str):
    """Raw OpenAI embeddings call, isolated so tests can monkeypatch it."""
    return await _openai_client().embeddings.create(model=OPENAI_EMBED_MODEL, input=text)


async def chat(
    purpose: Purpose,
    messages: list[dict[str, str]],
    schema: dict | None,
    system: str | None,
    ticket_id: str | UUID | None,
    ledger: Ledger,
) -> LLMResult:
    """OpenAI chat completion, normalized via the shared OpenAI-compatible parser."""
    return await _complete_openai_compatible(
        _call_openai, "openai", OPENAI_MODEL, purpose, messages, schema, system, ticket_id, ledger
    )


async def embed(text: str, ticket_id: str | UUID | None, ledger: Ledger) -> LLMResult:
    """Embed via OpenAI, dimension-checked against the frozen vector(1536) column."""
    start = time.monotonic()
    response = await _call_openai_embed(text)
    embedding = list(response.data[0].embedding)
    tokens_in = response.usage.total_tokens
    _check_embed_dim(embedding, "openai", OPENAI_EMBED_MODEL)
    latency_ms = int((time.monotonic() - start) * 1000)
    cost = _cost(OPENAI_EMBED_MODEL, tokens_in, 0)
    await ledger.record(
        ticket_id, "embed", "openai", OPENAI_EMBED_MODEL, tokens_in, 0, cost, latency_ms, True
    )
    return LLMResult(
        provider="openai",
        model=OPENAI_EMBED_MODEL,
        tokens_in=tokens_in,
        tokens_out=0,
        cost_usd=cost,
        latency_ms=latency_ms,
        success=True,
        embedding=embedding,
    )
