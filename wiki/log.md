# log.md — chronological record (append-only)

Entry prefix convention (parseable): `## [YYYY-MM-DD HH:MM] <op> | <agent> | <title>`
where `<op>` ∈ `build | ingest | review | lint | query`.
Last N entries: `grep "^## \[" wiki/log.md | tail -5`

## [2026-07-05 11:00] build | kit-generator (Claude, chat) | Agent kit authored (pre-P0)
- Completed: AGENTS.md, CLAUDE.md, SPEC, TESTPLAN, prompts P0–P6 + R1/R2, wiki, PROGRESS
- Decisions: ADR-001 pre-locked (LLM calls only via FastAPI service); ADR-004 pre-locked (asyncpg, no ORM)
- Gotchas added: #1–#7 seeded from the owner's known environment
- Handoff / next: run prompts/P0_foundation.md in Claude Code (plan mode) from a fresh git repo

## [2026-07-05 12:00] ingest | kit-generator (Claude, chat) | karpathy LLM Wiki pattern adopted (v1.1)
- Source: gist.github.com/karpathy/442a6bf555914893e9891c11519de94f (read-only reference, not vendored)
- Changes: log.md prefix convention; INDEX.md → content catalog; map.md added as the zero-hop project map;
  R3 wiki-lint prompt added; AGENTS.md gained the "Wiki schema" section (page-creation heuristic, file-back rule)
- Deliberate deviation: single dense map page instead of per-entity pages — for a small greppable codebase,
  entity-page sprawl measured worse than one map page (see README → memory system notes)
- Handoff / next: unchanged — start with prompts/P0_foundation.md

## [2026-07-05 19:00] build | Claude Code | Phase 0 — Foundation (P0-1..P0-4)
- Completed: P0-1 docker-compose.yml (postgres pgvector/pgvector:pg16 + rag-api only), P0-2
  db/init/01_schema.sql (verbatim from SPEC §3.3), P0-3 Makefile/.env.example/pyproject.toml
  (uv-managed) + .gitattributes/.gitignore, P0-4 kb/seed (10 fake "Acme Cloud Suite" docs, UA+EN)
- Files touched: docker-compose.yml, db/init/01_schema.sql, Makefile, .env.example, pyproject.toml,
  uv.lock, .gitattributes, .gitignore, services/rag/{Dockerfile,app/*,tests/test_health.py},
  kb/seed/*.md (10 files), PROGRESS.md, wiki/map.md, wiki/gotchas.md
- Decisions: git repo initialized this session (was not a repo before); n8n port collision (gotcha
  #1) resolved by reusing the existing local n8n instance on :5678 rather than running a second one
  — no n8n service in this project's compose at all
- Gotchas added: #8 (port 8000 often taken on this machine, rag-api moved to 8010), #9 (`make` not
  installed in the Windows Git-Bash toolchain — verified via `uv run ruff/pytest` + `docker compose`
  directly instead); gotcha #1 updated to record its resolution
- Verified: `docker compose up -d` → both services healthy; `\dt` shows 5 tables; pgvector 0.8.4;
  `curl :8010/health` → 200 `{"status":"ok","db":true}`; `uv run ruff format --check .` and
  `uv run ruff check .` clean; `uv run pytest services/rag/tests` → 2 passed; kb/seed facts
  cross-checked via grep for contradictions — none found
- Handoff / next: Phase 1 (prompts/P1_rag_service.md) builds the real llm.py provider layer and
  /kb/ingest, /classify, /query, /summarize, /stats endpoints on top of this stub

## [2026-07-05 20:30] build | Claude Code | Phase 1 — RAG/LLM service (P1-1..P1-6)
- Completed: P1-1 app/llm.py (claude-haiku-4-5 primary, gpt-5.4-mini fallback on 5xx/timeout/
  connection errors, fake provider, daily budget guardrail, per-attempt llm_calls logging incl.
  fake calls), P1-2 POST /kb/ingest + scripts/ingest.py, P1-3 POST /classify (schema + 1 retry),
  P1-4 POST /query (top-5 pgvector + confidence gate), P1-5 POST /summarize + GET /stats, P1-6
  17 L1/L2 tests (all green, LLM_PROVIDER=fake)
- Files touched: services/rag/app/{llm,retrieval,schemas,main,settings}.py, services/rag/prompts/
  {classify,answer,self_check,digest}.md, services/rag/tests/{conftest,test_chunking,
  test_confidence,test_classify_schema,test_llm_fallback,test_budget_guardrail,
  test_ingest_query_roundtrip,test_idempotency,test_stats}.py, scripts/ingest.py, Dockerfile,
  docker-compose.yml, pyproject.toml, Makefile (seed target), PROGRESS.md, wiki/map.md,
  wiki/gotchas.md
- Decisions: model IDs verified live (not guessed) — Anthropic via the bundled claude-api skill
  (claude-haiku-4-5, $1/$5 per 1M), OpenAI via WebFetch of developers.openai.com
  (gpt-5.4-mini, $0.75/$4.50 per 1M; text-embedding-3-small unchanged, Context7 was
  quota-exhausted); kb/seed mounted read-only into rag-api rather than baked into the image;
  scripts/ingest.py is an HTTP client against the running service, not a direct DB script (host
  vs. container DATABASE_URL hostname mismatch); citations in /query are computed in code from
  top-k retrieval, not parsed out of LLM text, since the fake provider can't produce them
- Gotchas added: #10 (kb/ bind mount + KB_SEED_DIR), #11 (tests rewrite DATABASE_URL to
  localhost), #12 (app.db pool is loop-bound — pytest vs TestClient loops corrupt it if shared),
  #13 (llm_calls.ticket_id is UUID — type it as uuid.UUID at the API boundary, not str)
- Verified: `uv run ruff format --check .` / `ruff check .` clean; `uv run pytest
  services/rag/tests` → 17 passed; rebuilt rag-api via `docker compose up -d --build`; `make seed`
  (uv run scripts/ingest.py) → 10 docs / 15 chunks against the real kb/seed; manually curled
  /classify (valid UUID → 200, bad UUID → clean 422), /query (cited sources, confidence in
  [0,1]), /summarize (correct UTF-8 Ukrainian text — an earlier mangled-looking curl pipe was a
  terminal decoding artifact, not an app bug), /stats (reflects logged llm_calls)
- Handoff / next: Phase 2 (prompts/P2_intake_autoanswer.md) — n8n WF-1 Intake & Triage and WF-2
  Draft Answer, calling this service's /classify and /query over HTTP; P2-1 (BotFather bot
  creation) is [HUMAN]-only
