"""Telegram file download adapter for asynchronous media jobs."""

from __future__ import annotations

from pathlib import Path

from aiogram import Bot

from gqmrmed.services.media_ingestion import MediaIngestionError


class TelegramMediaSource:
    """Resolve the internal telegram:// storage key and download its file."""

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def download(self, storage_key: str, destination: Path) -> None:
        prefix, separator, file_id = storage_key.partition("/")
        if prefix != "telegram:" or not separator or not file_id.strip():
            raise MediaIngestionError("telegram_storage_key_invalid")
        try:
            await self._bot.download(file_id, destination=destination)
        except Exception as exc:
            raise MediaIngestionError("telegram_media_download_failed") from exc
        if not destination.is_file():
            raise MediaIngestionError("telegram_media_download_missing")


__all__ = ["TelegramMediaSource"]
