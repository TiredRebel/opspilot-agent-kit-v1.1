# CLAUDE.md — Claude Code notes for OpsPilot

**Read `AGENTS.md` first — it is canonical for all rules** (mission, session protocol, conventions,
guardrails). This file adds only what is specific to Claude Code. On conflict, `AGENTS.md` wins.

## How to work in this repo

1. Every session begins with the memory protocol from `AGENTS.md`: read `PROGRESS.md`,
   `wiki/map.md` (trusted project map), `wiki/INDEX.md`, the last 2 entries of `wiki/log.md`, and `wiki/gotchas.md`.
2. Each phase is driven by one prompt file in `prompts/` (P0–P6). Enter **plan mode** at phase
   kickoff, produce the plan, get approval, then execute.
3. Only make changes directly requested by the active phase prompt. Do not add features,
   abstractions, or files beyond what was asked.

## Claude Code specifics

- **Plan mode:** mandatory at the start of each phase prompt; optional for small follow-ups.
- **Subagents:** delegate bulk content generation to subagents to keep the main context clean —
  KB seed documents (`kb/seed/`), eval fixtures (`evals/tickets.jsonl`), fake customer messages.
- **Context hygiene:** `/compact` after each completed task ID; the durable state lives in
  `PROGRESS.md`, `wiki/map.md`, and `wiki/log.md`, not in the chat.
- **Parallel work:** if running multiple Claude Code sessions, use git worktrees and respect the
  path-ownership map in `ops/AGENT_WORKFLOW.md` — one writer per directory.
- **MCP:** use Context7 for current n8n / FastAPI / pgvector docs instead of guessing API shapes.
  The Notion MCP or plain Notion REST may be used to test the digest append (P4-3) with a sandbox page.

## Commands

```bash
make up        # docker compose up -d (postgres, rag-api, n8n)
make seed      # ingest kb/seed into pgvector + insert demo tickets
make lint      # ruff format --check + ruff check
make test      # pytest (fake LLM provider)
make evals     # pytest -m evals (live cheap models, budget-capped)
make backup    # pg_dump snapshot
```

## Definition of Done for any task ID

Code + tests green + `PROGRESS.md` updated + `wiki/map.md` rows refreshed + `wiki/log.md` entry appended. Nothing less.
