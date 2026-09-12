"""Bounded contracts at the generation pipeline boundary."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InputType(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    MIXED = "mixed"


class GenerationRequest(BaseModel):
    """Normalized request accepted by the pipeline."""

    model_config = ConfigDict(extra="forbid")

    input_type: InputType
    text: str | None = Field(default=None, max_length=100_000)
    storage_key: str | None = Field(default=None, max_length=1024)
    mime_type: str | None = Field(default=None, max_length=128)
    metadata: dict[str, object] | None = None

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def validate_payload(self) -> None:
        """Reject requests that contain neither inline text nor stored input."""
        if self.text is None and self.storage_key is None:
            raise ValueError("generation_input_required")


class GenerationProgress(BaseModel):
    """Safe progress payload for Telegram/UI adapters."""

    model_config = ConfigDict(extra="forbid")

    stage: str = Field(min_length=1, max_length=64)
    progress: int = Field(ge=0, le=100)
    elapsed_seconds: int = Field(ge=0)
