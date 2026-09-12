"""Small HTTP client for the OpenAI Responses API."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from gqmrmed.contracts.research import ResearchBundle, SynthesizedContent


class AIProviderError(RuntimeError):
    """Raised when the configured synthesis provider cannot produce content."""


@dataclass(frozen=True, slots=True)
class OpenAIResponsesConfig:
    api_key: str
    model: str = "gpt-5.6-luna"
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: float = 60.0


class OpenAIResponsesSynthesizer:
    """Generate evidence-linked medical content using the Responses API."""

    def __init__(self, config: OpenAIResponsesConfig, client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self._client = client

    async def synthesize(
        self,
        *,
        user_input: str,
        research: ResearchBundle,
    ) -> SynthesizedContent:
        if not self.config.api_key.strip():
            raise AIProviderError("ai_api_key_missing")

        prompt = _build_prompt(user_input=user_input, research=research)
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.config.timeout_seconds)
        try:
            response = await client.post(
                f"{self.config.base_url.rstrip('/')}/responses",
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.config.model,
                    "instructions": _SYSTEM_INSTRUCTIONS,
                    "input": prompt,
                },
            )
            if response.is_error:
                raise AIProviderError(f"ai_request_failed:{response.status_code}")
            payload: dict[str, Any] = response.json()
            text = _extract_output_text(payload)
            if not text:
                raise AIProviderError("ai_empty_output")
            return SynthesizedContent.model_validate(_parse_json(text))
        except httpx.HTTPError as exc:
            raise AIProviderError("ai_network_error") from exc
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise AIProviderError("ai_invalid_structured_output") from exc
        finally:
            if owns_client:
                await client.aclose()


_SYSTEM_INSTRUCTIONS = """You are the medical synthesis stage of GQMRMed.
Produce concise educational content for a medical infographic. Use only facts
supported by the supplied evidence or directly supplied user text. Never invent
numbers, doses, contraindications, laboratory ranges, or treatment instructions.
Every factual claim must reference one or more supplied evidence IDs. If evidence
is weak or incomplete, lower confidence and use a caution instead of guessing.
Return ONLY valid JSON matching the requested schema. Do not include markdown.
"""


def _build_prompt(*, user_input: str, research: ResearchBundle) -> str:
    evidence = [source.model_dump() for source in research.sources]
    schema = SynthesizedContent.model_json_schema()
    return json.dumps(
        {
            "task": "Create a structured medical infographic content plan.",
            "user_input": user_input[:20_000],
            "evidence": evidence,
            "evidence_warnings": research.warnings,
            "output_schema": schema,
            "rules": [
                "Keep title short and medically precise.",
                "Use 3-12 key points.",
                "Keep each claim concise and evidence-linked.",
                "Prefer clinically important distinctions and mechanisms.",
                "Do not give individualized diagnosis or patient-specific advice.",
                "Preserve medical terminology supplied by the user.",
            ],
        },
        ensure_ascii=False,
    )


def _extract_output_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str):
        return direct.strip()
    chunks: list[str] = []
    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") in {"output_text", "text"}:
                text = content.get("text")
                if isinstance(text, str):
                    chunks.append(text)
    return "\n".join(chunks).strip()


def _parse_json(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```").removeprefix("json").strip()
        cleaned = cleaned.removesuffix("```").strip()
    return json.loads(cleaned)
