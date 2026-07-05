from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Env-driven config for the RAG service. Values come from `.env` (see `.env.example`)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://opspilot:changeme@localhost:5432/opspilot"
    llm_provider: str = "fake"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    daily_budget_usd: float = 2.00
    confidence_threshold: float = 0.70
    kb_seed_dir: str = "kb/seed"


settings = Settings()
