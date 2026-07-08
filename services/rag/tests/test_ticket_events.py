"""L2 tests for the trigger-captured ticket_events audit log (ADR-006).

Writes go through the raw pool connection — the same SQL shapes n8n's postgres nodes use — so
these tests prove capture works for the non-rag-api writer too."""

import json

import asyncpg
import pytest
from app import main
from fastapi.testclient import TestClient


async def _insert_ticket(pool, **overrides):
    defaults = {"source": "webform", "external_ref": "evt-test-1", "body": "help"}
    defaults.update(overrides)
    return await pool.fetchval(
        "INSERT INTO tickets (source, external_ref, body) VALUES ($1, $2, $3) RETURNING id",
        defaults["source"],
        defaults["external_ref"],
        defaults["body"],
    )


async def _events(pool, ticket_id):
    return await pool.fetch(
        "SELECT type, payload, created_at FROM ticket_events "
        "WHERE ticket_id = $1 ORDER BY created_at, seq",
        ticket_id,
    )


async def test_insert_produces_created_event(pool):
    ticket_id = await _insert_ticket(pool)
    rows = await _events(pool, ticket_id)
    assert [row["type"] for row in rows] == ["ticket.created"]


async def test_triage_update_produces_classified_event(pool):
    ticket_id = await _insert_ticket(pool)
    await pool.execute(
        "UPDATE tickets SET category='billing', priority='high', sentiment='negative', lang='en' "
        "WHERE id = $1",
        ticket_id,
    )
    rows = await _events(pool, ticket_id)
    classified = [row for row in rows if row["type"] == "ticket.classified"]
    assert len(classified) == 1
    assert json.loads(classified[0]["payload"]) == {
        "category": "billing",
        "priority": "high",
        "sentiment": "negative",
        "lang": "en",
    }


async def test_status_transition_produces_status_changed_event(pool):
    ticket_id = await _insert_ticket(pool)
    await pool.execute("UPDATE tickets SET status='needs_human' WHERE id = $1", ticket_id)
    await pool.execute("UPDATE tickets SET status='answered' WHERE id = $1", ticket_id)
    rows = await _events(pool, ticket_id)
    transitions = [
        json.loads(row["payload"]) for row in rows if row["type"] == "ticket.status_changed"
    ]
    assert transitions == [
        {"from": "new", "to": "needs_human"},
        {"from": "needs_human", "to": "answered"},
    ]


async def test_sla_reminder_produces_sla_reminded_event(pool):
    ticket_id = await _insert_ticket(pool)
    await pool.execute("UPDATE tickets SET last_reminder_at=now() WHERE id = $1", ticket_id)
    rows = await _events(pool, ticket_id)
    assert "ticket.sla_reminded" in [row["type"] for row in rows]


async def test_message_insert_produces_message_added_event(pool):
    ticket_id = await _insert_ticket(pool)
    await pool.execute(
        "INSERT INTO messages (ticket_id, role, content) VALUES ($1, 'ai_draft', 'draft text')",
        ticket_id,
    )
    rows = await _events(pool, ticket_id)
    added = [json.loads(row["payload"]) for row in rows if row["type"] == "message.added"]
    assert len(added) == 1
    assert added[0]["role"] == "ai_draft"
    assert "message_id" in added[0]


async def test_update_and_delete_are_rejected(pool):
    ticket_id = await _insert_ticket(pool)
    with pytest.raises(asyncpg.RaiseError, match="append-only"):
        await pool.execute(
            "UPDATE ticket_events SET type='tampered' WHERE ticket_id = $1", ticket_id
        )
    with pytest.raises(asyncpg.RaiseError, match="append-only"):
        await pool.execute("DELETE FROM ticket_events WHERE ticket_id = $1", ticket_id)
    rows = await _events(pool, ticket_id)
    assert [row["type"] for row in rows] == ["ticket.created"]


async def test_endpoint_returns_ordered_events(pool):
    ticket_id = await _insert_ticket(pool)
    await pool.execute(
        "UPDATE tickets SET category='technical', priority='normal', sentiment='neutral', "
        "lang='en' WHERE id = $1",
        ticket_id,
    )
    await pool.execute("UPDATE tickets SET status='answered' WHERE id = $1", ticket_id)

    with TestClient(main.app) as client:
        response = client.get(f"/tickets/{ticket_id}/events")

    assert response.status_code == 200
    body = response.json()
    assert body["ticket_id"] == str(ticket_id)
    assert [event["type"] for event in body["events"]] == [
        "ticket.created",
        "ticket.classified",
        "ticket.status_changed",
    ]
    assert body["events"][2]["payload"] == {"from": "new", "to": "answered"}
    timestamps = [event["created_at"] for event in body["events"]]
    assert timestamps == sorted(timestamps)


def test_endpoint_unknown_ticket_returns_404():
    with TestClient(main.app) as client:
        response = client.get("/tickets/00000000-0000-0000-0000-000000000000/events")
    assert response.status_code == 404


def test_endpoint_malformed_ticket_id_returns_422():
    with TestClient(main.app) as client:
        response = client.get("/tickets/not-a-uuid/events")
    assert response.status_code == 422
