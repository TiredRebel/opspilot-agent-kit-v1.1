## Context

`gemma4:31b-cloud` is already pulled/registered locally (`ollama list` shows it, added recently).
The `OLLAMA_API_KEY` cloud-auth path (from `add-ollama-cloud-auth`) already lets the `ollama`
provider hit `https://ollama.com/v1` directly with a real bearer token — no code path is missing
to run this test. Every prior cloud candidate (`minimax-m3:cloud`, `kimi-k2.7-code:cloud`) scored
*worse* than the local 12B default (0.833); this is one more data point, not a new mechanism.

## Goals / Non-Goals

**Goals:**
- Get one clean accuracy number for `gemma4:31b-cloud` against `evals/test_classify.py`.
- Update the default only if it's actually better than 0.833 — no speculative switch.
- Record the result either way, so this doesn't become an undocumented one-off like earlier
  ad-hoc tests risked being before gotchas #38–#41 formalized the practice.

**Non-Goals:**
- Not writing new code — `_ollama_client()`'s existing branching already supports this test as-is.
- Not re-tuning `prompts/classify.md` again — P5-2's stop condition already used its one allowed
  prompt-tuning pass; this change tests a model, not a prompt.
- Not fixing the known `_cost()` $0-tracking gap for `ollama` cloud usage (gotcha #41) — orthogonal
  to this change, already an open follow-up.
- Not attempting `evals/test_grounding.py` — unrelated to classify accuracy, blocked on a separate
  embedding-dimension issue (gotcha #37).

## Decisions

**1. Test via ephemeral env vars, never write the real API key to any file.** Same pattern as
every prior cloud-model test this session: `LLM_PROVIDER=ollama OLLAMA_MODEL=gemma4:31b-cloud
OLLAMA_API_KEY=<key> uv run pytest evals/test_classify.py -m evals -s`, key supplied only on the
command line for that one invocation.

**2. Decision rule is a plain threshold, not a judgment call**: update `.env`'s default only if
the new result's accuracy is strictly greater than 0.833 (the current default's recorded score).
Equal-or-worse keeps the current default — avoids rationalizing a lateral or negative move.

**3. Update `wiki/gotchas.md`'s existing model-comparison entry (gotcha #38, extended by #40/#41)
rather than creating a new gotcha number for this** — it's the same comparison table, one more
row, not a new category of finding.

## Risks / Trade-offs

- **[Risk]** `gemma4:31b-cloud` might also require the ollama.com subscription plan (like
  `glm-5.2:cloud`/`kimi-k2.7-code:cloud` did through the local daemon) even via the direct API key
  path. → **Mitigation**: the `OLLAMA_API_KEY` path already proved to work around exactly this for
  `kimi-k2.7-code:cloud`; if this model is gated differently, that's itself a useful negative data
  point to record, not a blocker to work around further.
- **[Risk]** Real per-token cost, invisible to budget tracking (gotcha #41, unfixed). →
  **Mitigation**: same as prior cloud tests — operator-accepted, one-off cost, not a recurring
  budget item.

## Migration Plan

Config-only change, conditional on eval outcome. No rollback complexity: if the new default
underperforms after being set, reverting `.env`'s `OLLAMA_MODEL` to the prior value is a one-line
change.

## Open Questions

- None blocking.
