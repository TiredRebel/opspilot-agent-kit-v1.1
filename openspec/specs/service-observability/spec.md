# service-observability

## Purpose

Defines the RAG service's structured logging (stdlib-only, `app/logging_setup.py`, `LOG_LEVEL`
setting, one INFO record per LLM attempt via the default ledger) and the meaningful-message
requirements for error and degraded-state paths: classify validation failure detail, the
empty-retrieval `/query` short-circuit, unparseable self-check replies, DB-down health output,
budget exhaustion, unknown provider, and `n8n_sync.py` per-workflow reporting. Request-ID
middleware and log shipping are deliberately out of scope until there is more than one service
or log consumer.

## Requirements

### Requirement: The service SHALL emit structured application logs
The RAG service SHALL configure stdlib logging at startup (level from a `LOG_LEVEL` setting,
default `INFO`) and emit single-line records to stderr containing timestamp, level, logger
name, message, and contextual `key=value` pairs (e.g. `ticket_id`, `provider`, `model`) where
applicable. No third-party logging dependency SHALL be introduced.

#### Scenario: Logging is configured at startup
- **WHEN** the FastAPI app starts
- **THEN** loggers under the `app` namespace SHALL emit records at the configured level in the
  structured line format, without altering uvicorn's own loggers

#### Scenario: Every LLM attempt produces a log record
- **WHEN** any LLM/embedding attempt is recorded through the default ledger (success or
  failure, any provider)
- **THEN** an INFO record SHALL be emitted carrying purpose, provider, model, token counts,
  cost, latency, success, and ticket_id

#### Scenario: Provider fallback is visible in the log
- **WHEN** the Anthropic provider falls back to OpenAI on a retryable error (ADR-001)
- **THEN** a WARNING record SHALL be emitted naming the triggering exception class before the
  fallback attempt is made

### Requirement: Classification failure SHALL report what failed
When `/classify` returns 422 after its retry, the response detail SHALL name the missing or
invalid fields, the provider and model that produced the output, and the attempt count.

#### Scenario: Invalid structured output after retry
- **WHEN** both classify attempts return output missing required fields (e.g. `priority`,
  `lang`)
- **THEN** the 422 detail SHALL include the missing field names, the provider, the model, and
  that 2 attempts were made

### Requirement: Empty-retrieval queries SHALL be answered honestly without LLM calls
When `/query` retrieves zero chunks, the service SHALL NOT invoke the answer or self-check
LLM calls; it SHALL return HTTP 200 with `confidence` 0.0, empty `sources`, and a fixed
sentinel answer directing the operator to ingest the KB, and SHALL log a WARNING. The response
shape is unchanged (the existing confidence gate routes 0.0 to `needs_human`).

#### Scenario: Query against an empty knowledge base
- **WHEN** `/query` is called and retrieval returns no chunks
- **THEN** the response SHALL be 200 with `confidence` 0.0, `sources` `[]`, and the sentinel
  answer text, no `llm_calls` rows SHALL be written for answer/self_check, and a WARNING SHALL
  be logged

### Requirement: Degraded and error states SHALL carry specific, actionable messages
Silent or generic failure paths SHALL state what happened and what to check: an unparseable
self-check reply SHALL log a WARNING with the raw text before scoring 0.0; `/health` SHALL log
the caught DB exception and include its class name in the response body when the DB is down;
`BudgetExceeded` SHALL state when the budget resets; an unknown `LLM_PROVIDER` SHALL list the
valid options derived from the provider registry.

#### Scenario: Unparseable self-check reply
- **WHEN** the self-check model returns text with no extractable number
- **THEN** a WARNING SHALL be logged containing the raw reply text, and the score SHALL be 0.0
  as before

#### Scenario: Health check with the database down
- **WHEN** `GET /health` runs while the database is unreachable
- **THEN** the response SHALL be 503 with `db: false` and an `error` field naming the exception
  class, and the exception SHALL be logged

#### Scenario: Budget exhausted
- **WHEN** the daily budget check raises `BudgetExceeded`
- **THEN** the message SHALL include the budget, the spend, and that the budget resets at
  midnight UTC

#### Scenario: Unknown provider configured
- **WHEN** `complete()` is called with an `LLM_PROVIDER` value not in the registry
- **THEN** the `ValueError` message SHALL name the bad value and list the valid options from
  the registry

### Requirement: n8n sync output SHALL report per-workflow outcomes
`scripts/n8n_sync.py` SHALL print one line per workflow stating its name and outcome
(imported/activated), printing a raw API response only when that workflow fails; exit-code
behavior is unchanged.

#### Scenario: Successful sync
- **WHEN** all five workflows import and activate successfully
- **THEN** the output SHALL contain five `<workflow name>: imported, activated` lines and no
  raw response dicts
