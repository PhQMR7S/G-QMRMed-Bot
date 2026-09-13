"""Redis queue operations used by Phase 6 workers."""

from collections.abc import Awaitable
from typing import cast
from uuid import UUID

from redis.asyncio import Redis


class RedisJobQueue:
    """Push and blocking-pop generation IDs from Redis."""

    def __init__(self, redis: Redis, *, queue_name: str = "gqmrmed:generation") -> None:
        self._redis = redis
        self._queue_name = queue_name

    async def enqueue(self, *, job_id: UUID) -> str:
        value = str(job_id)
        result = self._redis.rpush(self._queue_name, value)
        await cast(Awaitable[int], result)
        return value

    async def dequeue(self, *, timeout_seconds: int = 2) -> str | None:
        result = await self._redis.blpop([self._queue_name], timeout=timeout_seconds)
        if result is None:
            return None
        _, value = result
        return value.decode() if isinstance(value, bytes) else value

    async def close(self) -> None:
        await self._redis.aclose()


__all__ = ["RedisJobQueue"]
