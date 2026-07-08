# Tasks — split-llm-provider-package

## 1. Package skeleton and shared pieces

- [x] 1.1 Create `services/rag/app/llm/base.py`: move `Purpose`, `LLMResult`, `BudgetExceeded`,
      `EMBED_DIM`, `_parse_json`, and `_JSON_FENCE_RE` verbatim from `llm.py`; define the
      `Provider` protocol (`chat()`, `embed()`)
- [x] 1.2 Create `services/rag/app/llm/pricing.py`: move model-name constants, `PRICING`, and
      `_cost()` verbatim
- [x] 1.3 Create `services/rag/app/llm/prompts.py`: move `PROMPTS_DIR` and `load_prompt()`
      verbatim
- [x] 1.4 Create `services/rag/app/llm/ledger.py`: define the `Ledger` interface
      (`record(...)` = today's `_log` signature, `check_budget()`), plus `PgLedger` moving the
      `_log`/`_check_budget` bodies verbatim — pool resolved via `app.db.get_pool()` inside each
      call, never cached (gotcha #12)

## 2. Provider modules

- [x] 2.1 Create `services/rag/app/llm/providers/_openai_compat.py`: move
      `_complete_openai_compatible()` verbatim, taking the ledger as a parameter
- [x] 2.2 Create `providers/openai.py`: move `_openai_client`, `_call_openai`,
      `_call_openai_embed`, and the openai embed branch of `_embed()` (incl. the EMBED_DIM
      assertion and ledger logging)
- [x] 2.3 Create `providers/anthropic.py`: move `_anthropic_client`, `_call_anthropic`,
      `_is_retryable`, and `_complete_chat` verbatim — preserving the exact ordering: log failed
      attempt → re-raise if not retryable → fall back to the openai provider (ADR-001); embeds
      delegate to the openai embed path as today
- [x] 2.4 Create `providers/gemini.py`: move `_to_gemini_schema`, `_GEMINI_RETRY_AFTER_RE`,
      `_post_gemini_with_retry`, `_call_gemini`, `_call_gemini_embed`, `_complete_gemini`, and
      the gemini embed branch (approx. token count comment included)
- [x] 2.5 Create `providers/ollama.py`: move `_ollama_client` (local-daemon vs. ollama.com cloud
      key logic), `_call_ollama` (8192 max_tokens rationale comment included),
      `_call_ollama_embed`, and the ollama embed branch
- [x] 2.6 Create `providers/fake.py`: move `_fake_embedding` and `_fake_result` verbatim

## 3. Registry, dispatch, and façade

- [x] 3.1 Create `services/rag/app/llm/registry.py`: explicit `PROVIDERS` dict mapping
      `anthropic | openai | gemini | ollama | fake` to provider implementations constructed with
      the default `PgLedger`
- [x] 3.2 Create `services/rag/app/llm/__init__.py`: implement `complete()` — fake short-circuit
      (log via ledger, skip budget check), budget check, embed vs. chat routing via the registry,
      existing `ValueError` on unknown provider — and re-export `complete`, `LLMResult`,
      `BudgetExceeded`, `load_prompt`
- [x] 3.3 Delete `services/rag/app/llm.py`; grep `services/` and `evals/` for `app.llm` imports
      and confirm only façade-level imports remain (`main.py` unchanged)

## 4. Tests and verification

- [x] 4.1 Update monkeypatch targets in `services/rag/tests/` (e.g. `app.llm._call_anthropic` →
      `app.llm.providers.anthropic._call_anthropic`); assertions unchanged
- [x] 4.2 Add a small DB-free provider test using a stub `Ledger` (spec: "provider is
      unit-tested without a database")
- [x] 4.3 Run `make lint && make test` — all green with the fake provider
- [x] 4.4 Live spot-check: `LLM_PROVIDER=ollama` `/classify` roundtrip against the local daemon;
      confirm an `llm_calls` row is written with the same columns/values as before

## 5. Docs and session protocol

- [x] 5.1 Update `wiki/map.md` RAG-service row to point at `app/llm/` (package) and note the
      registry + ledger seams
- [x] 5.2 Append `wiki/log.md` entry and update `PROGRESS.md` for this change
- [x] 5.3 `openspec validate split-llm-provider-package` passes
