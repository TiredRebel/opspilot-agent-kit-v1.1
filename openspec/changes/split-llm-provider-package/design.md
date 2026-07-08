# Design — split-llm-provider-package

## Context

`services/rag/app/llm.py` (627 lines) is the provider layer mandated by ADR-001 ("only module
allowed to call an LLM or embedding API"). It currently holds provider clients and raw-call
wrappers for five providers, response normalization into `LLMResult`, the `PRICING` table and
cost math, the daily-budget guardrail, `llm_calls` logging, prompt loading, and the deterministic
fake provider for tests. Dispatch is an `if provider ==` chain repeated in `complete()` and
`_embed()`. `_log()`/`_check_budget()` call `app.db` directly, so nothing in the module is
testable without a database. Tests monkeypatch the raw-call functions (`_call_anthropic`,
`_call_openai`, `_call_ollama`, `_call_gemini`, and the embed variants) — that seam must survive
the split.

Constraints: AGENTS.md scope discipline (structural refactor only, no feature creep), ADR-001
(fallback chain semantics unchanged), ADR-004 (asyncpg, no ORM), gotcha #5 (EMBED_DIM 1536
assertion stays on every embed path), gotcha #12 (pool is loop-bound; ledger must keep going
through `app.db.get_pool()` lazily, never capture a pool at import time).

## Goals / Non-Goals

**Goals:**
- One module per provider; adding a provider touches only a new module + one registry entry.
- Providers are import-clean: no `app.db`, no cross-provider imports (one exception: the
  anthropic module's ADR-001 fallback explicitly composes the openai provider).
- Budget + logging isolated in a `Ledger` interface — the package's single DB touchpoint.
- `from app.llm import complete, LLMResult, BudgetExceeded, load_prompt` keeps working; callers
  (`main.py`) unchanged.
- Behavior byte-for-byte identical: same prompts, same `llm_calls` rows, same errors, same
  fallback triggers, same fake outputs.

**Non-Goals:**
- No new providers, no retry/backoff changes, no message-quality improvements (separate change).
- No event emission from the ledger (future `ticket_events` work builds on this seam, later).
- No changes to HTTP API, DB schema, settings names, or n8n workflows.
- No test-assertion changes — only patch-target paths move.

## Decisions

1. **Package with re-exporting `__init__.py`** over renaming imports everywhere.
   `app/llm/__init__.py` re-exports the public four (`complete`, `LLMResult`, `BudgetExceeded`,
   `load_prompt`). Rationale: `main.py` and most tests import from `app.llm`; keeping that path
   makes "no caller changes" checkable by grep. Alternative — update all imports to deep paths —
   rejected: churn with no benefit, and it breaks the ADR-001 "one façade" reading.

2. **Registry dict over subclass auto-discovery.** `registry.py` holds
   `PROVIDERS: dict[str, Provider]` built explicitly (`{"anthropic": ..., "openai": ...,
   "gemini": ..., "ollama": ..., "fake": ...}`). `complete()` looks up
   `settings.llm_provider` and raises the existing `ValueError` (unknown provider) on a miss.
   Rationale: five entries don't justify entry-points or `__subclasses__` magic; an explicit dict
   is greppable and import-order-safe. Alternative — decorator-based registration — rejected:
   hides the provider list, and import side effects are exactly what this repo avoids.

3. **`Provider` as a Protocol with `chat()` and `embed()`** (in `base.py`), not an ABC.
   Modules stay plain functions grouped in a small class (or module-level functions wrapped in a
   dataclass holding the ledger). Providers without native embeddings (anthropic) delegate to the
   openai embed path exactly as today — that asymmetry lives in the anthropic module, not in
   dispatch. Rationale: Protocol keeps `fake` trivial and avoids inheritance coupling.

4. **`Ledger` interface in `ledger.py`; asyncpg implementation is the default.**
   `Ledger.record(...)` (today's `_log`) and `Ledger.check_budget()` (today's `_check_budget`).
   The default `PgLedger` resolves the pool via `app.db.get_pool()` per call (gotcha #12: never
   cache the pool). Providers receive the ledger from the dispatch layer; they never import
   `app.db`. Rationale: this is the seam that makes providers DB-free-testable and is the future
   hook for event emission. Alternative — keep logging inline and only split providers —
   rejected: leaves the DB weld, which is half the point.

5. **Raw-call functions keep their names inside provider modules** (`_call_anthropic` in
   `providers/anthropic.py`, etc.). Tests change patch targets from `app.llm._call_anthropic` to
   `app.llm.providers.anthropic._call_anthropic` — a mechanical path substitution, assertions
   untouched. Rationale: preserving the existing monkeypatch seam is cheaper and safer than
   inventing a new fake-transport abstraction mid-refactor.

6. **Shared OpenAI-compatible response parsing** (`_complete_openai_compatible`) moves to
   `providers/_openai_compat.py` (used by openai + ollama). Rationale: it is genuinely shared
   parsing of one wire shape, not dispatch logic; a private helper module keeps it out of the
   public surface.

7. **Migration is one commit, no shim period.** Delete `llm.py` and land the package in the same
   commit, gated by the full test suite. Rationale: an `llm.py`-imports-package shim would leave
   two import paths alive and invite drift; the repo is small enough to cut over atomically.

## Risks / Trade-offs

- [Tests patch moved symbols and fail confusingly] → Update patch paths in the same commit;
  `make test` green is the gate. Grep for `app.llm.` and `app\.llm import` across `services/` and
  `evals/` before declaring done.
- [Subtle behavior drift while moving code (e.g. log-on-failure ordering in the anthropic
  fallback)] → Move code verbatim; the fallback's "log failed attempt, then maybe re-raise, then
  fall back" ordering is copied, not rewritten. `test_llm_fallback.py` covers the matrix.
- [Circular import: providers ↔ registry ↔ dispatch] → Strict one-way layering:
  `base.py` ← `providers/*` ← `registry.py` ← `__init__.py`; `ledger.py` depends only on
  `base.py` + `app.db`. The anthropic→openai fallback imports `providers.openai` (sibling), which
  is acyclic.
- [Ledger injection adds indirection for a 5-file package] → Accepted: it is one constructor
  argument, and it is the enabling seam for both DB-free provider tests now and event emission
  later.
- [Import-time `settings` reads move around and change env-loading timing] → Keep all
  `settings.<field>` reads at call time (as today: client builders read keys per call), never at
  module import.

## Migration Plan

1. Create the package with code moved verbatim; keep `llm.py` deleted in the same commit.
2. Update test patch targets; run `make lint && make test` (fake provider — no keys needed).
3. Spot-check live: `LLM_PROVIDER=ollama` `/classify` roundtrip (the default local setup).
4. Update `wiki/map.md` row, `wiki/log.md`, `PROGRESS.md`.
Rollback: single revert commit restores `llm.py` — no data or schema involvement.

## Open Questions

- None blocking. (Whether `Ledger` later emits `ticket_events` is explicitly deferred to the
  events change.)
