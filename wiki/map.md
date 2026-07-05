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
| RAG service | services/rag/app/{main,llm,retrieval,schemas,db,settings}.py | built (P1-1..P1-5) | 17 L1/L2 tests, all pass | claude-haiku-4-5 primary, gpt-5.4-mini fallback, fake provider (also cost-logged); all 6 endpoints live |
| KB seed | kb/seed/*.md | built (P0-4) | manual consistency review | 10 fake "Acme Cloud Suite" docs, UA+EN, facts verified consistent via grep sweep; ingested via P1-2 |
| Ingest | POST /kb/ingest + scripts/ingest.py | built (P1-2) | test_ingest_query_roundtrip.py (L2) | ~500/50-word chunks, 1536-dim (text-embedding-3-small); idempotent re-ingest by title; scripts/ingest.py just POSTs to the running rag-api (see gotcha #10 on kb/ mount + KB_SEED_DIR) |
| Classify | POST /classify | built (P1-3) | test_classify_schema.py (L1) | JSON-schema structured output, 1 retry, 422 on second failure; ticket_id is UUID (bad input → 422, not 500) |
| Query | POST /query | built (P1-4) | test_ingest_query_roundtrip.py (L2), test_confidence.py (L1) | top-5 cosine via pgvector `<=>`, citations computed in code (not LLM-formatted), confidence = 0.5*similarity + 0.5*self_check, gate boundary 0.70/0.699 verified exactly |
| Stats/health | GET /stats, /health | built (P1-5) | test_stats.py (L2), test_health.py (L1) | ticket status counts, auto-resolution rate, avg confidence, SUM(cost_usd), p95 latency |
| WF-1 Intake | n8n/workflows/wf1_intake_triage.json | built (P2-2+P3-1 routing), **status unknown — n8n instance down** | M1 (E2E via Webhook, pre-outage); Telegram/callback/edit-reply routing not yet live-tested | Telegram Trigger now `updates:["message","callback_query"]` (re-enabled at P3-1) with a router (IF chain) in front: callback_query → WF-3, ops-chat reply → WF-3 (edit capture), else → existing customer-intake pipeline. WF-1 is the sole Telegram entry point for this bot — see ADR-005. Two `PLACEHOLDER_OPS_CHAT_ID` spots now (urgent-alert node + the "Is Ops Reply" IF condition) |
| WF-2 Draft | n8n/workflows/wf2_draft_answer.json | built (P2-3+P3-2 fix), **status unknown — n8n down** | E2E'd pre-outage via WF-1's webhook trigger; needs_human ai_draft-insert + WF-3 handoff not yet live-tested | Gate literal `0.70` hardcoded (gotcha #15). `needs_human` branch now also inserts the `ai_draft` message (P3-2 fix — was missing) and calls WF-3 (`mode:"post_for_approval"`) instead of a NoOp placeholder |
| WF-3 HITL | n8n/workflows/wf3_hitl.json | built (P3-1/P3-2), **not yet imported/activated** | Structural validation only (connection-graph script) — see PROGRESS.md Blockers | No trigger of its own (ADR-005) — pure Execute-Workflow sub-workflow, routed by `mode` (post_for_approval/callback/edit_reply) then by `action` (apr/edt/rej) via two Switch nodes. Reply→ticket mapping: `[ticket:<uuid>]` footer in the draft text, parsed from `reply_to_message.text`. `PLACEHOLDER_OPS_CHAT_ID` in 2 nodes (Send Ops Message, Prompt For Correction) |
| WF-4 SLA | n8n/workflows/wf4_sla_watchdog.json | built (P3-3), **not yet imported/activated** | Structural validation only | Cron `0 */15 * * * *` (n8n's Schedule Trigger cron format has a leading seconds field — 6 fields, not 5). One SELECT fans out to an aggregate-Code+single-Telegram branch (grouped reminder) and a per-item Postgres UPDATE branch (`last_reminder_at`) — avoids unverified array-parameter binding. `PLACEHOLDER_OPS_CHAT_ID` in 1 node |
| WF-5 Digest | n8n/workflows/wf5_*.json | not built | M6 | 09:00 Europe/Kyiv; Notion append |
| Evals | evals/ | not built | L3 | acc ≥ 0.85; run cost < $0.50 |
| CI | .github/workflows/ci.yml | not built | — | evals = manual dispatch only |
| Deploy | docs/infrastructure.md | not built | M7 | caddy behind `prod` profile |

## Invariants (violating any of these is a defect)
1. No LLM call outside `llm.py`. 2. Schema frozen after P0-2. 3. No secrets in any committed file,
including workflow JSON. 4. Tests never hit live APIs without `@pytest.mark.live`. 5. Confidence gate
boundary: 0.70 passes, 0.699 escalates. 6. Dev spend < $2 total.

## Key decisions (details in docs/decisions/)
ADR-001 LLM-via-service · ADR-002 confidence gate (to write) · ADR-003 pgvector (to write) · ADR-004 asyncpg/no-ORM · ADR-005 single Telegram entry point (WF-1 only; WF-3 has no trigger)
