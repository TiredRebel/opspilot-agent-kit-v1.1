"""Anthropic provider — the only one with a fallback chain (-> OpenAI on 5xx/timeout/connection
errors, the original ADR-001 design). Embeddings delegate to the OpenAI embed path: Anthropic
has no native embeddings API."""

import logging
import time
from decimal import Decimal
from uuid import UUID

import anthropic

from app.llm.base import LLMResult, Purpose, _parse_json
from app.llm.ledger import Ledger
from app.llm.pricing import ANTHROPIC_MODEL, _cost
from app.llm.providers import openai as openai_provider
from app.logging_setup import kv
from app.settings import settings

logger = logging.getLogger("app.llm.providers.anthropic")


def _anthropic_client() -> anthropic.AsyncAnthropic:
    """Build an Anthropic client using the configured API key."""
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


async def _call_anthropic(messages: list[dict[str, str]], schema: dict | None, system: str | None):
    """Raw call, isolated so tests can monkeypatch it to simulate 5xx/timeout/connection errors."""
    kwargs: dict = {}
    if schema is not None:
        kwargs["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
    return await _anthropic_client().messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1024,
        system=system or anthropic.NOT_GIVEN,
        messages=messages,
        **kwargs,
    )


def _is_retryable(exc: Exception) -> bool:
    """True if `exc` is a 5xx/timeout/connection error that should trigger the OpenAI fallback."""
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code >= 500
    return isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError))


async def chat(
    purpose: Purpose,
    messages: list[dict[str, str]],
    schema: dict | None,
    system: str | None,
    ticket_id: str | UUID | None,
    ledger: Ledger,
) -> LLMResult:
    """Call Anthropic, falling back to OpenAI once on a retryable error (ADR-001)."""
    start = time.monotonic()
    try:
        response = await _call_anthropic(messages, schema, system)
    except (
        anthropic.APIStatusError,
        anthropic.APIConnectionError,
        anthropic.APITimeoutError,
    ) as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        await ledger.record(
            ticket_id, purpose, "anthropic", ANTHROPIC_MODEL, 0, 0, Decimal("0"), latency_ms, False
        )
        if not _is_retryable(exc):
            raise
        logger.warning(
            kv(
                "anthropic call failed with retryable error — falling back to openai (ADR-001)",
                error=type(exc).__name__,
                purpose=purpose,
                ticket_id=ticket_id,
            )
        )
        return await openai_provider.chat(purpose, messages, schema, system, ticket_id, ledger)

    latency_ms = int((time.monotonic() - start) * 1000)
    tokens_in = response.usage.input_tokens
    tokens_out = response.usage.output_tokens
    cost = _cost(ANTHROPIC_MODEL, tokens_in, tokens_out)
    text = next((b.text for b in response.content if b.type == "text"), None)
    parsed = _parse_json(text, schema)
    await ledger.record(
        ticket_id,
        purpose,
        "anthropic",
        ANTHROPIC_MODEL,
        tokens_in,
        tokens_out,
        cost,
        latency_ms,
        True,
    )
    return LLMResult(
        provider="anthropic",
        model=ANTHROPIC_MODEL,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost,
        latency_ms=latency_ms,
        success=True,
        text=text,
        parsed=parsed,
    )


async def embed(text: str, ticket_id: str | UUID | None, ledger: Ledger) -> LLMResult:
    """Anthropic has no embeddings API — `anthropic` mode uses the OpenAI embed path (ADR-001)."""
    return await openai_provider.embed(text, ticket_id, ledger)
