"""Subscription resolution and activation-code business rules."""

from datetime import datetime, timedelta, UTC
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.db.models import (
    ActivationCode,
    ActivationCodeStatus,
    Plan,
    PlanCode,
    Subscription,
    SubscriptionStatus,
    User,
)


def normalize_activation_code(code: str) -> str:
    """Normalize user-entered activation codes before hashing."""
    return "".join(code.upper().split())


def hash_activation_code(code: str) -> str:
    """Return a non-reversible SHA-256 representation of a code."""
    normalized = normalize_activation_code(code)
    return sha256(normalized.encode("utf-8")).hexdigest()


async def get_plan(session: AsyncSession, code: PlanCode) -> Plan | None:
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
    """Resolve one server-authoritative entitlement using UTC and deterministic precedence."""
    now = datetime.now(UTC)
    rank = case((Plan.code == PlanCode.PRO.value, 3), (Plan.code == PlanCode.PLUS.value, 2), else_=1)
    result = await session.execute(
        select(Subscription)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE.value,
            Subscription.starts_at.is_not(None),
            Subscription.starts_at <= now,
            Subscription.expires_at.is_not(None),
            Subscription.expires_at > now,
            Plan.is_active.is_(True),
        )
        .order_by(rank.desc(), Subscription.expires_at.desc(), Subscription.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def grant_paid_subscription(
    session: AsyncSession,
    *,
    user_id: UUID,
    plan: Plan,
    duration_days: int | None = None,
) -> Subscription:
    """Grant a paid entitlement with explicit same-plan, upgrade and downgrade semantics.

    - Same plan: extends from max(now, current expiry).
    - Upgrade: starts immediately, cancels the weaker active entitlement, and converts
      its remaining paid value into additional days of the stronger plan.
    - Downgrade: queues after the strongest current entitlement so access is never reduced.
    """
    if plan.code == PlanCode.FREE.value:
        raise ValueError("cannot_grant_free_plan")
    duration = duration_days if duration_days is not None else plan.duration_days
    if duration is None or duration <= 0:
        raise ValueError("invalid_subscription_duration")

    user_result = await session.execute(select(User).where(User.id == user_id).with_for_update())
    if user_result.scalar_one_or_none() is None:
        raise ValueError("user_not_found")

    now = datetime.now(UTC)
    active_result = await session.execute(
        select(Subscription, Plan)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE.value,
            Subscription.starts_at.is_not(None),
            Subscription.starts_at <= now,
            Subscription.expires_at.is_not(None),
            Subscription.expires_at > now,
            Plan.is_active.is_(True),
        )
        .order_by(Subscription.expires_at.desc())
        .with_for_update()
    )
    active_rows = active_result.all()
    current = active_rows[0] if active_rows else None

    if current is None:
        start = now
        expires = start + timedelta(days=duration)
    else:
        current_subscription, current_plan = current
        if current_plan.code == plan.code:
            start = current_subscription.expires_at or now
            expires = start + timedelta(days=duration)
        else:
            rank = {PlanCode.FREE.value: 1, PlanCode.PLUS.value: 2, PlanCode.PRO.value: 3}
            if rank.get(plan.code, 0) > rank.get(current_plan.code, 0):
                remaining_seconds = max(
                    0.0, (current_subscription.expires_at - now).total_seconds()
                )
                old_total_days = current_plan.duration_days or 1
                old_price = Decimal(current_plan.price)
                new_price = Decimal(plan.price)
                credit_value = old_price * Decimal(remaining_seconds) / Decimal(old_total_days * 86400)
                credit_days = float(credit_value / new_price * Decimal(duration)) if new_price else 0.0
                start = now
                expires = start + timedelta(days=duration + max(0.0, credit_days))
                for subscription, _ in active_rows:
                    subscription.status = SubscriptionStatus.CANCELLED.value
            else:
                start = max(now, current_subscription.expires_at)
                expires = start + timedelta(days=duration)

    subscription = Subscription(
        user_id=user_id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE.value,
        starts_at=start,
        expires_at=expires,
        activated_at=now,
    )
    session.add(subscription)
    await session.flush()
    return subscription


async def activate_code(
    session: AsyncSession,
    *,
    user_id: UUID,
    raw_code: str,
) -> Subscription:
    """Atomically consume an unused activation code and grant its entitlement."""
    code_hash = hash_activation_code(raw_code)
    user_result = await session.execute(select(User.id).where(User.id == user_id).with_for_update())
    if user_result.scalar_one_or_none() is None:
        raise ValueError("user_not_found")

    result = await session.execute(
        select(ActivationCode).where(ActivationCode.code_hash == code_hash).with_for_update()
    )
    code = result.scalar_one_or_none()
    now = datetime.now(UTC)
    if code is None or code.status != ActivationCodeStatus.UNUSED.value:
        raise ValueError("invalid_or_used_activation_code")
    if code.expires_at is not None and code.expires_at <= now:
        code.status = ActivationCodeStatus.EXPIRED.value
        raise ValueError("activation_code_expired")

    plan = (
        await session.execute(
            select(Plan).where(Plan.id == code.plan_id, Plan.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if plan is None:
        raise ValueError("plan_unavailable")

    duration = code.duration_days if code.duration_days > 0 else plan.duration_days
    if duration is None or duration <= 0:
        raise ValueError("invalid_subscription_duration")

    subscription = await grant_paid_subscription(
        session,
        user_id=user_id,
        plan=plan,
        duration_days=duration,
    )
    code.status = ActivationCodeStatus.ACTIVATED.value
    code.activated_by = user_id
    code.activated_at = now
    await session.flush()
    return subscription
