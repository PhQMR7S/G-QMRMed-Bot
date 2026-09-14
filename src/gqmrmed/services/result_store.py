"""Persistent result storage and Telegram delivery adapters."""

import asyncio
from pathlib import Path
from typing import Any
from uuid import UUID

import boto3
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

    async def load(self, storage_key: str) -> StoredResult:
        """Reload a persisted result for delivery retry after process restart."""
        path = Path(storage_key)
        if not path.is_file():
            raise FileNotFoundError("stored_result_missing")
        data = path.read_bytes()
        if not data:
            raise ValueError("stored_result_empty")
        return StoredResult(
            storage_key=storage_key,
            width=0,
            height=0,
            mime_type="image/png",
            image_bytes=data,
        )


class S3ResultStore:
    """Persist final PNGs in any S3-compatible object storage service."""

    def __init__(
        self,
        *,
        endpoint: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        region: str | None = None,
    ) -> None:
        if not endpoint.strip() or not access_key_id.strip() or not secret_access_key.strip():
            raise ValueError("incomplete_s3_configuration")
        if not bucket.strip():
            raise ValueError("invalid_s3_bucket")
        self._bucket = bucket
        self._client: Any = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
        )

    async def put(self, *, job_id: UUID, image: GeneratedIllustration) -> StoredResult:
        if image.mime_type != "image/png":
            raise ValueError("final_result_must_be_png")
        if image.width <= 0 or image.height <= 0 or not image.image_bytes:
            raise ValueError("invalid_final_result")
        key = f"results/{job_id}.png"
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=image.image_bytes,
            ContentType="image/png",
        )
        return StoredResult(
            storage_key=f"s3://{self._bucket}/{key}",
            width=image.width,
            height=image.height,
            mime_type=image.mime_type,
            image_bytes=image.image_bytes,
        )

    async def load(self, storage_key: str) -> StoredResult:
        """Reload an object for durable Telegram delivery retry."""
        prefix = f"s3://{self._bucket}/"
        if not storage_key.startswith(prefix):
            raise ValueError("invalid_s3_storage_key")
        key = storage_key[len(prefix) :]
        response = await asyncio.to_thread(
            self._client.get_object,
            Bucket=self._bucket,
            Key=key,
        )
        body = response["Body"]
        try:
            data = await asyncio.to_thread(body.read)
        finally:
            await asyncio.to_thread(body.close)
        if not data:
            raise ValueError("stored_result_empty")
        return StoredResult(
            storage_key=storage_key,
            width=0,
            height=0,
            mime_type="image/png",
            image_bytes=data,
        )


class TelegramResultDelivery:
    """Send completed infographics and safe user-facing generation failures."""

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def __call__(self, job: GenerationJob, result: StoredResult) -> int | None:
        chat_id = (job.input_metadata or {}).get("telegram_chat_id")
        if not isinstance(chat_id, int) or chat_id <= 0:
            raise ValueError("telegram_chat_id_unavailable")
        if not result.image_bytes:
            raise ValueError("result_bytes_unavailable")
        sent = await self._bot.send_photo(
            chat_id=chat_id,
            photo=BufferedInputFile(result.image_bytes, filename=f"{job.id}.png"),
        )
        return sent.message_id

    async def notify_failure(self, job: GenerationJob) -> None:
        chat_id = (job.input_metadata or {}).get("telegram_chat_id")
        if not isinstance(chat_id, int) or chat_id <= 0:
            return
        await self._bot.send_message(
            chat_id=chat_id,
            text=(
                "⚠️ <b>تعذر إكمال التصميم الطبي</b>\n\n"
                "تعذر تشغيل خدمة تركيب المحتوى الطبي حاليًا، لذلك لم يتم إرسال تصميم ناقص أو غير موثوق.\n"
                "لم يتم احتساب التصميم من رصيدك. سنتمكن من المتابعة بعد عودة خدمة التوليد."
            ),
            parse_mode="HTML",
        )


__all__ = ["FilesystemResultStore", "S3ResultStore", "TelegramResultDelivery"]
