"""Bounded contracts at the generation pipeline boundary."""

import json
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class InputType(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"
    MIXED = "mixed"


class GenerationStage(StrEnum):
    """Ordered stages exposed by the generation pipeline."""

    RESEARCHING = "researching"
    SYNTHESIZING = "synthesizing"
    ARCHITECTURE = "architecture"
    GENERATING = "generating"
    RENDERING = "rendering"
    QUALITY_CONTROL = "quality_control"


class GenerationRequest(BaseModel):
    """Normalized request accepted by the pipeline."""

    model_config = ConfigDict(extra="forbid")

    input_type: InputType
    text: str | None = Field(default=None, max_length=100_000)
    storage_key: str | None = Field(default=None, max_length=1024)
    mime_type: str | None = Field(default=None, max_length=128)
    metadata: dict[str, object] | None = None

    @field_validator("text", "storage_key", "mime_type")
    @classmethod
    def normalize_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object] | None) -> dict[str, object] | None:
        if value is None:
            return None
        try:
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValueError("generation_metadata_must_be_json") from exc
        if len(encoded.encode("utf-8")) > 32_768:
            raise ValueError("generation_metadata_too_large")
        return value

    @model_validator(mode="after")
    def validate_model_payload(self) -> "GenerationRequest":
        self.validate_payload()
        return self

    def validate_payload(self) -> None:
        """Reject requests that contain neither inline text nor stored input."""
        if self.text is None and self.storage_key is None:
            raise ValueError("generation_input_required")


class GenerationProgress(BaseModel):
    """Safe progress payload for Telegram/API progress updates."""

    model_config = ConfigDict(extra="forbid")

    stage: GenerationStage
    progress: int = Field(ge=0, le=100)
    elapsed_seconds: int = Field(ge=0)
