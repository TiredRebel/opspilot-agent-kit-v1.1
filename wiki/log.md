# log.md — chronological record (append-only)

Entry prefix convention (parseable): `## [YYYY-MM-DD HH:MM] <op> | <agent> | <title>`
where `<op>` ∈ `build | ingest | review | lint | query`.
Last N entries: `grep "^## \[" wiki/log.md | tail -5`

## [2026-07-05 11:00] build | kit-generator (Claude, chat) | Agent kit authored (pre-P0)
- Completed: AGENTS.md, CLAUDE.md, SPEC, TESTPLAN, prompts P0–P6 + R1/R2, wiki, PROGRESS
- Decisions: ADR-001 pre-locked (LLM calls only via FastAPI service); ADR-004 pre-locked (asyncpg, no ORM)
- Gotchas added: #1–#7 seeded from the owner's known environment
- Handoff / next: run prompts/P0_foundation.md in Claude Code (plan mode) from a fresh git repo

## [2026-07-05 12:00] ingest | kit-generator (Claude, chat) | karpathy LLM Wiki pattern adopted (v1.1)
- Source: gist.github.com/karpathy/442a6bf555914893e9891c11519de94f (read-only reference, not vendored)
- Changes: log.md prefix convention; INDEX.md → content catalog; map.md added as the zero-hop project map;
  R3 wiki-lint prompt added; AGENTS.md gained the "Wiki schema" section (page-creation heuristic, file-back rule)
- Deliberate deviation: single dense map page instead of per-entity pages — for a small greppable codebase,
  entity-page sprawl measured worse than one map page (see README → memory system notes)
- Handoff / next: unchanged — start with prompts/P0_foundation.md
