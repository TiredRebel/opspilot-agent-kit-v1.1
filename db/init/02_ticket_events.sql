-- 02_ticket_events.sql — append-only ticket lifecycle event log (ADR-006).
--
-- Additive-only schema change: 01_schema.sql remains byte-for-byte frozen (map.md invariant #2,
-- as amended by ADR-006). Fresh volumes pick this file up automatically (the postgres entrypoint
-- runs docker-entrypoint-initdb.d files in lexical order); existing databases apply it once via
-- psql — every statement is idempotent, so re-running is harmless.
--
-- Events are captured by triggers (not application code) so BOTH writers — n8n's postgres nodes
-- and the rag-api — are covered without touching any workflow JSON. Triggers see row diffs, not
-- operator intent: approve and edit-reply both surface as status_changed needs_human->answered.
-- Intent-level events belong to a future change where the service owns ticket writes.

-- seq exists because events from one transaction share created_at (now() is transaction time);
-- it is the deterministic tiebreak for "ORDER BY created_at" reads.
CREATE TABLE IF NOT EXISTS ticket_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  seq BIGINT GENERATED ALWAYS AS IDENTITY,
  ticket_id UUID NOT NULL REFERENCES tickets(id),
  type TEXT NOT NULL,        -- ticket.created | ticket.classified | ticket.status_changed
                             -- | ticket.sla_reminded | message.added
  payload JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ticket_events_ticket_created_idx
  ON ticket_events (ticket_id, created_at, seq);

-- Append-only, enforced in the database: a REVOKE-based scheme would not bind here because both
-- writers connect as the owning role (owners bypass their own revokes); a raising trigger binds
-- every role. TRUNCATE stays permitted deliberately — the test suite truncates between tests.
CREATE OR REPLACE FUNCTION ticket_events_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'ticket_events is append-only: % not allowed (ADR-006)', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS ticket_events_append_only ON ticket_events;
CREATE TRIGGER ticket_events_append_only
  BEFORE UPDATE OR DELETE ON ticket_events
  FOR EACH ROW EXECUTE FUNCTION ticket_events_append_only();

-- Capture: tickets. One UPDATE may legitimately emit several events (e.g. a triage update that
-- also flips status emits ticket.classified AND ticket.status_changed).
CREATE OR REPLACE FUNCTION tickets_capture_events() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    INSERT INTO ticket_events (ticket_id, type, payload)
    VALUES (NEW.id, 'ticket.created',
            jsonb_build_object('source', NEW.source, 'status', NEW.status));
    RETURN NEW;
  END IF;

  IF OLD.category IS NULL AND NEW.category IS NOT NULL THEN
    INSERT INTO ticket_events (ticket_id, type, payload)
    VALUES (NEW.id, 'ticket.classified',
            jsonb_build_object('category', NEW.category, 'priority', NEW.priority,
                               'sentiment', NEW.sentiment, 'lang', NEW.lang));
  END IF;

  IF NEW.status IS DISTINCT FROM OLD.status THEN
    INSERT INTO ticket_events (ticket_id, type, payload)
    VALUES (NEW.id, 'ticket.status_changed',
            jsonb_build_object('from', OLD.status, 'to', NEW.status));
  END IF;

  IF NEW.last_reminder_at IS DISTINCT FROM OLD.last_reminder_at
     AND NEW.last_reminder_at IS NOT NULL THEN
    INSERT INTO ticket_events (ticket_id, type, payload)
    VALUES (NEW.id, 'ticket.sla_reminded',
            jsonb_build_object('reminded_at', NEW.last_reminder_at));
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tickets_capture_events ON tickets;
CREATE TRIGGER tickets_capture_events
  AFTER INSERT OR UPDATE ON tickets
  FOR EACH ROW EXECUTE FUNCTION tickets_capture_events();

-- Capture: messages. messages.ticket_id is nullable; ticket_events.ticket_id is NOT NULL, so an
-- unlinked message is skipped rather than failing the original INSERT.
CREATE OR REPLACE FUNCTION messages_capture_events() RETURNS trigger AS $$
BEGIN
  IF NEW.ticket_id IS NOT NULL THEN
    INSERT INTO ticket_events (ticket_id, type, payload)
    VALUES (NEW.ticket_id, 'message.added',
            jsonb_build_object('role', NEW.role, 'message_id', NEW.id));
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS messages_capture_events ON messages;
CREATE TRIGGER messages_capture_events
  AFTER INSERT ON messages
  FOR EACH ROW EXECUTE FUNCTION messages_capture_events();
