from __future__ import annotations

import json

import httpx
import pytest

from gqmrmed.ai.providers import (
    OllamaConfig,
    OllamaSynthesizer,
    OpenAICompatibleChatSynthesizer,
    OpenAICompatibleConfig,
    ProviderDescriptor,
    ProviderRouter,
    ProviderRoutingError,
)
from gqmrmed.contracts.research import (
    EvidenceSource,
    ResearchBundle,
    SourceType,
    SynthesizedContent,
)


@pytest.fixture
def research() -> ResearchBundle:
    return ResearchBundle(
        query="diabetes",
        sources=[
            EvidenceSource(
                source_id="pmid:1",
                source_type=SourceType.PUBMED,
                title="Diabetes",
                url="https://pubmed.ncbi.nlm.nih.gov/1/",
            )
        ],
    )


def content() -> SynthesizedContent:
    return SynthesizedContent(
        title="Diabetes",
        key_points=["A key point"],
        claims=[
            {
                "claim_id": "c1",
                "text": "A supported claim",
                "evidence_ids": ["pmid:1"],
                "confidence": 0.9,
            }
        ],
    )


class SuccessProvider:
    async def synthesize(self, *, user_input: str, research: ResearchBundle) -> SynthesizedContent:
        return content()


class FailingProvider:
    async def synthesize(self, *, user_input: str, research: ResearchBundle) -> SynthesizedContent:
        raise RuntimeError("offline")


@pytest.mark.asyncio
async def test_router_falls_back_in_configured_order(research: ResearchBundle) -> None:
    router = ProviderRouter(
        [
            (ProviderDescriptor("local", "qwen3:8b", "free-local"), FailingProvider()),
            (ProviderDescriptor("gateway", "model", "free-tier"), SuccessProvider()),
        ]
    )
    result = await router.synthesize(user_input="diabetes", research=research)
    assert result.title == "Diabetes"


@pytest.mark.asyncio
async def test_router_raises_when_all_providers_fail(research: ResearchBundle) -> None:
    router = ProviderRouter([(ProviderDescriptor("local", "qwen3:8b"), FailingProvider())])
    with pytest.raises(ProviderRoutingError, match="all_synthesis_providers_failed"):
        await router.synthesize(user_input="diabetes", research=research)


@pytest.mark.asyncio
async def test_ollama_parses_structured_response(research: ResearchBundle) -> None:
    payload = {"message": {"content": json.dumps(content().model_dump())}}

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert body["stream"] is False
        assert body["format"] == "json"
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaSynthesizer(OllamaConfig(), client=client)
    try:
        result = await provider.synthesize(user_input="diabetes", research=research)
    finally:
        await client.aclose()
    assert result.title == "Diabetes"


@pytest.mark.asyncio
async def test_openai_compatible_adapter_parses_structured_response(
    research: ResearchBundle,
) -> None:
    payload = {"choices": [{"message": {"content": json.dumps(content().model_dump())}}]}

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleChatSynthesizer(
        OpenAICompatibleConfig(
            api_key="test-key",
            base_url="https://gateway.example/v1",
            model="free-model",
        ),
        client=client,
    )
    try:
        result = await provider.synthesize(user_input="diabetes", research=research)
    finally:
        await client.aclose()
    assert result.title == "Diabetes"
