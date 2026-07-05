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
- [x] P2-1 [HUMAN] (2026-07-05) Bot created via BotFather (@opspilot_cc_bot) and added to the ops group; TELEGRAM_BOT_TOKEN + TELEGRAM_OPS_CHAT_ID in .env (not committed), both verified live via getMe/getChat.
- [x] P2-2 (Claude, 2026-07-05) WF-1 Intake & Triage — n8n/workflows/wf1_intake_triage.json, imported + activated via n8n REST API (active=true, verified via GET). Telegram Trigger node present but `disabled: true` (no public webhook URL on this n8n instance — gotcha #2/#14); Webhook Trigger (`POST /webhook/opspilot-intake`) is live and is what E2E-tested this phase.
- [x] P2-3 (Claude, 2026-07-05) WF-2 Draft Answer — n8n/workflows/wf2_draft_answer.json, imported + activated. Confidence gate confirmed working end-to-end against the live threshold (0.70, hardcoded literal — n8n's `$env` cannot see this project's `.env`, see gotcha #15).
- [x] P2-4 (Claude, 2026-07-05) Idempotency proven at the workflow level: `scripts/check_intake_idempotency.sh` posts an identical webhook payload twice → exactly one ticket row (on top of the DB-constraint-level proof already in P1's `test_idempotency.py`).
- [ ] P2-5 [HUMAN] E2E M1 happy path + backup screen recording — blocked on a public webhook URL for the Telegram Trigger (see gotcha #2: set up a cloudflared tunnel or similar, then re-enable the Telegram Trigger node in the n8n UI and set its ops-alert node's `chatId` — see Blockers).

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
- [CLOSED] 2026-07-05 human: WF-1's "Alert Ops - Urgent" Telegram node's `chatId` set to the real
  ops chat ID directly in the n8n editor (verified via `GET /api/v1/workflows/{id}` — live node now
  shows `-5134402265`, not the placeholder). **Caveat carried forward:** the committed
  `n8n/workflows/wf1_intake_triage.json` still has (and per AGENTS.md must keep)
  `"PLACEHOLDER_OPS_CHAT_ID"` — if `make n8n-sync` is ever re-run to push a future edit to WF-1, the
  `PUT` update will overwrite the whole node's parameters and silently revert `chatId` back to the
  placeholder. Whoever re-syncs WF-1 next must re-apply this same one-time UI edit afterward (see
  gotcha #20).
- [OPEN] 2026-07-05 Claude: WF-1's Telegram Trigger node is `disabled: true` — this n8n instance has
  no public webhook URL configured (`N8N_HOST`/`N8N_EDITOR_BASE_URL` empty), so Telegram's
  `setWebhook` call fails activation (gotcha #2). P2-5's E2E M1 needs a real Telegram flow: set up a
  tunnel (or the eventual VM domain), then re-enable the node in the n8n UI and re-save/activate.
  The Webhook Trigger path (`/webhook/opspilot-intake`) is fully live and already E2E-verified.
- [OPEN] 2026-07-05 Claude: `/query`'s embed call doesn't pass `ticket_id` (see
  `services/rag/app/main.py`), so `llm_calls` rows for `purpose='embed'` aren't attributed to a
  ticket. Out of scope for Phase 2 (guardrail: don't touch `services/rag` internals) — minor P1
  follow-up for whoever picks it up.
- [CLOSED] 2026-07-05 Claude: n8n credential setup ended up needing course-correction — see
  wiki/log.md for the full sequence (duplicate/misnamed Telegram credentials, a missing Postgres
  credential, and a `.env` DB-password edit that didn't match the live container until `ALTER USER`
  was run). Final state verified working: `Postgres - OpsPilot` (id `wpExxcblEvJLO3DZ`) and
  `Telegram - OpsPilot` (id `I8bufo32jgs857lq`, the renamed pre-existing "Telegram account 2").

## Metrics to fill before applying
- Auto-resolution rate: __% · Avg confidence: __ · Avg cost/ticket: $__ · p95 answer latency: __ s · Eval accuracy: __%
