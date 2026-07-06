## 1. Settings

- [x] 1.1 Add `ollama_api_key: str | None = None` (env `OLLAMA_API_KEY`) to `services/rag/app/settings.py`, alongside the existing `ollama_*` settings.

## 2. Provider client

- [x] 2.1 Update `_ollama_client()` in `services/rag/app/llm.py` to branch: if `settings.ollama_api_key` is set, construct the client with `base_url="https://ollama.com/v1"` and `api_key=settings.ollama_api_key`; otherwise keep the existing `base_url=f"{settings.ollama_base_url}/v1"`, `api_key="ollama"` behavior unchanged.
- [x] 2.2 Confirm `_call_ollama` and `_call_ollama_embed` both go through the updated `_ollama_client()` with no other changes needed at their call sites.

## 3. Config documentation

- [x] 3.1 Add a documented, empty `OLLAMA_API_KEY=` line to `.env.example` near the other `OLLAMA_*` entries, with a short comment noting it's optional and enables the direct cloud endpoint.

## 4. Verification

- [x] 4.1 With `OLLAMA_API_KEY` unset, run the existing L1/L2 suite (`make test`) and confirm no behavior change (fake provider is unaffected; this is a smoke check that nothing in settings/llm.py broke import-time).
- [x] 4.2 With a real `OLLAMA_API_KEY` set as an ephemeral env var (never written to `.env`), run `LLM_PROVIDER=ollama OLLAMA_MODEL=kimi-k2.7-code:cloud uv run pytest evals/test_classify.py -m evals -s` and confirm the request reaches `https://ollama.com/v1` and completes (no 403), regardless of the resulting accuracy number. **Result:** confirmed working (no 403, two runs completed at 0.792 and 0.750 accuracy — below the 0.833 local-model baseline, not an improvement). Also observed: `eval run cost` printed `$0.0000` despite this being a real paid cloud call — `llm.py`'s cost logging has no per-token pricing entry for the `ollama` provider, so cloud-endpoint spend isn't reflected in `llm_calls`/the `$2` dev-budget invariant. Flagged in PROGRESS.md as a follow-up, not fixed by this change (out of scope per design.md non-goals).
- [x] 4.3 Update `PROGRESS.md` (P5-2 blocker note) and `wiki/gotchas.md` with whether the cloud-auth path works end-to-end, and `wiki/map.md`'s RAG service row if the provider matrix description needs a one-line update.
