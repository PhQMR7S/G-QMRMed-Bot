import pytest
from pydantic import ValidationError

from gqmrmed.config import Settings


def test_development_allows_missing_runtime_secrets() -> None:
    settings = Settings(app_env="development")
    assert settings.telegram_bot_token is None


def test_production_requires_telegram_token() -> None:
    with pytest.raises(ValidationError, match="TELEGRAM_BOT_TOKEN"):
        Settings(app_env="production", admin_secret="x" * 32)


def test_production_requires_strong_admin_secret() -> None:
    with pytest.raises(ValidationError, match="ADMIN_SECRET"):
        Settings(app_env="production", telegram_bot_token="123:token", admin_secret="short")


def test_production_accepts_required_secrets() -> None:
    settings = Settings(
        app_env="production",
        telegram_bot_token="123:token",
        admin_secret="x" * 32,
    )
    assert settings.app_env == "production"


def test_production_rejects_partial_s3_credentials() -> None:
    with pytest.raises(ValidationError, match="complete S3 credentials"):
        Settings(
            app_env="production",
            telegram_bot_token="123:token",
            admin_secret="x" * 32,
            s3_endpoint="https://storage.example",
            s3_access_key_id="access",
        )
