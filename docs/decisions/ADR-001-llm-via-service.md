# ADR-001 — All LLM calls go through the FastAPI service, never from n8n directly

**Context.** n8n orchestrates the whole system (intake, HITL routing, SLA watchdog, digest), and
several of those workflows need an LLM call (classify a ticket, draft an answer, self-check
groundedness, summarize a digest). n8n has its own HTTP Request node and could call an LLM API
directly from a workflow.

**Decision.** No workflow ever calls an LLM API directly. Every LLM interaction goes through the
FastAPI service's endpoints (`/classify`, `/query`, `/summarize`) over HTTP; `services/rag/app/
llm.py` is the only module allowed to hold a provider client or API key.

**Consequences.**
- Provider fallback (Anthropic → OpenAI on 5xx/timeout), the daily budget guardrail, and
  per-attempt cost/latency logging to `llm_calls` all live in one place instead of being
  duplicated (or forgotten) in every workflow that needs an LLM call.
- Prompts are version-controlled files (`services/rag/prompts/*.md`), not inline strings scattered
  across workflow JSON — a prompt change is one file diff, not a hunt through `n8n/workflows/`.
- Adding a new provider (Gemini, Ollama — done in Phase 5) or evaluating classifier accuracy
  (`evals/`) only ever touches this one service, never n8n.
- Rules out ever giving an n8n HTTP Request node a provider API key, even for something that
  looks like a one-off/simple call.
