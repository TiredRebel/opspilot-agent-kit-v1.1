# Design — add-structured-logging

## Context

`services/rag/app/` contains no logging at all; uvicorn's access log and the `llm_calls` table
are the only runtime signals. The service runs under docker compose (stderr → `docker logs`)
and locally under uvicorn. Prior changes this cycle added the `app/llm/` package (with
`PgLedger.record()` seeing every LLM attempt) and the `ticket_events` audit log — this pass is
the third review item and deliberately the lowest-risk one: messages and log lines, one narrow
behavior fix (empty-KB `/query`), no schema or workflow changes.

Constraints: AGENTS.md scope discipline (no new dependencies for a single-service prototype);
docstring rules D100–D104 apply to any new module; existing 28 tests must pass unmodified
except where a test asserts on a message this change improves (none do — the classify test
asserts the status code only).

## Goals / Non-Goals

**Goals:**
- Every failure or degraded state an operator can hit leaves a specific, greppable trace:
  what failed, with which provider/model/ticket, and what to do about it.
- One log line per LLM attempt, centrally, without touching provider modules.
- Kill the one silently-wrong behavior found in review: `/query` drafting an "answer" from an
  empty context window (two wasted LLM calls per empty-KB query, plus a hallucination risk).

**Non-Goals:**
- No structlog/loguru/OpenTelemetry — stdlib `logging` only; revisit if this ever runs
  multi-service.
- No request-ID middleware or contextvars propagation — explicit `ticket_id=` keys at call
  sites; the service is small enough that implicit context is more machinery than signal.
- No log shipping/rotation config — stderr is the contract; docker/journald own the rest.
- No changes to response models, status codes (the 422/429/404/503 map is unchanged), n8n
  workflows, or the DB schema.

## Decisions

1. **stdlib `logging` with a key=value line format** (`2026-07-08 11:00:00 WARNING app.query
   msg="..." ticket_id=... provider=...`), configured once in `app/logging_setup.py` by a
   `setup_logging(level)` called from the FastAPI lifespan startup. Rationale: zero deps,
   greppable, and docker-logs-native. JSON lines were rejected as over-tooling for a
   single-consumer (human) log; structlog rejected per no-new-deps. The module is named
   `logging_setup.py` because `app/logging.py` would shadow stdlib `logging` inside the
   package.
2. **Contextual keys are appended by the caller in the message via a small helper**
   (`kv(msg, **keys)` in `logging_setup.py`) rather than `extra=` + a custom Formatter dance.
   Rationale: `extra=` requires every key pre-declared in the format string or a filter;
   a helper that renders `key=value` suffixes is 6 lines and keeps call sites obvious.
3. **LLM attempt logging lives in `PgLedger.record()`** — it already receives ticket_id,
   purpose, provider, model, tokens, cost, latency, success for every attempt (including
   failed Anthropic attempts pre-fallback). One INFO line there covers all providers with zero
   provider-module edits; the fallback WARNING (naming the caught exception class) goes in
   `providers/anthropic.py` where the exception is caught. Trade-off: a stub `Ledger` in tests
   logs nothing — correct, since the stub explicitly replaces accounting.
4. **Empty-KB `/query` short-circuits before any LLM call**: `rows == []` → log WARNING,
   return `QueryResponse(answer=<sentinel>, sources=[], confidence=0.0)`. The sentinel is a
   fixed English string ("I could not find any knowledge-base content for this question — the
   KB may not be ingested yet (POST /kb/ingest)."). Rationale: drafting from an empty context
   is the only path where the service *knowingly* invites hallucination and pays two LLM calls
   for it; confidence 0.0 routes to `needs_human` through the existing WF-2 gate unchanged, and
   the ops reviewer sees an honest sentinel instead of a confident fabrication. Alternatives —
   404/409 (breaks WF-2's HTTP node, which doesn't branch on error codes) and keep-current
   (hallucination by design) — both rejected.
5. **`check_db` keeps returning a bool-ish result but surfaces the error**: it returns
   `str | None` (the exception class name, None when healthy) alongside logging the full
   exception — implemented as a second return value `(ok, error)` consumed only by `/health`.
   Rationale: /health's body is not a Pydantic model today; adding `"error"` is additive and
   the compose healthcheck greps status only.
6. **Unknown-provider message derives options from the registry**
   (`sorted(registry.PROVIDERS)`), so the message can never drift from the actual valid set —
   the same never-drift trick as conftest globbing `db/init/*.sql`.
7. **`scripts/n8n_sync.py` prints `"<name>: imported, activated"` per workflow** and dumps the
   raw response dict only on failure, keeping the exit-code behavior identical.

## Risks / Trade-offs

- [A message-text change breaks a hidden consumer] → Grep confirms nothing parses the classify
  422 detail or BudgetExceeded text (n8n branches on status codes only; tests assert codes).
  The one text a test does match is the append-only trigger's ("append-only"), untouched here.
- [Empty-KB short-circuit changes /query semantics] → Narrow and intentional: response shape
  identical, gate routing identical (0.0 < 0.70); only the two pointless LLM calls disappear.
  Covered by a dedicated L2 test; evals run against a seeded KB and never hit it.
- [Log noise at INFO with one line per LLM attempt] → At prototype volume this is the desired
  signal, not noise; `LOG_LEVEL=WARNING` exists the day it isn't.
- [Double logging if uvicorn also configures the root logger] → `setup_logging()` configures
  the `app` logger namespace with `propagate = False`, leaving uvicorn's own loggers alone.

## Migration Plan

1. Land `logging_setup.py` + settings + lifespan hook; then the message/short-circuit edits;
   then tests. Single commit, gated on `make lint && make test`.
2. Live check: run with `LLM_PROVIDER=ollama`, hit `/classify` and an empty-KB `/query` (fresh
   test DB), eyeball the log lines and the sentinel response.
3. Docs: map.md note, log.md entry, PROGRESS.md, `.env.example` (+`LOG_LEVEL=INFO`).
Rollback: single revert; no schema, no workflow, no API-shape involvement.

## Open Questions

- None blocking. (Request-ID middleware and log shipping are explicitly deferred until there
  is more than one service or more than one log consumer.)
