# Design — add-rabbitmq-messaging

## Topology

All resources are **durable**; queues are classic queues (single-node, portfolio deployment).
Declared by `scripts/rabbitmq_topology.py` via the management HTTP API, idempotently.

```
Exchange              Type        Bindings
opspilot.work         direct      draft        -> q.draft_answer
                                  deliver      -> q.outbound_delivery
                                  deliver.retry-> q.outbound_delivery.retry
opspilot.dlx          fanout                 -> q.dead_letter
opspilot.events       topic                    no bindings yet
```

`q.outbound_delivery.retry` has:
- `x-message-ttl = 30000` ms
- `x-dead-letter-exchange = opspilot.work`
- `x-dead-letter-routing-key = deliver`

When WF-6 fails to send to Telegram, it explicitly republishes to `deliver.retry` with
`attempts` incremented. After the TTL the message returns to `q.outbound_delivery`. WF-6 caps at
5 attempts (body counter) before parking the message in `opspilot.dlx` + alerting ops. This
consumer-managed counter is necessary because n8n's RabbitMQ trigger nacks failures with
`requeue=true` (amqplib default), so broker `x-death` headers never accumulate.

## Message contracts

### `draft` → `q.draft_answer`

```json
{ "ticket_id": "<uuid>" }
```

Producer: WF-1 after `Update Triage Fields`.
Consumer: WF-2 `RabbitMQ Trigger` (ack on success, nack on failure).

### `deliver` / `deliver.retry` → `q.outbound_delivery`

```json
{ "ticket_id": "<uuid>", "chat_id": "<string>", "text": "<string>", "attempts": 0 }
```

Producers:
- WF-2 high-confidence branch when `chat_id` is resolvable (Telegram source).
- WF-3 `Approve` and `Edit Reply` branches when `chat_id` is resolvable.

Webform tickets have no `chat_id`; existing skip behavior is preserved.

Consumer: WF-6.

### events topic → `opspilot.events`

Routing key = `ticket.created`, `ticket.classified`, `ticket.status_changed`,
`ticket.sla_reminded`, or `message.added`.

Payload:

```json
{
  "id": "<uuid>",
  "seq": 42,
  "ticket_id": "<uuid>",
  "type": "ticket.status_changed",
  "payload": { "from": "needs_human", "to": "answered" },
  "created_at": "2026-07-08T..."
}
```

Producer: WF-7.

## WF-6 Outbound Delivery detail

1. `RabbitMQ Trigger` on `q.outbound_delivery`, acknowledge `executionFinishesSuccessfully`.
2. `Assess Delivery` code node computes `attempts` (default 0), checks `chat_id`, and sets
   `give_up` true if no `chat_id` OR `attempts >= 5`.
3. `Give Up?` if true:
   - `Park In Dead Letter` → publish to `opspilot.dlx` (fanout).
   - `Alert Ops - Dead Letter` → Telegram message to `PLACEHOLDER_OPS_CHAT_ID`.
4. Else `Send To Customer` Telegram node; on error output branch → `Publish Retry` to
   `opspilot.work` / `deliver.retry` with `attempts + 1`.

## WF-7 Event Publisher detail

1. `Postgres Trigger` in `listenTrigger` mode on channel `ticket_events`.
2. `Parse Notify Payload` code node: parses `payload` string into `{ event_id }`.
3. `Select Full Event`: `SELECT id, seq, ticket_id, type, payload, created_at FROM ticket_events
   WHERE id = $1`.
4. `Publish Event`: RabbitMQ publish to `opspilot.events` topic exchange with routing key
   `={{ $json.type }}` and message = full row JSON.

`pg_notify` payload is intentionally tiny (`{id, type, ticket_id}`) to avoid the ~8 KB
payload cap; full JSONB `payload` is fetched by the SELECT.

## Delivery semantics

- **At-least-once.** Duplicates possible on redelivery or when a WF-2/WF-3 publish is acked but
  the status update is committed before the send. Producers/consumers are idempotent at the
  ticket level (status writes are not transactionally guarded, but duplicate sends to the same
  chat_id with the same text are harmless in practice).
- **WF-2 status may briefly show `answered` before Telegram send completes.** Acceptable for the
  demo deployment; noted in proposal/ADR.

## Open questions resolved

- **Why not use `load_definitions` or `definitions.json`?** It would either need a password
  hash in a committed file or replace the seeded default user. The management-HTTP script is
  password-free in the repo and mirrors the existing `scripts/ingest.py` pattern.
- **Why n8n consumers instead of a Python worker?** Keeps n8n as the pure orchestrator
  (ADR-001), reuses existing Telegram/Postgres credentials and monitoring, and avoids a new
  deployable unit for a portfolio project.
- **Why consumer-managed retry counter?** n8n's trigger nack behavior is `requeue=true`; relying
  on `x-death` headers will not count attempts.
