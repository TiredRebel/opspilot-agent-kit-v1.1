# Design — add-ticket-events-log

## Context

Ticket state transitions are performed by two writers: ~10 postgres nodes across the five n8n
workflows (insert ticket, update triage fields, update status on answer/escalation, mark
reminded) and the rag-api (which today writes only `llm_calls`/`kb_*`, but owns the HTTP surface).
The DB schema has been frozen since P0-2 (map.md invariant #2) — five tables, init SQL in
`db/init/01_schema.sql` run by the postgres image's entrypoint on fresh volumes only. The test
suite builds its dedicated `<POSTGRES_DB>_test` database by executing `01_schema.sql` directly
(hardcoded in `services/rag/tests/conftest.py` and `evals/conftest.py`).

Constraints: AGENTS.md scope discipline; ADR-004 (asyncpg, no ORM — DDL is plain SQL); the
dual-writer reality means any capture mechanism that requires editing workflow JSONs multiplies
the coupling this repo's architecture review flagged as hotspot #1; the freeze exists to prevent
casual schema drift, so an exception must be explicit and narrow, not silent.

## Goals / Non-Goals

**Goals:**
- Durable, queryable audit trail of ticket lifecycle events, capturing writes from *both*
  writers with no n8n workflow changes.
- Append-only enforced by the database itself (UPDATE/DELETE on `ticket_events` raise), so no
  writer — including a future buggy one — can rewrite history.
- A read path (`GET /tickets/{ticket_id}/events`) so the trail is usable without psql.
- An explicit, documented amendment to the schema freeze (ADR-006) that keeps its protective
  intent: existing tables stay frozen; additive changes need a numbered init file + ADR.

**Non-Goals:**
- Not event sourcing: `tickets.status` remains the source of truth; events are derived history,
  and no projection/replay machinery is built.
- No semantic intent events the database cannot know (`draft.approved` vs `draft.edited` both
  land as `status_changed {from: needs_human, to: answered}` — distinguishing them requires the
  service to own ticket writes, which is the separate hotspot-#1 change).
- No `pg_notify`/LISTEN, no queue, no consumers — this is the substrate a later async change
  builds on, deliberately shipped without speculation about its consumers.
- No n8n workflow or existing-endpoint changes; no backfill of historical tickets (the log
  starts when the triggers land).

## Decisions

1. **Trigger-based capture over application-level writes.** AFTER INSERT/UPDATE triggers on
   `tickets` and AFTER INSERT on `messages` derive events from row diffs. Rationale: it is the
   only mechanism that covers both writers today without editing five workflow JSONs (which
   would deepen the dual-writer coupling) and without first doing the service-owns-ticket-writes
   refactor. Alternatives — n8n INSERT nodes per transition (10+ edit sites, drift-prone) or
   rag-api-only capture (misses every n8n write) — both rejected. Trade-off accepted: triggers
   are less visible than application code; mitigated by ADR-006 + a map.md row pointing at the
   one SQL file that defines them.

2. **Generic `ticket.status_changed {from, to}` over invented per-transition names.** The
   trigger sees column values, not operator intent; emitting `draft.approved` from a trigger
   would be guessing (approve and edit-reply are indistinguishable at the row level). Honest
   generic events now; intent-level events arrive when the service owns writes. `type` is TEXT
   (not an enum) so that later change can add richer types without DDL.

3. **Append-only enforced by a BEFORE UPDATE OR DELETE trigger that raises.** Rationale: a
   GRANT/REVOKE scheme doesn't bite here (both writers connect as the owning role `opspilot`,
   and owners bypass revokes on their own tables); a trigger binds the rule to the table itself
   for every role. TRUNCATE is left permitted deliberately — the test suite truncates all tables
   between tests.

4. **DDL ships as `db/init/02_ticket_events.sql`**, not an edit to `01_schema.sql` and not a new
   migrations framework. The postgres entrypoint runs `docker-entrypoint-initdb.d` files in
   lexical order on fresh volumes, so fresh installs need nothing; existing databases get a
   documented one-off `docker exec ... psql -f` apply (idempotent: `CREATE TABLE IF NOT EXISTS`
   + `CREATE OR REPLACE FUNCTION` + drop/recreate triggers). Rationale: one additive file
   preserves "01 is frozen" literally and avoids adopting a migration tool for a single table —
   revisit only if additive files start accumulating.

5. **Both conftests switch from hardcoded `01_schema.sql` to executing all `db/init/*.sql` in
   sorted order.** Otherwise the test DB diverges from a fresh-volume DB the moment a second
   init file exists — this is the one existing-code change the DDL forces, and it also future-
   proofs any later additive file.

6. **`ticket.classified` fires when `category` transitions from NULL to non-NULL** (payload
   carries all four triage fields). A later re-classify (category changing between non-NULL
   values) emits `ticket.status_changed`-style granular events only if status also changes —
   re-classification of an already-triaged ticket is not a flow that exists today, and the
   trigger stays simple rather than speculating.

7. **Read endpoint in `main.py` following the existing route pattern** (Pydantic response model
   in `schemas.py`, SQL inline via the pool, 404 on unknown ticket). No repository-layer
   refactor smuggled in — that's a separate review item.

## Risks / Trade-offs

- [Triggers add write overhead to every ticket/message write] → One indexed INSERT per event on
  a low-volume prototype; negligible. Measured stance: accept until volume says otherwise.
- [Trigger logic drifts from reality if columns change] → Existing tables are frozen (that part
  of invariant #2 is unchanged), so the diffed columns are stable by policy.
- [Existing dev/prod DBs silently missing the table (init files don't rerun)] → The one-off
  apply is a numbered task, `GET .../events` 500s loudly if the table is absent, and the L2
  suite fails without it (conftest applies all init files).
- [JSONB payload is schemaless and could rot] → Payload shapes are pinned in the spec's
  scenarios; the trigger SQL is the single producer, so shapes have exactly one definition site.
- [Freeze exception could become a slippery slope] → ADR-006 requires an ADR per additive file;
  the invariant wording keeps "existing tables frozen" absolute.

## Migration Plan

1. Land `db/init/02_ticket_events.sql` + conftest change + endpoint + tests (one commit).
2. Apply the SQL file to the running dev database (documented `docker exec` psql step).
3. Verify: L2 tests green; live smoke — create a ticket via WF-1 or SQL, watch events appear;
   `GET /tickets/{id}/events` returns them.
4. Docs: ADR-006, map.md (invariant #2 wording + component row), log.md, PROGRESS.md.
Rollback: drop the two triggers and the table (one documented SQL block); no existing table or
code path depends on it.

## Open Questions

- None blocking. (Whether `PgLedger`/a future service layer also writes intent-level events into
  this table is explicitly deferred to the service-owns-ticket-writes change.)
