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
