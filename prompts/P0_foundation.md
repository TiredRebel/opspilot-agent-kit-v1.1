# Phase 0 — Foundation (paste into Claude Code plan mode, or Codex, from repo root)
# Prerequisite: this kit's files are committed in a fresh git repo.

===== COPY FROM HERE =====
## Objective
Scaffold the OpsPilot repository: running docker-compose stack, database schema, tooling, and knowledge-base seed content. This is a portfolio project — a clean, reproducible foundation matters more than speed.

## Context
Read first: AGENTS.md (session protocol — mandatory), docs/SPEC.md, PROGRESS.md, wiki/gotchas.md (esp. #1 n8n port, #4 pgvector image, #7 line endings). The repo currently contains only the agent kit files. An n8n instance already exists on this machine — resolve gotcha #1 explicitly and record the decision.

## Target State (task IDs P0-1..P0-4)
- P0-1: `docker-compose.yml` with postgres (pgvector/pgvector:pg16), rag-api (minimal FastAPI returning /health), n8n — healthchecks, named volumes, pinned tags, env from `.env`.
- P0-2: `db/init/01_schema.sql` copied exactly from docs/SPEC.md §3.3, auto-applied on first postgres start.
- P0-3: `Makefile` (up, seed [stub], lint, test, evals [stub], backup [stub]), `.env.example` with every variable the spec implies (DB, LLM keys, N8N_API_URL/KEY, TELEGRAM tokens placeholder, CONFIDENCE_THRESHOLD, DAILY_BUDGET_USD, NOTION page), `pyproject.toml` with ruff+pytest config, `.gitattributes` forcing LF, `.gitignore`.
- P0-4: `kb/seed/` — 8–12 fake "Acme" product docs (mixed UA/EN, 300–800 words, consistent product/plan names and prices across all docs). Use subagents for drafting; you review consistency.

## Scope
Work only in: repo root config files, db/, kb/seed/, services/rag/ (stub only). Do NOT touch: wiki/ history, prompts/, docs/SPEC.md.

## Constraints
Follow AGENTS.md conventions exactly (Python, uv, 3.12, ruff, LF). Only make changes directly requested — no extra services, no ORM, no CI yet. Create documented comments. Follow PEP-8, use typing 

## Acceptance Criteria
- [ ] `cp .env.example .env && docker compose up -d` → all services healthy
- [ ] `docker compose exec postgres psql -U $POSTGRES_USER -c "\dt"` shows all 4 tables; vector extension present
- [ ] `curl localhost:<rag_port>/health` → 200
- [ ] `make lint` green; kb/seed contains 8–12 consistent docs
- [ ] PROGRESS.md P0 boxes ticked; session entry appended to wiki/log.md; port decision recorded

## Stop Conditions
Stop and record a blocker before: changing the schema, adding services beyond the three, or if the existing n8n instance cannot be reused AND port 5679 is occupied.

## Progress
After each completed step output: ✅ [what was done] — [files affected]
===== COPY TO HERE =====
