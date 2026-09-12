"""Subscription resolution and activation-code business rules."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.db.models import (
    ActivationCode,
    ActivationCodeStatus,
    Plan,
    PlanCode,
    Subscription,
    SubscriptionStatus,
)


def normalize_activation_code(code: str) -> str:
    """Normalize user-entered activation codes before hashing."""
    return "".join(code.upper().split())


def hash_activation_code(code: str) -> str:
    """Return a non-reversible SHA-256 representation of a code."""
    normalized = normalize_activation_code(code)
    return sha256(normalized.encode("utf-8")).hexdigest()


async def get_plan(
    session: AsyncSession,
    code: PlanCode,
) -> Plan | None:
    """Return an active plan by stable public code."""
    result = await session.execute(
        select(Plan).where(Plan.code == code.value, Plan.is_active.is_(True))
    )
    return result.scalar_one_or_none()


async def get_effective_subscription(
    session: AsyncSession,
    *,
    user_id: UUID,
) -> Subscription | None:
    """Return the latest currently active, non-expired subscription."""
    now = datetime.now(UTC)
    result = await session.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE.value,
            Subscription.starts_at.is_not(None),
            Subscription.starts_at <= now,
            Subscription.expires_at.is_not(None),
            Subscription.expires_at > now,
        )
        .order_by(Subscription.expires_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def activate_code(
    session: AsyncSession,
    *,
    user_id: UUID,
    raw_code: str,
) -> Subscription:
    """Atomically consume an unused activation code and create its subscription."""
    code_hash = hash_activation_code(raw_code)
    result = await session.execute(
        select(ActivationCode)
        .where(ActivationCode.code_hash == code_hash)
        .with_for_update()
    )
    code = result.scalar_one_or_none()
    now = datetime.now(UTC)
    if code is None or code.status != ActivationCodeStatus.UNUSED.value:
        raise ValueError("invalid_or_used_activation_code")
    if code.expires_at is not None and code.expires_at <= now:
        code.status = ActivationCodeStatus.EXPIRED.value
        raise ValueError("activation_code_expired")

    plan = (
        await session.execute(select(Plan).where(Plan.id == code.plan_id, Plan.is_active.is_(True)))
    ).scalar_one_or_none()
    if plan is None:
        raise ValueError("plan_unavailable")

    existing = await get_effective_subscription(session, user_id=user_id)
    start = now
    if existing is not None and existing.expires_at is not None:
        start = max(now, existing.expires_at)

    duration = code.duration_days if code.duration_days > 0 else plan.duration_days
    if duration is None or duration <= 0:
        raise ValueError("invalid_subscription_duration")

    subscription = Subscription(
        user_id=user_id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE.value,
        starts_at=start,
        expires_at=start + timedelta(days=duration),
        activated_at=now,
    )
    session.add(subscription)
    code.status = ActivationCodeStatus.ACTIVATED.value
    code.activated_by = user_id
    code.activated_at = now
    await session.flush()
    return subscription
