"""Phase 7 worker orchestration with durable live progress delivery."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from gqmrmed.contracts.generation import GenerationStage
from gqmrmed.db.models import GenerationJob, GenerationResult, UsageReservation
from gqmrmed.generation.providers import GeneratedIllustration
from gqmrmed.services.jobs import finish_job, mark_running, update_progress
from gqmrmed.services.usage import commit_generation, release_generation, Reservation

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StoredResult:
    """Metadata returned after an output image has been persisted."""

    storage_key: str
    width: int
    height: int
    mime_type: str


class GenerationPipeline(Protocol):
    async def run(
        self,
        job: GenerationJob,
        progress: Callable[[GenerationStage, int], Awaitable[None]],
    ) -> GeneratedIllustration:
        ...


class ResultStore(Protocol):
    async def put(
        self,
        *,
        job_id: UUID,
        image: GeneratedIllustration,
    ) -> StoredResult:
        ...


class ProgressSink(Protocol):
    async def __call__(
        self,
        job: GenerationJob,
        stage: GenerationStage,
        progress: int,
    ) -> None:
        ...


class ThrottledProgressReporter:
    """Emit progress updates at a bounded cadence."""

    def __init__(self, *, interval_seconds: float = 4.0) -> None:
        if interval_seconds < 1.0:
            raise ValueError("progress_interval_too_short")
        self._interval = interval_seconds
        self._last_emit = 0.0
        self._last_stage: GenerationStage | None = None
        self._last_progress = -1

    def should_emit(
        self,
        stage: GenerationStage,
        progress: int,
        *,
        force: bool = False,
    ) -> bool:
        now = time.monotonic()
        meaningful = stage != self._last_stage or progress >= self._last_progress + 5
        due = now - self._last_emit >= self._interval
        if force or meaningful or due:
            self._last_emit = now
            self._last_stage = stage
            self._last_progress = progress
            return True
        return False


class JobQueue(Protocol):
    async def dequeue(self, *, timeout_seconds: int) -> str | None:
        ...


class GenerationWorker:
    """Consume durable job IDs and settle DB state exactly once per execution."""

    def __init__(
        self,
        *,
        queue: JobQueue,
        session_factory: async_sessionmaker[AsyncSession],
        pipeline: GenerationPipeline,
        result_store: ResultStore,
        progress_sink: ProgressSink | None = None,
        poll_timeout_seconds: int = 2,
    ) -> None:
        if poll_timeout_seconds <= 0:
            raise ValueError("invalid_worker_poll_timeout")
        self._queue = queue
        self._session_factory = session_factory
        self._pipeline = pipeline
        self._result_store = result_store
        self._progress_sink = progress_sink
        self._poll_timeout = poll_timeout_seconds

    async def run_once(self) -> bool:
        raw_job_id = await self._queue.dequeue(timeout_seconds=self._poll_timeout)
        if raw_job_id is None:
            return False
        try:
            job_id = UUID(raw_job_id)
        except ValueError:
            logger.error(
                "generation_queue_invalid_job_id",
                extra={"job_id": raw_job_id},
            )
            return True
        await self.process(job_id)
        return True

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await self.run_once()
            except Exception:
                logger.exception("generation_worker_iteration_failed")

    async def _emit_progress(
        self,
        job: GenerationJob,
        stage: GenerationStage,
        progress: int,
    ) -> None:
        if self._progress_sink is None:
            return
        try:
            await self._progress_sink(job, stage, progress)
        except Exception:
            logger.exception(
                "generation_progress_delivery_failed",
                extra={"job_id": str(job.id), "stage": stage.value, "progress": progress},
            )

    async def process(self, job_id: UUID) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                job_result = await session.execute(
                    select(GenerationJob)
                    .where(GenerationJob.id == job_id)
                    .with_for_update()
                )
                job = job_result.scalar_one_or_none()
                if job is None or job.status != "QUEUED":
                    return
                await mark_running(
                    session,
                    job_id,
                    GenerationStage.RESEARCHING.value,
                )

        try:
            async with self._session_factory() as session:
                job_result = await session.execute(
                    select(GenerationJob).where(GenerationJob.id == job_id)
                )
                job = job_result.scalar_one()

            reporter = ThrottledProgressReporter()
            await self._emit_progress(job, GenerationStage.RESEARCHING, 1)

            async def progress(stage: GenerationStage, value: int) -> None:
                if not reporter.should_emit(stage, value):
                    return
                async with self._session_factory() as progress_session:
                    async with progress_session.begin():
                        await update_progress(
                            progress_session,
                            job_id,
                            stage=stage.value,
                            progress=value,
                        )
                await self._emit_progress(job, stage, value)

            image = await self._pipeline.run(job, progress)
            stored = await self._result_store.put(job_id=job_id, image=image)

            async with self._session_factory() as session:
                async with session.begin():
                    usage_result = await session.execute(
                        select(UsageReservation).where(
                            UsageReservation.job_id == job_id
                        )
                    )
                    ledger = usage_result.scalar_one_or_none()
                    if ledger is not None:
                        await commit_generation(
                            session,
                            Reservation(
                                id=ledger.id,
                                user_id=ledger.user_id,
                                job_id=ledger.job_id,
                                usage_date=ledger.usage_date,
                            ),
                        )
                    await finish_job(session, job_id, success=True)
                    session.add(
                        GenerationResult(
                            job_id=job_id,
                            storage_key=stored.storage_key,
                            mime_type=stored.mime_type,
                            width=stored.width,
                            height=stored.height,
                        )
                    )

            await self._emit_progress(job, GenerationStage.QUALITY_CONTROL, 100)
        except Exception as exc:
            logger.exception(
                "generation_job_failed",
                extra={"job_id": str(job_id)},
            )
            async with self._session_factory() as session:
                async with session.begin():
                    usage_result = await session.execute(
                        select(UsageReservation).where(
                            UsageReservation.job_id == job_id
                        )
                    )
                    ledger = usage_result.scalar_one_or_none()
                    if ledger is not None:
                        await release_generation(
                            session,
                            Reservation(
                                id=ledger.id,
                                user_id=ledger.user_id,
                                job_id=ledger.job_id,
                                usage_date=ledger.usage_date,
                            ),
                        )
                    await finish_job(
                        session,
                        job_id,
                        success=False,
                        error=f"{type(exc).__name__}: {exc}"[:4000],
                    )


__all__ = [
    "GenerationWorker",
    "JobQueue",
    "ProgressSink",
    "ResultStore",
    "StoredResult",
    "ThrottledProgressReporter",
]
