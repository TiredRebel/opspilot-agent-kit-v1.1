# ticket-event-log — new capability for add-ticket-events-log

## ADDED Requirements

### Requirement: Ticket lifecycle events SHALL be captured from all writers via database triggers
The system SHALL record ticket lifecycle events in a `ticket_events` table
(`id, ticket_id, type, payload jsonb, created_at`), populated by database triggers on `tickets`
and `messages` so that writes from every client (n8n postgres nodes and the rag-api alike) are
captured without workflow changes. Event types and payloads:
`ticket.created` (on ticket INSERT), `ticket.classified` (when `category` first becomes
non-NULL; payload carries category/priority/sentiment/lang), `ticket.status_changed` (on any
status transition; payload `{"from": <old>, "to": <new>}`), `ticket.sla_reminded` (when
`last_reminder_at` is set or advanced), and `message.added` (on message INSERT; payload carries
the message role and id).

#### Scenario: Ticket insert produces a created event
- **WHEN** a row is inserted into `tickets` (by any client)
- **THEN** a `ticket.created` event for that ticket SHALL exist in `ticket_events`

#### Scenario: Triage update produces a classified event
- **WHEN** a ticket's `category` is updated from NULL to a non-NULL value
- **THEN** a `ticket.classified` event SHALL be recorded with the ticket's category, priority,
  sentiment, and lang in its payload

#### Scenario: Status transition produces a status_changed event
- **WHEN** a ticket's `status` is updated from `needs_human` to `answered`
- **THEN** a `ticket.status_changed` event SHALL be recorded with payload
  `{"from": "needs_human", "to": "answered"}`

#### Scenario: SLA reminder produces an sla_reminded event
- **WHEN** a ticket's `last_reminder_at` is set or moved forward
- **THEN** a `ticket.sla_reminded` event SHALL be recorded for that ticket

#### Scenario: Message insert produces a message.added event
- **WHEN** a row with role `ai_draft` is inserted into `messages` for a ticket
- **THEN** a `message.added` event SHALL be recorded for that ticket with role `ai_draft` in its
  payload

### Requirement: The event log SHALL be append-only, enforced by the database
`ticket_events` SHALL reject UPDATE and DELETE statements at the database level (raising an
error), for every role including the table owner. TRUNCATE remains permitted (test-suite
cleanup).

#### Scenario: Updates are rejected
- **WHEN** any client executes an UPDATE against a `ticket_events` row
- **THEN** the statement SHALL fail with an error and the row SHALL remain unchanged

#### Scenario: Deletes are rejected
- **WHEN** any client executes a DELETE against a `ticket_events` row
- **THEN** the statement SHALL fail with an error and the row SHALL remain present

### Requirement: The rag-api SHALL expose a ticket's event history
`GET /tickets/{ticket_id}/events` SHALL return the ticket's events ordered by `created_at`
ascending, each with `type`, `payload`, and `created_at`. An unknown `ticket_id` SHALL return
404; a malformed (non-UUID) `ticket_id` SHALL return 422.

#### Scenario: Events are returned in order
- **WHEN** a ticket has `ticket.created`, `ticket.classified`, and `ticket.status_changed`
  events and `GET /tickets/{ticket_id}/events` is called
- **THEN** the response SHALL be 200 with the three events in chronological order, each carrying
  its type, payload, and timestamp

#### Scenario: Unknown ticket returns 404
- **WHEN** `GET /tickets/{ticket_id}/events` is called with a well-formed UUID that matches no
  ticket
- **THEN** the response SHALL be 404

### Requirement: The schema freeze SHALL be amended additively, not broken
The `ticket_events` DDL SHALL ship as a new `db/init/02_ticket_events.sql` file (auto-applied on
fresh volumes, idempotent so it can be applied once to existing databases), with no modification
to `db/init/01_schema.sql` or any existing table. The amended freeze policy — existing
tables/columns frozen; additive-only changes via new numbered init files, each requiring an
ADR — SHALL be recorded in an ADR and reflected in `wiki/map.md` invariant #2. The test suites
SHALL build their databases from all `db/init/*.sql` files in lexical order so test schemas
match fresh-volume schemas.

#### Scenario: Fresh database includes the event log
- **WHEN** postgres initializes a fresh volume from `db/init/`
- **THEN** `ticket_events`, its triggers, and its index SHALL exist alongside the original five
  tables, with `01_schema.sql` byte-for-byte unchanged

#### Scenario: Idempotent apply to an existing database
- **WHEN** `db/init/02_ticket_events.sql` is executed against a database where it has already
  been applied
- **THEN** it SHALL complete without error and without duplicating triggers or data

#### Scenario: Test database matches fresh-volume schema
- **WHEN** the L1/L2 test suite builds its dedicated test database
- **THEN** every file in `db/init/` SHALL have been applied in lexical order, and the
  trigger-capture tests SHALL pass against that database
