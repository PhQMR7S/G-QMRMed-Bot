"""Native Gemini API adapter for reliable medical-content synthesis."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from gqmrmed.ai.providers import (
    _build_prompt,
    _SYSTEM_INSTRUCTIONS,
    ProviderRoutingError,
    TextSynthesisProvider,
)
from gqmrmed.contracts.research import ResearchBundle, SynthesizedContent


@dataclass(frozen=True, slots=True)
class GeminiNativeConfig:
    api_key: str
    model: str
    base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    timeout_seconds: float = 180.0


class GeminiNativeSynthesizer(TextSynthesisProvider):
    """Call Gemini's native generateContent REST API directly."""

    def __init__(self, config: GeminiNativeConfig, client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self._client = client

    async def synthesize(self, *, user_input: str, research: ResearchBundle) -> SynthesizedContent:
        if not self.config.api_key.strip():
            raise ProviderRoutingError("provider_api_key_missing")
        if not self.config.model.strip():
            raise ProviderRoutingError("provider_configuration_missing")

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.config.timeout_seconds)
        try:
            response = await client.post(
                f"{self.config.base_url.rstrip('/')}/models/{self.config.model}:generateContent",
                headers={
                    "x-goog-api-key": self.config.api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "systemInstruction": {
                        "parts": [{"text": _SYSTEM_INSTRUCTIONS}],
                    },
                    "contents": [
                        {
                            "role": "user",
                            "parts": [{"text": _build_prompt(user_input, research)}],
                        }
                    ],
                    "generationConfig": {
                        "responseMimeType": "application/json",
                    },
                },
            )
            if response.is_error:
                raise ProviderRoutingError(f"provider_request_failed:{response.status_code}")
            payload: dict[str, Any] = response.json()
            content = _extract_native_content(payload)
            return SynthesizedContent.model_validate(json.loads(content))
        except httpx.HTTPError as exc:
            raise ProviderRoutingError("provider_network_error") from exc
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ProviderRoutingError("provider_invalid_structured_output") from exc
        finally:
            if owns_client:
                await client.aclose()


def _extract_native_content(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ProviderRoutingError("provider_empty_candidates")
    first = candidates[0]
    if not isinstance(first, dict):
        raise ProviderRoutingError("provider_invalid_candidate")
    content = first.get("content")
    if not isinstance(content, dict):
        raise ProviderRoutingError("provider_invalid_content")
    parts = content.get("parts")
    if not isinstance(parts, list):
        raise ProviderRoutingError("provider_empty_parts")
    text_parts: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        value = part.get("text")
        if isinstance(value, str):
            text_parts.append(value)
    text = "".join(text_parts).strip()
    if not text:
        raise ProviderRoutingError("provider_empty_output")
    return text


__all__ = ["GeminiNativeConfig", "GeminiNativeSynthesizer"]
