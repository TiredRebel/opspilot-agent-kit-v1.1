# Phase 4 — Daily digest & Notion, WF-5 (paste into Claude Code or Codex)
# Prerequisite: Phase 3 accepted.

===== COPY FROM HERE =====
## Objective
Ship the reporting loop: a scheduled digest that proves the system is measured — volumes, auto-resolution rate, and LLM spend in USD — delivered to Telegram and archived in Notion.

## Context
Read first: AGENTS.md, docs/SPEC.md §3.2 (WF-5) + §3.1 (/summarize, /stats), PROGRESS.md, wiki/log.md (last 2). NOTION_PAGE_ID and NOTION_TOKEN placeholders exist in .env.example; the human provides a sandbox page. Use the plain Notion REST API (append block children) from an n8n HTTP node — check current API version headers in Notion docs.

## Target State (task IDs P4-1..P4-3)
- P4-1 Digest SQL (as an n8n Postgres node or a /stats extension — prefer reusing GET /stats to avoid SQL duplication; if /stats lacks a field, extend it in services/rag with tests): last-24h ticket count by category/priority, auto-resolution %, avg confidence, SUM(cost_usd), p95 latency.
- P4-2 `n8n/workflows/wf5_daily_digest.json`: Schedule Trigger 09:00 Europe/Kyiv → fetch stats → HTTP POST /summarize → Ukrainian digest text.
- P4-3 Same workflow: post digest to ops Telegram chat + append to the Notion page (heading with date + paragraph blocks). Manual-trigger path included for testing.

## Scope
Work only in: n8n/workflows/, services/rag (only if /stats needs a field, with tests), Makefile. Schema frozen.

## Acceptance Criteria
- [ ] Manual trigger of WF-5 posts a digest to Telegram AND appends to Notion; numbers match GET /stats
- [ ] Digest includes USD spend and auto-resolution %; text is Ukrainian
- [ ] Timezone verified as Europe/Kyiv in the schedule node
- [ ] PROGRESS.md updated; "P4-4 ready for [HUMAN] E2E M6" flagged; session entry appended
===== COPY TO HERE =====
