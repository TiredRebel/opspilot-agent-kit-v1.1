# Tasks — add-ticket-events-log

## 1. Database

- [x] 1.1 Write `db/init/02_ticket_events.sql`: `ticket_events` table
      (`id UUID PK default gen_random_uuid(), ticket_id UUID NOT NULL REFERENCES tickets(id),
      type TEXT NOT NULL, payload JSONB NOT NULL DEFAULT '{}', created_at TIMESTAMPTZ NOT NULL
      DEFAULT now()`) + index on `(ticket_id, created_at)` — idempotent
      (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`)
- [x] 1.2 Same file: append-only guard — `BEFORE UPDATE OR DELETE` trigger on `ticket_events`
      whose function raises an exception naming the table and the policy
- [x] 1.3 Same file: `tickets` capture trigger (AFTER INSERT OR UPDATE) emitting
      `ticket.created`, `ticket.classified` (category NULL→non-NULL, payload = 4 triage fields),
      `ticket.status_changed` (payload `{"from","to"}`), `ticket.sla_reminded`
      (`last_reminder_at` set/advanced); `CREATE OR REPLACE FUNCTION` + `DROP TRIGGER IF EXISTS`
      before `CREATE TRIGGER` for idempotency
- [x] 1.4 Same file: `messages` capture trigger (AFTER INSERT) emitting `message.added`
      (payload: role, message id)
- [x] 1.5 Apply the file to the running dev database
      (`docker exec opspilot-agent-kit-v11-postgres-1 psql -U opspilot -d opspilot -f ...` via
      the mounted `/docker-entrypoint-initdb.d/02_ticket_events.sql`) and re-run it once more to
      prove idempotency

## 2. Test harness

- [x] 2.1 `services/rag/tests/conftest.py`: replace the hardcoded `01_schema.sql` read with all
      `db/init/*.sql` files applied in sorted order; add `ticket_events` to `_clean_tables`'
      TRUNCATE list
- [x] 2.2 `evals/conftest.py`: verified NO change needed — corrected during apply: it applies
      no schema at all (runs against the real dev DB, which got the DDL via task 1.5)

## 3. Read endpoint

- [x] 3.1 `services/rag/app/schemas.py`: add `TicketEvent` (`type: str, payload: dict,
      created_at: datetime`) and `TicketEventsResponse` (`ticket_id: UUID,
      events: list[TicketEvent]`) models
- [x] 3.2 `services/rag/app/main.py`: add `GET /tickets/{ticket_id}/events` — UUID-typed path
      param (422 on malformed), 404 when the ticket doesn't exist, otherwise events ordered by
      `created_at` ascending

## 4. Tests (L2, fake provider)

- [x] 4.1 `test_ticket_events.py`: ticket INSERT → `ticket.created`; triage UPDATE →
      `ticket.classified` with 4-field payload; `needs_human`→`answered` status UPDATE →
      `ticket.status_changed` with `{"from","to"}` payload; `last_reminder_at` UPDATE →
      `ticket.sla_reminded`; message INSERT (role `ai_draft`) → `message.added`
- [x] 4.2 Same file: UPDATE and DELETE against `ticket_events` each raise
      (append-only enforcement), row unchanged/present afterwards
- [x] 4.3 Same file: endpoint tests — ordered 200 response for a ticket with 3+ events, 404 for
      an unknown UUID, 422 for a malformed ticket_id
- [x] 4.4 `make lint && make test` — all green

## 5. Live verification

- [x] 5.1 Smoke test against the dev stack: insert a ticket + status update via psql (same SQL
      shapes n8n's postgres nodes use), confirm events appear and
      `GET /tickets/{id}/events` returns them in order

## 6. Docs and session protocol

- [x] 6.1 Write `docs/decisions/ADR-006-additive-schema-changes.md`: freeze amendment (existing
      tables frozen; additive-only via numbered `db/init/NN_*.sql` + ADR each), trigger-based
      capture rationale, append-only enforcement choice
- [x] 6.2 `wiki/map.md`: reword invariant #2 per ADR-006; add a component row for
      `ticket_events` (path `db/init/02_ticket_events.sql` + endpoint + tests)
- [x] 6.3 Append `wiki/log.md` entry and update `PROGRESS.md` (Maintenance section)
- [x] 6.4 `openspec validate add-ticket-events-log` passes
