# llm-provider-layer

## Purpose

Defines how the `services/rag/app/llm/` package authenticates and routes outbound calls per
configured `LLM_PROVIDER` (`anthropic`, `openai`, `gemini`, `ollama`, `fake`), and the package's
structural contract (registry dispatch, database-free providers, stable façade — added by the
`split-llm-provider-package` change). Provider selection and request-routing responsibilities
beyond these requirements are documented in `wiki/map.md`'s RAG service row and ADR-001, not
restated here; this spec grows to cover other providers' requirements as future changes touch
them.

## Requirements

### Requirement: Ollama provider SHALL support optional direct cloud authentication
When the `LLM_PROVIDER` is `ollama` and an `OLLAMA_API_KEY` is configured, the system SHALL
authenticate directly against Ollama's hosted API (`https://ollama.com/v1`) using that key as a
bearer token, instead of the local Ollama daemon.

#### Scenario: OLLAMA_API_KEY is set
- **WHEN** `LLM_PROVIDER=ollama` and `OLLAMA_API_KEY` is set to a non-empty value
- **THEN** the ollama client SHALL send requests to `https://ollama.com/v1` authenticated with that
  key as the bearer token, for both chat/classify calls and embed calls

#### Scenario: A configured cloud model is accessible without the ollama.com subscription plan
- **WHEN** `OLLAMA_MODEL` is set to a cloud-hosted model (e.g. `kimi-k2.7-code:cloud`) and a valid
  `OLLAMA_API_KEY` is configured
- **THEN** `/classify` SHALL be able to complete a request against that model via the direct cloud
  endpoint, without requiring the local daemon to hold the separate ollama.com subscription plan

### Requirement: Ollama provider SHALL default to unchanged local-daemon behavior
When `OLLAMA_API_KEY` is not configured, the system SHALL behave exactly as before this change:
requests go to the local Ollama daemon at `OLLAMA_BASE_URL`, authenticated with a placeholder key.

#### Scenario: OLLAMA_API_KEY is unset
- **WHEN** `LLM_PROVIDER=ollama` and `OLLAMA_API_KEY` is unset or empty
- **THEN** the ollama client SHALL send requests to `{OLLAMA_BASE_URL}/v1` (default
  `http://localhost:11434/v1`) authenticated with the existing placeholder key, identical to
  current behavior

### Requirement: The real API key SHALL never be committed to the repository
`OLLAMA_API_KEY` SHALL be documented in `.env.example` as an empty, optional value. No real key
value SHALL ever be written to any committed file.

#### Scenario: .env.example documents the setting without a real value
- **WHEN** a developer inspects `.env.example`
- **THEN** they SHALL find an `OLLAMA_API_KEY=` line with no real key value, consistent with how
  `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/`GEMINI_API_KEY` are already documented there

### Requirement: Provider dispatch SHALL be registry-based
Provider selection SHALL be resolved through a single registry mapping
(`app/llm/registry.py`) from `LLM_PROVIDER` values (`anthropic`, `openai`, `gemini`, `ollama`,
`fake`) to provider implementations, replacing conditional dispatch chains. Adding a provider
SHALL require only a new provider module and one registry entry, with no modification to
dispatch code.

#### Scenario: Configured provider is resolved via the registry
- **WHEN** `complete()` is called with any supported `LLM_PROVIDER` value
- **THEN** the call SHALL be routed to that provider's implementation via the registry mapping,
  and the resulting behavior (request shape, `LLMResult` fields, `llm_calls` row) SHALL be
  identical to the pre-split module

#### Scenario: Unknown provider is rejected with the existing error
- **WHEN** `LLM_PROVIDER` is set to a value not present in the registry
- **THEN** `complete()` SHALL raise `ValueError` identifying the unknown provider, as before the
  split

### Requirement: Provider modules SHALL be database-free
No module under `app/llm/providers/` SHALL import `app.db` or execute SQL. All call logging and
budget accounting SHALL go through a `Ledger` interface (`app/llm/ledger.py`), whose default
implementation is the package's only database touchpoint and resolves the connection pool
lazily per call.

#### Scenario: A provider is unit-tested without a database
- **WHEN** a provider's chat or embed path is exercised in a test with a stub `Ledger`
- **THEN** the test SHALL run to completion without any database connection being opened

#### Scenario: Budget guardrail and call logging behave as before
- **WHEN** any non-fake provider call is made through `complete()`
- **THEN** the daily-budget check SHALL run before the call and every attempt SHALL be recorded
  in `llm_calls` with the same columns and values as the pre-split module (including failed
  anthropic attempts logged before the ADR-001 fallback to OpenAI)

### Requirement: The package façade SHALL preserve the existing public import surface
`app.llm` SHALL re-export `complete`, `LLMResult`, `BudgetExceeded`, and `load_prompt` so that
existing callers and tests importing from `app.llm` require no changes. The package SHALL remain
the only code in the service that calls an LLM or embedding API (ADR-001).

#### Scenario: Callers are unchanged by the split
- **WHEN** `services/rag/app/main.py` imports `BudgetExceeded`, `complete`, and `load_prompt`
  from `app.llm` after the split
- **THEN** the imports SHALL succeed unmodified and the full test suite (`make test`, fake
  provider) SHALL pass with no assertion changes

### Requirement: Ollama provider default model SHALL be justified by an eval comparison
The `OLLAMA_MODEL` default configured in `.env`/`.env.example` SHALL be the option with the best
recorded `evals/test_classify.py` accuracy among models actually tested, with that comparison
documented in `wiki/gotchas.md`.

#### Scenario: A new candidate model is tested
- **WHEN** a new Ollama model (local or cloud) is evaluated against `evals/test_classify.py`
- **THEN** the result (accuracy, and confusion summary if available) SHALL be recorded in
  `wiki/gotchas.md`'s model-comparison entries, regardless of whether it becomes the new default

#### Scenario: A tested candidate beats the current default
- **WHEN** a newly tested model's accuracy exceeds the current `OLLAMA_MODEL` default's recorded
  accuracy
- **THEN** `.env`'s `OLLAMA_MODEL` SHALL be updated to the new candidate, and `PROGRESS.md`'s
  P5-2 entry SHALL reflect the new baseline

#### Scenario: A tested candidate does not beat the current default
- **WHEN** a newly tested model's accuracy is equal to or worse than the current default's
  recorded accuracy
- **THEN** the current default SHALL remain unchanged, and the result SHALL still be recorded as
  a negative data point (per the first scenario) rather than left undocumented
