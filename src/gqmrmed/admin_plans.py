"""Private operator controls for plan configuration and activation-code lifecycle."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.admin import require_admin
from gqmrmed.db.models import ActivationCode, ActivationCodeStatus, Plan, PlanCode
from gqmrmed.db.session import get_session

router = APIRouter(prefix="/admin", tags=["admin"])


class PlanUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    price: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=1, max_length=8)
    stars_price: int | None = Field(default=None, gt=0)
    duration_days: int | None = Field(default=None, gt=0)
    daily_limit: int | None = Field(default=None, gt=0)
    is_active: bool | None = None


@router.get("/plans", dependencies=[Depends(require_admin)])
async def list_plans(
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:  # noqa: B008
    """Return the commercial plan configuration without private user data."""
    result = await session.execute(select(Plan).order_by(Plan.code.asc()))
    return [
        {
            "id": str(plan.id),
            "code": plan.code,
            "name": plan.name,
            "price": str(plan.price),
            "currency": plan.currency,
            "stars_price": plan.stars_price,
            "duration_days": plan.duration_days,
            "daily_limit": plan.daily_limit,
            "is_active": plan.is_active,
        }
        for plan in result.scalars()
    ]


@router.patch("/plans/{plan_code}", dependencies=[Depends(require_admin)])
async def update_plan(
    plan_code: str,
    request: PlanUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:  # noqa: B008
    """Update commercial settings while preserving the stable plan code."""
    normalized = plan_code.strip().upper()
    async with session.begin():
        plan = (
            await session.execute(select(Plan).where(Plan.code == normalized).with_for_update())
        ).scalar_one_or_none()
        if plan is None:
            raise HTTPException(status_code=404, detail="plan_not_found")
        if normalized == PlanCode.FREE.value:
            if request.stars_price is not None or request.duration_days is not None or request.daily_limit is not None:
                raise HTTPException(status_code=400, detail="free_plan_fields_are_fixed")
        if request.name is not None:
            plan.name = request.name.strip()
        if request.price is not None:
            plan.price = request.price
        if request.currency is not None:
            plan.currency = request.currency.upper()
        if request.stars_price is not None:
            plan.stars_price = request.stars_price
        if request.duration_days is not None:
            plan.duration_days = request.duration_days
        if request.daily_limit is not None:
            plan.daily_limit = request.daily_limit
        if request.is_active is not None:
            if normalized == PlanCode.FREE.value and not request.is_active:
                raise HTTPException(status_code=400, detail="free_plan_must_remain_active")
            plan.is_active = request.is_active
    return {
        "id": str(plan.id),
        "code": plan.code,
        "name": plan.name,
        "price": str(plan.price),
        "currency": plan.currency,
        "stars_price": plan.stars_price,
        "duration_days": plan.duration_days,
        "daily_limit": plan.daily_limit,
        "is_active": plan.is_active,
    }


@router.get("/activation-codes", dependencies=[Depends(require_admin)])
async def list_activation_codes(
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:  # noqa: B008
    """List code metadata only; never expose hashes or plaintext activation codes."""
    result = await session.execute(
        select(ActivationCode, Plan.code)
        .join(Plan, Plan.id == ActivationCode.plan_id)
        .order_by(ActivationCode.created_at.desc())
        .limit(200)
    )
    return [
        {
            "id": str(code.id),
            "plan": plan_code,
            "duration_days": code.duration_days,
            "status": code.status,
            "created_at": code.created_at.isoformat(),
            "expires_at": code.expires_at.isoformat() if code.expires_at else None,
            "activated_at": code.activated_at.isoformat() if code.activated_at else None,
        }
        for code, plan_code in result.all()
    ]


@router.post("/activation-codes/{code_id}/revoke", dependencies=[Depends(require_admin)])
async def revoke_activation_code(
    code_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:  # noqa: B008
    """Revoke an unused activation code; activated codes cannot be retroactively revoked here."""
    async with session.begin():
        code = await session.get(ActivationCode, code_id, with_for_update=True)
        if code is None:
            raise HTTPException(status_code=404, detail="activation_code_not_found")
        if code.status != ActivationCodeStatus.UNUSED.value:
            raise HTTPException(status_code=409, detail="activation_code_not_unused")
        code.status = ActivationCodeStatus.REVOKED.value
    return {"id": str(code.id), "status": code.status}
