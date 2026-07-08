"""Model-name constants, the per-token pricing table, and cost computation."""

from decimal import Decimal

ANTHROPIC_MODEL = "claude-haiku-4-5"
OPENAI_MODEL = "gpt-5.4-mini"
OPENAI_EMBED_MODEL = "text-embedding-3-small"
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_EMBED_MODEL = "gemini-embedding-001"

# USD per 1M tokens: (input, output). Embedding models have no output tokens. Gemini's output
# price covers "thinking" tokens too (billed as output, per Google's pricing page) — the gemini
# provider folds thinking into tokens_out accordingly. Ollama models aren't listed here: `_cost`
# treats any unlisted model as free (local inference has no per-token API cost).
PRICING: dict[str, tuple[float, float]] = {
    ANTHROPIC_MODEL: (1.00, 5.00),
    OPENAI_MODEL: (0.75, 4.50),
    OPENAI_EMBED_MODEL: (0.02, 0.0),
    GEMINI_MODEL: (0.30, 2.50),
    GEMINI_EMBED_MODEL: (0.15, 0.0),
}


def _cost(model: str, tokens_in: int, tokens_out: int) -> Decimal:
    """Compute USD cost for a call from `PRICING`, treating any unlisted model as free."""
    # Unlisted models (Ollama, local) have no per-token API price — treat as free rather than
    # raising, so a locally-run model doesn't need a fake PRICING entry just to log a call.
    if model not in PRICING:
        return Decimal("0")
    price_in, price_out = PRICING[model]
    return Decimal(str(tokens_in / 1_000_000 * price_in + tokens_out / 1_000_000 * price_out))
