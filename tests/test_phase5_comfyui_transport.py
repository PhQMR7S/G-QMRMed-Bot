from __future__ import annotations

import httpx
import pytest

from gqmrmed.ai.comfyui import (
    ComfyUIHTTPTransport,
    ComfyUITransportConfig,
)
from gqmrmed.ai.image_generation import ComfyUIConfig, ImageGenerationRequest


class MemoryStore:
    def __init__(self) -> None:
        self.data: bytes | None = None
        self.content_type: str | None = None

    async def put_image(self, *, data: bytes, content_type: str) -> str:
        self.data = data
        self.content_type = content_type
        return "generated/test.png"


@pytest.mark.asyncio
async def test_comfyui_transport_submits_polls_downloads_and_stores_image() -> None:
    calls: list[str] = []
    history_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal history_calls
        calls.append(request.url.path)
        if request.url.path == "/prompt":
            assert request.method == "POST"
            body = request.content.decode()
            assert "medical illustration" in body
            return httpx.Response(200, json={"prompt_id": "prompt-123"})
        if request.url.path == "/history/prompt-123":
            history_calls += 1
            if history_calls == 1:
                return httpx.Response(200, json={"prompt-123": {"outputs": {}}})
            return httpx.Response(
                200,
                json={
                    "prompt-123": {
                        "outputs": {
                            "9": {
                                "images": [
                                    {
                                        "filename": "result.png",
                                        "subfolder": "",
                                        "type": "output",
                                    }
                                ]
                            }
                        }
                    }
                },
            )
        if request.url.path == "/view":
            assert request.url.params["filename"] == "result.png"
            return httpx.Response(200, content=b"PNGDATA", headers={"content-type": "image/png"})
        raise AssertionError(f"unexpected path: {request.url.path}")

    store = MemoryStore()
    client = httpx.AsyncClient(
        base_url="http://comfyui.test",
        transport=httpx.MockTransport(handler),
    )
    transport = ComfyUIHTTPTransport(
        config=ComfyUIConfig(base_url="http://comfyui.test", workflow_id="flux-klein"),
        workflow_factory=lambda request: {
            "1": {"class_type": "CLIPTextEncode", "inputs": {"text": request.prompt}}
        },
        artifact_store=store,
        transport_config=ComfyUITransportConfig(
            poll_interval_seconds=0.001,
            max_poll_seconds=1,
        ),
        client=client,
    )

    result = await transport.generate(
        ImageGenerationRequest(prompt="medical illustration of anatomy")
    )
    await client.aclose()

    assert result.storage_key == "generated/test.png"
    assert result.provider == "comfyui"
    assert result.model == "FLUX.2 Klein 4B"
    assert store.data == b"PNGDATA"
    assert store.content_type == "image/png"
    assert calls == ["/prompt", "/history/prompt-123", "/history/prompt-123", "/view"]


@pytest.mark.asyncio
async def test_comfyui_transport_rejects_missing_prompt_id() -> None:
    client = httpx.AsyncClient(
        base_url="http://comfyui.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )
    transport = ComfyUIHTTPTransport(
        config=ComfyUIConfig(base_url="http://comfyui.test", workflow_id="flux-klein"),
        workflow_factory=lambda request: {"workflow": request.prompt},
        artifact_store=MemoryStore(),
        client=client,
    )

    with pytest.raises(RuntimeError, match="comfyui_generation_failed"):
        await transport.generate(ImageGenerationRequest(prompt="test"))
    await client.aclose()
