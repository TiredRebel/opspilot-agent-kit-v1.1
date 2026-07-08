# Tasks — add-structured-logging

## 1. Logging foundation

- [x] 1.1 Create `services/rag/app/logging_setup.py`: `setup_logging(level)` configuring the
      `app` logger namespace (stderr handler, single-line format with timestamp/level/name,
      `propagate = False` so uvicorn's loggers are untouched) and a `kv(msg, **keys)` helper
      rendering `key=value` suffixes (None-valued keys omitted)
- [x] 1.2 `services/rag/app/settings.py`: add `log_level: str = "INFO"`; document
      `LOG_LEVEL=INFO` in `.env.example` and pass it through in `docker-compose.yml`'s rag-api
      environment
- [x] 1.3 `services/rag/app/main.py`: call `setup_logging(settings.log_level)` in the lifespan
      startup

## 2. LLM attempt logging

- [x] 2.1 `app/llm/ledger.py`: `PgLedger.record()` emits one INFO line (purpose, provider,
      model, tokens_in/out, cost_usd, latency_ms, success, ticket_id) before the insert
- [x] 2.2 `app/llm/providers/anthropic.py`: WARNING naming the exception class when a
      retryable error triggers the OpenAI fallback (logged before the fallback call)

## 3. Meaningful messages

- [x] 3.1 `/classify` 422 detail: missing/invalid fields + provider + model + attempt count
      (compute missing fields from the required set; use the last attempt's LLMResult)
- [x] 3.2 `/query` empty-retrieval short-circuit: `rows == []` → WARNING log + 200 with
      sentinel answer, `sources=[]`, `confidence=0.0`, and NO answer/self_check LLM calls
- [x] 3.3 `_parse_score`: WARNING with the raw self-check text when no number is extractable
- [x] 3.4 `db.check_db`: return `(ok, error_class_name)` and log the exception; `/health`
      includes `error` in the body when db is down
- [x] 3.5 `app/llm/ledger.py` `check_budget`: BudgetExceeded message gains "resets at midnight
      UTC (spend is per created_at::date)"
- [x] 3.6 `app/llm/__init__.py`: unknown-provider ValueError lists
      `sorted(registry.PROVIDERS)` as valid options
- [x] 3.7 `scripts/n8n_sync.py`: per-workflow `<name>: imported, activated` lines; raw
      response dict printed only on failure; exit codes unchanged

## 4. Tests

- [x] 4.1 New `test_observability.py`: empty-KB `/query` → 200, sentinel answer, `sources=[]`,
      `confidence==0.0`, zero answer/self_check rows in `llm_calls`, WARNING in caplog
- [x] 4.2 Same file: classify 422 detail contains missing field names, provider, model, and
      attempt count (AsyncMock returning invalid parse, per test_classify_schema.py pattern)
- [x] 4.3 Same file: `/health` with `db.get_pool` monkeypatched to raise → 503 body has
      `db: false` and `error` naming the exception class
- [x] 4.4 Same file: fake-provider `complete()` call emits the per-attempt INFO record
      (caplog); unknown provider ValueError message lists all five registry options
- [x] 4.5 `make lint && make test` — full suite green (existing 28 tests unmodified)

## 5. Live verification

- [x] 5.1 Run the API locally with `LLM_PROVIDER=ollama`: hit `/classify` (see the attempt
      INFO line with ticket_id) and `/query` against an empty KB (see the WARNING + sentinel
      response); confirm uvicorn access logs are unchanged

## 6. Docs and session protocol

- [x] 6.1 `wiki/map.md`: RAG-service row note (structured logging via logging_setup.py,
      LOG_LEVEL setting, empty-KB sentinel behavior)
- [x] 6.2 Append `wiki/log.md` entry and update `PROGRESS.md` (Maintenance section)
- [x] 6.3 `openspec validate add-structured-logging` passes
