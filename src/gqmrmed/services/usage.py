"""Atomic daily quota and purchased-credit reservation/settlement."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.db.models import DailyUsage, UsageReservation, UsageReservationSource, UsageReservationStatus, User


@dataclass(frozen=True, slots=True)
class Reservation:
    id: UUID
    user_id: UUID
    job_id: UUID
    usage_date: date
    source: str


class QuotaExceededError(Exception):
    """Raised when daily quota and purchased credits are exhausted."""


async def reserve_generation(
    session: AsyncSession,
    *,
    user_id: UUID,
    job_id: UUID,
    usage_date: date,
    daily_limit: int | None,
) -> Reservation:
    """Reserve one generation from daily quota, then purchased credits."""
    if daily_limit is not None and daily_limit <= 0:
        raise QuotaExceededError

    reservation_stmt = (
        insert(UsageReservation)
        .values(
            user_id=user_id,
            job_id=job_id,
            usage_date=usage_date,
            status=UsageReservationStatus.RESERVED.value,
            source=UsageReservationSource.DAILY.value,
        )
        .on_conflict_do_nothing(index_elements=[UsageReservation.job_id])
        .returning(UsageReservation.id)
    )
    reservation_result = await session.execute(reservation_stmt)
    reservation_id = reservation_result.scalar_one_or_none()
    if reservation_id is None:
        existing = (
            await session.execute(
                select(UsageReservation).where(UsageReservation.job_id == job_id).with_for_update()
            )
        ).scalar_one_or_none()
        if existing is None:
            raise RuntimeError("usage reservation conflict without persisted ledger")
        if existing.user_id != user_id or existing.usage_date != usage_date:
            raise RuntimeError("usage reservation identity mismatch")
        return Reservation(existing.id, existing.user_id, existing.job_id, existing.usage_date, existing.source)

    if daily_limit is None:
        daily_stmt = insert(DailyUsage).values(
            user_id=user_id, usage_date=usage_date, reserved=1, committed=0
        ).on_conflict_do_update(
            index_elements=[DailyUsage.user_id, DailyUsage.usage_date],
            set_={"reserved": DailyUsage.reserved + 1},
        )
    else:
        daily_stmt = insert(DailyUsage).values(
            user_id=user_id, usage_date=usage_date, reserved=1, committed=0
        ).on_conflict_do_update(
            index_elements=[DailyUsage.user_id, DailyUsage.usage_date],
            set_={"reserved": DailyUsage.reserved + 1},
            where=(DailyUsage.reserved + DailyUsage.committed < daily_limit),
        )

    daily_result = await session.execute(daily_stmt.returning(DailyUsage.id))
    if daily_result.scalar_one_or_none() is not None:
        await session.flush()
        return Reservation(
            reservation_id, user_id, job_id, usage_date, UsageReservationSource.DAILY.value
        )

    credit_result = await session.execute(
        update(User)
        .where(User.id == user_id, User.design_credits > 0)
        .values(design_credits=User.design_credits - 1)
        .returning(User.id)
    )
    if credit_result.scalar_one_or_none() is None:
        await session.execute(delete(UsageReservation).where(UsageReservation.id == reservation_id))
        raise QuotaExceededError

    await session.execute(
        update(UsageReservation)
        .where(UsageReservation.id == reservation_id)
        .values(source=UsageReservationSource.CREDIT.value)
    )
    await session.flush()
    return Reservation(reservation_id, user_id, job_id, usage_date, UsageReservationSource.CREDIT.value)


async def commit_generation(session: AsyncSession, reservation: Reservation) -> None:
    """Commit a reservation exactly once."""
    ledger = (
        await session.execute(
            select(UsageReservation).where(UsageReservation.id == reservation.id).with_for_update()
        )
    ).scalar_one_or_none()
    if ledger is None or ledger.job_id != reservation.job_id:
        raise RuntimeError("generation reservation is missing")
    if ledger.status == UsageReservationStatus.COMMITTED.value:
        return
    if ledger.status != UsageReservationStatus.RESERVED.value:
        raise RuntimeError("generation reservation is already released")

    if ledger.source == UsageReservationSource.DAILY.value:
        result = await session.execute(
            update(DailyUsage)
            .where(
                DailyUsage.user_id == reservation.user_id,
                DailyUsage.usage_date == reservation.usage_date,
                DailyUsage.reserved > 0,
            )
            .values(reserved=DailyUsage.reserved - 1, committed=DailyUsage.committed + 1)
            .returning(DailyUsage.id)
        )
        if result.scalar_one_or_none() is None:
            raise RuntimeError("generation reservation counters are inconsistent")

    ledger.status = UsageReservationStatus.COMMITTED.value
    ledger.settled_at = datetime.now(UTC)
    await session.flush()


async def release_generation(session: AsyncSession, reservation: Reservation) -> None:
    """Release a reservation; purchased credits are refunded on failure."""
    ledger = (
        await session.execute(
            select(UsageReservation).where(UsageReservation.id == reservation.id).with_for_update()
        )
    ).scalar_one_or_none()
    if ledger is None or ledger.job_id != reservation.job_id:
        raise RuntimeError("generation reservation is missing")
    if ledger.status == UsageReservationStatus.RELEASED.value:
        return
    if ledger.status == UsageReservationStatus.COMMITTED.value:
        raise RuntimeError("cannot release a committed generation")

    if ledger.source == UsageReservationSource.DAILY.value:
        result = await session.execute(
            update(DailyUsage)
            .where(
                DailyUsage.user_id == reservation.user_id,
                DailyUsage.usage_date == reservation.usage_date,
                DailyUsage.reserved > 0,
            )
            .values(reserved=DailyUsage.reserved - 1)
            .returning(DailyUsage.id)
        )
        if result.scalar_one_or_none() is None:
            raise RuntimeError("generation reservation counters are inconsistent")
    else:
        result = await session.execute(
            update(User)
            .where(User.id == reservation.user_id)
            .values(design_credits=User.design_credits + 1)
            .returning(User.id)
        )
        if result.scalar_one_or_none() is None:
            raise RuntimeError("user is missing for credit refund")

    ledger.status = UsageReservationStatus.RELEASED.value
    ledger.settled_at = datetime.now(UTC)
    await session.flush()


async def get_usage(
    session: AsyncSession,
    *,
    user_id: UUID,
    usage_date: date,
) -> DailyUsage | None:
    """Return a usage record without creating one."""
    result = await session.execute(
        select(DailyUsage).where(DailyUsage.user_id == user_id, DailyUsage.usage_date == usage_date)
    )
    return result.scalar_one_or_none()
