# R3 — Wiki lint prompt (run after each phase, and always before publishing the repo)
# Any agent; a fresh session is preferable. This is the maintenance pass that makes wiki/map.md trustworthy.

===== COPY FROM HERE =====
## Objective
Health-check the wiki layer (wiki/ + PROGRESS.md + docs/decisions/) against the actual repo state. You verify and repair bookkeeping; you do NOT change application code or docs/SPEC.md.

## Checks (run in order)
1. **Map freshness (most important).** For every row in wiki/map.md: does Status/Tests/Notes match reality (files exist, tests present, behavior as described)? Fix rows where the correct value is unambiguous from code/git; flag uncertain ones.
2. **Contradictions.** wiki/map.md vs docs/SPEC.md vs code vs PROGRESS.md — list every disagreement (e.g., map says "not built" but the endpoint exists; PROGRESS ticked but tests absent).
3. **Log integrity.** Every entry in wiki/log.md matches the prefix convention `## [YYYY-MM-DD HH:MM] <op> | <agent> | <title>`; entries exist for all substantive commit clusters in git history (`git log --oneline`). Fix formatting; flag missing entries — do not fabricate them.
4. **Gotcha hygiene.** wiki/gotchas.md: duplicates merged, numbering intact, entries that code now guards against marked "(mitigated in <path>)".
5. **Catalog completeness.** wiki/INDEX.md lists every wiki page with an accurate one-liner; no orphan pages (unlinked from INDEX); no page that merely mirrors a small source file (per AGENTS.md → Wiki schema, such pages should be folded into map.md — propose the fold, don't delete unilaterally).
6. **Coverage gaps.** Concepts referenced repeatedly across log/map/ADRs that lack a home (undocumented decision, unwritten ADR) — list them.

## Output contract
1. Apply unambiguous repairs directly (map rows, log formatting, catalog lines, gotcha annotations).
2. Append a lint report to wiki/log.md as `## [date] lint | <agent> | wiki health check` with: 🟢/🟡/🔴 status, findings per check, repairs applied, flags requiring a human or builder decision.
3. Mirror blocking findings into PROGRESS.md → Blockers as `- [OPEN] date lint: ...`.

## Hard rules
Never delete pages, ADRs, or log entries. Never modify application code, tests, docs/SPEC.md, or prompts/. If check 2 reveals a code-vs-SPEC conflict, that is a blocker for the builder, not something you resolve.
===== COPY TO HERE =====
