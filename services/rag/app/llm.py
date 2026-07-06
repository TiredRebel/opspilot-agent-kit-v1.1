"""LLM provider layer (ADR-001) — the only module allowed to call an LLM or embedding API.

`complete()` dispatches on `settings.llm_provider`. Only `anthropic` has a fallback chain
(-> OpenAI on 5xx/timeout/connection errors, the original ADR-001 design); `openai`, `gemini`,
and `ollama` each run standalone with no fallback of their own. `fake` is deterministic for
tests. Every attempt is logged to `llm_calls`, and a daily budget guardrail runs before any
non-fake provider call.
"""

import asyncio
import json
import random
import re
import time
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

import anthropic
import httpx
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
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_EMBED_MODEL = "gemini-embedding-001"
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
# Every embedding path must return exactly this many dimensions — kb_chunks.embedding is a
# frozen `vector(1536)` column (gotcha #5). Gemini's embedding model natively supports requesting
# this dimension via `outputDimensionality` (Matryoshka-trained, verified live); Ollama has no
# such control, so `_embed()` asserts the returned length rather than silently corrupting rows.
EMBED_DIM = 1536

# USD per 1M tokens: (input, output). Embedding models have no output tokens. Gemini's output
# price covers "thinking" tokens too (billed as output, per Google's pricing page) — `_complete_
# gemini` folds thinking into tokens_out accordingly. Ollama models aren't listed here: `_cost`
# treats any unlisted model as free (local inference has no per-token API cost).
PRICING: dict[str, tuple[float, float]] = {
    ANTHROPIC_MODEL: (1.00, 5.00),
    OPENAI_MODEL: (0.75, 4.50),
    OPENAI_EMBED_MODEL: (0.02, 0.0),
    GEMINI_MODEL: (0.30, 2.50),
    GEMINI_EMBED_MODEL: (0.15, 0.0),
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


_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)


def _parse_json(text: str | None, schema: dict | None) -> dict | None:
    """Parse structured-output text, tolerating a model that wraps valid JSON in markdown code
    fences despite an explicit schema + `strict: true` instruction not to (seen live with
    minimax-m3:cloud via Ollama — not every provider's "strict" mode is actually strict). Returns
    None rather than raising on anything unparseable, so callers retry/422 cleanly instead of
    crashing with an unhandled JSONDecodeError."""
    if schema is None or not text:
        return None
    match = _JSON_FENCE_RE.match(text.strip())
    candidate = match.group(1) if match else text
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _cost(model: str, tokens_in: int, tokens_out: int) -> Decimal:
    # Unlisted models (Ollama, local) have no per-token API price — treat as free rather than
    # raising, so a locally-run model doesn't need a fake PRICING entry just to log a call.
    if model not in PRICING:
        return Decimal("0")
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


def _ollama_client() -> openai.AsyncOpenAI:
    """Ollama exposes an OpenAI-compatible chat/embeddings API, so we reuse the OpenAI SDK
    pointed at the local server instead of a separate client library. Ollama doesn't check the
    api_key, but the SDK requires a non-empty string.

    If `ollama_api_key` is set, talk to ollama.com's hosted endpoint directly with that key as
    the bearer token instead — the local daemon's proxying of `:cloud` models is gated behind a
    separate ollama.com subscription plan, but a personal API key works against the hosted API
    on its own (pay-per-token), independent of that plan."""
    if settings.ollama_api_key:
        return openai.AsyncOpenAI(base_url="https://ollama.com/v1", api_key=settings.ollama_api_key)
    return openai.AsyncOpenAI(base_url=f"{settings.ollama_base_url}/v1", api_key="ollama")


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


async def _call_ollama(messages: list[dict[str, str]], schema: dict | None, system: str | None):
    """Raw call, isolated so tests can monkeypatch it. Ollama's OpenAI-compatible endpoint takes
    the same request shape as `_call_openai`. `max_tokens` is set generously (not the 1024 used
    for Anthropic/OpenAI): reasoning-style local models emit a long internal "thinking" trace
    before the final JSON, and without enough headroom the response gets cut off mid-generation,
    producing truncated, unparseable JSON — not a schema-compliance failure but a token-budget
    one, and easy to mistake for the model just being wrong."""
    kwargs: dict[str, Any] = {}
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


def _to_gemini_schema(schema: dict) -> dict:
    """Gemini's structured-output schema is a JSON-Schema subset with UPPERCASE type names and
    no `additionalProperties` support — convert our JSON-Schema dicts (e.g. CLASSIFY_SCHEMA in
    schemas.py) rather than hand-maintaining a second schema per shape. Verified against the live
    API this session (lowercase types are rejected)."""
    converted: dict[str, Any] = {}
    for key, value in schema.items():
        if key == "additionalProperties":
            continue
        if key == "type":
            converted["type"] = value.upper()
        elif key == "properties":
            converted["properties"] = {k: _to_gemini_schema(v) for k, v in value.items()}
        elif key == "items":
            converted["items"] = _to_gemini_schema(value)
        else:
            converted[key] = value
    return converted


_GEMINI_MAX_RETRIES = 3
_GEMINI_RETRY_AFTER_RE = re.compile(r"retry in ([\d.]+)s")


async def _post_gemini_with_retry(url: str, body: dict) -> dict:
    """Google's free tier is rate-limited as low as 5 req/min for gemini-2.5-flash — the 429
    body names the exact wait in its message text (no Retry-After header), so we parse and honor
    it rather than guessing a fixed backoff (SPEC §4.1: retry with backoff on all HTTP hops)."""
    for attempt in range(_GEMINI_MAX_RETRIES + 1):
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, params={"key": settings.gemini_api_key}, json=body)
        if response.status_code != 429 or attempt == _GEMINI_MAX_RETRIES:
            response.raise_for_status()
            return response.json()
        message = response.json().get("error", {}).get("message", "")
        match = _GEMINI_RETRY_AFTER_RE.search(message)
        delay = float(match.group(1)) + 1 if match else 15.0
        await asyncio.sleep(delay)
    raise AssertionError("unreachable")  # loop always returns or raises on the last attempt


async def _call_gemini(messages: list[dict[str, str]], schema: dict | None, system: str | None):
    """Isolated so tests can monkeypatch it. Uses the plain REST API via httpx rather than a
    Google SDK — request/response shape verified empirically against the live API this session
    (structured JSON output, usage metadata field names)."""
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
        for m in messages
    ]
    body: dict[str, Any] = {"contents": contents}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if schema is not None:
        body["generationConfig"] = {
            "responseMimeType": "application/json",
            "responseSchema": _to_gemini_schema(schema),
        }
    return await _post_gemini_with_retry(
        f"{GEMINI_API_BASE}/models/{GEMINI_MODEL}:generateContent", body
    )


async def _call_openai_embed(text: str):
    return await _openai_client().embeddings.create(model=OPENAI_EMBED_MODEL, input=text)


async def _call_ollama_embed(text: str):
    """Untested against a live server in this environment — verify locally. Ollama exposes an
    OpenAI-compatible /v1/embeddings endpoint for models pulled with embedding support (the
    configured chat model, e.g. a Qwen variant, is not itself an embedding model — set
    OLLAMA_EMBED_MODEL to one that is, e.g. `nomic-embed-text`)."""
    return await _ollama_client().embeddings.create(model=settings.ollama_embed_model, input=text)


async def _call_gemini_embed(text: str):
    """Requests EMBED_DIM natively via `outputDimensionality` (Matryoshka-trained model, verified
    live) rather than truncating a larger vector after the fact."""
    return await _post_gemini_with_retry(
        f"{GEMINI_API_BASE}/models/{GEMINI_EMBED_MODEL}:embedContent",
        {"content": {"parts": [{"text": text}]}, "outputDimensionality": EMBED_DIM},
    )


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code >= 500
    return isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError))


async def _embed(text: str, ticket_id: str | UUID | None) -> LLMResult:
    """Anthropic has no native embeddings API, so `anthropic` mode (like `openai` mode) still
    uses OpenAI for this step only — unchanged from the original ADR-001 design. `gemini` and
    `ollama` use their own embedding model. Every path is dimension-checked against EMBED_DIM
    before returning, since a mismatch would silently corrupt the frozen `vector(1536)` column."""
    provider = settings.llm_provider
    start = time.monotonic()

    if provider == "gemini":
        data = await _call_gemini_embed(text)
        embedding = data["embedding"]["values"]
        # embedContent doesn't return token usage — approximate at ~4 chars/token (rough
        # English-text average) purely for cost-tracking visibility, not billing precision.
        tokens_in = max(1, len(text) // 4)
        model, api_provider = GEMINI_EMBED_MODEL, "gemini"
    elif provider == "ollama":
        response = await _call_ollama_embed(text)
        embedding = list(response.data[0].embedding)
        tokens_in = response.usage.total_tokens
        model, api_provider = settings.ollama_embed_model, "ollama"
    else:
        response = await _call_openai_embed(text)
        embedding = list(response.data[0].embedding)
        tokens_in = response.usage.total_tokens
        model, api_provider = OPENAI_EMBED_MODEL, "openai"

    if len(embedding) != EMBED_DIM:
        raise ValueError(
            f"{api_provider}/{model} returned a {len(embedding)}-dim embedding, expected "
            f"{EMBED_DIM} (schema is frozen at vector(1536) — gotcha #5)"
        )

    latency_ms = int((time.monotonic() - start) * 1000)
    cost = _cost(model, tokens_in, 0)
    await _log(ticket_id, "embed", api_provider, model, tokens_in, 0, cost, latency_ms, True)
    return LLMResult(
        provider=api_provider,
        model=model,
        tokens_in=tokens_in,
        tokens_out=0,
        cost_usd=cost,
        latency_ms=latency_ms,
        success=True,
        embedding=embedding,
    )


async def _complete_openai_compatible(
    call_fn,
    provider: str,
    model: str,
    purpose: Purpose,
    messages: list[dict[str, str]],
    schema: dict | None,
    system: str | None,
    ticket_id: str | UUID | None,
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
    await _log(ticket_id, purpose, provider, model, tokens_in, tokens_out, cost, latency_ms, True)
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


async def _complete_gemini(
    purpose: Purpose,
    messages: list[dict[str, str]],
    schema: dict | None,
    system: str | None,
    ticket_id: str | UUID | None,
) -> LLMResult:
    start = time.monotonic()
    data = await _call_gemini(messages, schema, system)
    latency_ms = int((time.monotonic() - start) * 1000)
    usage = data.get("usageMetadata", {})
    tokens_in = usage.get("promptTokenCount", 0)
    total_tokens = usage.get("totalTokenCount", tokens_in)
    # Gemini bills "thinking" tokens as output (per Google's pricing page) but reports them in a
    # separate thoughtsTokenCount field alongside candidatesTokenCount — totalTokenCount minus
    # promptTokenCount captures both together without depending on thoughtsTokenCount always
    # being present (it's only set for models that actually used extended thinking).
    tokens_out = total_tokens - tokens_in
    cost = _cost(GEMINI_MODEL, tokens_in, tokens_out)
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    parsed = _parse_json(text, schema)
    await _log(
        ticket_id, purpose, "gemini", GEMINI_MODEL, tokens_in, tokens_out, cost, latency_ms, True
    )
    return LLMResult(
        provider="gemini",
        model=GEMINI_MODEL,
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
        return await _complete_openai_compatible(
            _call_openai, "openai", OPENAI_MODEL, purpose, messages, schema, system, ticket_id
        )

    latency_ms = int((time.monotonic() - start) * 1000)
    tokens_in = response.usage.input_tokens
    tokens_out = response.usage.output_tokens
    cost = _cost(ANTHROPIC_MODEL, tokens_in, tokens_out)
    text = next((b.text for b in response.content if b.type == "text"), None)
    parsed = _parse_json(text, schema)
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

    provider = settings.llm_provider
    messages = messages or []
    if provider == "anthropic":
        return await _complete_chat(purpose, messages, schema, system, ticket_id)
    if provider == "openai":
        return await _complete_openai_compatible(
            _call_openai, "openai", OPENAI_MODEL, purpose, messages, schema, system, ticket_id
        )
    if provider == "gemini":
        return await _complete_gemini(purpose, messages, schema, system, ticket_id)
    if provider == "ollama":
        return await _complete_openai_compatible(
            _call_ollama,
            "ollama",
            settings.ollama_model,
            purpose,
            messages,
            schema,
            system,
            ticket_id,
        )
    raise ValueError(f"unknown llm_provider: {provider!r}")
