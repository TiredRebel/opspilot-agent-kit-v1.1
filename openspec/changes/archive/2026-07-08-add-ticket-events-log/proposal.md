# Add an append-only ticket_events audit log

## Why

Ticket lifecycle state lives only in mutable columns (`tickets.status`, `category`,
`last_reminder_at`), overwritten in place by ~10 raw-SQL postgres nodes scattered across five n8n
workflow JSONs plus the rag-api. There is no record of *when* a ticket changed state, *what* the
transition was, or that an SLA reminder fired — the HITL flow (approve/edit/reject) leaves no
audit trail, and debugging a misrouted ticket means reading n8n execution logs before they
rotate. An event log is also the backbone the architecture review identified for future async
work (job queues, notifications), and the recently landed `Ledger` seam anticipates emitting to
it.

## What Changes

- New `ticket_events` table: append-only log of `(ticket_id, type, payload jsonb, created_at)`,
  indexed by `(ticket_id, created_at)`. Append-only is enforced in the database (UPDATE/DELETE
  raise), not by convention.
- Events are captured by **database triggers** on `tickets` and `messages` — not by editing
  workflow JSONs. Both writers (n8n's postgres nodes and the rag-api) are covered automatically,
  with zero n8n changes and no new dual-writer sprawl. Event types:
  - `ticket.created` — INSERT into `tickets`
  - `ticket.classified` — triage fields first populated (payload: category/priority/sentiment/lang)
  - `ticket.status_changed` — any status transition (payload: `{"from": ..., "to": ...}`)
  - `ticket.sla_reminded` — `last_reminder_at` set/advanced
  - `message.added` — INSERT into `messages` (payload: role + message id; covers `ai_draft`,
    `operator`, `customer`, `system`)
- New endpoint `GET /tickets/{ticket_id}/events` on the rag-api — the read path for the audit
  trail (returns the ordered event list; 404 for an unknown ticket).
- **Schema-freeze amendment (ADR-006)**: the P0-2 freeze (map.md invariant #2) is restated as
  "existing tables/columns are frozen; additive-only changes are allowed via new numbered
  `db/init/NN_*.sql` files, each requiring an ADR". The new DDL ships as
  `db/init/02_ticket_events.sql` (auto-applied on fresh volumes by the postgres entrypoint;
  applied to existing databases with a documented one-off `psql` step). No existing table or
  column is touched.
- `tickets.status` **remains the source of truth** — events are an audit log, not event sourcing;
  no existing behavior, workflow, or endpoint changes.

## Capabilities

### New Capabilities

- `ticket-event-log`: the append-only `ticket_events` table — trigger-based capture of ticket
  lifecycle events from all writers, database-enforced append-only semantics, additive-only
  schema-freeze exception, and the events read endpoint.

### Modified Capabilities

_None — no existing spec's requirements change (`llm-provider-layer`, `n8n-workflow-export`, and
`code-documentation-standards` are untouched)._

## Impact

- **DB**: new `db/init/02_ticket_events.sql` (table + trigger functions + triggers on
  `tickets`/`messages`). Existing tables untouched. One-off apply needed on the existing dev DB
  and any deployed instance.
- **Code**: `services/rag/app/main.py` (or a small new route module) gains
  `GET /tickets/{ticket_id}/events`; `services/rag/app/schemas.py` gains the response model.
- **Tests**: `services/rag/tests/conftest.py` must apply all `db/init/*.sql` in order (it
  currently hardcodes `01_schema.sql`); new L2 tests for trigger capture, append-only
  enforcement, and the endpoint.
- **Docs**: `docs/decisions/ADR-006-*.md` (new), `wiki/map.md` (invariant #2 rewording + new
  component row), `wiki/log.md`, `PROGRESS.md`.
- **Not affected**: n8n workflow JSONs, existing endpoints, `kb_*`/`llm_calls` tables, evals.
