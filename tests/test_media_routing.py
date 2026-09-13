from pathlib import Path

import pytest

from gqmrmed.contracts.generation import InputType
from gqmrmed.services.media_routing import RoutingMediaExtractor


class FakeLocal:
    async def extract(self, *, path: Path, mime_type: str, input_type: InputType) -> str:
        return "local document text"


class FakeRich:
    async def extract(self, *, path: Path, mime_type: str, input_type: InputType) -> str:
        return "AI image text"


@pytest.mark.asyncio
async def test_routing_uses_local_for_documents(tmp_path: Path) -> None:
    extractor = RoutingMediaExtractor(FakeLocal(), FakeRich())
    result = await extractor.extract(
        path=tmp_path / "x.pdf", mime_type="application/pdf", input_type=InputType.DOCUMENT
    )
    assert result == "local document text"


@pytest.mark.asyncio
async def test_routing_uses_rich_media_for_images(tmp_path: Path) -> None:
    extractor = RoutingMediaExtractor(FakeLocal(), FakeRich())
    result = await extractor.extract(
        path=tmp_path / "x.jpg", mime_type="image/jpeg", input_type=InputType.IMAGE
    )
    assert result == "AI image text"
