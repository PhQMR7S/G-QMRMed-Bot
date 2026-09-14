from functools import lru_cache

from pydantic import Field, model_validator
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
    run_worker_in_api: bool = Field(default=False, alias="RUN_WORKER_IN_API")
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
        default="ollama,openrouter_free,groq_free,huggingface_free,openai_compatible,openai",
        alias="AI_PROVIDER_ORDER",
    )
    ai_allow_paid: bool = Field(default=False, alias="AI_ALLOW_PAID")
    ai_api_key: str | None = Field(default=None, alias="AI_API_KEY")
    ai_base_url: str = Field(default="https://api.openai.com/v1", alias="AI_BASE_URL")
    ai_model: str = Field(default="gpt-5.6-luna", alias="AI_MODEL")
    ai_compatible_api_key: str | None = Field(default=None, alias="AI_COMPATIBLE_API_KEY")
    ai_compatible_base_url: str | None = Field(default=None, alias="AI_COMPATIBLE_BASE_URL")
    ai_compatible_model: str | None = Field(default=None, alias="AI_COMPATIBLE_MODEL")
    openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL"
    )
    openrouter_model: str = Field(default="openrouter/free", alias="OPENROUTER_MODEL")
    openrouter_timeout_seconds: float = Field(
        default=120.0, gt=0, le=900, alias="OPENROUTER_TIMEOUT_SECONDS"
    )
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1", alias="GROQ_BASE_URL")
    groq_model: str = Field(default="openai/gpt-oss-20b", alias="GROQ_MODEL")
    groq_timeout_seconds: float = Field(
        default=120.0, gt=0, le=900, alias="GROQ_TIMEOUT_SECONDS"
    )
    huggingface_token: str | None = Field(default=None, alias="HUGGINGFACE_TOKEN")
    huggingface_text_model: str = Field(
        default="openai/gpt-oss-120b:fastest", alias="HUGGINGFACE_TEXT_MODEL"
    )
    huggingface_image_model: str = Field(
        default="black-forest-labs/FLUX.1-dev", alias="HUGGINGFACE_IMAGE_MODEL"
    )
    huggingface_base_url: str = Field(
        default="https://router.huggingface.co/v1", alias="HUGGINGFACE_BASE_URL"
    )
    huggingface_image_provider: str = Field(
        default="auto", alias="HUGGINGFACE_IMAGE_PROVIDER"
    )
    huggingface_timeout_seconds: float = Field(
        default=180.0, gt=0, le=900, alias="HUGGINGFACE_TIMEOUT_SECONDS"
    )
    ollama_base_url: str = Field(default="http://ollama:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="qwen3:8b", alias="OLLAMA_MODEL")
    ollama_timeout_seconds: float = Field(
        default=180.0, gt=0, le=900, alias="OLLAMA_TIMEOUT_SECONDS"
    )

    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_text_model: str = Field(default="gemini-3.8-flash", alias="GEMINI_TEXT_MODEL")
    gemini_image_model: str = Field(default="gemini-3.1-flash-image", alias="GEMINI_IMAGE_MODEL")
    gemini_timeout_seconds: float = Field(
        default=180.0, gt=0, le=900, alias="GEMINI_TIMEOUT_SECONDS"
    )
    cloudflare_api_token: str | None = Field(default=None, alias="CLOUDFLARE_API_TOKEN")
    cloudflare_account_id: str | None = Field(default=None, alias="CLOUDFLARE_ACCOUNT_ID")
    cloudflare_image_model: str = Field(
        default="@cf/black-forest-labs/flux-2-klein-4b", alias="CLOUDFLARE_IMAGE_MODEL"
    )
    dashscope_api_key: str | None = Field(default=None, alias="DASHSCOPE_API_KEY")
    dashscope_base_url: str | None = Field(default=None, alias="DASHSCOPE_BASE_URL")
    dashscope_image_model: str = Field(
        default="qwen-image-3.0-pro", alias="DASHSCOPE_IMAGE_MODEL"
    )
    nararouter_api_key: str | None = Field(default=None, alias="NARAROUTER_API_KEY")
    nararouter_base_url: str = Field(
        default="https://router.bynara.id/v1", alias="NARAROUTER_BASE_URL"
    )
    nararouter_model: str = Field(default="agnes-2.5-flash", alias="NARAROUTER_MODEL")
    image_provider_order: str = Field(
        default="cloudflare,qwen,gemini,huggingface,procedural", alias="IMAGE_PROVIDER_ORDER"
    )
    image_generation_timeout_seconds: float = Field(
        default=180.0, gt=0, le=900, alias="IMAGE_GENERATION_TIMEOUT_SECONDS"
    )

    research_provider: str | None = Field(default="gemini_grounded,pubmed", alias="RESEARCH_PROVIDER")
    research_api_key: str | None = Field(default=None, alias="RESEARCH_API_KEY")
    research_email: str | None = Field(default=None, alias="RESEARCH_EMAIL")

    comfyui_base_url: str = Field(default="http://comfyui:8188", alias="COMFYUI_BASE_URL")
    comfyui_timeout_seconds: float = Field(
        default=120.0, gt=0, le=600, alias="COMFYUI_TIMEOUT_SECONDS"
    )
    comfyui_workflow_json: str | None = Field(default=None, alias="COMFYUI_WORKFLOW_JSON")
    result_storage_dir: str = Field(
        default="/tmp/gqmrmed-results", alias="RESULT_STORAGE_DIR"
    )
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
    admin_panel_url: str = Field(
        default="https://gqmrmed-bot-api.onrender.com", alias="ADMIN_PANEL_URL"
    )

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """Reject unsafe secret defaults when the application is marked production."""
        if self.app_env.strip().lower() == "production":
            if not self.telegram_bot_token:
                raise ValueError("TELEGRAM_BOT_TOKEN is required in production")
            if not self.admin_secret or len(self.admin_secret) < 32:
                raise ValueError("ADMIN_SECRET must be at least 32 characters in production")
            if self.s3_endpoint and (
                not self.s3_access_key_id or not self.s3_secret_access_key
            ):
                raise ValueError("complete S3 credentials are required when S3 is configured")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
