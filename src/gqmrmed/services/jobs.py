"""Generation-job lifecycle primitives."""

from datetime import datetime, UTC
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.db.models import GenerationJob, JobStatus

VALID_STAGES = (
    "researching",
    "synthesizing",
    "architecture",
    "generating",
    "rendering",
    "quality_control",
)
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
    """Create a queued job for text, image, file, or mixed input."""
    normalized_type = input_type.strip()
    normalized_text = input_text.strip() if input_text is not None else None
    if not normalized_type:
        raise ValueError("generation_input_type_required")
    if len(normalized_type) > 32:
        raise ValueError("generation_input_type_too_long")
    if not normalized_text and not input_storage_key:
        raise ValueError("generation_input_required")
    job = GenerationJob(
        user_id=user_id,
        input_type=normalized_type,
        input_text=normalized_text or None,
        input_storage_key=input_storage_key,
        input_mime_type=input_mime_type[:128] if input_mime_type else None,
        input_metadata=input_metadata,
        status=JobStatus.QUEUED.value,
        progress=0,
    )
    session.add(job)
    await session.flush()
    return job


async def mark_running(session: AsyncSession, job_id: UUID, stage: str) -> None:
    """Transition a queued job to running and set its current stage."""
    if stage not in VALID_STAGES:
        raise ValueError("invalid_generation_stage")
    result = await session.execute(
        select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()
    )
    job = result.scalar_one()
    if job.status != JobStatus.QUEUED.value:
        raise ValueError("invalid_job_transition")
    job.status = JobStatus.RUNNING.value
    job.current_stage = stage
    job.progress = max(job.progress, 1)
    job.started_at = datetime.now(UTC)
    await session.flush()


async def update_progress(
    session: AsyncSession,
    job_id: UUID,
    *,
    stage: str,
    progress: int,
) -> None:
    """Update progress while enforcing monotonic stage and progress order."""
    if stage not in VALID_STAGES:
        raise ValueError("invalid_generation_stage")
    if not 0 <= progress <= 100:
        raise ValueError("invalid_generation_progress")
    result = await session.execute(
        select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()
    )
    job = result.scalar_one()
    if job.status != JobStatus.RUNNING.value:
        raise ValueError("invalid_job_transition")
    if job.current_stage is not None and _STAGE_INDEX[stage] < _STAGE_INDEX[job.current_stage]:
        raise ValueError("generation_stage_regression")
    job.current_stage = stage
    job.progress = max(job.progress, progress)
    await session.flush()


async def finish_job(
    session: AsyncSession,
    job_id: UUID,
    *,
    success: bool,
    error: str | None = None,
) -> None:
    """Finalize a running job exactly once."""
    result = await session.execute(
        select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()
    )
    job = result.scalar_one()
    if job.status != JobStatus.RUNNING.value:
        raise ValueError("invalid_job_transition")
    job.status = JobStatus.SUCCEEDED.value if success else JobStatus.FAILED.value
    job.progress = 100 if success else job.progress
    job.completed_at = datetime.now(UTC)
    job.error = error if not success else None
    if success:
        job.current_stage = "quality_control"
    await session.flush()
