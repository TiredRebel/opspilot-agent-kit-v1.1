#!/usr/bin/env python3
"""CLI entrypoint for `make mq-topology` — declares the OpsPilot broker topology (ADR-007).

Declares exchanges/queues/bindings via RabbitMQ's management HTTP API. Chosen over a
`definitions.json` boot-load because load_definitions replaces the seeded default user (it
would either embed a password hash in a committed file or leave the broker with no user).
Every call is idempotent: PUT on an existing exchange/queue with identical arguments is a
no-op, and a binding is identified by (source, destination, routing key, arguments) so a
repeated POST creates nothing new. Re-declaring a queue with DIFFERENT arguments returns
406 PRECONDITION_FAILED — delete the queue in the management UI first, then re-run.

Topology (all durable, classic queues — single-node dev):
  opspilot.work   (direct)  rk=draft         -> q.draft_answer            (WF-2 consumes)
                            rk=deliver       -> q.outbound_delivery       (WF-6 consumes)
                            rk=deliver.retry -> q.outbound_delivery.retry (TTL 30s, dead-letters
                                                back to opspilot.work/deliver)
  opspilot.dlx    (fanout)                   -> q.dead_letter             (parked after 5 attempts)
  opspilot.events (topic)   rk=<event type>  -> no bindings yet (fan-out contract for future
                                                consumers; WF-7 publishes ticket_events rows)
"""

import os
import sys

import httpx

VHOST = "%2F"  # URL-encoded default vhost "/"

EXCHANGES: list[tuple[str, str]] = [
    ("opspilot.work", "direct"),
    ("opspilot.dlx", "fanout"),
    ("opspilot.events", "topic"),
]

# (name, arguments)
QUEUES: list[tuple[str, dict]] = [
    ("q.draft_answer", {}),
    ("q.outbound_delivery", {}),
    (
        "q.outbound_delivery.retry",
        {
            "x-message-ttl": 30000,
            "x-dead-letter-exchange": "opspilot.work",
            "x-dead-letter-routing-key": "deliver",
        },
    ),
    ("q.dead_letter", {}),
]

# (exchange, queue, routing key)
BINDINGS: list[tuple[str, str, str]] = [
    ("opspilot.work", "q.draft_answer", "draft"),
    ("opspilot.work", "q.outbound_delivery", "deliver"),
    ("opspilot.work", "q.outbound_delivery.retry", "deliver.retry"),
    ("opspilot.dlx", "q.dead_letter", ""),
]


def main() -> int:
    """Declare the full topology against the running broker and print what was ensured."""
    port = os.environ.get("RABBITMQ_MGMT_PORT", "15672")
    user = os.environ.get("RABBITMQ_USER", "opspilot")
    password = os.environ.get("RABBITMQ_PASSWORD", "changeme")
    base = f"http://localhost:{port}/api"

    try:
        with httpx.Client(auth=(user, password), timeout=30) as client:
            for name, kind in EXCHANGES:
                r = client.put(
                    f"{base}/exchanges/{VHOST}/{name}",
                    json={"type": kind, "durable": True},
                )
                r.raise_for_status()
                print(f"exchange ensured: {name} ({kind})")

            for name, arguments in QUEUES:
                r = client.put(
                    f"{base}/queues/{VHOST}/{name}",
                    json={"durable": True, "arguments": arguments},
                )
                r.raise_for_status()
                print(f"queue ensured: {name}")

            for exchange, queue, routing_key in BINDINGS:
                r = client.post(
                    f"{base}/bindings/{VHOST}/e/{exchange}/q/{queue}",
                    json={"routing_key": routing_key},
                )
                r.raise_for_status()
                print(f"binding ensured: {exchange} --{routing_key or '(fanout)'}--> {queue}")
    except httpx.ConnectError:
        print(f"Could not reach {base} — is `docker compose up -d` running?", file=sys.stderr)
        return 1
    except httpx.HTTPStatusError as exc:
        print(
            f"{exc.request.method} {exc.request.url} -> {exc.response.status_code}: "
            f"{exc.response.text}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
