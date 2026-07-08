"""LLM provider layer (ADR-001) — the only package allowed to call an LLM or embedding API.

`complete()` dispatches on `settings.llm_provider` via the registry. Only `anthropic` has a
fallback chain (-> OpenAI on 5xx/timeout/connection errors, the original ADR-001 design);
`openai`, `gemini`, and `ollama` each run standalone with no fallback of their own. `fake` is
deterministic for tests. Every attempt is logged to `llm_calls` through the `Ledger`, and a
daily budget guardrail runs before any non-fake provider call.

Public surface (unchanged by the package split): `complete`, `LLMResult`, `BudgetExceeded`,
`load_prompt`.
"""

from typing import Any
from uuid import UUID

from app.llm import registry
from app.llm.base import BudgetExceeded, LLMResult, Purpose
from app.llm.ledger import Ledger, PgLedger
from app.llm.prompts import load_prompt
from app.llm.providers.fake import _fake_result
from app.settings import settings

__all__ = ["BudgetExceeded", "LLMResult", "Purpose", "complete", "load_prompt"]

# Default ledger for production dispatch. Providers take the ledger as a parameter, so tests
# can exercise any provider with a stub ledger and no database.
_DEFAULT_LEDGER: Ledger = PgLedger()


async def complete(
    purpose: Purpose,
    messages: list[dict[str, str]] | None = None,
    *,
    schema: dict[str, Any] | None = None,
    system: str | None = None,
    ticket_id: str | UUID | None = None,
    embed_text: str | None = None,
) -> LLMResult:
    """Entry point for every LLM/embedding call — dispatches on `settings.llm_provider`."""
    provider_name = settings.llm_provider
    provider = registry.PROVIDERS.get(provider_name)
    if provider is None:
        raise ValueError(f"unknown llm_provider: {provider_name!r}")

    if provider_name == "fake":
        result = _fake_result(purpose, embed_text)
        await _DEFAULT_LEDGER.record(
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

    await _DEFAULT_LEDGER.check_budget()

    if purpose == "embed":
        return await provider.embed(embed_text or "", ticket_id, _DEFAULT_LEDGER)
    return await provider.chat(purpose, messages or [], schema, system, ticket_id, _DEFAULT_LEDGER)
