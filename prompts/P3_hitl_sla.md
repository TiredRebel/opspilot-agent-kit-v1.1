# Phase 3 — Human-in-the-loop & SLA, WF-3 + WF-4 (paste into Claude Code or Codex)
# Prerequisite: Phase 2 accepted; human has verified M1.

===== COPY FROM HERE =====
## Objective
Build the human-in-the-loop approval flow (the strongest "production, not a GPT toy" signal in this project) and the SLA watchdog.

## Context
Read first: AGENTS.md, docs/SPEC.md §3.2 (WF-3, WF-4), docs/TESTPLAN.md (M2–M5 define expected behavior), wiki/log.md (last 2), wiki/gotchas.md. Telegram callback_query handling in n8n is the known hard part — consult current n8n Telegram Trigger docs for callback update types before authoring; if the single-trigger approach proves unreliable, the approved fallback is a dedicated webhook route for callbacks (record as ADR-005).

## Target State (task IDs P3-1..P3-3)
- P3-1 `n8n/workflows/wf3_hitl.json`: entry from WF-2's needs_human branch → Telegram sendMessage to ops chat: draft + sources + confidence + inline keyboard callback_data `apr|<ticket_id>`, `edt|<ticket_id>`, `rej|<ticket_id>` → Telegram Trigger (callback_query) → Switch:
  • apr → send draft to customer → status='answered' → answerCallbackQuery confirmation
  • rej → status='escalated' → holding message to customer → escalation notice to ops
- P3-2 Edit path: edt → prompt the operator to reply-to the draft message with corrected text → capture the reply and match it back to the ticket → send the corrected text to the customer → INSERT both ai_draft and operator rows into messages → status='answered'. The DB schema is FROZEN, so the reply→ticket mapping must use a schema-free mechanism: either n8n workflow static data keyed by message_id, or a ticket_id footer embedded in the draft message and parsed from reply_to_message. Pick one, justify it in the session entry.
- P3-3 `n8n/workflows/wf4_sla_watchdog.json`: cron */15 → SELECT tickets WHERE status IN ('needs_human','escalated') AND updated_at < now()-interval '2 hours' AND (last_reminder_at IS NULL OR last_reminder_at < now()-interval '2 hours') → one grouped ops message → UPDATE last_reminder_at.

## Scope
Work only in: n8n/workflows/, Makefile (n8n-sync already covers new files). Do NOT touch: db schema (frozen), services/rag.

## Constraints
Sanitized JSON; callback_data ≤ 64 bytes (Telegram limit); every branch updates ticket status exactly once; retries on HTTP nodes.

## Acceptance Criteria
- [ ] make n8n-sync activates WF-3 and WF-4
- [ ] Scripted checks: forcing a ticket to needs_human posts the ops message with 3 buttons (verify via Telegram API getUpdates or human)
- [ ] SLA: backdated ticket triggers exactly one reminder; second cron tick produces none
- [ ] No schema changes; no secrets in JSON
- [ ] PROGRESS.md updated; "P3-4 ready for [HUMAN] E2E M2–M5" flagged; session entry + any ADR appended

## Stop Conditions
Stop and record a blocker before: schema changes, adding services, or if callback capture cannot work without persisting new state — propose options in the blocker instead of improvising.
===== COPY TO HERE =====
