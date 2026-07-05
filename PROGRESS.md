# PROGRESS.md — Build board (single source of "what is done")

**Legend:** `[ ]` todo · `[~]` in progress (claimed: agent, date) · `[x]` done (date, agent) · `[HUMAN]` human-only task
**Rule:** claim a task by editing its line to `[~] (agent, YYYY-MM-DD)` in your first commit.

## Phase 0 — Foundation
- [x] P0-1 (Claude, 2026-07-05) docker-compose (postgres/pgvector, rag-api stub) with healthchecks + pinned tags. n8n excluded — existing local instance (localhost:5678) reused instead, see gotcha #1 resolution in wiki/log.md.
- [x] P0-2 (Claude, 2026-07-05) db/init/01_schema.sql per SPEC §3.3 — verified 5 tables + pgvector 0.8.4 on first postgres start.
- [x] P0-3 (Claude, 2026-07-05) Makefile, .env.example, ruff+pytest config, .gitattributes (LF), .gitignore, uv-managed pyproject.toml.
- [x] P0-4 (Claude, 2026-07-05) kb/seed: 10 fake Acme Cloud Suite docs (UA+EN, internally consistent — verified via grep sweep).

## Phase 1 — RAG/LLM service
- [ ] P1-1 llm.py provider layer: Claude primary, OpenAI fallback, fake provider, cost logging, budget guardrail
- [ ] P1-2 POST /kb/ingest + scripts/ingest.py (chunk 500/50, embed, upsert)
- [ ] P1-3 POST /classify (structured output, schema-validated, 1 retry)
- [ ] P1-4 POST /query (top-5 pgvector, citations, confidence blend, 0.70 gate)
- [ ] P1-5 POST /summarize, GET /health, GET /stats
- [ ] P1-6 L1/L2 tests per docs/TESTPLAN.md

## Phase 2 — Intake & auto-answer
- [ ] P2-1 [HUMAN] Create bot via BotFather; ops group; tokens/chat IDs into .env
- [ ] P2-2 WF-1 Intake & Triage (JSON authored + imported + activated via n8n API)
- [ ] P2-3 WF-2 Draft Answer with confidence gate
- [ ] P2-4 Intake idempotency verified (test_idempotency green)
- [ ] P2-5 [HUMAN] E2E M1 happy path + backup screen recording

## Phase 3 — Human-in-the-loop & SLA
- [ ] P3-1 WF-3 inline keyboard (Approve/Edit/Reject) + callback handling
- [ ] P3-2 Edit capture (reply-to) — both variants logged to messages
- [ ] P3-3 WF-4 SLA watchdog (idempotent reminders, last_reminder_at)
- [ ] P3-4 [HUMAN] E2E M2–M5

## Phase 4 — Digest & Notion
- [ ] P4-1 WF-5 digest SQL aggregates
- [ ] P4-2 /summarize integration (UA digest text)
- [ ] P4-3 Notion page append (sandbox page ID in .env)
- [ ] P4-4 [HUMAN] E2E M6

## Phase 5 — Evals & CI
- [ ] P5-1 evals/tickets.jsonl (25–30, ≥8 UA, ≥3 ambiguous)
- [ ] P5-2 eval tests: accuracy ≥ 0.85, groundedness, cost < $0.50/run
- [ ] P5-3 .github/workflows/ci.yml (lint + L1/L2 on push; evals manual dispatch)

## Phase 6 — Deploy & packaging
- [ ] P6-1 [HUMAN+AGENT] VM provision, compose up, domain + Caddy TLS, n8n auth
- [ ] P6-2 scripts/backup.sh + nightly cron to object storage
- [ ] P6-3 ADRs (001 locked, 002 confidence gate, 003 pgvector, 004 asyncpg) + docs/infrastructure.md with GCP↔AWS map
- [ ] P6-4 README final (diagram, metrics from /stats, live handle) + [HUMAN] 3-min video

## Blockers / Findings
_(agents append here; format: `- [OPEN|CLOSED] YYYY-MM-DD agent: description`)_

## Metrics to fill before applying
- Auto-resolution rate: __% · Avg confidence: __ · Avg cost/ticket: $__ · p95 answer latency: __ s · Eval accuracy: __%
