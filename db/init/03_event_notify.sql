-- 03_event_notify.sql — pg_notify fan-out hook for ticket_events (ADR-007).
--
-- Additive-only schema change (ADR-006): no table or column is touched; this file only adds an
-- AFTER INSERT trigger on ticket_events that broadcasts each new event on the 'ticket_events'
-- NOTIFY channel. WF-7 (n8n Postgres Trigger, LISTEN mode) consumes the channel and republishes
-- the full event row to the opspilot.events topic exchange.
--
-- The NOTIFY payload is deliberately minimal ({id, type, ticket_id}) — pg_notify payloads are
-- capped at ~8000 bytes and ticket_events.payload is unbounded JSONB, so the listener SELECTs
-- the full row by id instead. NOTIFY is fire-and-forget (no listener = event dropped from the
-- channel); ticket_events remains the durable source of truth and missed events stay
-- recoverable via GET /tickets/{id}/events.
--
-- Idempotent: CREATE OR REPLACE + DROP TRIGGER IF EXISTS — safe to re-run. Fresh volumes pick
-- this up automatically (initdb runs docker-entrypoint-initdb.d in lexical order, after
-- 02_ticket_events.sql created the table); existing databases apply it once via:
--   docker exec opspilot-agent-kit-v11-postgres-1 \
--     psql -U opspilot -d opspilot -f /docker-entrypoint-initdb.d/03_event_notify.sql

CREATE OR REPLACE FUNCTION ticket_events_notify() RETURNS trigger AS $$
BEGIN
  PERFORM pg_notify(
    'ticket_events',
    json_build_object('id', NEW.id, 'type', NEW.type, 'ticket_id', NEW.ticket_id)::text
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS ticket_events_notify ON ticket_events;
CREATE TRIGGER ticket_events_notify
  AFTER INSERT ON ticket_events
  FOR EACH ROW EXECUTE FUNCTION ticket_events_notify();
