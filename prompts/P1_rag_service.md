# Phase 1 — RAG/LLM service (paste into Claude Code plan mode, or Codex)
# Prerequisite: Phase 0 accepted.

===== COPY FROM HERE =====
## Objective
Implement the FastAPI service that owns ALL LLM access: ingestion, classification, RAG answering with a confidence gate, digest generation, and per-call cost logging. This service is the project's engineering centerpiece — production markers (fallback, budget guardrail, tests) are the point.

## Context
Read first: AGENTS.md, docs/SPEC.md §3.1+§4, docs/TESTPLAN.md (L1/L2 list), PROGRESS.md, wiki/log.md (last 2), wiki/gotchas.md (#5 embedding dims). Compose stack from P0 is running. Consult Context7/official docs for current API shapes of the Anthropic and OpenAI Python SDKs — do not guess.

## Target State (task IDs P1-1..P1-6)
- P1-1 `app/llm.py`: `complete(purpose, messages, schema=None) -> LLMResult`; providers: anthropic (Haiku-class, primary), openai (mini-class, fallback on 5xx/timeout), fake (deterministic canned outputs keyed by purpose, default in tests). Every call → INSERT into llm_calls (tokens, cost_usd from a pricing table in settings, latency_ms, success). Daily budget guardrail: if today's SUM(cost_usd) ≥ DAILY_BUDGET_USD → raise BudgetExceeded → HTTP 429.
- P1-2 `POST /kb/ingest` + `scripts/ingest.py` (reads kb/seed/*, chunks ~500 tokens/50 overlap, embeds via text-embedding-3-small, upserts). Wire `make seed`.
- P1-3 `POST /classify`: prompt from services/rag/prompts/classify.md; JSON-schema-validated output {category, priority, sentiment, lang}; exactly one retry on invalid JSON, then 422 + success=false logged.
- P1-4 `POST /query`: embed → top-5 cosine via pgvector → grounded answer with [source: title#chunk] citations (prompts/answer.md) → confidence = 0.5·mean_similarity + 0.5·self_check (prompts/self_check.md); return {answer, sources, confidence}.
- P1-5 `POST /summarize` (prompts/digest.md, Ukrainian output), `GET /health`, `GET /stats` per SPEC.
- P1-6 All L1/L2 tests listed in docs/TESTPLAN.md, using the fake provider; live tests behind @pytest.mark.live.

## Scope
Work only in: services/rag/, scripts/, Makefile (seed/test targets). Do NOT touch: db schema, n8n/, docker-compose service definitions (image/env additions for rag-api allowed).

## Constraints
asyncpg + raw SQL (no ORM). Prompts live in .md files, never inline. No new dependencies beyond: fastapi, uvicorn, asyncpg, pydantic, pydantic-settings, anthropic, openai, httpx, pytest, pytest-asyncio, ruff — ask before adding others.

## Acceptance Criteria
- [ ] `make seed` ingests all kb/seed docs; kb_chunks populated with 1536-dim embeddings
- [ ] `curl POST /query` with a seeded fact returns a cited answer and confidence in [0,1]
- [ ] `make test` green with LLM_PROVIDER=fake; boundary test proves gate: 0.70 passes, 0.699 escalates
- [ ] Fallback test proves primary failure → single fallback attempt, both rows in llm_calls
- [ ] Budget test proves 429 without a provider call when the cap is hit
- [ ] PROGRESS.md + wiki/log.md updated

## Stop Conditions
Stop and record a blocker before: schema changes, new dependencies, changing the confidence formula, or any live-API test outside @pytest.mark.live.

## Progress
After each completed step output: ✅ [what was done] — [files affected]
===== COPY TO HERE =====
