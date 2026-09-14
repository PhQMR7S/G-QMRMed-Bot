"""Result persistence and Telegram delivery adapters."""

from __future__ import annotations

import asyncio
from pathlib import Path

from aiogram import Bot
from aiogram.types import BufferedInputFile

from gqmrmed.db.models import GenerationJob
from gqmrmed.generation.providers import GeneratedIllustration


class FilesystemResultStore:
    """Persist final PNGs under a deterministic, job-scoped key."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    async def put(self, *, job_id, image: GeneratedIllustration):
        from gqmrmed.services.worker import StoredResult

        path = self._root / f"{job_id}.png"
        await asyncio.to_thread(path.write_bytes, image.image_bytes)
        return StoredResult(
            storage_key=str(path),
            width=image.width,
            height=image.height,
            mime_type=image.mime_type,
            image_bytes=image.image_bytes,
        )

    async def load(self, storage_key: str):
        from gqmrmed.services.worker import StoredResult

        path = Path(storage_key)
        data = await asyncio.to_thread(path.read_bytes)
        return StoredResult(
            storage_key=storage_key,
            width=0,
            height=0,
            mime_type="image/png",
            image_bytes=data,
        )


class S3ResultStore:
    """Persist final PNGs in S3-compatible object storage."""

    def __init__(self, *, endpoint, access_key_id, secret_access_key, bucket, region=None) -> None:
        import boto3

        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
        )

    async def put(self, *, job_id, image: GeneratedIllustration):
        from gqmrmed.services.worker import StoredResult

        key = f"generations/{job_id}.png"
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=image.image_bytes,
            ContentType=image.mime_type,
        )
        return StoredResult(
            storage_key=f"s3://{self._bucket}/{key}",
            width=image.width,
            height=image.height,
            mime_type=image.mime_type,
            image_bytes=image.image_bytes,
        )

    async def load(self, storage_key: str):
        from gqmrmed.services.worker import StoredResult

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

    async def __call__(self, job: GenerationJob, result) -> int | None:
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
