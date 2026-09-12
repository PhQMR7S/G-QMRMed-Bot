"""Atomic daily generation quota reservation and settlement."""

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.db.models import DailyUsage


@dataclass(frozen=True, slots=True)
class Reservation:
    user_id: UUID
    usage_date: date


class QuotaExceededError(Exception):
    """Raised when the user's daily generation quota is exhausted."""


async def reserve_generation(
    session: AsyncSession,
    *,
    user_id: UUID,
    usage_date: date,
    daily_limit: int | None,
) -> Reservation:
    """Atomically reserve one generation slot.

    ``None`` means unlimited. PostgreSQL's ON CONFLICT path makes the finite
    quota check atomic, so concurrent Telegram updates cannot oversubscribe it.
    """
    if daily_limit is not None and daily_limit <= 0:
        raise QuotaExceededError

    if daily_limit is None:
        stmt = insert(DailyUsage).values(
            user_id=user_id,
            usage_date=usage_date,
            reserved=1,
            committed=0,
        ).on_conflict_do_update(
            index_elements=[DailyUsage.user_id, DailyUsage.usage_date],
            set_={"reserved": DailyUsage.reserved + 1},
        )
    else:
        stmt = insert(DailyUsage).values(
            user_id=user_id,
            usage_date=usage_date,
            reserved=1,
            committed=0,
        ).on_conflict_do_update(
            index_elements=[DailyUsage.user_id, DailyUsage.usage_date],
            set_={"reserved": DailyUsage.reserved + 1},
            where=(DailyUsage.reserved + DailyUsage.committed < daily_limit),
        )

    result = await session.execute(stmt.returning(DailyUsage.id))
    if result.scalar_one_or_none() is None:
        raise QuotaExceededError

    return Reservation(user_id=user_id, usage_date=usage_date)


async def commit_generation(session: AsyncSession, reservation: Reservation) -> None:
    """Convert one reserved slot into a committed generation."""
    stmt = (
        update(DailyUsage)
        .where(
            DailyUsage.user_id == reservation.user_id,
            DailyUsage.usage_date == reservation.usage_date,
            DailyUsage.reserved > 0,
        )
        .values(
            reserved=DailyUsage.reserved - 1,
            committed=DailyUsage.committed + 1,
        )
    )
    result = await session.execute(stmt)
    if result.rowcount != 1:
        raise RuntimeError("generation reservation is missing or already settled")


async def release_generation(session: AsyncSession, reservation: Reservation) -> None:
    """Release one reservation after a failed/cancelled generation."""
    stmt = (
        update(DailyUsage)
        .where(
            DailyUsage.user_id == reservation.user_id,
            DailyUsage.usage_date == reservation.usage_date,
            DailyUsage.reserved > 0,
        )
        .values(reserved=DailyUsage.reserved - 1)
    )
    result = await session.execute(stmt)
    if result.rowcount != 1:
        raise RuntimeError("generation reservation is missing or already released")


async def get_usage(
    session: AsyncSession,
    *,
    user_id: UUID,
    usage_date: date,
) -> DailyUsage | None:
    """Return today's usage record without creating one."""
    result = await session.execute(
        select(DailyUsage).where(
            DailyUsage.user_id == user_id,
            DailyUsage.usage_date == usage_date,
        )
    )
    return result.scalar_one_or_none()
