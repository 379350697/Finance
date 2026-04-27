from app.core.config import Settings


def test_settings_defaults_are_local_dev_friendly():
    settings = Settings()

    assert settings.app_name == "A Share Strategy Assistant"
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.redis_url.startswith("redis://")
    assert settings.llm_provider == "openai_codex"
    assert settings.llm_model == "openai-codex"
