## Why

`evals/test_classify.py` accuracy is stuck at 0.833 (best local Ollama model) against the frozen
`docs/SPEC.md` §4.5 target of ≥0.85. Every free/local route to a stronger model has now been tried
and ruled out (Gemini free-tier daily quota exhausted, `minimax-m3:cloud` scored worse at 0.750).
Ollama's cloud-hosted models (`kimi-k2.7-code:cloud`, `glm-5.2:cloud`) are the one untried candidate
that could plausibly close the gap, but they 403 through the local Ollama daemon
(`this model requires a subscription, upgrade for access`) even when the daemon is signed into an
account holding a working pay-per-token API key — confirmed live this session, including after a
full `ollama serve` restart. Separately, that same API key was confirmed live to work cleanly
(HTTP 200) against `https://ollama.com`'s own OpenAI-compatible endpoint, directly, outside the
local daemon. The app has no code path today that can use it that way.

## What Changes

- Add an optional `ollama_api_key` setting (env var `OLLAMA_API_KEY`) to
  `services/rag/app/settings.py`.
- When `OLLAMA_API_KEY` is set, `_ollama_client()` in `services/rag/app/llm.py` authenticates
  directly against `https://ollama.com/v1` using that key as the bearer token, instead of the local
  daemon at `settings.ollama_base_url`.
- When `OLLAMA_API_KEY` is unset (the default), behavior is byte-for-byte unchanged: local daemon,
  dummy `api_key="ollama"`, exactly as today.
- No change to `/classify`, `/query`, or any other endpoint's contract — this only changes how the
  `ollama` provider authenticates its outbound calls.
- No change to `docs/SPEC.md`'s 0.85 target or to the P5 stop-condition process — this unblocks
  *testing* against the existing target, it does not change the target.

## Capabilities

### New Capabilities
(none — this is a provider-layer change, not a new product capability)

### Modified Capabilities
- `llm-provider-layer`: the `ollama` provider mode gains a second, optional authentication path
  (direct cloud API via personal API key) alongside its existing local-daemon path. Since no
  `specs/llm-provider-layer/spec.md` exists yet in this repo (Phases 0-6 predate this OpenSpec
  setup), this change creates the first spec for it, scoped only to the `ollama` provider's
  authentication behavior — not a full retroactive spec of `llm.py`.

## Impact

- **Code**: `services/rag/app/settings.py` (new setting), `services/rag/app/llm.py`
  (`_ollama_client()` and `_call_ollama`/`_call_ollama_embed` call sites only).
- **Config**: `.env.example` gains a documented, empty-by-default `OLLAMA_API_KEY` line. The real
  key itself is never committed anywhere (per `wiki/map.md` invariant #3, no secrets in committed
  files) — it stays in the untracked `.env` only.
- **Tests**: existing `services/rag/tests/` suite (fake provider) is unaffected. `evals/` is where
  this actually gets exercised, manually, against the real cloud model.
- **Downstream**: once this lands, `evals/test_classify.py` can be re-run with
  `LLM_PROVIDER=ollama OLLAMA_MODEL=kimi-k2.7-code:cloud OLLAMA_API_KEY=<key>` to determine whether
  P5-2's 0.85 target is reachable this way. That eval run itself is out of scope for this change —
  this change only makes the run possible.
