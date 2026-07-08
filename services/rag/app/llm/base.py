"""Shared types for the LLM package: `LLMResult`, `Purpose`, `BudgetExceeded`, the `Provider`
protocol, and the JSON/embedding helpers every provider module builds on."""

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal, Protocol
from uuid import UUID

if TYPE_CHECKING:
    # Type-only: ledger.py imports BudgetExceeded from this module at runtime, so a runtime
    # import here would be circular.
    from app.llm.ledger import Ledger

Purpose = Literal["classify", "answer", "self_check", "summarize", "embed"]

# Every embedding path must return exactly this many dimensions — kb_chunks.embedding is a
# frozen `vector(1536)` column (gotcha #5). Gemini's embedding model natively supports requesting
# this dimension via `outputDimensionality` (Matryoshka-trained, verified live); Ollama has no
# such control, so embed paths assert the returned length rather than silently corrupting rows.
EMBED_DIM = 1536


class BudgetExceeded(Exception):
    """Today's LLM spend has hit DAILY_BUDGET_USD. Callers map this to HTTP 429."""


@dataclass
class LLMResult:
    """Normalized result of any provider call — chat completion or embedding alike."""

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


class Provider(Protocol):
    """Structural interface every provider module in `app/llm/providers/` satisfies.

    Modules (not class instances) are registered in `app/llm/registry.py`; each exposes these
    two module-level coroutines. Providers never touch the database — all logging and budget
    accounting goes through the injected `Ledger`.
    """

    async def chat(
        self,
        purpose: Purpose,
        messages: list[dict[str, str]],
        schema: dict | None,
        system: str | None,
        ticket_id: str | UUID | None,
        ledger: "Ledger",
    ) -> LLMResult:
        """Run a chat/structured-output completion and return a normalized `LLMResult`."""
        ...

    async def embed(
        self,
        text: str,
        ticket_id: str | UUID | None,
        ledger: "Ledger",
    ) -> LLMResult:
        """Embed `text` into exactly `EMBED_DIM` dimensions and return a normalized `LLMResult`."""
        ...


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


def _check_embed_dim(embedding: list[float], api_provider: str, model: str) -> None:
    """Raise if an embedding is not exactly `EMBED_DIM` dimensions — a mismatch would silently
    corrupt the frozen `vector(1536)` column (gotcha #5)."""
    if len(embedding) != EMBED_DIM:
        raise ValueError(
            f"{api_provider}/{model} returned a {len(embedding)}-dim embedding, expected "
            f"{EMBED_DIM} (schema is frozen at vector(1536) — gotcha #5)"
        )
