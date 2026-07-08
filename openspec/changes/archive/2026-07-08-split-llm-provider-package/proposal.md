# Split llm.py into an app/llm/ provider package

## Why

`services/rag/app/llm.py` has grown into a 627-line god module (the three most-connected nodes in
the project knowledge graph are `complete()`, `_complete_chat()`, and `_embed()`). It mixes six
concerns — provider clients, response normalization, pricing, the daily-budget guardrail, call
logging, and the fake test provider — and adding a provider today means editing the `if provider ==`
chains in `complete()` and `_embed()` plus the client builders. The direct `app.db` calls inside
`_log()`/`_check_budget()` also weld the provider layer to Postgres, so no provider code can be
unit-tested without a database.

## What Changes

- Restructure `services/rag/app/llm.py` into a `services/rag/app/llm/` package:
  - `base.py` — `LLMResult`, `Purpose`, `BudgetExceeded`, and a `Provider` protocol
    (`chat()` / `embed()`).
  - `providers/anthropic.py` (including its OpenAI fallback chain per ADR-001),
    `providers/openai.py`, `providers/gemini.py` (schema conversion + retry-after parsing),
    `providers/ollama.py` (local-daemon vs. ollama.com cloud auth), `providers/fake.py`.
  - `registry.py` — a `PROVIDERS` mapping replaces the `if provider ==` dispatch chains; adding a
    provider means adding one module and one registry entry, with no edits to dispatch code.
  - `pricing.py` — `PRICING` table and cost computation.
  - `ledger.py` — call logging + daily-budget guardrail behind a `Ledger` interface; the only
    part of the package that touches the database.
  - `prompts.py` — `load_prompt()`.
  - `__init__.py` — re-exports `complete()`, `LLMResult`, `BudgetExceeded`, `load_prompt` so
    `main.py` and tests keep their existing imports (`from app.llm import ...`).
- **No behavior change**: request/response shapes, provider selection semantics, the
  anthropic→openai fallback, budget enforcement, `llm_calls` logging, pricing, and the fake
  provider's canned outputs all stay byte-for-byte identical. Existing tests must pass unmodified
  (import paths included).
- Providers receive their `Ledger` via injection (default: the asyncpg-backed one), so provider
  modules import neither `app.db` nor each other.

## Capabilities

### New Capabilities

_None — this is a structural refactor of an existing capability._

### Modified Capabilities

- `llm-provider-layer`: the capability's boundary changes from a single module
  (`services/rag/app/llm.py`) to a package (`services/rag/app/llm/`). New structural requirements:
  registry-based provider dispatch (open for extension without modifying dispatch code), a
  database-free provider layer with the ledger isolated behind an interface, and a stable public
  API (`app.llm` re-exports) that keeps callers and tests unchanged. Existing authentication and
  default-model requirements are unaffected.

## Impact

- **Code**: `services/rag/app/llm.py` (deleted, replaced by the package),
  `services/rag/app/llm/` (new). `services/rag/app/main.py` needs no changes if re-exports are
  faithful; verify imports only.
- **Tests**: `services/rag/tests/` monkeypatch `_call_anthropic`/`_call_openai`/etc. — those
  patch targets move to `app.llm.providers.*`; conftest/test patch paths must be updated (the
  assertions themselves stay identical). `evals/` uses HTTP only and is unaffected.
- **Docs**: `wiki/map.md` RAG-service row, `wiki/log.md` entry, `PROGRESS.md`; ADR-001 remains
  valid (the package is still the only LLM caller).
- **Dependencies / APIs / DB**: none — no new packages, no HTTP or schema changes.
