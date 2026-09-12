"""Resolve the plan and generation entitlement for a user."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.db.models import Plan, PlanCode
from gqmrmed.services.subscriptions import get_effective_subscription, get_plan


@dataclass(frozen=True, slots=True)
class Entitlement:
    plan: Plan
    daily_limit: int | None
    subscription_id: UUID | None


async def resolve_entitlement(session: AsyncSession, *, user_id: UUID) -> Entitlement:
    """Return the effective paid plan, or FREE when no valid subscription exists."""
    subscription = await get_effective_subscription(session, user_id=user_id)
    if subscription is not None:
        plan = (
            await session.execute(
                select(Plan).where(Plan.id == subscription.plan_id, Plan.is_active.is_(True))
            )
        ).scalar_one_or_none()
        if plan is not None:
            return Entitlement(
                plan=plan,
                daily_limit=plan.daily_limit,
                subscription_id=subscription.id,
            )

    free_plan = await get_plan(session, PlanCode.FREE)
    if free_plan is None:
        raise RuntimeError("free_plan_not_configured")
    return Entitlement(plan=free_plan, daily_limit=free_plan.daily_limit, subscription_id=None)
