## Why

P5-2's classify-accuracy target (≥0.85, `docs/SPEC.md` §4.5, frozen) is still open. Every model
tried so far tops out at 0.833 (local 12B `gemma-coder`, current `.env` default) or scores worse
(`minimax-m3:cloud` 0.750, `kimi-k2.7-code:cloud` 0.750–0.792 across two runs) — see
`wiki/gotchas.md` #38–#41 and `PROGRESS.md`'s P5-2 blocker for the full history.
`gemma4:31b-cloud` (already pulled locally per `ollama list`) is a larger, untried candidate —
worth one more test given the infrastructure to do so (`OLLAMA_API_KEY` routing to
`https://ollama.com/v1`) already exists from the prior `add-ollama-cloud-auth` change.

## What Changes

- Run `evals/test_classify.py` against `OLLAMA_MODEL=gemma4:31b-cloud` via the existing
  `OLLAMA_API_KEY` cloud-auth path (no new code needed — this is a config value change, testing
  what already exists).
- **If** the result reaches or beats the local 12B baseline (0.833) **and preferably clears 0.85**:
  update `.env`'s `OLLAMA_MODEL` default (and document the new baseline in `wiki/gotchas.md`,
  `PROGRESS.md`).
- **If** the result is worse than 0.833 (matching the pattern of every other cloud model tried so
  far): leave the current local 12B default in place, document the result as another negative
  data point, and do not tune further — per the P5-2 stop condition (test once, accept the result,
  don't loop indefinitely on live evals).
- This change does **not** touch `services/rag/app/llm.py`/`settings.py` — the `OLLAMA_API_KEY`
  cloud-routing mechanism this relies on already shipped in `add-ollama-cloud-auth`. If that
  mechanism itself needs a fix to make this test possible, that's a signal to pause and report,
  not silently patch mid-change.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `llm-provider-layer`: adds one new requirement (not modifying existing ones) — the configured
  `OLLAMA_MODEL` default SHALL be justified by an actual eval comparison recorded in
  `wiki/gotchas.md`, not an arbitrary choice. This formalizes the practice this project has
  already followed since P5-2 (test candidates, keep the best-measured one) as an explicit,
  checkable requirement rather than leaving it as unwritten convention.

## Impact

- **Code**: none. Config only (`.env`'s `OLLAMA_MODEL` value, conditionally).
- **Cost**: real, billed `ollama.com` cloud usage for the test run (pay-per-token, on the
  existing personal API key). Known gap, unrelated to this change: this spend won't show up in
  `llm_calls`/the `$2` dev-budget invariant (gotcha #41, `_cost()` has no pricing entry for
  `ollama`) — noted, not fixed here.
- **Downstream**: if this closes P5-2, update `PROGRESS.md`'s P5-2 blocker entry to reflect it;
  if not, append one more data point to the existing model-comparison record rather than
  reopening the investigation further.
