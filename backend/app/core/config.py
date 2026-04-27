from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "A Share Strategy Assistant"
    database_url: str = "postgresql+psycopg://finance:finance@localhost:5432/finance"
    redis_url: str = "redis://localhost:6379/0"
    llm_provider: str = "openai_codex"
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str = "openai-codex"
    llm_oauth_client_id: str = "DRivsnm2Mu42T3KOpqdtwB3NYkfbp1"
    llm_oauth_redirect_uri: str | None = None
    tushare_token: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_prefix="FINANCE_")


settings = Settings()
