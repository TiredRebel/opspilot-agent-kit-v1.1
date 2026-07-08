"""Gemini provider — plain REST via httpx (no Google SDK), with schema conversion and
rate-limit-aware retry. Request/response shapes were verified empirically against the live API
(structured JSON output, usage metadata field names)."""

import asyncio
import re
import time
from typing import Any
from uuid import UUID

import httpx

from app.llm.base import EMBED_DIM, LLMResult, Purpose, _check_embed_dim, _parse_json
from app.llm.ledger import Ledger
from app.llm.pricing import GEMINI_EMBED_MODEL, GEMINI_MODEL, _cost
from app.settings import settings

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"

_GEMINI_MAX_RETRIES = 3
_GEMINI_RETRY_AFTER_RE = re.compile(r"retry in ([\d.]+)s")


def _to_gemini_schema(schema: dict) -> dict:
    """Gemini's structured-output schema is a JSON-Schema subset with UPPERCASE type names and
    no `additionalProperties` support — convert our JSON-Schema dicts (e.g. CLASSIFY_SCHEMA in
    schemas.py) rather than hand-maintaining a second schema per shape. Verified against the live
    API (lowercase types are rejected)."""
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
    """Raw call, isolated so tests can monkeypatch it."""
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


async def _call_gemini_embed(text: str):
    """Requests EMBED_DIM natively via `outputDimensionality` (Matryoshka-trained model, verified
    live) rather than truncating a larger vector after the fact."""
    return await _post_gemini_with_retry(
        f"{GEMINI_API_BASE}/models/{GEMINI_EMBED_MODEL}:embedContent",
        {"content": {"parts": [{"text": text}]}, "outputDimensionality": EMBED_DIM},
    )


async def chat(
    purpose: Purpose,
    messages: list[dict[str, str]],
    schema: dict | None,
    system: str | None,
    ticket_id: str | UUID | None,
    ledger: Ledger,
) -> LLMResult:
    """Call Gemini and normalize its response into an `LLMResult`, logging the attempt."""
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
    await ledger.record(
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


async def embed(text: str, ticket_id: str | UUID | None, ledger: Ledger) -> LLMResult:
    """Embed via Gemini, dimension-checked against the frozen vector(1536) column."""
    start = time.monotonic()
    data = await _call_gemini_embed(text)
    embedding = data["embedding"]["values"]
    # embedContent doesn't return token usage — approximate at ~4 chars/token (rough
    # English-text average) purely for cost-tracking visibility, not billing precision.
    tokens_in = max(1, len(text) // 4)
    _check_embed_dim(embedding, "gemini", GEMINI_EMBED_MODEL)
    latency_ms = int((time.monotonic() - start) * 1000)
    cost = _cost(GEMINI_EMBED_MODEL, tokens_in, 0)
    await ledger.record(
        ticket_id, "embed", "gemini", GEMINI_EMBED_MODEL, tokens_in, 0, cost, latency_ms, True
    )
    return LLMResult(
        provider="gemini",
        model=GEMINI_EMBED_MODEL,
        tokens_in=tokens_in,
        tokens_out=0,
        cost_usd=cost,
        latency_ms=latency_ms,
        success=True,
        embedding=embedding,
    )
