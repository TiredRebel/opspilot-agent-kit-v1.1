# PROGRESS.md — Build board (single source of "what is done")

**Legend:** `[ ]` todo · `[~]` in progress (claimed: agent, date) · `[x]` done (date, agent) · `[HUMAN]` human-only task
**Rule:** claim a task by editing its line to `[~] (agent, YYYY-MM-DD)` in your first commit.

## Phase 0 — Foundation
- [x] P0-1 (Claude, 2026-07-05) docker-compose (postgres/pgvector, rag-api stub) with healthchecks + pinned tags. n8n excluded — existing local instance (localhost:5678) reused instead, see gotcha #1 resolution in wiki/log.md.
- [x] P0-2 (Claude, 2026-07-05) db/init/01_schema.sql per SPEC §3.3 — verified 5 tables + pgvector 0.8.4 on first postgres start.
- [x] P0-3 (Claude, 2026-07-05) Makefile, .env.example, ruff+pytest config, .gitattributes (LF), .gitignore, uv-managed pyproject.toml.
- [x] P0-4 (Claude, 2026-07-05) kb/seed: 10 fake Acme Cloud Suite docs (UA+EN, internally consistent — verified via grep sweep).

## Phase 1 — RAG/LLM service
- [x] P1-1 (Claude, 2026-07-05) llm.py provider layer: claude-haiku-4-5 primary, gpt-5.4-mini fallback on 5xx/timeout/connection errors, fake provider (also cost-logged), budget guardrail (BudgetExceeded → 429), per-attempt cost logging to llm_calls.
- [x] P1-2 (Claude, 2026-07-05) POST /kb/ingest (idempotent re-ingest by title) + scripts/ingest.py (HTTP CLI wrapper for `make seed`); chunk ~500/50 words, embed via text-embedding-3-small, upsert kb_documents/kb_chunks.
- [x] P1-3 (Claude, 2026-07-05) POST /classify — JSON-schema structured output, 1 retry on invalid parse, 422 on second failure. ticket_id is UUID-typed (bad input → clean 422, not a raw 500).
- [x] P1-4 (Claude, 2026-07-05) POST /query — top-5 pgvector cosine search, [source: title#chunk] citations, confidence = 0.5*similarity + 0.5*self_check, gate boundary verified exactly at 0.70/0.699.
- [x] P1-5 (Claude, 2026-07-05) POST /summarize (UA digest text), GET /stats (ticket/cost/latency aggregates).
- [x] P1-6 (Claude, 2026-07-05) 17 L1/L2 tests, all green with LLM_PROVIDER=fake: chunking, classify-schema, confidence boundary, llm-fallback (5xx + 4xx), budget-guardrail, ingest/query roundtrip, idempotency, stats.

## Phase 2 — Intake & auto-answer
- [~] P2-1 [HUMAN] (2026-07-05) Bot created via BotFather (@opspilot_cc_bot); TELEGRAM_BOT_TOKEN in .env (not committed). Still needed: create the ops group and add TELEGRAM_OPS_CHAT_ID to .env.
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
