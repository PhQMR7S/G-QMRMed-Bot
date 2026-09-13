"""Filesystem result persistence and Telegram delivery adapters."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from aiogram import Bot
from aiogram.types import BufferedInputFile

from gqmrmed.db.models import GenerationJob
from gqmrmed.generation.providers import GeneratedIllustration
from gqmrmed.services.worker import StoredResult


class FilesystemResultStore:
    """Persist final PNGs under a deterministic, job-scoped key."""

    def __init__(self, root: Path = Path("/data/results")) -> None:
        self._root = root

    async def put(self, *, job_id: UUID, image: GeneratedIllustration) -> StoredResult:
        if image.mime_type != "image/png":
            raise ValueError("final_result_must_be_png")
        if image.width <= 0 or image.height <= 0 or not image.image_bytes:
            raise ValueError("invalid_final_result")
        path = self._root / f"{job_id}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(image.image_bytes)
        return StoredResult(
            storage_key=str(path),
            width=image.width,
            height=image.height,
            mime_type=image.mime_type,
            image_bytes=image.image_bytes,
        )


class TelegramResultDelivery:
    """Send only the completed infographic to the originating Telegram chat."""

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def __call__(self, job: GenerationJob, result: StoredResult) -> None:
        chat_id = (job.input_metadata or {}).get("telegram_chat_id")
        if not isinstance(chat_id, int) or chat_id <= 0:
            raise ValueError("telegram_chat_id_unavailable")
        if not result.image_bytes:
            raise ValueError("result_bytes_unavailable")
        await self._bot.send_photo(
            chat_id=chat_id,
            photo=BufferedInputFile(result.image_bytes, filename=f"{job.id}.png"),
        )


__all__ = ["FilesystemResultStore", "TelegramResultDelivery"]
