from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    app_name: str = Field(default="GQMRMed", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    service_role: str = Field(default="api", alias="SERVICE_ROLE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_webhook_secret: str | None = Field(default=None, alias="TELEGRAM_WEBHOOK_SECRET")

    database_url: str = Field(
        default="postgresql+asyncpg://gqmrmed:gqmrmed@postgres:5432/gqmrmed",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")

    s3_endpoint: str | None = Field(default=None, alias="S3_ENDPOINT")
    s3_access_key_id: str | None = Field(default=None, alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: str | None = Field(default=None, alias="S3_SECRET_ACCESS_KEY")
    s3_bucket: str = Field(default="gqmrmed", alias="S3_BUCKET")
    s3_region: str | None = Field(default=None, alias="S3_REGION")

    ai_provider: str | None = Field(default=None, alias="AI_PROVIDER")
    ai_provider_order: str = Field(
        default="ollama,openai_compatible,openai", alias="AI_PROVIDER_ORDER"
    )
    ai_api_key: str | None = Field(default=None, alias="AI_API_KEY")
    ai_base_url: str = Field(default="https://api.openai.com/v1", alias="AI_BASE_URL")
    ai_model: str = Field(default="gpt-5.6-luna", alias="AI_MODEL")
    ai_compatible_api_key: str | None = Field(default=None, alias="AI_COMPATIBLE_API_KEY")
    ai_compatible_base_url: str | None = Field(default=None, alias="AI_COMPATIBLE_BASE_URL")
    ai_compatible_model: str | None = Field(default=None, alias="AI_COMPATIBLE_MODEL")
    ollama_base_url: str = Field(default="http://ollama:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="qwen3:8b", alias="OLLAMA_MODEL")
    ollama_timeout_seconds: float = Field(
        default=180.0, gt=0, le=900, alias="OLLAMA_TIMEOUT_SECONDS"
    )
    research_provider: str | None = Field(default="pubmed", alias="RESEARCH_PROVIDER")
    research_api_key: str | None = Field(default=None, alias="RESEARCH_API_KEY")
    research_email: str | None = Field(default=None, alias="RESEARCH_EMAIL")

    comfyui_base_url: str = Field(default="http://comfyui:8188", alias="COMFYUI_BASE_URL")
    comfyui_timeout_seconds: float = Field(
        default=120.0, gt=0, le=600, alias="COMFYUI_TIMEOUT_SECONDS"
    )
    comfyui_workflow_json: str | None = Field(default=None, alias="COMFYUI_WORKFLOW_JSON")
    result_storage_dir: str = Field(default="/data/results", alias="RESULT_STORAGE_DIR")
    media_temp_dir: str = Field(default="/tmp/gqmrmed-media", alias="MEDIA_TEMP_DIR")
    media_max_bytes: int = Field(
        default=25 * 1024 * 1024,
        gt=0,
        le=100 * 1024 * 1024,
        alias="MEDIA_MAX_BYTES",
    )
    media_transcription_model: str = Field(
        default="gpt-4o-mini-transcribe", alias="MEDIA_TRANSCRIPTION_MODEL"
    )
    image_width: int = Field(default=1080, ge=256, le=4096, alias="IMAGE_WIDTH")
    image_height: int = Field(default=1920, ge=256, le=4096, alias="IMAGE_HEIGHT")
    admin_secret: str | None = Field(default=None, alias="ADMIN_SECRET")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
