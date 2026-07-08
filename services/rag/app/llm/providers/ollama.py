"""Ollama provider — reuses the OpenAI SDK against Ollama's OpenAI-compatible API, pointed at
either the local daemon or ollama.com's hosted endpoint depending on configuration."""

import time
from uuid import UUID

import openai

from app.llm.base import LLMResult, Purpose, _check_embed_dim
from app.llm.ledger import Ledger
from app.llm.pricing import _cost
from app.llm.providers._openai_compat import _complete_openai_compatible
from app.settings import settings


def _ollama_client() -> openai.AsyncOpenAI:
    """Ollama exposes an OpenAI-compatible chat/embeddings API, so we reuse the OpenAI SDK instead
    of a separate client library, pointed at one of two targets.

    Default: the local daemon (`ollama_base_url`) — it doesn't check `api_key` at all, but the SDK
    requires a non-empty string, hence the placeholder `"ollama"` value.

    If `ollama_api_key` is set, talk to ollama.com's hosted endpoint directly with that key as a
    real bearer token instead — the local daemon's proxying of `:cloud` models is gated behind a
    separate ollama.com subscription plan, but a personal API key works against the hosted API on
    its own (pay-per-token), independent of that plan."""
    if settings.ollama_api_key:
        return openai.AsyncOpenAI(base_url="https://ollama.com/v1", api_key=settings.ollama_api_key)
    return openai.AsyncOpenAI(base_url=f"{settings.ollama_base_url}/v1", api_key="ollama")


async def _call_ollama(messages: list[dict[str, str]], schema: dict | None, system: str | None):
    """Raw call, isolated so tests can monkeypatch it. Ollama's OpenAI-compatible endpoint takes
    the same request shape as `_call_openai`. `max_tokens` is set generously (not the 1024 used
    for Anthropic/OpenAI): reasoning-style local models emit a long internal "thinking" trace
    before the final JSON, and without enough headroom the response gets cut off mid-generation,
    producing truncated, unparseable JSON — not a schema-compliance failure but a token-budget
    one, and easy to mistake for the model just being wrong."""
    kwargs: dict = {}
    if schema is not None:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "response", "schema": schema, "strict": True},
        }
    full_messages = ([{"role": "system", "content": system}] if system else []) + messages
    return await _ollama_client().chat.completions.create(
        model=settings.ollama_model,
        messages=full_messages,
        max_tokens=8192,
        **kwargs,
    )


async def _call_ollama_embed(text: str):
    """Untested against a live server in this environment — verify locally. Ollama exposes an
    OpenAI-compatible /v1/embeddings endpoint for models pulled with embedding support (the
    configured chat model, e.g. a Qwen variant, is not itself an embedding model — set
    OLLAMA_EMBED_MODEL to one that is, e.g. `nomic-embed-text`)."""
    return await _ollama_client().embeddings.create(model=settings.ollama_embed_model, input=text)


async def chat(
    purpose: Purpose,
    messages: list[dict[str, str]],
    schema: dict | None,
    system: str | None,
    ticket_id: str | UUID | None,
    ledger: Ledger,
) -> LLMResult:
    """Ollama chat completion, normalized via the shared OpenAI-compatible parser."""
    return await _complete_openai_compatible(
        _call_ollama,
        "ollama",
        settings.ollama_model,
        purpose,
        messages,
        schema,
        system,
        ticket_id,
        ledger,
    )


async def embed(text: str, ticket_id: str | UUID | None, ledger: Ledger) -> LLMResult:
    """Embed via Ollama, dimension-checked against the frozen vector(1536) column."""
    start = time.monotonic()
    response = await _call_ollama_embed(text)
    embedding = list(response.data[0].embedding)
    tokens_in = response.usage.total_tokens
    _check_embed_dim(embedding, "ollama", settings.ollama_embed_model)
    latency_ms = int((time.monotonic() - start) * 1000)
    cost = _cost(settings.ollama_embed_model, tokens_in, 0)
    await ledger.record(
        ticket_id,
        "embed",
        "ollama",
        settings.ollama_embed_model,
        tokens_in,
        0,
        cost,
        latency_ms,
        True,
    )
    return LLMResult(
        provider="ollama",
        model=settings.ollama_embed_model,
        tokens_in=tokens_in,
        tokens_out=0,
        cost_usd=cost,
        latency_ms=latency_ms,
        success=True,
        embedding=embedding,
    )
