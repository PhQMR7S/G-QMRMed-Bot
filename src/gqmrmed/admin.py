"""Private admin HTTP API; protect it with a strong ADMIN_SECRET."""

from decimal import Decimal
from secrets import compare_digest
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.config import get_settings
from gqmrmed.db.models import ActivationCode, Payment, PaymentStatus, Plan, User
from gqmrmed.db.session import get_session
from gqmrmed.services.activation import create_activation_code
from gqmrmed.services.payments import set_payment_status

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()


async def require_admin(x_admin_secret: str | None = Header(default=None)) -> None:
    """Require constant-time comparison against the configured admin secret."""
    configured = settings.admin_secret
    if not configured or not x_admin_secret or not compare_digest(x_admin_secret, configured):
        raise HTTPException(status_code=401, detail="unauthorized")


class CodeRequest(BaseModel):
    plan: str = Field(min_length=1, max_length=16)
    duration_days: int = Field(gt=0, le=3650)
    count: int = Field(default=1, ge=1, le=100)


class PaymentStatusRequest(BaseModel):
    status: PaymentStatus


@router.get("/overview", dependencies=[Depends(require_admin)])
async def overview(session: AsyncSession = Depends(get_session)) -> dict[str, int]:  # noqa: B008
    """Return small operational counters without exposing private user data."""
    users = await session.scalar(select(func.count()).select_from(User))
    active_plans = await session.scalar(
        select(func.count()).select_from(Plan).where(Plan.is_active.is_(True))
    )
    pending_payments = await session.scalar(
        select(func.count())
        .select_from(Payment)
        .where(Payment.status == PaymentStatus.PENDING.value)
    )
    unused_codes = await session.scalar(
        select(func.count()).select_from(ActivationCode).where(ActivationCode.status == "UNUSED")
    )
    return {
        "users": users or 0,
        "active_plans": active_plans or 0,
        "pending_payments": pending_payments or 0,
        "unused_codes": unused_codes or 0,
    }


@router.post("/activation-codes", dependencies=[Depends(require_admin)])
async def issue_codes(  # noqa: B008
    request: CodeRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, list[str]]:
    """Issue plaintext activation codes; plaintext is returned only in this response."""
    codes: list[str] = []
    async with session.begin():
        plan = (
            await session.execute(
                select(Plan).where(
                    Plan.code == request.plan.upper(),
                    Plan.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if plan is None:
            raise HTTPException(status_code=404, detail="plan_not_found")
        for _ in range(request.count):
            _, plaintext = await create_activation_code(
                session,
                plan=plan,
                duration_days=request.duration_days,
            )
            codes.append(plaintext)
    return {"codes": codes}


@router.post("/payments/{payment_id}", dependencies=[Depends(require_admin)])
async def update_payment(  # noqa: B008
    payment_id: UUID,
    request: PaymentStatusRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Approve, reject, or refund a payment under a database row lock."""
    try:
        async with session.begin():
            payment = await set_payment_status(
                session,
                payment_id=payment_id,
                status=request.status,
            )
    except ValueError as exc:
        detail = str(exc)
        status = 404 if detail == "payment_not_found" else 409
        raise HTTPException(status_code=status, detail=detail) from exc
    return {"payment_id": str(payment.id), "status": payment.status}


@router.get("/payments", dependencies=[Depends(require_admin)])
async def list_pending_payments(  # noqa: B008
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, str]]:
    """List pending payments for the private admin workflow."""
    result = await session.execute(
        select(Payment)
        .where(Payment.status == PaymentStatus.PENDING.value)
        .order_by(Payment.created_at.asc())
        .limit(100)
    )
    return [
        {
            "id": str(payment.id),
            "user_id": str(payment.user_id),
            "plan_id": str(payment.plan_id),
            "provider": payment.provider,
            "transaction_id": payment.transaction_id or "",
            "amount": str(Decimal(payment.amount)),
            "currency": payment.currency,
            "status": payment.status,
        }
        for payment in result.scalars()
    ]
