# async-messaging

## Purpose

Defines the RabbitMQ topology, message contracts, retry/dead-letter semantics, and n8n-native
consumer responsibilities introduced by the `add-rabbitmq-messaging` change (ADR-007). This
replaces the previously synchronous WF-1→WF-2 handoff and inline Telegram sends with buffered,
retry-capable queues while adding a fan-out topic for `ticket_events`.

## Requirements

### Requirement: Broker topology SHALL be declared idempotently without embedded secrets
The system SHALL provide a script (`scripts/rabbitmq_topology.py`) that creates exchanges,
queues, and bindings against the running RabbitMQ management HTTP API so that re-running it is
a no-op. No password hash, credential, or user definition SHALL be committed.

#### Scenario: Re-declaring after the broker restarts
- **WHEN** the topology script is run against a freshly started broker
- **THEN** durable exchanges `opspilot.work` (direct), `opspilot.dlx` (fanout), and
  `opspilot.events` (topic) SHALL exist, along with queues `q.draft_answer`,
  `q.outbound_delivery`, `q.outbound_delivery.retry`, and `q.dead_letter`, with the bindings
  described in this spec

### Requirement: WF-1 SHALL hand off new tickets to WF-2 via a queue
After classifying and triaging a new ticket, WF-1 SHALL publish a `{ticket_id}` message to
`opspilot.work` with routing key `draft` bound to `q.draft_answer`. WF-2 SHALL consume that
queue via a `rabbitmqTrigger` node.

#### Scenario: WF-1 finishes triage
- **WHEN** WF-1 has successfully updated a new ticket's category/priority/sentiment/lang
- **THEN** it publishes `{ticket_id: "<uuid>"}` to `opspilot.work`/`draft` instead of
  executing WF-2 directly

### Requirement: WF-2 SHALL draft answers on buffered intake jobs
WF-2's trigger SHALL be a RabbitMQ Trigger on `q.draft_answer` that acknowledges the message
only when the workflow execution finishes successfully.

#### Scenario: A draft job arrives while WF-2 was briefly unavailable
- **WHEN** a message is in `q.draft_answer` and WF-2 comes back online
- **THEN** WF-2 eventually consumes it and processes the ticket through the existing confidence
  gate (no message loss)

### Requirement: Customer-facing sends SHALL be retried with a dead-letter queue
WF-2 (auto-answer branch) and WF-3 (Approve / Edit-Reply branches) SHALL publish customer-facing
answers to `opspilot.work`/`deliver` bound to `q.outbound_delivery`. A dedicated WF-6 SHALL consume
that queue, attempt a Telegram send, and on failure republish the message to
`opspilot.work`/`deliver.retry` (TTL 30s) with an incremented attempt counter. After 5 attempts
the message SHALL be published to the `opspilot.dlx` fanout exchange and an alert SHALL be sent
to the ops channel.

#### Scenario: Telegram API is temporarily down
- **WHEN** WF-6 tries to send a message and Telegram returns an error
- **THEN** the message re-enters `q.outbound_delivery` after 30 seconds, up to 5 times, before
  moving to `q.dead_letter` and alerting ops

#### Scenario: A ticket has no resolvable Telegram chat ID
- **WHEN** the delivery message has no `chat_id` (e.g. a webform source)
- **THEN** WF-6 SHALL park it in `q.dead_letter` immediately (no retry loop for an impossible
  delivery)

### Requirement: Ticket lifecycle events SHALL be published to a topic exchange
`db/init/03_event_notify.sql` SHALL add an AFTER INSERT trigger on `ticket_events` that emits a
lightweight `{id, type, ticket_id}` payload on the PostgreSQL `pg_notify` channel
`ticket_events`. WF-7 SHALL consume that channel with a Postgres Trigger node, SELECT the full
row, and publish it to `opspilot.events` with a routing key equal to the event `type`.

#### Scenario: A ticket status changes
- **WHEN** `ticket_events` gains a row with `type = ticket.status_changed`
- **THEN** WF-7 eventually publishes the full event row to `opspilot.events` with routing key
  `ticket.status_changed`

### Requirement: The events fan-out SHALL be durable but not lossless over listener downtime
`ticket_events` SHALL remain the source of truth. The `pg_notify` + topic exchange path is
fire-and-forget; missed events while no listener is connected SHALL be recoverable by reading the
`ticket_events` table directly.

#### Scenario: WF-7 is not running when an event fires
- **WHEN** a `ticket_events` row is inserted while WF-7 is stopped
- **THEN** the NOTIFY is dropped from the channel, but the row persists and can be queried via
  `GET /tickets/{ticket_id}/events`

## Constraints

- No LLM call outside the existing `app/llm/` package (unchanged by this change).
- No secret-bearing value in workflow JSON — use the existing placeholder-name convention for
  credentials and the ops chat ID.
- No change to existing tables or columns beyond the additive trigger file `03_event_notify.sql`
  (ADR-006).
