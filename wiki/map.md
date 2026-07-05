# map.md — OpsPilot project map (zero-hop entry point)

**Contract:** this page is TRUSTED at query time — agents answer from it without re-verifying against
code, which is only safe because the R3 lint pass keeps it fresh. Every session that changes behavior
MUST update the affected rows here. Stale map = failed lint.

## System in one paragraph
Support requests (Telegram + webhook) → n8n orchestration → FastAPI service owns ALL LLM calls
(Claude primary, OpenAI fallback, `fake` in tests; every call cost-logged) → RAG over pgvector →
confidence ≥ 0.70 auto-answers, below it a human approves/edits/rejects in Telegram → SLA watchdog →
daily digest (Telegram + Notion) with USD spend. Spec: `docs/SPEC.md` (frozen).

## Component matrix
| Component | Path | Status | Tests | Notes |
|---|---|---|---|---|
| Compose stack | docker-compose.yml | built (P0-1) | manual verify | postgres (pgvector/pgvector:pg16) + rag-api only; n8n NOT in compose — reuses existing local instance on :5678 (gotcha #1 resolved this way) |
| DB schema | db/init/01_schema.sql | built (P0-2) | manual verify | FROZEN after P0-2; 5 tables (tickets, messages, kb_documents, kb_chunks, llm_calls) + hnsw index; pgvector 0.8.4 confirmed |
| RAG service | services/rag/app/{main,llm,retrieval,schemas,db,settings}.py | built (P1-1..P1-5, P4-1 stats ext) | 18 L1/L2 tests, all pass, against a dedicated `<POSTGRES_DB>_test` DB (gotcha #31) | claude-haiku-4-5 primary, gpt-5.4-mini fallback, fake provider (also cost-logged); all 6 endpoints live |
| KB seed | kb/seed/*.md | built (P0-4) | manual consistency review | 10 fake "Acme Cloud Suite" docs, UA+EN, facts verified consistent via grep sweep; ingested via P1-2 |
| Ingest | POST /kb/ingest + scripts/ingest.py | built (P1-2) | test_ingest_query_roundtrip.py (L2) | ~500/50-word chunks, 1536-dim (text-embedding-3-small); idempotent re-ingest by title; scripts/ingest.py just POSTs to the running rag-api (see gotcha #10 on kb/ mount + KB_SEED_DIR) |
| Classify | POST /classify | built (P1-3) | test_classify_schema.py (L1) | JSON-schema structured output, 1 retry, 422 on second failure; ticket_id is UUID (bad input → 422, not 500) |
| Query | POST /query | built (P1-4) | test_ingest_query_roundtrip.py (L2), test_confidence.py (L1) | top-5 cosine via pgvector `<=>`, citations computed in code (not LLM-formatted), confidence = 0.5*similarity + 0.5*self_check, gate boundary 0.70/0.699 verified exactly |
| Stats/health | GET /stats, /health | built (P1-5, P4-1) | test_stats.py (L2, incl. `?hours=` filter test), test_health.py (L1) | ticket status/category/priority counts, auto-resolution rate, avg confidence, SUM(cost_usd), p95 latency; optional `hours` query param scopes every aggregate to `created_at >= now() - N hours` (no param = all-time, backward compatible) |
| WF-1 Intake | n8n/workflows/wf1_intake_triage.json | **active, live-verified (P2-5/P3-4)** | Real E2E: webform + Telegram Trigger (public ngrok webhook), callback routing, ops-reply routing all confirmed via n8n execution logs | Telegram Trigger `updates:["message","callback_query"]`, enabled, live webhook. Router (IF chain): callback_query → WF-3, ops-chat reply → WF-3 (edit capture, "Is Ops Reply" chat-id compare wrapped in `String(...)` — gotcha #27), else → customer-intake pipeline. Sole Telegram entry point — ADR-005. 2 `PLACEHOLDER_OPS_CHAT_ID` spots (urgent-alert node + "Is Ops Reply"), live-patched (gotcha #20 applies on re-sync) |
| WF-2 Draft | n8n/workflows/wf2_draft_answer.json | **active, live-verified (P2-5/P3-4)** | Confidence gate, ai_draft insert on needs_human, and WF-3 handoff all confirmed live | Gate literal `0.70` hardcoded (gotcha #15). `needs_human` branch inserts the `ai_draft` message then calls WF-3 (`mode:"post_for_approval"`) |
| WF-3 HITL | n8n/workflows/wf3_hitl.json | **active, live-verified (P3-1..P3-4)** | Ops message + 3 buttons, Approve/Edit/Reject callback routing, edit-reply capture all confirmed via real Telegram interactions | No trigger of its own (ADR-005) — routed by `mode` then `action` via two Switch nodes. Reply→ticket mapping: bracket-free `TICKET-ID:<uuid>` footer (changed from `[ticket:<uuid>]` after gotcha #26 — Telegram's Markdown parser strips square brackets). 3 `PLACEHOLDER_OPS_CHAT_ID` spots (Send Ops Message, Prompt For Correction, Escalation Notice To Ops), live-patched. **Caveat:** Approve/Edit-reply/Reject's final customer-facing send only tested against synthetic webform tickets (no real Telegram chat to reply to) — see PROGRESS.md Blockers |
| WF-4 SLA | n8n/workflows/wf4_sla_watchdog.json | **active, live-verified (P3-3)** | Real cron tick confirmed: backdated ticket produced exactly one grouped reminder, `last_reminder_at` set correctly | Cron `0 */15 * * * *` (6-field format — gotcha #22). One SELECT fans out to grouped-reminder + per-item `last_reminder_at` UPDATE. 1 `PLACEHOLDER_OPS_CHAT_ID` spot, live-patched |
| WF-5 Digest | n8n/workflows/wf5_daily_digest.json | **active, live-verified (P4-1..P4-3)** | Full flow confirmed via its Webhook Trigger: `/stats?hours=24` → `/summarize` → Telegram + Notion append, both landed correctly | Schedule Trigger `0 0 9 * * *` + `settings.timezone:"Europe/Kyiv"` (production) and a parallel Webhook Trigger (`/webhook/opspilot-digest`, on-demand testing). "Append To Notion" uses `notionApi` predefined-credential-type auth (new `Notion - OpsPilot` credential) and **PATCH** (not POST — gotcha #32) against `/v1/blocks/{page_id}/children`. `PLACEHOLDER_OPS_CHAT_ID` + `PLACEHOLDER_NOTION_PAGE_ID`, live-patched (gotcha #20 applies on re-sync). **P4-4 open:** the real 09:00 Kyiv cron tick itself hasn't been observed yet, only the webhook test path |
| Evals | evals/ | not built | L3 | acc ≥ 0.85; run cost < $0.50 |
| CI | .github/workflows/ci.yml | not built | — | evals = manual dispatch only |
| Deploy | docs/infrastructure.md | not built | M7 | caddy behind `prod` profile |

## Invariants (violating any of these is a defect)
1. No LLM call outside `llm.py`. 2. Schema frozen after P0-2. 3. No secrets in any committed file,
including workflow JSON. 4. Tests never hit live APIs without `@pytest.mark.live`. 5. Confidence gate
boundary: 0.70 passes, 0.699 escalates. 6. Dev spend < $2 total.

## Key decisions (details in docs/decisions/)
ADR-001 LLM-via-service · ADR-002 confidence gate (to write) · ADR-003 pgvector (to write) · ADR-004 asyncpg/no-ORM · ADR-005 single Telegram entry point (WF-1 only; WF-3 has no trigger)
