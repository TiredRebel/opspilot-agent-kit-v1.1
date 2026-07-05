# Phase 2 — Intake & auto-answer, WF-1 + WF-2 (paste into Claude Code or Codex)
# Prerequisite: Phase 1 accepted AND human completed P2-1 (bot token + ops chat ID in .env).

===== COPY FROM HERE =====
## Objective
Build the first two n8n workflows as version-controlled JSON: multi-channel intake with LLM triage (WF-1) and RAG answer drafting with the confidence gate (WF-2). Result: a live bot that auto-answers KB questions.

## Context
Read first: AGENTS.md (n8n workflow rules), docs/SPEC.md §3.2, PROGRESS.md, wiki/gotchas.md (#1 port, #2 webhook tunnel, #6 n8n API). The rag-api endpoints are live. Telegram credentials exist in .env but must be configured as n8n credentials by the human once — your JSON references credentials by name only, never by value. Consult current n8n node docs (Context7: n8n) before authoring node parameters — do not guess schemas.

## Target State (task IDs P2-2..P2-4)
- P2-2 `n8n/workflows/wf1_intake_triage.json`: Telegram Trigger (message) + Webhook Trigger → Code node normalize {source, external_ref, subject, body} → Postgres INSERT ... ON CONFLICT (source, external_ref) DO NOTHING → HTTP POST /classify → Postgres UPDATE triage fields → IF priority='urgent' → Telegram alert to ops chat → Execute Workflow WF-2.
- P2-3 `n8n/workflows/wf2_draft_answer.json`: Execute Workflow Trigger(ticket_id) → HTTP POST /query → IF confidence >= {{$env.CONFIDENCE_THRESHOLD}} → send answer to customer + UPDATE status='answered', auto_resolved=true → INSERT ai_draft into messages; ELSE UPDATE status='needs_human' (WF-3 hook left as a no-op placeholder node).
- P2-4 Idempotency proven: re-delivering the same webhook payload creates no duplicate ticket (extend L2 test or a scripted curl check documented in the session entry).
- Import + activate both via the n8n REST API; verify active=true via API. Add `make n8n-sync` target that imports all n8n/workflows/*.json.

## Scope
Work only in: n8n/workflows/, Makefile (n8n-sync), scripts/ (optional curl helpers). Do NOT touch: services/rag internals, schema.

## Constraints
Sanitized JSON only (no tokens/chat IDs/credential secrets — names/placeholders only, real values via n8n credentials + env). Timeouts and retry-on-fail enabled on HTTP nodes per SPEC §4.1.

## Acceptance Criteria
- [ ] `make n8n-sync` imports and activates WF-1 and WF-2; API reports both active
- [ ] Webhook curl with a seeded-KB question → ticket answered, auto_resolved=true, llm_calls rows present
- [ ] Duplicate webhook delivery → still exactly one ticket
- [ ] Committed JSON contains no secrets (grep for token patterns before commit)
- [ ] PROGRESS.md updated; flag "P2-5 ready for [HUMAN] E2E M1" in Blockers; session entry appended
===== COPY TO HERE =====

# Human afterwards: configure the two Telegram credentials in the n8n UI, run TESTPLAN M1, record backup video (P2-5).
