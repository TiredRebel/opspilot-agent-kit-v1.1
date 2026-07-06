from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Env-driven config for the RAG service. Values come from `.env` (see `.env.example`)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://opspilot:changeme@localhost:5432/opspilot"
    # One of: fake, anthropic, openai, gemini, ollama. Only "anthropic" has a fallback chain
    # (-> openai on 5xx/timeout/connection errors, per ADR-001); the others run standalone.
    llm_provider: str = "fake"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    # llama3.2:3b is fast and reliable but only ~0.667 classify accuracy in this project's eval
    # (wiki/gotchas.md #38) — a bigger local model (e.g. a 12B+ one) scores meaningfully higher
    # at the cost of speed. Kept as the default here since it's small enough to pull quickly.
    ollama_model: str = "llama3.2:3b"
    # No common local embedding model outputs the required 1536 dims (gotcha #37) — /query's
    # embed step will raise with `ollama` until a matching model is found; /classify is unaffected.
    ollama_embed_model: str = "nomic-embed-text"
    daily_budget_usd: float = 2.00
    confidence_threshold: float = 0.70
    kb_seed_dir: str = "kb/seed"


settings = Settings()
