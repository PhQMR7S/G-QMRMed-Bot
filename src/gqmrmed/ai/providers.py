"""Provider registry, routing, and local/OpenAI-compatible synthesis adapters."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from gqmrmed.contracts.research import ResearchBundle, SynthesizedContent


class TextSynthesisProvider(Protocol):
    """Contract shared by every medical text synthesis provider."""

    async def synthesize(
        self, *, user_input: str, research: ResearchBundle
    ) -> SynthesizedContent: ...


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    """Operational metadata used by the deterministic provider router."""

    name: str
    model: str
    cost_tier: str = "unknown"
    enabled: bool = True


class ProviderRoutingError(RuntimeError):
    """Raised when no configured provider can complete synthesis."""


class ProviderRouter:
    """Try configured providers in order; only provider failures trigger fallback."""

    def __init__(
        self,
        providers: Sequence[tuple[ProviderDescriptor, TextSynthesisProvider]],
    ) -> None:
        enabled = [(meta, provider) for meta, provider in providers if meta.enabled]
        if not enabled:
            raise ValueError("provider_router_requires_enabled_provider")
        self.providers = tuple(enabled)

    async def synthesize(
        self, *, user_input: str, research: ResearchBundle
    ) -> SynthesizedContent:
        errors: list[str] = []
        for metadata, provider in self.providers:
            try:
                return await provider.synthesize(user_input=user_input, research=research)
            except Exception as exc:  # noqa: BLE001 - isolate provider outages at boundary.
                errors.append(f"{metadata.name}:{type(exc).__name__}")
        raise ProviderRoutingError("all_synthesis_providers_failed:" + ",".join(errors))


@dataclass(frozen=True, slots=True)
class OpenAICompatibleConfig:
    """Configuration for APIs exposing the OpenAI chat-completions contract."""

    api_key: str
    base_url: str
    model: str
    timeout_seconds: float = 60.0


class OpenAICompatibleChatSynthesizer:
    """Adapter for OpenAI-compatible gateways without vendor coupling."""

    def __init__(
        self,
        config: OpenAICompatibleConfig,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self._client = client

    async def synthesize(
        self, *, user_input: str, research: ResearchBundle
    ) -> SynthesizedContent:
        if not self.config.api_key.strip():
            raise ProviderRoutingError("provider_api_key_missing")
        if not self.config.base_url.strip() or not self.config.model.strip():
            raise ProviderRoutingError("provider_configuration_missing")

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.config.timeout_seconds)
        try:
            response = await client.post(
                f"{self.config.base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.config.model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_INSTRUCTIONS},
                        {"role": "user", "content": _build_prompt(user_input, research)},
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
            if response.is_error:
                raise ProviderRoutingError(f"provider_request_failed:{response.status_code}")
            payload: dict[str, Any] = response.json()
            content = _extract_chat_content(payload)
            return SynthesizedContent.model_validate(json.loads(content))
        except httpx.HTTPError as exc:
            raise ProviderRoutingError("provider_network_error") from exc
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ProviderRoutingError("provider_invalid_structured_output") from exc
        finally:
            if owns_client:
                await client.aclose()


@dataclass(frozen=True, slots=True)
class OllamaConfig:
    """Local Ollama HTTP configuration; no hosted API subscription is required."""

    base_url: str = "http://ollama:11434"
    model: str = "qwen3:8b"
    timeout_seconds: float = 180.0


class OllamaSynthesizer:
    """Local-first adapter using Ollama's native chat endpoint."""

    def __init__(self, config: OllamaConfig, client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self._client = client

    async def synthesize(
        self, *, user_input: str, research: ResearchBundle
    ) -> SynthesizedContent:
        if not self.config.base_url.strip() or not self.config.model.strip():
            raise ProviderRoutingError("ollama_configuration_missing")
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.config.timeout_seconds)
        try:
            response = await client.post(
                f"{self.config.base_url.rstrip('/')}/api/chat",
                json={
                    "model": self.config.model,
                    "stream": False,
                    "format": "json",
                    "messages": [
                        {"role": "system", "content": _SYSTEM_INSTRUCTIONS},
                        {"role": "user", "content": _build_prompt(user_input, research)},
                    ],
                },
            )
            if response.is_error:
                raise ProviderRoutingError(f"ollama_request_failed:{response.status_code}")
            payload: dict[str, Any] = response.json()
            message = payload.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, str) or not content.strip():
                raise ProviderRoutingError("ollama_empty_output")
            return SynthesizedContent.model_validate(json.loads(content))
        except httpx.HTTPError as exc:
            raise ProviderRoutingError("ollama_network_error") from exc
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ProviderRoutingError("ollama_invalid_structured_output") from exc
        finally:
            if owns_client:
                await client.aclose()


_SYSTEM_INSTRUCTIONS = """You are the medical synthesis stage of GQMRMed.
Use only facts supported by supplied evidence or directly supplied user text.
Never invent numbers, doses, contraindications, laboratory ranges, or treatment
instructions. Every factual claim must reference supplied evidence IDs. If evidence
is weak or incomplete, lower confidence and use a caution instead of guessing.
Return only valid JSON matching the supplied schema. Do not include markdown."""


def _build_prompt(user_input: str, research: ResearchBundle) -> str:
    return json.dumps(
        {
            "task": "Create a structured medical infographic content plan.",
            "user_input": user_input[:20_000],
            "evidence": [source.model_dump() for source in research.sources],
            "evidence_warnings": research.warnings,
            "output_schema": SynthesizedContent.model_json_schema(),
            "rules": [
                "Keep title short and medically precise.",
                "Use 3-12 key points.",
                "Keep each claim concise and evidence-linked.",
                "Prefer clinically important distinctions and mechanisms.",
                "Do not give individualized diagnosis or patient-specific advice.",
            ],
        },
        ensure_ascii=False,
    )


def _extract_chat_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProviderRoutingError("provider_empty_choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise ProviderRoutingError("provider_invalid_choice")
    message = first.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise ProviderRoutingError("provider_empty_output")
    return content.strip()
