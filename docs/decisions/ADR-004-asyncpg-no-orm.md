# ADR-004 — asyncpg with raw SQL, no ORM

**Context.** The FastAPI service needs async Postgres access for five tables and a handful of
aggregate queries (`/stats`), plus a pgvector similarity query with a nonstandard operator
(`<=>`). An ORM (SQLAlchemy async, Tortoise, etc.) was the alternative.

**Decision.** Use `asyncpg` directly with hand-written SQL, no ORM layer. A single module-level
connection pool (`app/db.py`) is created lazily and reused for the lifetime of the process.

**Consequences.**
- Full control over exactly what SQL runs, including pgvector's `<=>` operator and dynamic
  `WHERE`-clause construction (`/stats`'s optional `?hours=` filter) — no ORM query-builder
  fighting a vector-similarity operator it doesn't know about.
- No migration framework either — schema changes are hand-edited SQL in `db/init/01_schema.sql`
  (frozen after P0-2; any change needs an ADR, per `AGENTS.md`), acceptable for a project this size
  with one schema file, not dozens of evolving tables.
- The pool is bound to whichever asyncio event loop first creates it, which is a real footgun in
  tests (pytest's own loop vs. `TestClient`'s worker-thread loop) — worked around by resetting the
  pool to `None` between tests (wiki/gotchas.md #12), not by the ORM handling it for us.
- More boilerplate per query (manual parameter binding, manual row→model mapping) than an ORM would
  give — accepted as the right tradeoff for a service this size with a stable, small schema.
