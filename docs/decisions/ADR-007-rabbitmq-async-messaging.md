# ADR-007 — Async message processing with RabbitMQ

## Context

Current OpsPilot hops are synchronous:
- WF-1 calls `Execute Workflow` into WF-2 immediately after classification.
- WF-2 and WF-3 send Telegram answers inline, with no retry if Telegram or the bot credential
  is temporarily down.
- `ticket_events` (the audit log added by ADR-006) has no push path; any future analytics or
  notification consumer would have to poll the database.

These work in the dev/demo environment but are fragile: a burst of intake while WF-2 is slow or
unavailable stalls WF-1 executions; a failed Telegram send loses the answer permanently; the
events table is a hidden integration seam without a published contract.

## Decision

Introduce RabbitMQ as the async backbone, consumed by **n8n's native RabbitMQ nodes** — no new
Python worker service. Use it for three patterns:

1. **Intake buffering** (WF-1 → `q.draft_answer` → WF-2): decouples intake from drafting.
2. **Outbound delivery** (WF-2/WF-3 → `q.outbound_delivery` → WF-6): explicit retry with a
   30-second delay, max 5 attempts, then a dead-letter queue + ops alert.
3. **Ticket-event fan-out** (pg_notify `ticket_events` → WF-7 → topic exchange `opspilot.events`):
   publishes a durable contract so future consumers can bind queues without touching the service.

Topology is declared idempotently by a small Python script (`scripts/rabbitmq_topology.py`) via
the management HTTP API, avoiding the `load_definitions` foot-gun of replacing the seeded broker
user or embedding password hashes in committed files.

## Consequences

- **At-least-once delivery everywhere.** Duplicates are possible on redelivery; consumers must
  be idempotent (ticket status is already an upsert-friendly target).
- **WF-1 no longer passes `ticket_id` to WF-2 as a workflow input; it publishes to a queue.**
  This is a deviation from the frozen `docs/SPEC.md` v1.0 architecture diagram and is recorded as
  a user-approved extension in `PROGRESS.md`.
- **No LLM or DB access outside existing boundaries.** The change touches only compose, n8n
  workflows, a broker topology script, and one additive DB trigger (ADR-006).
- **n8n stays the pure orchestrator** (ADR-001 spirit), with RabbitMQ replacing some of the
  `Execute Workflow` handoffs rather than adding a separate worker tier.
- **RabbitMQ credentials follow the existing convention:** workflow JSON references
  `"RabbitMQ - OpsPilot"` by name; real user/pass live only in `.env`.
- **Delivery retries are consumer-managed, not broker-managed.** n8n's RabbitMQ trigger nacks
  failed messages with `requeue=true` (amqplib default), so WF-6 republishes to a retry queue with
  `x-message-ttl` and a `attempts` counter in the message body. This avoids relying on broker
  `x-death` headers that would never accumulate under n8n's requeue behavior.
- **Event fan-out is fire-and-forget.** `pg_notify` drops notifications if no listener is
  connected; `ticket_events` remains the durable source of truth and is recoverable via
  `GET /tickets/{id}/events`.

## What this rules out

- A dedicated Python consumer service (would add a new deployable unit and test surface).
- Event sourcing (status remains the source of truth; events are an audit log + fan-out hook).
- MQTT, Kafka, or SQS (RabbitMQ is sufficient for a single-node portfolio deployment and ships
  with a management UI that makes demo verification easy).
