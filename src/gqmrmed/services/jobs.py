"""Generation-job lifecycle and durable queue-dispatch primitives."""

from datetime import datetime, timedelta, UTC
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.contracts.generation import GenerationStage
from gqmrmed.db.models import GenerationJob, JobStatus

VALID_STAGES = tuple(stage.value for stage in GenerationStage)
_STAGE_INDEX = {stage: index for index, stage in enumerate(VALID_STAGES)}


async def create_generation_job(
    session: AsyncSession,
    *,
    user_id: UUID,
    input_type: str,
    input_text: str | None = None,
    input_storage_key: str | None = None,
    input_mime_type: str | None = None,
    input_metadata: dict[str, object] | None = None,
) -> GenerationJob:
    """Create a normalized queued generation job."""
    if not input_type.strip():
        raise ValueError("input_type_required")
    if input_text is not None and not input_text.strip():
        input_text = None
    if input_text is None and input_storage_key is None:
        raise ValueError("generation_input_required")
    job = GenerationJob(
        user_id=user_id,
        input_type=input_type,
        input_text=input_text,
        input_storage_key=input_storage_key,
        input_mime_type=input_mime_type,
        input_metadata=input_metadata or {},
        status=JobStatus.QUEUED.value,
        progress=0,
        stage=GenerationStage.RESEARCHING.value,
    )
    session.add(job)
    await session.flush()
    return job


async def claim_queued_job(session: AsyncSession, job_id: UUID) -> GenerationJob | None:
    """Claim a queued job under a row lock."""
    result = await session.execute(
        select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()
    )
    job = result.scalar_one_or_none()
    if job is None or job.status != JobStatus.QUEUED.value:
        return None
    return job


async def mark_enqueued(session: AsyncSession, job_id: UUID) -> None:
    """Persist that a queued job has been published to Redis."""
    result = await session.execute(
        select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()
    )
    job = result.scalar_one_or_none()
    if job is None or job.status != JobStatus.QUEUED.value:
        return
    job.enqueued_at = datetime.now(UTC)


async def record_dispatch_failure(session: AsyncSession, job_id: UUID, error: str) -> None:
    """Clear the dispatch lease after a Redis publish failure."""
    result = await session.execute(
        select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()
    )
    job = result.scalar_one_or_none()
    if job is None or job.status != JobStatus.QUEUED.value:
        return
    job.enqueued_at = None
    metadata = dict(job.input_metadata or {})
    metadata["dispatch_last_error"] = error[:2000]
    metadata["dispatch_attempts"] = int(metadata.get("dispatch_attempts", 0)) + 1
    job.input_metadata = metadata


async def recover_stale_queued_jobs(
    session: AsyncSession,
    *,
    stale_after_seconds: int = 120,
) -> list[UUID]:
    """Clear stale Redis dispatch leases so queued jobs can be re-published."""
    cutoff = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
    result = await session.execute(
        select(GenerationJob)
        .where(
            GenerationJob.status == JobStatus.QUEUED.value,
            GenerationJob.enqueued_at.is_not(None),
            GenerationJob.enqueued_at <= cutoff,
        )
        .with_for_update(skip_locked=True)
    )
    jobs = list(result.scalars())
    for job in jobs:
        job.enqueued_at = None
    return [job.id for job in jobs]


async def recover_stale_running_jobs(
    session: AsyncSession,
    *,
    stale_after_seconds: int = 900,
) -> list[UUID]:
    """Reset jobs whose worker heartbeat/updated_at lease has expired."""
    cutoff = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
    result = await session.execute(
        select(GenerationJob)
        .where(
            GenerationJob.status == JobStatus.RUNNING.value,
            GenerationJob.updated_at <= cutoff,
        )
        .with_for_update(skip_locked=True)
    )
    jobs = list(result.scalars())
    for job in jobs:
        job.status = JobStatus.QUEUED.value
        job.progress = 0
        job.stage = GenerationStage.RESEARCHING.value
        job.error = "worker_lease_expired"
        job.enqueued_at = None
    return [job.id for job in jobs]


async def mark_running(session: AsyncSession, job_id: UUID, stage: str) -> None:
    """Move a queued job to running under a row lock."""
    result = await session.execute(
        select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()
    )
    job = result.scalar_one_or_none()
    if job is None or job.status != JobStatus.QUEUED.value:
        return
    job.status = JobStatus.RUNNING.value
    job.stage = stage
    job.progress = max(job.progress, 1)
    job.enqueued_at = None


async def touch_job_heartbeat(session: AsyncSession, job_id: UUID) -> None:
    """Refresh the worker lease without changing user-visible progress."""
    result = await session.execute(
        select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()
    )
    job = result.scalar_one_or_none()
    if job is None or job.status != JobStatus.RUNNING.value:
        return
    metadata = dict(job.input_metadata or {})
    metadata["worker_heartbeat_at"] = datetime.now(UTC).isoformat()
    job.input_metadata = metadata


async def mark_delivery_pending(session: AsyncSession, job_id: UUID) -> None:
    """Persist the delivery state before attempting Telegram delivery."""
    result = await session.execute(
        select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()
    )
    job = result.scalar_one_or_none()
    if job is None:
        return
    metadata = dict(job.input_metadata or {})
    metadata["telegram_delivery_status"] = "PENDING"
    metadata.setdefault("telegram_delivery_attempts", 0)
    job.input_metadata = metadata


async def mark_delivery_succeeded(
    session: AsyncSession,
    job_id: UUID,
    *,
    message_id: int | None,
) -> None:
    """Persist successful Telegram delivery and optional message ID."""
    result = await session.execute(
        select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()
    )
    job = result.scalar_one_or_none()
    if job is None:
        return
    metadata = dict(job.input_metadata or {})
    metadata["telegram_delivery_status"] = "DELIVERED"
    if message_id is not None:
        metadata["telegram_delivery_message_id"] = message_id
    job.input_metadata = metadata


async def cancel_queued_job(session: AsyncSession, job_id: UUID) -> bool:
    """Cancel a queued job; running/succeeded jobs are not mutated."""
    result = await session.execute(
        select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()
    )
    job = result.scalar_one_or_none()
    if job is None or job.status != JobStatus.QUEUED.value:
        return False
    job.status = JobStatus.CANCELLED.value
    job.enqueued_at = None
    return True


async def update_progress(
    session: AsyncSession,
    job_id: UUID,
    *,
    stage: str,
    progress: int,
) -> None:
    """Update monotonic stage/progress state under a row lock."""
    if stage not in _STAGE_INDEX:
        raise ValueError("invalid_generation_stage")
    if not 0 <= progress <= 100:
        raise ValueError("invalid_generation_progress")
    result = await session.execute(
        select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()
    )
    job = result.scalar_one_or_none()
    if job is None or job.status != JobStatus.RUNNING.value:
        return
    current_index = _STAGE_INDEX.get(job.stage, -1)
    next_index = _STAGE_INDEX[stage]
    if next_index < current_index or progress < job.progress:
        raise ValueError("non_monotonic_generation_progress")
    job.stage = stage
    job.progress = progress


async def set_progress_message_id(
    session: AsyncSession,
    job_id: UUID,
    message_id: int,
) -> None:
    """Persist the Telegram progress message identifier."""
    result = await session.execute(
        select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()
    )
    job = result.scalar_one_or_none()
    if job is not None:
        job.progress_message_id = message_id


async def finish_job(
    session: AsyncSession,
    job_id: UUID,
    *,
    success: bool,
    error: str | None = None,
) -> None:
    """Finalize a job after its result/usage transaction is ready."""
    result = await session.execute(
        select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()
    )
    job = result.scalar_one_or_none()
    if job is None:
        return
    job.status = JobStatus.SUCCEEDED.value if success else JobStatus.FAILED.value
    job.progress = 100 if success else job.progress
    job.stage = GenerationStage.QUALITY_CONTROL.value if success else job.stage
    job.error = None if success else (error or "generation_failed")
