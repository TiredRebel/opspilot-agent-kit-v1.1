# Tasks — add-rabbitmq-messaging

## 1. Infrastructure

- [x] 1.1 Add `rabbitmq` service to `docker-compose.yml` (pinned
      `rabbitmq:3.13-management-alpine`, env credentials, ports, volume, healthcheck)
- [x] 1.2 Append RabbitMQ vars to `.env.example`
- [x] 1.3 Create `scripts/rabbitmq_topology.py` — idempotent topology declaration via management
      HTTP API (httpx, already a dependency)
- [x] 1.4 Add `make mq-topology` target to `Makefile`
- [x] 1.5 Run `make up` and `make mq-topology` twice to verify broker health and idempotency

## 2. Intake buffering (WF-1 → WF-2)

- [x] 2.1 Replace WF-1 tail `Execute Workflow (WF-2)` with a RabbitMQ publish to
      `opspilot.work` / `draft`, body `{ticket_id}`
- [x] 2.2 Replace WF-2 `executeWorkflowTrigger` with `rabbitmqTrigger` on `q.draft_answer`,
      acknowledge `executionFinishesSuccessfully`
- [x] 2.3 Update `scripts/n8n_sync.py` dependency order: no `WF2_WORKFLOW_ID_PLACEHOLDER` patching
      in WF-1

## 3. Outbound delivery with retry/DLQ

- [x] 3.1 Create `n8n/workflows/wf6_delivery.json` with RabbitMQ Trigger on
      `q.outbound_delivery`, delivery assessment, Telegram send, retry publish to
      `deliver.retry`, and dead-letter parking with ops alert
- [x] 3.2 Replace WF-2 `Reply To Customer` telegram node with RabbitMQ publish to
      `opspilot.work` / `deliver`
- [x] 3.3 Replace WF-3 Approve and Edit-Reply customer-send telegram nodes with RabbitMQ publishes
      to `opspilot.work` / `deliver`

## 4. Ticket-event fan-out

- [x] 4.1 Create `db/init/03_event_notify.sql`: AFTER INSERT trigger on `ticket_events` calling
      `pg_notify('ticket_events', {id,type,ticket_id}::json)`, idempotent
- [x] 4.2 Apply to dev DB twice to prove idempotency
- [x] 4.3 Create `n8n/workflows/wf7_event_publisher.json`: Postgres Trigger (LISTEN), parse payload,
      SELECT full event row, publish to `opspilot.events` topic keyed by event type

## 5. Tooling update

- [x] 5.1 Update `scripts/n8n_sync.py` to sync all 7 workflows
- [x] 5.2 Update `scripts/export_n8n_workflows.py` to export all 7 workflows

## 6. Documentation and tracking

- [x] 6.1 Create `docs/decisions/ADR-007-rabbitmq-async-messaging.md`
- [x] 6.2 Write `openspec/changes/add-rabbitmq-messaging/specs/async-messaging/spec.md` delta spec
      (topology, message contracts, retry/DLQ semantics)
- [x] 6.3 Update `PROGRESS.md` with new task entry and SPEC v1.0 deviation note
- [x] 6.4 Update `wiki/map.md`: new RabbitMQ/component rows, workflow count 7, updated WF-1/WF-2/WF-3
      notes
- [x] 6.5 Append `wiki/log.md` entry
- [x] 6.6 Add gotchas for RabbitMQ if any new traps are discovered (e.g. n8n trigger ack mode,
      host-port reachability)
- [x] 6.7 Update `README.md` quickstart with `make mq-topology` and management UI URL

## 7. Verification

- [x] 7.1 `make lint && make test` green
- [x] 7.2 Live E2E: webform/Telegram intake → message in `q.draft_answer` → WF-2 fires
- [x] 7.3 Delivery retry proof: break Telegram send temporarily, observe retries, then delivery
- [x] 7.4 Event fan-out proof: create ticket, observe publish on `opspilot.events`
- [x] 7.5 `python scripts/n8n_sync.py` imports all 7 workflows
- [x] 7.6 `python scripts/export_n8n_workflows.py` round-trips clean
- [x] 7.7 OpenSpec validate passes: `openspec validate --change add-rabbitmq-messaging`
