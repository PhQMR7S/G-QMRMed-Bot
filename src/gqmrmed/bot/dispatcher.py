"""Durable DB-to-Redis dispatcher for generation jobs."""

import asyncio
import logging

from redis.asyncio import Redis

from gqmrmed.db.session import SessionFactory
from gqmrmed.services.jobs import (
    get_undispatched_jobs,
    mark_dispatched,
    record_dispatch_failure,
)
from gqmrmed.services.redis_queue import RedisJobQueue

logger = logging.getLogger(__name__)


class GenerationDispatcher:
    """Continuously publish queued DB jobs to Redis with recovery after crashes."""

    def __init__(self, redis: Redis, *, interval_seconds: float = 2.0) -> None:
        if interval_seconds <= 0:
            raise ValueError("invalid_dispatch_interval")
        self._queue = RedisJobQueue(redis)
        self._interval = interval_seconds

    async def dispatch_once(self) -> int:
        """Publish one bounded batch and return the number successfully recorded."""
        async with SessionFactory() as session:
            job_ids = await get_undispatched_jobs(session)

        dispatched = 0
        for job_id in job_ids:
            try:
                await self._queue.enqueue(job_id=job_id)
            except Exception as exc:
                logger.exception("generation_queue_publish_failed", extra={"job_id": str(job_id)})
                async with SessionFactory() as session:
                    async with session.begin():
                        await record_dispatch_failure(
                            session,
                            job_id,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                continue

            async with SessionFactory() as session:
                async with session.begin():
                    if await mark_dispatched(session, job_id=job_id):
                        dispatched += 1
        return dispatched

    async def run(self, stop_event: asyncio.Event) -> None:
        """Run until shutdown is requested; DB remains the source of truth."""
        while not stop_event.is_set():
            try:
                await self.dispatch_once()
            except Exception:
                logger.exception("generation_dispatcher_iteration_failed")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self._interval)
            except TimeoutError:
                pass


__all__ = ["GenerationDispatcher"]
