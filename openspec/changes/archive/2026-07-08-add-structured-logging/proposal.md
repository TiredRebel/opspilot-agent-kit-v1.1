# Structured logging and meaningful messages for the RAG service

## Why

The service has zero application logging — `import logging` appears nowhere under
`services/rag/app/`; the `llm_calls` table is the only telemetry. When something misbehaves, the
operator gets generic signals: a bare `"classification failed validation after retry"` 422 with
no hint of which fields were missing or which model failed, a `/health` that says `"db": false`
after swallowing the actual exception, a `/query` that silently drafts answers from an empty
knowledge base, and a self-check score that silently becomes `0.0` when the model's reply was
unparseable. The architecture review ranked this pass as the highest debugging payoff per unit
of effort and risk.

## What Changes

- **Structured logging, stdlib only (no new dependency):** a `setup_logging()` configured at app
  startup emits single-line `key=value` records (timestamp, level, logger, message, plus
  contextual keys like `ticket_id`, `provider`, `model`) to stderr — greppable and
  docker-logs/journald friendly. Log level comes from a new `LOG_LEVEL` setting (default
  `INFO`; documented in `.env.example`).
- **One INFO line per LLM attempt, logged centrally in `PgLedger.record()`** — purpose,
  provider, model, tokens, cost, latency, success, ticket_id. The Anthropic→OpenAI fallback
  path logs a WARNING naming the triggering error. `llm_calls` stays the durable record; logs
  are the live view.
- **Meaningful messages** (each currently generic or silent):
  - `/classify` 422 detail now names the missing fields, provider, model, and attempt count.
  - `/query` against an **empty retrieval result** no longer drafts from nothing: it skips the
    answer/self-check LLM calls (they could only hallucinate — and cost money), returns
    `confidence 0.0`, empty sources, and an explicit answer sentinel ("no knowledge-base
    content available — has /kb/ingest been run?"), and logs a WARNING. **BREAKING** only in
    the narrow sense that an empty-KB `/query` no longer produces two LLM calls; the response
    shape is unchanged and the confidence gate (< 0.70 → needs_human) routes it to a human
    exactly as before.
  - `_parse_score` logs a WARNING with the raw self-check text before returning `0.0`.
  - `check_db` logs the caught exception; `/health` includes the error class in its body when
    the DB is down (`{"status": "unavailable", "db": false, "error": "ConnectionRefusedError"}`).
  - `BudgetExceeded` message states when the budget resets (midnight UTC, per
    `created_at::date`).
  - Unknown `LLM_PROVIDER` `ValueError` lists the valid options (derived from the registry).
  - `scripts/n8n_sync.py` prints one `<workflow>: imported, activated` line per workflow
    instead of raw response dicts (raw dict only on failure).

## Capabilities

### New Capabilities

- `service-observability`: structured logging configuration, per-LLM-attempt log records, and
  the meaningful-message requirements for error and degraded-state paths (classify validation
  failure, empty-KB query, unparseable self-check, DB-down health, budget exhaustion, unknown
  provider).

### Modified Capabilities

_None. `llm-provider-layer`'s "ValueError identifying the unknown provider" requirement is
still satisfied (the message gains the valid-options list); no other spec'd requirement is
touched._

## Impact

- **Code**: new `services/rag/app/logging_setup.py` (named to avoid shadowing stdlib
  `logging`); edits to `main.py` (lifespan hook, classify/query/health messages), `db.py`
  (check_db error surfacing), `settings.py` (+`log_level`), `app/llm/__init__.py` (unknown
  provider message), `app/llm/base.py` or `ledger.py` (budget message, attempt logging),
  `scripts/n8n_sync.py` (output lines).
- **Tests**: new caplog-based assertions (L1/L2) for the empty-KB query path, classify 422
  detail, health error field, and the LLM-attempt log line; existing 28 tests must stay green
  (the classify 422 test asserts status code, not detail text — unaffected).
- **Docs**: `wiki/map.md` RAG-service row note, `wiki/log.md`, `PROGRESS.md`, `.env.example`.
- **Not affected**: DB schema (nothing added — `ticket_events` and `llm_calls` are unchanged),
  n8n workflow JSONs, response models/shapes, evals.
