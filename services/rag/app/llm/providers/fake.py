"""Deterministic fake provider for tests — canned results per purpose, no network, no cost.

Unlike the real providers this module is dispatched before the budget check (a fake call can
never spend money), so it exposes `result()` rather than the `chat()`/`embed()` pair; the
dispatch layer in `app/llm/__init__.py` handles the short-circuit."""

import json
import random
from decimal import Decimal
from hashlib import sha256

from app.llm.base import EMBED_DIM, LLMResult, Purpose


def _fake_embedding(text: str) -> list[float]:
    """Deterministic pseudo-embedding for the `fake` provider, seeded from the input text's hash."""
    seed = int(sha256(text.encode()).hexdigest(), 16)
    rng = random.Random(seed)
    return [rng.uniform(-1, 1) for _ in range(EMBED_DIM)]


def _fake_result(purpose: Purpose, embed_text: str | None) -> LLMResult:
    """Deterministic canned `LLMResult` per purpose, used by the `fake` provider in tests."""
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
