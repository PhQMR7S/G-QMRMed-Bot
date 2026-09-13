"""Phase 7 worker orchestration with durable progress, heartbeat and delivery retry."""

# The worker contains a few intentionally dense SQL/metadata expressions.
# Keep the implementation readable without forcing artificial wrapping.
# ruff: noqa: E501, I001

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from gqmrmed.contracts.generation import GenerationStage, InputType
from gqmrmed.db.models import GenerationJob, GenerationResult, JobStatus, UsageReservation
from gqmrmed.generation.providers import GeneratedIllustration
from gqmrmed.services.jobs import (
    finish_job,
    mark_delivery_pending,
    mark_delivery_succeeded,
    mark_running,
    recover_stale_running_jobs,
    touch_job_heartbeat,
    update_progress,
)
from gqmrmed.services.media_ingestion import MediaIngestor
from gqmrmed.services.usage import Reservation, commit_generation, release_generation

logger = logging.getLogger(__name__)


def _metadata_int(metadata: dict[str, object], key: str, default: int = 0) -> int:
    value = metadata.get(key, default)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


@dataclass(frozen=True, slots=True)
class StoredResult:
    """Metadata returned after an output image has been persisted."""

    storage_key: str
    width: int
    height: int
    mime_type: str
    image_bytes: bytes | None = None


class GenerationPipeline(Protocol):
    async def run(
        self,
        job: GenerationJob,
        progress: Callable[[GenerationStage, int], Awaitable[None]],
    ) -> GeneratedIllustration:
        ...


class ResultStore(Protocol):
    async def put(self, *, job_id: UUID, image: GeneratedIllustration) -> StoredResult: ...

    async def load(self, storage_key: str) -> StoredResult: ...


class DeliverySink(Protocol):
    async def __call__(self, job: GenerationJob, result: StoredResult) -> int | None: ...


class ProgressSink(Protocol):
    async def __call__(
        self,
        job: GenerationJob,
        stage: GenerationStage,
        progress: int,
    ) -> None: ...


class ThrottledProgressReporter:
    """Emit progress updates at a bounded cadence."""

    def __init__(self, *, interval_seconds: float = 4.0) -> None:
        if interval_seconds < 1.0:
            raise ValueError("progress_interval_too_short")
        self._interval = interval_seconds
        self._last_emit = 0.0
        self._last_stage: GenerationStage | None = None
        self._last_progress = -1

    def should_emit(self, stage: GenerationStage, progress: int, *, force: bool = False) -> bool:
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
    async def dequeue(self, *, timeout_seconds: int) -> str | None: ...


class GenerationWorker:
    """Consume durable jobs with heartbeat leases and at-least-once result delivery."""

    def __init__(
        self,
        *,
        queue: JobQueue,
        session_factory: async_sessionmaker[AsyncSession],
        pipeline: GenerationPipeline,
        result_store: ResultStore,
        progress_sink: ProgressSink | None = None,
        delivery_sink: DeliverySink | None = None,
        media_ingestor: MediaIngestor | None = None,
        media_temp_dir: str = "/tmp/gqmrmed-media",
        poll_timeout_seconds: int = 2,
        recovery_interval_seconds: int = 60,
        stale_running_after_seconds: int = 900,
        heartbeat_interval_seconds: int = 30,
    ) -> None:
        if poll_timeout_seconds <= 0 or recovery_interval_seconds <= 0:
            raise ValueError("invalid_worker_timing")
        if stale_running_after_seconds <= heartbeat_interval_seconds * 2:
            raise ValueError("stale_window_must_exceed_heartbeat_interval")
        if heartbeat_interval_seconds <= 0:
            raise ValueError("invalid_heartbeat_interval")
        self._queue = queue
        self._session_factory = session_factory
        self._pipeline = pipeline
        self._result_store = result_store
        self._progress_sink = progress_sink
        self._delivery_sink = delivery_sink
        self._media_ingestor = media_ingestor
        self._media_temp_dir = Path(media_temp_dir)
        self._poll_timeout = poll_timeout_seconds
        self._recovery_interval = recovery_interval_seconds
        self._stale_running_after = stale_running_after_seconds
        self._heartbeat_interval = heartbeat_interval_seconds
        self._last_recovery = 0.0

    async def run_once(self) -> bool:
        await self._recover_stale_jobs_if_due()
        await self._retry_pending_deliveries()
        raw_job_id = await self._queue.dequeue(timeout_seconds=self._poll_timeout)
        if raw_job_id is None:
            return False
        try:
            job_id = UUID(raw_job_id)
        except ValueError:
            logger.error("generation_queue_invalid_job_id", extra={"job_id": raw_job_id})
            return True
        await self.process(job_id)
        return True

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await self.run_once()
            except Exception:
                logger.exception("generation_worker_iteration_failed")

    async def _recover_stale_jobs_if_due(self) -> None:
        now = time.monotonic()
        if now - self._last_recovery < self._recovery_interval:
            return
        self._last_recovery = now
        async with self._session_factory() as session:
            async with session.begin():
                recovered = await recover_stale_running_jobs(
                    session, stale_after_seconds=self._stale_running_after
                )
                for job_id in recovered:
                    result = await session.execute(
                        select(UsageReservation).where(UsageReservation.job_id == job_id)
                    )
                    ledger = result.scalar_one_or_none()
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
                if recovered:
                    logger.warning(
                        "generation_stale_jobs_recovered",
                        extra={"count": len(recovered)},
                    )

    async def _retry_pending_deliveries(self) -> None:
        if self._delivery_sink is None:
            return
        async with self._session_factory() as session:
            result = await session.execute(
                select(GenerationResult, GenerationJob)
                .join(GenerationJob, GenerationJob.id == GenerationResult.job_id)
                .where(GenerationJob.status == JobStatus.SUCCEEDED.value)
                .order_by(GenerationResult.created_at.asc())
                .limit(20)
            )
            candidates = list(result.all())
        for stored_row, job in candidates:
            status = (job.input_metadata or {}).get("telegram_delivery_status")
            if status == "DELIVERED":
                continue
            try:
                stored = await self._result_store.load(stored_row.storage_key)
                stored = StoredResult(
                    storage_key=stored.storage_key,
                    width=stored_row.width,
                    height=stored_row.height,
                    mime_type=stored_row.mime_type,
                    image_bytes=stored.image_bytes,
                )
                message_id = await self._delivery_sink(job, stored)
            except Exception as exc:
                logger.exception(
                    "generation_delivery_retry_failed",
                    extra={"job_id": str(job.id)},
                )
                async with self._session_factory() as error_session:
                    async with error_session.begin():
                        fresh = await error_session.execute(
                            select(GenerationJob).where(GenerationJob.id == job.id).with_for_update()
                        )
                        current = fresh.scalar_one_or_none()
                        if current is not None:
                            metadata = dict(current.input_metadata or {})
                            attempts = _metadata_int(metadata, "telegram_delivery_attempts") + 1
                            metadata["telegram_delivery_attempts"] = attempts
                            metadata["telegram_delivery_last_error"] = f"{type(exc).__name__}: {exc}"[:2000]
                            current.input_metadata = metadata
                continue
            async with self._session_factory() as success_session:
                async with success_session.begin():
                    await mark_delivery_succeeded(
                        success_session,
                        job.id,
                        message_id=message_id,
                    )

    async def _emit_progress(self, job: GenerationJob, stage: GenerationStage, progress: int) -> None:
        if self._progress_sink is None:
            return
        try:
            await self._progress_sink(job, stage, progress)
        except Exception:
            logger.exception(
                "generation_progress_delivery_failed",
                extra={"job_id": str(job.id), "stage": stage.value, "progress": progress},
            )

    async def _heartbeat(self, job_id: UUID, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=self._heartbeat_interval)
            except TimeoutError:
                pass
            if stop.is_set():
                return
            try:
                async with self._session_factory() as session:
                    async with session.begin():
                        await touch_job_heartbeat(session, job_id)
            except Exception:
                logger.exception("generation_heartbeat_failed", extra={"job_id": str(job_id)})

    async def _prepare_media(self, job: GenerationJob) -> Path | None:
        """Download Telegram media and convert it into synthesis-ready text."""
        storage_key = job.input_storage_key
        if self._media_ingestor is None or not storage_key:
            return None
        destination = self._media_temp_dir / f"{job.id}.bin"
        ingested = await self._media_ingestor.ingest(
            storage_key=storage_key,
            mime_type=job.input_mime_type,
            destination=destination,
        )
        if not ingested.extracted_text:
            raise ValueError("media_content_extraction_required")
        prefix = (job.input_text or "").strip()
        if job.input_type == InputType.MIXED.value and prefix:
            job.input_text = (
                f"User caption/context:\n{prefix}\n\nExtracted media content:\n"
                f"{ingested.extracted_text}"
            )
        else:
            job.input_text = ingested.extracted_text
        job.input_type = InputType.TEXT.value
        return destination

    async def process(self, job_id: UUID) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                job_result = await session.execute(
                    select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()
                )
                job = job_result.scalar_one_or_none()
                if job is None or job.status != JobStatus.QUEUED.value:
                    return
                await mark_running(session, job_id, GenerationStage.RESEARCHING.value)

        media_destination: Path | None = None
        heartbeat_stop = asyncio.Event()
        heartbeat_task: asyncio.Task[None] | None = None
        try:
            async with self._session_factory() as session:
                job_result = await session.execute(
                    select(GenerationJob).where(GenerationJob.id == job_id)
                )
                job = job_result.scalar_one()

            heartbeat_task = asyncio.create_task(self._heartbeat(job_id, heartbeat_stop))
            reporter = ThrottledProgressReporter()
            await self._emit_progress(job, GenerationStage.RESEARCHING, 1)
            media_destination = await self._prepare_media(job)

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
                        select(UsageReservation).where(UsageReservation.job_id == job_id)
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
                    await mark_delivery_pending(session, job_id)

            await self._emit_progress(job, GenerationStage.QUALITY_CONTROL, 100)
            if self._delivery_sink is not None:
                try:
                    message_id = await self._delivery_sink(job, stored)
                except Exception:
                    logger.exception("generation_delivery_failed", extra={"job_id": str(job_id)})
                else:
                    async with self._session_factory() as session:
                        async with session.begin():
                            await mark_delivery_succeeded(session, job_id, message_id=message_id)
        except Exception as exc:
            logger.exception("generation_job_failed", extra={"job_id": str(job_id)})
            async with self._session_factory() as session:
                async with session.begin():
                    usage_result = await session.execute(
                        select(UsageReservation).where(UsageReservation.job_id == job_id)
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
        finally:
            heartbeat_stop.set()
            if heartbeat_task is not None:
                await heartbeat_task
            if media_destination is not None:
                media_destination.unlink(missing_ok=True)


__all__ = [
    "DeliverySink",
    "GenerationWorker",
    "JobQueue",
    "ProgressSink",
    "ResultStore",
    "StoredResult",
    "ThrottledProgressReporter",
]
