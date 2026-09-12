"""Atomic cancellation helpers for queued generation jobs."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.db.models import GenerationJob, UsageReservation
from gqmrmed.services.jobs import cancel_queued_job
from gqmrmed.services.usage import Reservation, release_generation


async def cancel_generation(
    session: AsyncSession,
    *,
    job_id: UUID,
) -> bool:
    """Cancel a queued job and release its reserved quota atomically.

    The job row is locked by ``cancel_queued_job`` and the reservation row is
    then locked by ``release_generation``. Repeating cancellation is safe: an
    already-cancelled job returns success and an already-released reservation
    is a no-op.
    """
    cancelled = await cancel_queued_job(session, job_id)
    if not cancelled:
        return False

    result = await session.execute(
        select(UsageReservation).where(UsageReservation.job_id == job_id)
    )
    ledger = result.scalar_one_or_none()
    if ledger is None:
        return True

    reservation = Reservation(
        id=ledger.id,
        user_id=ledger.user_id,
        job_id=ledger.job_id,
        usage_date=ledger.usage_date,
    )
    await release_generation(session, reservation)
    return True


async def get_job_for_cancellation(
    session: AsyncSession,
    *,
    job_id: UUID,
) -> GenerationJob | None:
    """Return a job for callers that need to verify ownership before cancel."""
    result = await session.execute(
        select(GenerationJob).where(GenerationJob.id == job_id)
    )
    return result.scalar_one_or_none()
