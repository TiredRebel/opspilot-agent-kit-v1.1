"""Explicit provider registry — the single place `LLM_PROVIDER` values map to implementations.

Adding a provider means adding one module under `providers/` and one entry here; the dispatch
code in `app/llm/__init__.py` never changes. Modules (not instances) are registered — each
structurally satisfies the `Provider` protocol in `base.py` with module-level `chat()`/`embed()`
coroutines (`fake` is the exception: it is short-circuited by dispatch before the budget check
and exposes `_fake_result()` instead)."""

from types import ModuleType

from app.llm.providers import anthropic, fake, gemini, ollama, openai

PROVIDERS: dict[str, ModuleType] = {
    "anthropic": anthropic,
    "openai": openai,
    "gemini": gemini,
    "ollama": ollama,
    "fake": fake,
}
