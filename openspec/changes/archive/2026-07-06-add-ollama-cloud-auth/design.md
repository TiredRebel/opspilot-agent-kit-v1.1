## Context

`services/rag/app/llm.py`'s `_ollama_client()` currently always constructs an
`openai.AsyncOpenAI(base_url=f"{settings.ollama_base_url}/v1", api_key="ollama")` — i.e. it always
targets the local daemon (default `http://localhost:11434`) and the `api_key` value is a throwaway
placeholder the OpenAI SDK requires but the local daemon ignores.

Cloud-hosted Ollama models (suffixed `:cloud`, e.g. `kimi-k2.7-code:cloud`) can be proxied through
that same local daemon *if* the daemon's signed-in account holds Ollama's separate paid subscription
plan. Confirmed live this session: with the daemon signed in as the correct account and freshly
restarted, `kimi-k2.7-code:cloud` still 403s through the local path
(`this model requires a subscription, upgrade for access`).

Separately, Ollama exposes an OpenAI-compatible endpoint directly at `https://ollama.com/v1`
(confirmed live via `curl https://ollama.com/api/chat` with `Authorization: Bearer <personal API
key>` → clean 200), authenticated with a personal API key from `ollama.com` — a different product
from the subscription plan, billed pay-per-token instead of a flat monthly fee. This key already
works for direct API calls; the app just has no code path that uses it.

## Goals / Non-Goals

**Goals:**
- Let `_ollama_client()` optionally target `https://ollama.com/v1` with a real bearer token, so
  cloud models become usable from `/classify` (and by extension `evals/test_classify.py`) without
  requiring the ollama.com subscription plan.
- Keep the existing local-daemon path completely unchanged when no key is configured — this is
  strictly additive.

**Non-Goals:**
- Not building general multi-tenant credential management — this is a single optional setting,
  same pattern as `settings.gemini_api_key` / `settings.openai_api_key` already in this codebase.
- Not changing which models are considered "local" vs "cloud" — the user picks the model via the
  existing `OLLAMA_MODEL` setting; this change only affects *how the client authenticates*, not
  routing/model-selection logic.
- Not touching `_call_ollama_embed` / `settings.ollama_embed_model` behavior beyond reusing the same
  client construction — embeddings still need a dimension-compatible model regardless of transport
  (unrelated to this change; see wiki/gotchas.md #5).
- Not re-running or fixing `evals/test_grounding.py` (768 vs 1536-dim embedding gap) — out of scope.
- Not altering `docs/SPEC.md`'s 0.85 target or the P5-2 stop-condition process.

## Decisions

**1. New setting: `ollama_api_key: str = ""` (env `OLLAMA_API_KEY`) in `settings.py`.**
Mirrors the existing optional-key pattern already used for `gemini_api_key`/`openai_api_key` in this
file — no new pattern introduced. (Corrected post-implementation: this design originally proposed
`str | None = None`; the shipped code used `str = ""` to match `anthropic_api_key`/
`openai_api_key`/`gemini_api_key`'s existing convention exactly, per Copilot PR review feedback.)

**2. `_ollama_client()` branches on whether `settings.ollama_api_key` is set:**
- If set: `base_url="https://ollama.com/v1"`, `api_key=settings.ollama_api_key`.
- If unset (default): unchanged — `base_url=f"{settings.ollama_base_url}/v1"`, `api_key="ollama"`.

Alternative considered: always send `settings.ollama_api_key or "ollama"` as the key but keep
`base_url` fixed to the local daemon. Rejected — this session proved the local daemon route 403s
regardless of key validity when the subscription plan isn't held; only the direct
`https://ollama.com` endpoint has been confirmed to work with a personal API key. Branching on
`base_url` too is what actually makes the key useful.

**3. No new `OLLAMA_API_KEY` value is ever written to `.env` by this change** — only
`.env.example` gets a new, empty, documented line (`OLLAMA_API_KEY=`). The real key stays operator-
supplied, matching how `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/`GEMINI_API_KEY` are already handled.

**4. `_call_ollama_embed` reuses the same `_ollama_client()`** — no separate branching needed there;
whatever transport `_ollama_client()` resolves to is used for both chat and embed calls, consistent
with how the function is used today.

## Risks / Trade-offs

- **[Risk]** A misconfigured `OLLAMA_API_KEY` (wrong/expired) would now cause `/classify` calls in
  `ollama` mode to fail against a remote host instead of localhost, which could look like a network
  issue rather than an auth issue. → **Mitigation**: existing error-surfacing in `llm.py` already
  propagates provider exceptions with status codes (as seen with the 403 encountered this session);
  no new silent-failure mode is introduced.
- **[Risk]** Real per-token cost when using the cloud endpoint, unlike the free local daemon.
  → **Correction (post-implementation, per Copilot PR review):** the mitigation originally
  written here was wrong — `_cost()` treats any model absent from `PRICING` as free, and `ollama`
  models are deliberately unlisted (local inference has no per-token cost), so cloud usage via
  `OLLAMA_API_KEY` actually logs as `$0`, not tracked, and invisible to the `$2` dev-budget
  invariant. Confirmed live: a real billed `kimi-k2.7-code:cloud` eval run printed
  `eval run cost: $0.0000`. This is an open, documented gap (wiki/gotchas.md #41,
  PROGRESS.md P5-2 follow-up) — out of scope to fix in this change (no pricing data for
  ollama.com's per-model cloud rates was gathered), but the risk should not have been marked
  mitigated.
- **[Risk]** Scope creep into "properly" distinguishing cloud vs. local Ollama models (e.g.
  validating `:cloud` suffix, auto-selecting endpoint). → **Mitigation**: explicitly a non-goal;
  the operator controls transport purely by whether `OLLAMA_API_KEY` is set.

## Migration Plan

Purely additive — no existing behavior changes when `OLLAMA_API_KEY` is unset. No data migration,
no rollback complexity: removing the env var (or reverting this change) restores today's behavior
exactly.

## Open Questions

- None blocking. Whether `kimi-k2.7-code:cloud` actually reaches 0.85 accuracy once this ships is a
  separate, follow-on question (an eval run, not part of this change).
