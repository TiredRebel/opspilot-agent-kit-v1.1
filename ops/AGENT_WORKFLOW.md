# AGENT_WORKFLOW.md — Orchestration modes and handoff protocol

How to run this build with one agent, two, or a team. Shared state is always the same triad:
**`PROGRESS.md` (what) + `wiki/map.md` (current truth) + `wiki/log.md` (history) + green tests (proof).**

---

## Mode A — Solo Claude Code (recommended for ASAP)

One Claude Code session per phase, driven by `prompts/P{N}_*.md`. Lowest coordination overhead;
the 6-day estimate assumes this mode.

```
For N in 0..6:
  1. Open Claude Code at repo root → paste prompts/P{N}_*.md → plan mode → approve plan
  2. Agent executes, committing per task ID
  3. Agent closes the session per AGENTS.md protocol (PROGRESS + map + log + tests green)
  4. HUMAN performs any [HUMAN] tasks of the phase (see PROGRESS.md)
  5. Optional: run prompts/R1_reviewer.md in a FRESH session (or Codex) before the next phase
  6. Run prompts/R3_wiki_lint.md after each phase — the lint is what keeps wiki/map.md trustworthy
```

## Mode B — Builder + Reviewer pair (quality gate)

Builder: Claude Code with the phase prompt. Reviewer: **Codex** (or a fresh Claude Code session)
with `prompts/R1_reviewer.md`. The reviewer never fixes code directly — it files findings into
`PROGRESS.md → Blockers/Findings`, and the builder addresses them next session. Cross-vendor review
(Claude builds, Codex reviews) catches more than self-review. Recommended after P1, P3, and P5.

## Mode C — Team of agents (Hermes-orchestrated or parallel Claude Code + git worktrees)

### Roles and path ownership (one writer per path — hard rule)

| Role | Owns (write access) | Task IDs |
|---|---|---|
| **Architect/Scaffolder** | repo root, `docker-compose.yml`, `db/`, `Makefile` | P0-1..P0-3 |
| **Backend** | `services/rag/`, `scripts/`, `evals/` | P1-*, P5-1, P5-2 |
| **Integrator** | `n8n/workflows/` | P2-*, P3-*, P4-* |
| **QA/Docs** | `docs/`, `.github/`, README | P5-3, P6-3, P6-4, all reviews |

Everyone may **read** everything. Writing outside your paths ⇒ failed session.
`wiki/` and `PROGRESS.md` are append/checkbox-only shared files; keep edits atomic (one commit, no rewrites of others' entries).

### Parallelization map

- After P0: **Backend (P1)** and **Integrator (WF JSON drafting)** run in parallel — the Integrator
  stubs workflows against the endpoint contracts in `docs/SPEC.md` §3.1 before the service is live.
- P5-1/P5-2 (evals) can start as soon as `/classify` (P1-3) is merged.
- QA/Docs drafts `docs/infrastructure.md` and README skeleton any time.

### Mechanics

- Parallel Claude Code sessions: `git worktree add ../opspilot-backend backend` etc.; merge to `main`
  only with green tests; rebase before merge; Integrator's workflow JSONs rarely conflict with Python paths by design.
- Hermes as orchestrator: Hermes assigns task IDs, spawns workers with the matching phase prompt +
  the role line ("You are the Backend role; your writable paths are ..."), and enforces the handoff checklist below.

## Handoff protocol (all modes)

A task ID may be marked done ONLY when:
1. `make lint && make test` green on the branch;
2. `PROGRESS.md` checkbox ticked with date + agent name;
3. Affected `wiki/map.md` rows refreshed and a `wiki/log.md` entry appended (template in `wiki/INDEX.md`);
4. New traps recorded in `wiki/gotchas.md`;
5. Anything needing human action is flagged `[HUMAN → ...]` in `PROGRESS.md → Blockers`.

## Conflict and blocker rules

- Spec ambiguity → blocker in `PROGRESS.md`, stop that task, take the next unblocked one. Never improvise around `docs/SPEC.md`.
- Merge conflict in shared files (`PROGRESS.md`, `wiki/log.md`) → keep both entries; these files are append-oriented.
- Two agents claiming one task ID → the claim line in `PROGRESS.md` (first commit wins) decides.
