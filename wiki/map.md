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
| Compose stack | docker-compose.yml | not built | — | postgres:pgvector-pg16, rag-api, n8n (port: see gotcha #1) |
| DB schema | db/init/01_schema.sql | not built | — | FROZEN after P0-2; 4 tables + hnsw index |
| Provider layer | services/rag/app/llm.py | not built | L1 | fallback, budget 429, cost rows |
| Ingest | /kb/ingest + scripts/ingest.py | not built | L2 roundtrip | 500/50 chunks, 1536-dim |
| Classify | POST /classify | not built | L1 + evals | JSON-schema, 1 retry |
| Query | POST /query | not built | L2 + evals | top-5, citations, confidence blend |
| Stats/health | GET /stats, /health | not built | L2 | digest reads /stats |
| WF-1 Intake | n8n/workflows/wf1_*.json | not built | M1 | idempotency: UNIQUE(source, external_ref) |
| WF-2 Draft | n8n/workflows/wf2_*.json | not built | M1/M2 | gate at CONFIDENCE_THRESHOLD |
| WF-3 HITL | n8n/workflows/wf3_*.json | not built | M2–M4 | callback_data ≤64 B; reply→ticket mapping is schema-free |
| WF-4 SLA | n8n/workflows/wf4_*.json | not built | M5 | idempotent via last_reminder_at |
| WF-5 Digest | n8n/workflows/wf5_*.json | not built | M6 | 09:00 Europe/Kyiv; Notion append |
| Evals | evals/ | not built | L3 | acc ≥ 0.85; run cost < $0.50 |
| CI | .github/workflows/ci.yml | not built | — | evals = manual dispatch only |
| Deploy | docs/infrastructure.md | not built | M7 | caddy behind `prod` profile |

## Invariants (violating any of these is a defect)
1. No LLM call outside `llm.py`. 2. Schema frozen after P0-2. 3. No secrets in any committed file,
including workflow JSON. 4. Tests never hit live APIs without `@pytest.mark.live`. 5. Confidence gate
boundary: 0.70 passes, 0.699 escalates. 6. Dev spend < $2 total.

## Key decisions (details in docs/decisions/)
ADR-001 LLM-via-service · ADR-002 confidence gate (to write) · ADR-003 pgvector (to write) · ADR-004 asyncpg/no-ORM
