# llm-provider-layer — delta for split-llm-provider-package

## ADDED Requirements

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
