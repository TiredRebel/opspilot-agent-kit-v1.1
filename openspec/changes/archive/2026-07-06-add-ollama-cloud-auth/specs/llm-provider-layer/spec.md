## ADDED Requirements

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
