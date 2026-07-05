# Phase 5 — Evals & CI (paste into Claude Code or Codex; can run in parallel with P3/P4 in Mode C)
# Prerequisite: P1-3 (/classify) and P1-4 (/query) merged.

===== COPY FROM HERE =====
## Objective
Build the evaluation harness and CI — the single strongest evidence in this portfolio that the author measures LLM systems instead of vibing them.

## Context
Read first: AGENTS.md, docs/SPEC.md §4.5, docs/TESTPLAN.md (L3), PROGRESS.md, wiki/log.md (last 2). Use a subagent to draft fixture tickets; you verify label quality and distribution.

## Target State (task IDs P5-1..P5-3)
- P5-1 `evals/tickets.jsonl`: 25–30 items {subject, body, expected_category, expected_priority, lang}; ≥8 Ukrainian; ≥3 deliberately ambiguous (marked expected_ambiguous=true — these validate the confidence gate, not accuracy); realistic phrasing consistent with kb/seed product facts.
- P5-2 `evals/test_classify.py`: accuracy ≥ 0.85 on category over non-ambiguous items; prints a per-class confusion summary. `evals/test_grounding.py`: for 5 KB questions, every numeric/factual anchor in the answer must appear in cited chunks. Run cost assertion: this run's SUM(llm_calls.cost_usd) < $0.50. All marked @pytest.mark.evals; `make evals` wired.
- P5-3 `.github/workflows/ci.yml`: on push/PR → ruff + L1/L2 tests (fake provider, service containers for postgres); evals job on workflow_dispatch only (needs API-key secrets). README badge.

## Scope
Work only in: evals/, .github/, Makefile, README (badge line only).

## Acceptance Criteria
- [ ] `make evals` passes locally with live cheap models; accuracy printed and ≥ 0.85; cost < $0.50
- [ ] CI green on push without any API keys (fake provider); evals job exists as manual dispatch
- [ ] Fixture distribution documented in the session entry (per-class counts)
- [ ] PROGRESS.md + wiki/log.md updated

## Stop Conditions
If accuracy < 0.85: do NOT tune by looping live evals (budget). Analyze the confusion summary, adjust prompts/classify.md once, rerun once; still failing → blocker with analysis attached.
===== COPY TO HERE =====
