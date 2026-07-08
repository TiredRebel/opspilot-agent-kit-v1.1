# ADR-006 — Additive-only schema changes; trigger-captured ticket event log

**Context.** Invariant #2 (wiki/map.md) froze the DB schema after P0-2 to prevent casual drift
across the two writers (n8n's raw-SQL postgres nodes and the rag-api). But ticket lifecycle
state lived only in mutable columns — no record of when a ticket changed status, what the
transition was, or that an SLA reminder fired; the HITL flow left no audit trail. Adding an
event log requires a schema change, which the freeze as originally worded forbade outright.

**Decision.**
1. The freeze is amended, not broken: **existing tables and columns remain frozen**; additive
   changes (new tables/indexes/triggers) are allowed only as new numbered
   `db/init/NN_*.sql` files, each requiring its own ADR. `01_schema.sql` stays byte-for-byte
   unchanged. Fresh volumes apply init files in lexical order automatically; existing databases
   get a documented one-off idempotent apply. The test conftest builds its database from all
   `db/init/*.sql` in the same order, so test schemas cannot drift from fresh-volume schemas.
2. `ticket_events` (`db/init/02_ticket_events.sql`) is an **append-only audit log** populated by
   AFTER triggers on `tickets` and `messages` — not by application code — because triggers are
   the only mechanism that covers both writers without editing five workflow JSONs or first
   moving ticket writes into the service. Emitted types: `ticket.created`, `ticket.classified`,
   `ticket.status_changed` (`{"from", "to"}`), `ticket.sla_reminded`, `message.added`.
3. Append-only is enforced by a `BEFORE UPDATE OR DELETE` trigger that raises — a REVOKE-based
   scheme would not bind because both writers connect as the owning role, and owners bypass
   revokes on their own tables. TRUNCATE stays permitted (test-suite cleanup).

**Consequences.**
- Every ticket gets a durable, queryable history (`GET /tickets/{id}/events`) regardless of
  which system wrote the change — the audit trail the HITL flow lacked.
- Triggers see row diffs, not intent: approve and edit-reply both surface as
  `status_changed needs_human→answered`. Intent-level events (`draft.approved` etc.) are
  deliberately deferred to a future change where the service owns ticket writes; `type` is TEXT
  (not an enum) so that change adds types without DDL.
- `tickets.status` remains the source of truth — this is an audit log, not event sourcing; no
  projection/replay machinery exists or is implied.
- Ticket rows can no longer be DELETEd once they have events (FK with no cascade, and the log
  rejects deletes) — correct for an audit trail; tests use TRUNCATE ... CASCADE.
- Events created in one transaction share `created_at` (`now()` is transaction time); the `seq`
  identity column is the deterministic tiebreak and read order is `(created_at, seq)`.
- The slippery-slope risk of "additive-only" is bounded by requiring an ADR per new init file;
  if these files start accumulating, adopt a real migration tool then, not preemptively.
