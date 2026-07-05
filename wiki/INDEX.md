# INDEX.md — wiki catalog (content-oriented routing file)

One line per page: link + what it answers. Agents read THIS first, then open only the pages they need.
Update this catalog in the same session as any page you add or materially change.

## Navigation & state
- [map.md](map.md) — the zero-hop project map: components, endpoints, workflows, invariants, decision refs. **Trusted at query time; read this before grepping code.**
- [log.md](log.md) — chronological record of builds/ingests/reviews/lints. Parseable: `grep "^## \[" wiki/log.md | tail -5`
- [gotchas.md](gotchas.md) — numbered environment/tooling traps. Read before touching Docker, n8n, Telegram, or pgvector.
- [../PROGRESS.md](../PROGRESS.md) — task board (IDs, claims, blockers, metrics).

## Knowledge pages (created by agents as the build progresses)
_None yet. Pages earn existence only per the heuristic in AGENTS.md → Wiki schema; most knowledge belongs in map.md._

## Decisions
- [../docs/decisions/](../docs/decisions/) — ADRs. ADR-001 (LLM via service) and ADR-004 (asyncpg) pre-locked; written up at P6-3.

## Templates

### log.md entry
```
## [YYYY-MM-DD HH:MM] <build|ingest|review|lint|query> | <agent> | <short title>
- Completed / Partial: <task IDs or scope>
- Files touched: <paths>
- Decisions: <one-liners; ADR refs>
- Gotchas added: <#numbers or none>
- Handoff / next: <the single most useful sentence for the next session>
```

### ADR (docs/decisions/ADR-NNN-slug.md)
**Context** (2–3 sentences) → **Decision** (1 sentence) → **Consequences** (bullets, incl. what this rules out).
