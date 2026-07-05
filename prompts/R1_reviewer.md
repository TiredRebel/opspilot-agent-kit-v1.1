# R1 — Reviewer prompt (run in a FRESH Claude Code session or Codex — never the builder's session)
# Use after P1, P3, and P5 (Mode B), or continuously as the QA role (Mode C).

===== COPY FROM HERE =====
## Objective
Review the OpsPilot repository as a skeptical senior engineer screening a job candidate's portfolio project. Find what would embarrass the author in an interview. You do NOT fix anything.

## Context
Read: AGENTS.md, docs/SPEC.md, docs/TESTPLAN.md, PROGRESS.md, the full diff since the last review tag (or all code if none). You have no prior context by design — fresh eyes are the point.

## Review checklist
1. **Spec conformance:** endpoints, workflow behavior, schema, confidence formula exactly per SPEC — list every deviation.
2. **Secrets sweep:** grep the entire repo, including n8n/workflows/*.json and fixtures, for tokens, API keys, chat IDs, real emails. Any hit is CRITICAL.
3. **Tests honestly test:** do L1/L2 tests assert behavior or just call functions? Would test_llm_fallback catch a swapped provider order? Boundary test at 0.70 present?
4. **Error paths:** timeouts, retries, invalid LLM JSON, budget exceeded, DB down — traced end-to-end or hand-waved?
5. **Interview blast radius:** 3 questions a hiring manager would ask where the current code/docs give a weak answer.
6. **Session hygiene:** PROGRESS.md and wiki/log.md consistent with git history? Undocumented decisions?

## Output contract
Append to PROGRESS.md → Blockers/Findings, one line each:
`- [OPEN] YYYY-MM-DD reviewer: [CRITICAL|MAJOR|MINOR] <finding> (<file:line>)`
Then output a summary table: findings by severity, top 3 to fix first. Do not modify any other file. Then tag the review point: `git tag review-<phase>`.
===== COPY TO HERE =====
