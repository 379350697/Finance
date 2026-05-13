from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "A Share Strategy Assistant"
    database_url: str = "sqlite:///./finance.db"
    redis_url: str = "redis://localhost:6379/0"
    llm_provider: str = "openai_codex"
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str = "openai-codex"
    llm_oauth_client_id: str = "app_EMoamEEZ73f0CkXaXp7hrann"
    llm_oauth_redirect_uri: str | None = None
    openai_proxy: str | None = None
    tushare_token: str | None = None

    # Transaction costs
    commission_rate: float = 0.00025
    min_commission: float = 5.0
    stamp_tax_rate: float = 0.001
    transfer_fee_rate: float = 0.00001

    # Execution
    slippage_std: float = 0.001
    entry_bias_min: float = 0.5
    entry_bias_max: float = 0.9

    # Risk management
    stop_loss_pct: float = -0.05
    take_profit_pct: float = 0.15

    # Factor & model
    factor_cache_dir: str = "data/factors"
    columnar_dir: str = "data/columnar"
    model_dir: str = "data/models"
    expression_cache_dir: str = "data/cache/expressions"
    expression_cache_ttl_days: int = 7
    dataset_cache_dir: str = "data/cache/datasets"
    dataset_cache_ttl_days: int = 7
    default_top_k: int = 30
    default_holding_days: int = 5
    default_label_type: str = "next_ret5"

    # Experiment tracking
    mlflow_tracking_uri: str | None = None
    experiment_dir: str = "data/experiments"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="FINANCE_")


settings = Settings()
