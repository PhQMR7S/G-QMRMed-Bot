"""Content extraction adapters for non-text Telegram inputs."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import httpx

from gqmrmed.contracts.generation import InputType
from gqmrmed.services.media_ingestion import MediaIngestionError


class LocalMediaExtractor:
    """Extract text locally where a deterministic parser is available."""

    async def extract(self, *, path: Path, mime_type: str, input_type: InputType) -> str:
        if input_type is InputType.DOCUMENT:
            return self._document(path, mime_type)
        if input_type is InputType.VIDEO:
            return await self._video(path)
        raise MediaIngestionError("no_local_extractor_for_media_type")

    @staticmethod
    def _document(path: Path, mime_type: str) -> str:
        if mime_type == "application/pdf" or path.suffix.lower() == ".pdf":
            try:
                from pypdf import PdfReader
            except ImportError as exc:
                raise MediaIngestionError("pdf_extractor_unavailable") from exc
            try:
                pages = [(page.extract_text() or "") for page in PdfReader(str(path)).pages]
            except Exception as exc:
                raise MediaIngestionError("pdf_extraction_failed") from exc
            text = "\n\n".join(pages).strip()
            if not text:
                raise MediaIngestionError("document_contains_no_extractable_text")
            return text[:50_000]

        if mime_type.startswith("text/") or path.suffix.lower() in {".txt", ".md", ".csv"}:
            try:
                return path.read_text(encoding="utf-8", errors="replace")[:50_000].strip()
            except OSError as exc:
                raise MediaIngestionError("text_extraction_failed") from exc

        raise MediaIngestionError("document_extractor_unsupported")

    @staticmethod
    async def _video(path: Path) -> str:
        """Extract an audio track for the transcription provider."""
        output = path.with_suffix(".gqmrmed-audio.mp3")
        try:
            process = await __import__("asyncio").create_subprocess_exec(
                "ffmpeg", "-y", "-i", str(path), "-vn", "-acodec", "libmp3lame", str(output),
                stdout=__import__("asyncio").subprocess.DEVNULL,
                stderr=__import__("asyncio").subprocess.DEVNULL,
            )
            code = await process.wait()
        except (FileNotFoundError, OSError) as exc:
            raise MediaIngestionError("video_ffmpeg_unavailable") from exc
        if code != 0 or not output.is_file():
            raise MediaIngestionError("video_audio_extraction_failed")
        return f"__AUDIO_FILE__:{output}"


class OpenAIMediaExtractor:
    """Use OpenAI for image OCR/understanding and audio transcription."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-5.6-luna",
        transcription_model: str = "gpt-4o-mini-transcribe",
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 120.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.transcription_model = transcription_model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def extract(self, *, path: Path, mime_type: str, input_type: InputType) -> str:
        if not self.api_key.strip():
            raise MediaIngestionError("media_ai_key_missing")
        if input_type is InputType.IMAGE:
            return await self._image(path, mime_type)
        if input_type is InputType.AUDIO:
            return await self._audio(path)
        if input_type is InputType.VIDEO:
            local = LocalMediaExtractor()
            marker = await local._video(path)
            audio_path = Path(marker.removeprefix("__AUDIO_FILE__:"))
            try:
                return await self._audio(audio_path)
            finally:
                audio_path.unlink(missing_ok=True)
        raise MediaIngestionError("media_ai_extractor_unsupported")

    async def _image(self, path: Path, mime_type: str) -> str:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        payload = {
            "model": self.model,
            "instructions": (
                "Extract all medically relevant visible text and describe clinically relevant "
                "diagram/anatomy labels. Preserve medical terminology. Return plain text only."
            ),
            "input": [{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Read and interpret this medical image."},
                    {"type": "input_image", "image_url": f"data:{mime_type};base64,{encoded}"},
                ],
            }],
        }
        response = await self._post_json("/responses", payload)
        text = _output_text(response)
        if not text:
            raise MediaIngestionError("image_extraction_empty")
        return text[:50_000]

    async def _audio(self, path: Path) -> str:
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise MediaIngestionError("audio_read_failed") from exc
        if not data:
            raise MediaIngestionError("audio_empty")
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    data={"model": self.transcription_model},
                    files={"file": (path.name, data, "application/octet-stream")},
                )
            except httpx.HTTPError as exc:
                raise MediaIngestionError("audio_transcription_network_error") from exc
        if response.is_error:
            raise MediaIngestionError(f"audio_transcription_failed:{response.status_code}")
        payload = response.json()
        text = payload.get("text") if isinstance(payload, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise MediaIngestionError("audio_transcription_empty")
        return text[:50_000]

    async def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            try:
                response = await client.post(
                    f"{self.base_url}{path}",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            except httpx.HTTPError as exc:
                raise MediaIngestionError("media_ai_network_error") from exc
        if response.is_error:
            raise MediaIngestionError(f"media_ai_request_failed:{response.status_code}")
        try:
            value = response.json()
        except json.JSONDecodeError as exc:
            raise MediaIngestionError("media_ai_invalid_response") from exc
        if not isinstance(value, dict):
            raise MediaIngestionError("media_ai_invalid_response")
        return value


def _output_text(payload: dict[str, Any]) -> str:
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


__all__ = ["LocalMediaExtractor", "OpenAIMediaExtractor"]
