"""Minimal Redis-backed queue adapter for generation jobs."""

from uuid import UUID

from redis.asyncio import Redis


class RedisJobQueue:
    """Push generation IDs to Redis without coupling business logic to Redis."""

    def __init__(self, redis: Redis, *, queue_name: str = "gqmrmed:generation") -> None:
        self._redis = redis
        self._queue_name = queue_name

    async def enqueue(self, *, job_id: UUID) -> str:
        """Enqueue a job ID and return its stable queue value."""
        value = str(job_id)
        await self._redis.rpush(self._queue_name, value)
        return value

    async def close(self) -> None:
        """Close the underlying Redis client."""
        await self._redis.aclose()
