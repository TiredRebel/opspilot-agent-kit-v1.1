# AGENTS.md — Canonical operating rules for all agents

> This file is the **single source of behavioral rules** for every agent working on OpsPilot
> (Claude Code, Codex, Hermes, or any other). `CLAUDE.md` points here and adds Claude-Code-specific
> notes only. If the two ever disagree, **this file wins.**

## Mission

Build **OpsPilot** — an AI support-triage and ops-automation hub — exactly as defined in `docs/SPEC.md`.
The deliverable is a portfolio project for a job application: **production markers matter more than
feature count.** A small system with retries, cost logging, evals, and a clean README beats a large
half-finished one.

## Source-of-truth order

1. `docs/SPEC.md` — architecture, schema, endpoints, workflows, Definition of Done
2. The active phase prompt in `prompts/`
3. This file (process rules)
4. `wiki/` (accumulated project memory)

If an instruction conflicts with `docs/SPEC.md`, STOP and record a blocker in `PROGRESS.md`. Do not improvise around the spec.

## Session protocol — the memory system (MANDATORY)

Agents have no memory between sessions. The repo **is** the memory, structured as an
**LLM Wiki** (three layers: immutable sources = `docs/SPEC.md` + code · agent-maintained wiki =
`wiki/` · schema = this file). Every session:

**On start (before writing any code):**
1. Read `PROGRESS.md` — find your assigned task IDs and any blockers.
2. Read `wiki/map.md` (the zero-hop project map — trusted; answer from it before grepping code),
   then `wiki/INDEX.md` (catalog) and the last 2 entries of `wiki/log.md`
   (`grep "^## \[" wiki/log.md | tail -2`).
3. Read `wiki/gotchas.md` — known environment traps. Do not rediscover them.
4. State which task IDs you are taking, in one line, before starting.

**During work:**
- After each completed step, output: `✅ [what was done] — [files affected]`
- Commit small, with conventional-commit messages referencing task IDs: `feat(rag): add /classify endpoint (P1-3)`

**Before ending (no exceptions):**
1. Run `make lint && make test`. Do not hand off red.
2. Update `PROGRESS.md` — check off completed tasks, note partial work.
3. Update the affected rows of `wiki/map.md` (status/tests/notes) — the map must always reflect reality.
4. Append a `log.md` entry using the prefix convention and template in `wiki/INDEX.md`.
5. Add any newly discovered trap to `wiki/gotchas.md`; update `wiki/INDEX.md` if you added/changed a page.
6. If you made a non-trivial technical choice, create/update an ADR in `docs/decisions/`.

A session that changed code but did not update `PROGRESS.md` + `wiki/map.md` + `wiki/log.md` is a
**failed session**, even if the code works.

## Wiki schema (LLM Wiki pattern, adapted for a small codebase)

- **Operations:** *build* (normal work), *ingest* (new external knowledge — a doc, an API quirk, a
  benchmark — gets compressed into map/gotchas/a page and logged), *review* (R1), *lint* (R3 —
  run after every phase; it is what makes trusting `map.md` at query time safe), *query*
  (answering questions from the wiki).
- **Page-creation heuristic:** create a standalone wiki page ONLY when the knowledge (a) synthesizes
  multiple sources/files AND (b) would be linked from ≥ 2 places. Otherwise it belongs in `map.md`
  (a row or an invariant) or `gotchas.md` (a numbered trap). Never create a page that merely mirrors
  one small, greppable source file — that is negative-value bookkeeping.
- **File-back rule:** if a session produces a valuable analysis or comparison (e.g., why an n8n
  callback approach was chosen, an eval-failure investigation), file it — as an ADR if it is a
  decision, as a wiki page if it meets the heuristic — instead of letting it die in chat history.
- **Log format:** `## [YYYY-MM-DD HH:MM] <op> | <agent> | <title>` — machine-greppable, append-only.

## Coding conventions

- Python 3.12 · FastAPI · pydantic v2 · **asyncpg with raw SQL** (no ORM — recorded as ADR-004) · Typings · Itertools · Functools 
- Embeddings: OpenAI `text-embedding-3-small` (1536 dims — matches `vector(1536)` in schema)
- LLM: Claude Haiku-class primary, OpenAI mini-class fallback; **all** provider access via `services/rag/app/llm.py`
- Formatting/lint: `ruff` (format + check). Type hints everywhere. Tests: `pytest`.
- Prompts are files in `services/rag/prompts/*.md` — never inline prompt strings in code.
- Config only via `pydantic-settings` from env. `.env` is gitignored; keep `.env.example` current.
- Pin all Docker image tags and Python dependencies.
- Line endings: LF (enforced by `.gitattributes`).
- PEP8
- Package management: uv
- Docstings

## Testing rules

- Unit/integration tests MUST NOT call live LLM APIs. Use the `fake` provider (`LLM_PROVIDER=fake`).
- Live-API tests carry `@pytest.mark.live` and run only when `RUN_LIVE_TESTS=1`.
- Every endpoint and every n8n workflow has a corresponding item in `docs/TESTPLAN.md`. New feature ⇒ update the test plan.

## n8n workflow rules

- Workflows are **code**: author JSON under `n8n/workflows/`, import/activate via the n8n REST API
  (`N8N_API_URL`, `N8N_API_KEY` in `.env`), then verify active status via the API.
- Do not guess node parameter schemas. Consult current n8n docs first (Context7 MCP or official docs).
- Before committing an exported workflow, **sanitize it**: no credential IDs, tokens, or chat IDs.
- The human verifies each workflow visually in the n8n UI — flag it in `PROGRESS.md` when ready for that check.

## Guardrails — MUST / NEVER

- NEVER commit secrets, tokens, API keys, or real chat IDs — in code, JSON exports, docs, or fixtures.
- NEVER modify `db/init/01_schema.sql` without updating `docs/SPEC.md` §3.3 and noting it in an ADR.
- NEVER add a dependency, delete a file, or touch CI config without a stated reason in the session entry.
- Dev LLM budget: **< $2 total.** Cheapest models only; batch where possible; the fake provider is the default.
- Stop and ask (record a blocker) before: schema changes, new external services, anything not in `docs/SPEC.md`.

## Tasks reserved for the human (never attempt these)

Marked `[HUMAN]` in `PROGRESS.md`: BotFather bot creation, pressing Telegram inline buttons in E2E tests,
cloud-account/VM provisioning credentials, recording the demo video, and final visual verification of n8n workflows.

## Agent-specific notes

- **Codex:** keep diffs small and reviewable; run the full test suite before finishing; if the task
  seems to require >~300 changed lines, split it and say so.
- **Hermes / multi-agent teams:** read `ops/AGENT_WORKFLOW.md` for role assignments, path ownership,
  and the handoff protocol before claiming any task.
- **Claude Code:** see `CLAUDE.md` for plan-mode and subagent guidance.
