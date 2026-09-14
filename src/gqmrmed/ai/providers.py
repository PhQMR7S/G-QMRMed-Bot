"""Provider registry, routing, and OpenAI-compatible/local synthesis adapters."""
from __future__ import annotations

import asyncio
import json
import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from gqmrmed.ai.infographic_design import detect_language_mode
from gqmrmed.contracts.research import ResearchBundle, SynthesizedContent


class TextSynthesisProvider(Protocol):
    async def synthesize(self, *, user_input: str, research: ResearchBundle) -> SynthesizedContent: ...


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    name: str
    model: str
    cost_tier: str = "unknown"
    enabled: bool = True


class ProviderRoutingError(RuntimeError):
    """Raised when no configured provider can complete synthesis."""


class ProviderRouter:
    """Try configured providers with bounded retry and concurrency."""

    def __init__(
        self,
        providers: Sequence[tuple[ProviderDescriptor, TextSynthesisProvider]],
        *,
        allow_paid: bool = False,
        retry_attempts: int = 4,
        max_concurrency_per_provider: int = 4,
    ) -> None:
        if retry_attempts < 0:
            raise ValueError("retry_attempts_must_be_nonnegative")
        if max_concurrency_per_provider <= 0:
            raise ValueError("max_concurrency_per_provider_must_be_positive")
        enabled = [
            (meta, provider)
            for meta, provider in providers
            if meta.enabled and (allow_paid or meta.cost_tier in {"free", "local"})
        ]
        if not enabled:
            raise ValueError("provider_router_requires_enabled_provider")
        self.providers = tuple(enabled)
        self.allow_paid = allow_paid
        self.retry_attempts = retry_attempts
        self._semaphores = {
            meta.name: asyncio.Semaphore(max_concurrency_per_provider)
            for meta, _ in self.providers
        }

    async def synthesize(self, *, user_input: str, research: ResearchBundle) -> SynthesizedContent:
        errors: list[str] = []
        for metadata, provider in self.providers:
            semaphore = self._semaphores[metadata.name]
            for attempt in range(self.retry_attempts + 1):
                try:
                    async with semaphore:
                        return await provider.synthesize(user_input=user_input, research=research)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{metadata.name}:{type(exc).__name__}")
                    if attempt >= self.retry_attempts or not _is_transient_provider_error(exc):
                        break
                    await asyncio.sleep(_retry_delay(attempt))
        raise ProviderRoutingError("all_synthesis_providers_failed:" + ",".join(errors))


def _is_transient_provider_error(exc: Exception) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    text = str(exc).lower()
    return any(
        marker in text
        for marker in (
            "provider_network_error",
            "provider_request_failed:408",
            "provider_request_failed:429",
            "provider_request_failed:500",
            "provider_request_failed:502",
            "provider_request_failed:503",
            "provider_request_failed:504",
            "ollama_network_error",
            "ollama_request_failed:408",
            "ollama_request_failed:429",
            "ollama_request_failed:500",
            "ollama_request_failed:502",
            "ollama_request_failed:503",
            "ollama_request_failed:504",
        )
    )


def _retry_delay(attempt: int) -> float:
    """Use exponential backoff long enough for transient 5xx recovery."""
    return float(min(16.0, 1.0 * (2**attempt)) + random.uniform(0.0, 0.5))


@dataclass(frozen=True, slots=True)
class OpenAICompatibleConfig:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float = 60.0
    extra_headers: tuple[tuple[str, str], ...] = ()


class OpenAICompatibleChatSynthesizer:
    """Adapter for OpenAI-compatible gateways."""

    def __init__(self, config: OpenAICompatibleConfig, client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self._client = client

    async def synthesize(self, *, user_input: str, research: ResearchBundle) -> SynthesizedContent:
        if not self.config.api_key.strip():
            raise ProviderRoutingError("provider_api_key_missing")
        if not self.config.base_url.strip() or not self.config.model.strip():
            raise ProviderRoutingError("provider_configuration_missing")
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.config.timeout_seconds)
        try:
            headers = {"Authorization": f"Bearer {self.config.api_key}", "Content-Type": "application/json"}
            headers.update(dict(self.config.extra_headers))
            response = await client.post(
                f"{self.config.base_url.rstrip('/')}/chat/completions",
                headers=headers,
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


class OpenRouterFreeSynthesizer(OpenAICompatibleChatSynthesizer):
    """OpenRouter free-only route."""


@dataclass(frozen=True, slots=True)
class OllamaConfig:
    base_url: str = "http://ollama:11434"
    model: str = "qwen3:8b"
    timeout_seconds: float = 180.0


class OllamaSynthesizer:
    """Local-first adapter using Ollama's native chat endpoint."""

    def __init__(self, config: OllamaConfig, client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self._client = client

    async def synthesize(self, *, user_input: str, research: ResearchBundle) -> SynthesizedContent:
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
Never invent numbers, doses, contraindications, laboratory ranges, or treatment instructions.
Every factual claim must reference supplied evidence IDs. If evidence is weak or incomplete,
use a caution instead of guessing. Return only valid JSON matching the supplied schema.
LANGUAGE CONTRACT: detect the language of user_input. Arabic input -> write all visible
educational prose in correct Arabic. English input -> write all visible prose in English.
Genuinely mixed input -> preserve the mixed language intentionally. Never output broken,
transliterated, or pseudo-Arabic characters. Keep medical terms in their normal clinical
form when a standard English abbreviation is required, but do not turn an Arabic sentence
into English. Do not include markdown, provider status, internal errors, or source URLs."""


def _build_prompt(user_input: str, research: ResearchBundle) -> str:
    language = detect_language_mode(user_input)
    return json.dumps(
        {
            "task": "Create a structured medical infographic content plan.",
            "user_input": user_input[:20_000],
            "language_mode": language,
            "evidence": [source.model_dump() for source in research.sources],
            "evidence_warnings": research.warnings,
            "output_schema": SynthesizedContent.model_json_schema(),
            "rules": [
                "Keep title short and medically precise.",
                "Use 3-12 key points.",
                "Keep each claim concise and evidence-linked.",
                "Prefer clinically important distinctions and mechanisms.",
                "Do not give individualized diagnosis or patient-specific advice.",
                "The final visible text must obey language_mode exactly.",
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
