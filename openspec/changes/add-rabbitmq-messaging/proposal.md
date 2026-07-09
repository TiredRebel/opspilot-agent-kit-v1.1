# Add RabbitMQ async messaging

## Why

Every OpsPilot hop is currently synchronous. WF-1 executes WF-2 directly; customer-facing
Telegram sends happen inline inside WF-2 and WF-3; and `ticket_events` (the audit log from
ADR-006) has no push contract for future consumers. This is brittle: bursts or rag-api downtime
stall intake; a failed Telegram send loses the answer permanently; future analytics/notifications
would have to poll the events table. RabbitMQ gives the project production markers — buffered
intake, retried delivery with a dead-letter queue, and a fan-out topic for ticket lifecycle
events — without adding a new service tier (consumers remain n8n-native).

## What Changes

- **Docker/infra**: add `rabbitmq:3.13-management-alpine` to `docker-compose.yml`, expose
  `5672`/`15672`, `.env.example` vars, and `scripts/rabbitmq_topology.py` to declare the broker
  topology idempotently via the management HTTP API.
- **Intake buffering**: WF-1's tail `Execute Workflow (WF-2)` becomes a RabbitMQ publish to
  `opspilot.work` / `draft`; WF-2's trigger becomes a RabbitMQ Trigger on `q.draft_answer`.
- **Outbound delivery with retry/DLQ**: WF-2 and WF-3 publish customer-facing answers to
  `opspilot.work` / `deliver`; a new **WF-6 Outbound Delivery** consumes `q.outbound_delivery`,
  tries to send via Telegram, republishes to `deliver.retry` on failure (up to 5 attempts with a
  30-second TTL delay), and parks exhausted messages in `opspilot.dlx` → `q.dead_letter` while
  alerting ops.
- **Event fan-out**: new `db/init/03_event_notify.sql` adds an AFTER INSERT trigger on
  `ticket_events` that `pg_notify`s a lightweight payload on channel `ticket_events`; a new
  **WF-7 Event Publisher** listens via n8n's Postgres Trigger, SELECTs the full row, and
  publishes it to `opspilot.events` topic exchange keyed by event type (no bound queues yet —
  contract for future consumers).
- **Sync/export scripts**: `scripts/n8n_sync.py` and `scripts/export_n8n_workflows.py` updated
  for 7 workflows; WF-1 no longer needs `WF2_WORKFLOW_ID_PLACEHOLDER` patching because the
  handoff is now queue-based.

## Capabilities

### New Capabilities

- `async-messaging`: RabbitMQ broker topology (exchanges, queues, bindings), message contracts
  (`draft`, `deliver`, `deliver.retry`, event topic), retry/DLQ semantics, and n8n-native
  consumers.

### Modified Capabilities

- `n8n-workflow-export`: exported workflow set grows from 5 to 7 files (`WF-6`, `WF-7`).

## Impact

- **Deviation from frozen `docs/SPEC.md` v1.0**: WF-1→WF-2 is no longer a direct `Execute
  Workflow` chain and customer sends are no longer inline. This is a user-approved extension,
  recorded as a blocker/deviation entry in `PROGRESS.md`; the SPEC file itself is not edited.
- **No change to `app/llm/`** (ADR-001 — all LLM calls stay centralized).
- **No table/column changes** to existing schema (ADR-006); `03_event_notify.sql` is an additive
  trigger-only file.
- **No secrets in workflow JSON**; RabbitMQ credential uses the existing placeholder-name
  convention.
- **Docs**: ADR-007, `wiki/map.md`, `wiki/log.md`, `PROGRESS.md`, README quickstart update.
- **Tests**: existing `make test` should stay green; new topology script is lintable Python but
  not unit-tested (it requires a running broker).
