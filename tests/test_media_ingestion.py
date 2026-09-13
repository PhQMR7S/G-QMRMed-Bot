from pathlib import Path

import pytest

from gqmrmed.contracts.generation import InputType
from gqmrmed.services.media_ingestion import (
    IngestedMedia,
    MediaIngestionConfig,
    MediaIngestionError,
    MediaIngestor,
)


class FakeSource:
    async def download(self, storage_key: str, destination: Path) -> None:
        destination.write_bytes(b"medical-input")


class FakeExtractor:
    async def extract(self, *, path: Path, mime_type: str, input_type: InputType) -> str:
        assert path.is_file()
        assert mime_type == "image/jpeg"
        assert input_type is InputType.IMAGE
        return "OCR: acute appendicitis"


@pytest.mark.asyncio
async def test_ingest_downloads_hashes_and_classifies_image(tmp_path: Path) -> None:
    result = await MediaIngestor(FakeSource()).ingest(
        storage_key="telegram://photo/123",
        mime_type="image/jpeg",
        destination=tmp_path / "input.bin",
    )
    assert isinstance(result, IngestedMedia)
    assert result.input_type is InputType.IMAGE
    assert result.size_bytes == len(b"medical-input")
    assert len(result.sha256) == 64


@pytest.mark.asyncio
async def test_ingest_runs_extractor_and_returns_text(tmp_path: Path) -> None:
    result = await MediaIngestor(FakeSource(), extractor=FakeExtractor()).ingest(
        storage_key="telegram://photo/123",
        mime_type="image/jpeg",
        destination=tmp_path / "input.bin",
    )
    assert result.extracted_text == "OCR: acute appendicitis"


@pytest.mark.asyncio
async def test_ingest_rejects_oversized_media(tmp_path: Path) -> None:
    with pytest.raises(MediaIngestionError, match="media_too_large"):
        await MediaIngestor(
            FakeSource(), MediaIngestionConfig(max_bytes=1)
        ).ingest(
            storage_key="telegram://document/123",
            mime_type="application/pdf",
            destination=tmp_path / "input.pdf",
        )
