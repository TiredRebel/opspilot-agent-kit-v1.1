# OpsPilot Agent Kit

Everything an AI coding agent (Claude Code, Codex, or a Hermes-style team) needs to build the
**OpsPilot** portfolio project — an AI support-triage and ops-automation hub — with minimal human
babysitting. Drop this kit into a fresh repo and drive the build with the phase prompts.

---

## Quickstart (Mode A — solo Claude Code, fastest path)

```bash
mkdir opspilot && cd opspilot
# copy the contents of this kit here, then:
git init && git add -A && git commit -m "chore: agent kit bootstrap"
claude   # open Claude Code at the repo root
```

1. Paste `prompts/P0_foundation.md` (the block between the COPY markers) → let it plan → approve → execute.
2. Do your `[HUMAN]` tasks for the phase (listed in `PROGRESS.md` — e.g., P2-1 BotFather).
3. Repeat with `P1` … `P6`. After P1, P3, P5 optionally run `prompts/R1_reviewer.md` in a **fresh** session or in Codex.
4. Any interruption, any agent, any day later: paste `prompts/R2_session_resume.md`. The repo remembers; the agent doesn't have to.

Total: ~6 focused agent-days; your hands-on time is mostly the `[HUMAN]` items (~3–4 hours) plus reviews.

## What's in the box

| Path | What it is | Why it exists |
|---|---|---|
| `AGENTS.md` | **Canonical rules** for every agent: session protocol, conventions, guardrails, human-only tasks | One rulebook, zero drift between tools. Codex and most agent frameworks auto-read this filename. |
| `CLAUDE.md` | Thin Claude-Code layer: plan mode, subagents, `/compact`, worktrees, MCP usage | Claude Code auto-loads it; it defers to AGENTS.md so rules never fork |
| `docs/SPEC.md` | Frozen technical spec: architecture, schema SQL, endpoint contracts, workflow behavior, DoD | The agents' source of truth; "stop and file a blocker" beats improvisation |
| `docs/TESTPLAN.md` | L1 unit → L2 integration → L3 evals → L4 manual E2E scripts (M1–M6) → L5 deploy smoke, with DoD traceability | Agents write L1–L3; M-scripts are your checklist for the parts only a human can do (tapping Telegram buttons) |
| `PROGRESS.md` | Task board with stable IDs (P0-1 … P6-4), claim protocol, blockers, metrics-to-fill | Shared "what" — the coordination surface for any number of agents |
| `wiki/` | The **LLM Wiki** memory layer: `map.md` (zero-hop project map, trusted at query time), `log.md` (append-only, machine-greppable journal), `gotchas.md` (numbered traps, pre-seeded with 7 from your environment), `INDEX.md` (catalog + templates) | Agents are amnesiac between sessions; the wiki is their compounding long-term memory. Reading it on start / writing on close is mandatory per AGENTS.md |
| `prompts/P0…P6` | One paste-ready prompt per phase: objective, context pointers, scope lock, binary acceptance criteria, stop conditions | Front-loaded single-turn briefs — no mid-task negotiation needed |
| `prompts/R1_reviewer.md` | Skeptical-senior-engineer review prompt (fresh session / cross-vendor) | Catches secrets, fake tests, and spec drift before they reach a hiring manager |
| `prompts/R2_session_resume.md` | Universal resume prompt | Continuity across days, machines, and agent vendors |
| `prompts/R3_wiki_lint.md` | Wiki health-check: map freshness, contradictions, log integrity, orphans, coverage gaps | Drift is the LLM-Wiki pattern's main failure mode; the lint pass is what makes trusting `map.md` safe |
| `ops/AGENT_WORKFLOW.md` | Modes A (solo), B (builder+reviewer), C (team with path ownership, worktrees, Hermes orchestration), handoff protocol | Scale from one agent to a team without changing any other file |

## How the memory system works — the LLM Wiki pattern, adapted

The memory layer is an instantiation of Karpathy's **LLM Wiki** pattern
(`gist.github.com/karpathy/442a6bf555914893e9891c11519de94f`): three layers — immutable sources
(`docs/SPEC.md` + the code itself), an agent-maintained wiki (`wiki/`), and a schema that turns a
generic agent into a disciplined maintainer (`AGENTS.md` → "Wiki schema" section). The pattern's
operations map directly: **build/ingest** (every session compresses what it learned back into the
wiki), **query** (agents answer from `wiki/map.md` before grepping code), and **lint**
(`R3_wiki_lint.md`, run after every phase). `wiki/log.md` follows the gist's parseable convention —
`## [date] op | agent | title` — so `grep "^## \[" wiki/log.md | tail -5` gives recent history in
one command. No external service to stand up: the wiki **is** files in git — vendor-neutral,
diff-able, Obsidian-browsable.

```
session start:  PROGRESS.md → wiki/map.md (trusted map) → wiki/log.md (last 2) → wiki/gotchas.md
session end:    tests green → tick PROGRESS.md → refresh map rows → append log.md → append gotchas.md
after a phase:  R3 wiki lint → 🟢/🟡/🔴 report appended to the log
```

**One deliberate deviation from the gist:** no per-entity page sprawl. For a small greppable
codebase, an entity page mirroring a ~100-line file is larger than its source and gets read *in
addition to* the code — negative value (a measured result reported in the gist's discussion
thread). So the default knowledge surface is one dense `wiki/map.md` (component matrix +
invariants + decision refs), and standalone pages must earn existence via the heuristic in
AGENTS.md: they synthesize multiple sources AND would be linked from ≥ 2 places. A session that
ships code but skips the write-back is defined as **failed** — that single rule is what lets
Claude Code today, Codex tomorrow, and a Hermes worker next week continue the same build.

## Choosing a mode

- **ASAP, one machine:** Mode A. Sequential phases, cleanest context.
- **Quality gate before the repo goes public:** Mode B — Claude builds, Codex reviews (cross-vendor review catches what self-review misses).
- **You want to showcase multi-agent orchestration itself:** Mode C — and mention in the interview that the project was built by an agent team you directed; the `wiki/log.md` history is the receipt.

## Human-only tasks (agents are forbidden to attempt these)

BotFather bot creation and credential entry (P2-1) · tapping inline buttons in E2E M2–M5 · cloud
account/VM provisioning and any credentials (P6-1) · recording the 3-minute demo video · final visual
check of each n8n workflow in the UI.

## FAQ

**Why is AGENTS.md canonical instead of CLAUDE.md?** `AGENTS.md` is the emerging cross-tool
convention (Codex and most frameworks look for it). Making it canonical and CLAUDE.md a thin overlay
means rules exist in exactly one place.

**How do agents build n8n workflows without clicking the UI?** They author workflow JSON in
`n8n/workflows/` and import/activate via the n8n REST API (`make n8n-sync`), consulting current node
docs via Context7 instead of guessing schemas. You re-link credentials once in the UI and visually
verify — that's it.

**What does this cost in LLM spend?** Dev/test uses a `fake` provider (zero cost). Live calls are
budget-guarded in code (< $2 dev, < $0.50 per eval run, < $5 total for the whole demo).

**Where did the project itself come from?** `docs/SPEC.md` is the frozen build target; the
recruiting-facing documents (vacancy analysis, application plan, video script, cover message) live
outside this repo — keep them out of the public portfolio.
