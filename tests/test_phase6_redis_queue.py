from typing import cast
from uuid import uuid4

from redis.asyncio import Redis

from gqmrmed.services.redis_queue import RedisJobQueue


class _FakeRedis:
    def __init__(self, result: tuple[str | bytes, str | bytes] | None) -> None:
        self.result = result
        self.pushed: list[tuple[str, str]] = []
        self.closed = False

    async def rpush(self, name: str, value: str) -> int:
        self.pushed.append((name, value))
        return len(self.pushed)

    async def blpop(
        self,
        keys: list[str],
        *,
        timeout: int,
    ) -> tuple[str | bytes, str | bytes] | None:
        assert keys == ["gqmrmed:generation"]
        assert timeout == 2
        return self.result

    async def aclose(self) -> None:
        self.closed = True


async def test_redis_queue_round_trips_job_ids() -> None:
    fake = _FakeRedis(None)
    queue = RedisJobQueue(cast(Redis, fake))
    job_id = uuid4()

    assert await queue.enqueue(job_id=job_id) == str(job_id)
    assert fake.pushed == [("gqmrmed:generation", str(job_id))]
    assert await queue.dequeue(timeout_seconds=2) is None
    await queue.close()
    assert fake.closed


async def test_redis_queue_decodes_bytes_values() -> None:
    fake = _FakeRedis((b"gqmrmed:generation", b"job-123"))
    queue = RedisJobQueue(cast(Redis, fake))

    assert await queue.dequeue(timeout_seconds=2) == "job-123"


async def test_redis_queue_preserves_string_values() -> None:
    fake = _FakeRedis(("gqmrmed:generation", "job-456"))
    queue = RedisJobQueue(cast(Redis, fake))

    assert await queue.dequeue(timeout_seconds=2) == "job-456"
