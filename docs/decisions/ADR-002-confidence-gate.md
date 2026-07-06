# ADR-002 — Confidence gate: blended similarity + self-check, threshold 0.70

**Context.** `/query` must decide, for every drafted answer, whether it's safe to auto-send to the
customer or whether a human should review it first (Approve/Edit/Reject in Telegram). A single
signal is easy to fool either direction: retrieval similarity alone says nothing about whether the
model actually used the retrieved context correctly, and asking the model to self-report confidence
alone is exactly the kind of thing LLMs are known to over-state.

**Decision.** Confidence = `0.5 × mean retrieval similarity + 0.5 × LLM self-check score`, where
the self-check is a **separate** LLM call asking "is this answer fully supported by the given
context, 0–1?" — not the same call that drafted the answer. Gate threshold is `0.70`
(`CONFIDENCE_THRESHOLD`, env-configurable), verified in tests to be an exact boundary: `0.70`
auto-sends, `0.699` escalates.

**Consequences.**
- A good retrieval match with a hallucinated/unsupported answer, or a poor match the model still
  answered confidently, both pull the blended score down — either failure mode alone isn't enough
  to slip through.
- Costs one extra LLM call per query (the self-check) versus trusting either signal alone; accepted
  given cheap-tier models and the daily budget guardrail already in place (ADR-001).
- The threshold is a single env var, not hardcoded per-workflow — but n8n's own copy of it
  (`wf2_draft_answer.json`'s gate literal) is *not* read from `.env` (n8n's `$env` can't see this
  project's `.env` — wiki/gotchas.md #15), so it's a literal `0.70` there too, kept in sync by hand.
  Rules out relying on `.env` alone to change the threshold — both `services/rag/app/settings.py`
  and the n8n workflow literal must be updated together.
