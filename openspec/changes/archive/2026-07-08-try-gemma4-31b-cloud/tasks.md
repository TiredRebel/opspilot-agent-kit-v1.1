## 1. Run the eval

- [x] 1.1 Run `LLM_PROVIDER=ollama OLLAMA_MODEL=gemma4:31b-cloud OLLAMA_API_KEY=<key> uv run pytest evals/test_classify.py -m evals -s` (key supplied only as an ephemeral env var, never written to any file) and capture the accuracy + confusion summary. **Result:** 19/24 = 0.792, reproducible across two runs (unlike `kimi-k2.7-code:cloud`'s run-to-run variance). Confusion: `account: {account:5, billing:1, technical:2}`, `billing: {billing:7, other:1}`, `other: {other:3}`, `technical: {technical:6, account:2}`.
- [x] 1.2 If the request fails with a 403/subscription-required error (same pattern as `glm-5.2:cloud`/`kimi-k2.7-code:cloud` through the local daemon), note that as the result and stop — no further workaround attempts, consistent with the P5-2 stop condition. **N/A** — no 403, the direct `OLLAMA_API_KEY` path worked cleanly on the first try.

## 2. Apply the decision rule

- [x] 2.1 If accuracy > 0.833: update `.env`'s `OLLAMA_MODEL` to `gemma4:31b-cloud` and `.env.example`'s comment/default if applicable. **N/A** — 0.792 does not beat 0.833.
- [x] 2.2 If accuracy <= 0.833: leave `.env` unchanged. **Applied** — `.env`'s `OLLAMA_MODEL` stays on the local 12B `gemma-coder` model.

## 3. Record the result

- [x] 3.1 Add this model's result to `wiki/gotchas.md`'s existing model-comparison entry (gotcha #38, already extended by #40/#41) — accuracy, confusion summary, and whether it became the new default.
- [x] 3.2 Update `PROGRESS.md`'s P5-2 blocker entry: either mark the 0.85 target reached (if it was) or add this as one more negative/neutral data point.
- [x] 3.3 If the default changed, update `wiki/map.md`'s RAG service row to reflect the new default model and accuracy. **N/A** — default unchanged, no map.md edit needed.
