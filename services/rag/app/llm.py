"""LLM provider layer (ADR-001) — the only module allowed to call an LLM or embedding API.

`complete()` is the single entry point: primary Claude Haiku, OpenAI mini-class fallback on
5xx/timeout/connection errors, deterministic `fake` provider for tests. Every attempt is logged
to `llm_calls`, and a daily budget guardrail runs before any provider call.
"""

import json
import random
import time
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

import anthropic
import openai

from app import db
from app.settings import settings

Purpose = Literal["classify", "answer", "self_check", "summarize", "embed"]

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Prompts are version-controlled files, never inline strings (AGENTS.md)."""
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


ANTHROPIC_MODEL = "claude-haiku-4-5"
OPENAI_MODEL = "gpt-5.4-mini"
OPENAI_EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536

# USD per 1M tokens: (input, output). Embedding models have no output tokens.
PRICING: dict[str, tuple[float, float]] = {
    ANTHROPIC_MODEL: (1.00, 5.00),
    OPENAI_MODEL: (0.75, 4.50),
    OPENAI_EMBED_MODEL: (0.02, 0.0),
}


class BudgetExceeded(Exception):
    """Today's LLM spend has hit DAILY_BUDGET_USD. Callers map this to HTTP 429."""


@dataclass
class LLMResult:
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: Decimal
    latency_ms: int
    success: bool
    text: str | None = None
    parsed: dict[str, Any] | None = None
    embedding: list[float] | None = None


def _cost(model: str, tokens_in: int, tokens_out: int) -> Decimal:
    price_in, price_out = PRICING[model]
    return Decimal(str(tokens_in / 1_000_000 * price_in + tokens_out / 1_000_000 * price_out))


async def _log(
    ticket_id: str | UUID | None,
    purpose: str,
    provider: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    cost_usd: Decimal,
    latency_ms: int,
    success: bool,
) -> None:
    pool = await db.get_pool()
    await pool.execute(
        """
        INSERT INTO llm_calls
            (ticket_id, purpose, provider, model,
             tokens_in, tokens_out, cost_usd, latency_ms, success)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """,
        ticket_id,
        purpose,
        provider,
        model,
        tokens_in,
        tokens_out,
        cost_usd,
        latency_ms,
        success,
    )


async def _check_budget() -> None:
    pool = await db.get_pool()
    spent = await pool.fetchval(
        "SELECT COALESCE(SUM(cost_usd), 0) FROM llm_calls WHERE created_at::date = CURRENT_DATE"
    )
    if float(spent) >= settings.daily_budget_usd:
        raise BudgetExceeded(
            f"daily budget ${settings.daily_budget_usd:.2f} exceeded (spent ${spent})"
        )


def _fake_embedding(text: str) -> list[float]:
    seed = int(sha256(text.encode()).hexdigest(), 16)
    rng = random.Random(seed)
    return [rng.uniform(-1, 1) for _ in range(EMBED_DIM)]


def _fake_result(purpose: Purpose, embed_text: str | None) -> LLMResult:
    if purpose == "embed":
        return LLMResult(
            provider="fake",
            model="fake",
            tokens_in=0,
            tokens_out=0,
            cost_usd=Decimal("0"),
            latency_ms=0,
            success=True,
            embedding=_fake_embedding(embed_text or ""),
        )
    if purpose == "classify":
        parsed = {
            "category": "technical",
            "priority": "normal",
            "sentiment": "neutral",
            "lang": "en",
        }
        return LLMResult(
            provider="fake",
            model="fake",
            tokens_in=10,
            tokens_out=10,
            cost_usd=Decimal("0"),
            latency_ms=1,
            success=True,
            text=json.dumps(parsed),
            parsed=parsed,
        )
    if purpose == "self_check":
        return LLMResult(
            provider="fake",
            model="fake",
            tokens_in=10,
            tokens_out=5,
            cost_usd=Decimal("0"),
            latency_ms=1,
            success=True,
            text="0.9",
        )
    if purpose == "answer":
        return LLMResult(
            provider="fake",
            model="fake",
            tokens_in=10,
            tokens_out=20,
            cost_usd=Decimal("0"),
            latency_ms=1,
            success=True,
            text="This is a fake grounded answer.",
        )
    if purpose == "summarize":
        return LLMResult(
            provider="fake",
            model="fake",
            tokens_in=10,
            tokens_out=20,
            cost_usd=Decimal("0"),
            latency_ms=1,
            success=True,
            text="Фейковий підсумок дня.",
        )
    raise ValueError(f"unknown purpose: {purpose}")


def _anthropic_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


def _openai_client() -> openai.AsyncOpenAI:
    return openai.AsyncOpenAI(api_key=settings.openai_api_key)


async def _call_anthropic(messages: list[dict[str, str]], schema: dict | None, system: str | None):
    """Raw call, isolated so tests can monkeypatch it to simulate 5xx/timeout/connection errors."""
    kwargs: dict[str, Any] = {}
    if schema is not None:
        kwargs["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
    return await _anthropic_client().messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1024,
        system=system or anthropic.NOT_GIVEN,
        messages=messages,
        **kwargs,
    )


async def _call_openai(messages: list[dict[str, str]], schema: dict | None, system: str | None):
    """Raw call, isolated so tests can monkeypatch it."""
    kwargs: dict[str, Any] = {}
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
    return await _openai_client().embeddings.create(model=OPENAI_EMBED_MODEL, input=text)


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code >= 500
    return isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError))


async def _embed(text: str, ticket_id: str | UUID | None) -> LLMResult:
    start = time.monotonic()
    response = await _call_openai_embed(text)
    latency_ms = int((time.monotonic() - start) * 1000)
    tokens_in = response.usage.total_tokens
    cost = _cost(OPENAI_EMBED_MODEL, tokens_in, 0)
    await _log(
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
        embedding=list(response.data[0].embedding),
    )


async def _fallback_openai(
    purpose: Purpose,
    messages: list[dict[str, str]],
    schema: dict | None,
    system: str | None,
    ticket_id: str | UUID | None,
) -> LLMResult:
    start = time.monotonic()
    response = await _call_openai(messages, schema, system)
    latency_ms = int((time.monotonic() - start) * 1000)
    tokens_in = response.usage.prompt_tokens
    tokens_out = response.usage.completion_tokens
    cost = _cost(OPENAI_MODEL, tokens_in, tokens_out)
    text = response.choices[0].message.content
    parsed = json.loads(text) if schema is not None and text else None
    await _log(
        ticket_id, purpose, "openai", OPENAI_MODEL, tokens_in, tokens_out, cost, latency_ms, True
    )
    return LLMResult(
        provider="openai",
        model=OPENAI_MODEL,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost,
        latency_ms=latency_ms,
        success=True,
        text=text,
        parsed=parsed,
    )


async def _complete_chat(
    purpose: Purpose,
    messages: list[dict[str, str]],
    schema: dict | None,
    system: str | None,
    ticket_id: str | UUID | None,
) -> LLMResult:
    start = time.monotonic()
    try:
        response = await _call_anthropic(messages, schema, system)
    except (
        anthropic.APIStatusError,
        anthropic.APIConnectionError,
        anthropic.APITimeoutError,
    ) as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        await _log(
            ticket_id, purpose, "anthropic", ANTHROPIC_MODEL, 0, 0, Decimal("0"), latency_ms, False
        )
        if not _is_retryable(exc):
            raise
        return await _fallback_openai(purpose, messages, schema, system, ticket_id)

    latency_ms = int((time.monotonic() - start) * 1000)
    tokens_in = response.usage.input_tokens
    tokens_out = response.usage.output_tokens
    cost = _cost(ANTHROPIC_MODEL, tokens_in, tokens_out)
    text = next((b.text for b in response.content if b.type == "text"), None)
    parsed = json.loads(text) if schema is not None and text else None
    await _log(
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


async def complete(
    purpose: Purpose,
    messages: list[dict[str, str]] | None = None,
    *,
    schema: dict[str, Any] | None = None,
    system: str | None = None,
    ticket_id: str | UUID | None = None,
    embed_text: str | None = None,
) -> LLMResult:
    if settings.llm_provider == "fake":
        result = _fake_result(purpose, embed_text)
        await _log(
            ticket_id,
            purpose,
            result.provider,
            result.model,
            result.tokens_in,
            result.tokens_out,
            result.cost_usd,
            result.latency_ms,
            result.success,
        )
        return result

    await _check_budget()

    if purpose == "embed":
        return await _embed(embed_text or "", ticket_id)

    return await _complete_chat(purpose, messages or [], schema, system, ticket_id)
