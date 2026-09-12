"""Dependency inversion ports for storage, queueing, and image generation."""

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol
from uuid import UUID


class ObjectStorage(Protocol):
    async def put(self, *, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, *, key: str) -> bytes: ...

    async def delete(self, *, key: str) -> None: ...


class JobQueue(Protocol):
    async def enqueue(self, *, job_id: UUID) -> str: ...


class ImageGenerationProvider(Protocol):
    async def generate(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
        metadata: Mapping[str, object] | None = None,
    ) -> Path: ...
