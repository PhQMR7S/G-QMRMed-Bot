"""Persistent result storage and Telegram delivery adapters."""

import asyncio
import io
import json
from pathlib import Path
from typing import Any
from uuid import UUID

import boto3
from aiogram import Bot
from aiogram.types import BufferedInputFile
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

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


class GoogleDriveResultStore:
    """Persist final PNGs in a dedicated Google Drive folder.

    Authentication uses a service-account JSON document supplied at runtime.
    The service account must have access to the configured folder; no Drive
    credentials or file data are stored in the repository.
    """

    _SCOPES = ("https://www.googleapis.com/auth/drive.file",)
    _PREFIX = "gdrive://"

    def __init__(self, *, credentials_json: str, folder_id: str) -> None:
        if not credentials_json.strip():
            raise ValueError("google_drive_credentials_required")
        if not folder_id.strip():
            raise ValueError("google_drive_folder_id_required")
        try:
            info = json.loads(credentials_json)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid_google_drive_credentials_json") from exc
        if not isinstance(info, dict) or not info:
            raise ValueError("invalid_google_drive_credentials_json")
        credentials = service_account.Credentials.from_service_account_info(
            info, scopes=self._SCOPES
        )
        self._folder_id = folder_id
        self._drive: Any = build("drive", "v3", credentials=credentials, cache_discovery=False)

    @staticmethod
    def _validate_image(image: GeneratedIllustration) -> None:
        if image.mime_type != "image/png":
            raise ValueError("final_result_must_be_png")
        if image.width <= 0 or image.height <= 0 or not image.image_bytes:
            raise ValueError("invalid_final_result")

    async def put(self, *, job_id: UUID, image: GeneratedIllustration) -> StoredResult:
        self._validate_image(image)
        filename = f"{job_id}.png"
        existing = await asyncio.to_thread(
            lambda: self._drive.files()
            .list(
                q=(
                    f"'{self._folder_id}' in parents and name='{filename}' "
                    "and trashed=false"
                ),
                pageSize=1,
                fields="files(id)",
                spaces="drive",
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
            )
            .execute()
        )
        files = existing.get("files", [])
        file_id = files[0].get("id") if files else None
        media = MediaIoBaseUpload(
            io.BytesIO(image.image_bytes), mimetype="image/png", resumable=True
        )
        if isinstance(file_id, str) and file_id:
            await asyncio.to_thread(
                lambda: self._drive.files()
                .update(
                    fileId=file_id,
                    media_body=media,
                    fields="id",
                    supportsAllDrives=True,
                )
                .execute()
            )
        else:
            metadata = {
                "name": filename,
                "parents": [self._folder_id],
                "mimeType": "image/png",
            }
            response = await asyncio.to_thread(
                lambda: self._drive.files()
                .create(
                    body=metadata,
                    media_body=media,
                    fields="id",
                    supportsAllDrives=True,
                )
                .execute()
            )
            file_id = response.get("id")
        if not isinstance(file_id, str) or not file_id:
            raise ValueError("google_drive_upload_missing_file_id")
        return StoredResult(
            storage_key=f"{self._PREFIX}{file_id}",
            width=image.width,
            height=image.height,
            mime_type=image.mime_type,
            image_bytes=image.image_bytes,
        )

    async def load(self, storage_key: str) -> StoredResult:
        """Reload a Drive file for durable Telegram delivery retry."""
        if not storage_key.startswith(self._PREFIX):
            raise ValueError("invalid_google_drive_storage_key")
        file_id = storage_key[len(self._PREFIX) :]
        if not file_id:
            raise ValueError("invalid_google_drive_storage_key")
        stream = io.BytesIO()
        request = self._drive.files().get_media(fileId=file_id, supportsAllDrives=True)
        downloader = MediaIoBaseDownload(stream, request)
        done = False
        while not done:
            _, done = await asyncio.to_thread(downloader.next_chunk)
        data = stream.getvalue()
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
    """Send only the completed infographic to the originating Telegram chat."""

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


__all__ = [
    "FilesystemResultStore",
    "GoogleDriveResultStore",
    "S3ResultStore",
    "TelegramResultDelivery",
]
