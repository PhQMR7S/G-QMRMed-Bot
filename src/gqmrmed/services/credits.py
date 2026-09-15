"""Purchased design-credit packs and balance operations."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.db.models import BillingLedger, CreditPack, User


# Telegram currently assigns a $0.013 reward value per earned Star. Actual
# user acquisition cost can vary by region and platform.
CREDIT_PACK_CATALOG: tuple[tuple[str, int, int], ...] = (
    ("DESIGN_5", 5, 60),
    ("DESIGN_12", 12, 120),
    ("DESIGN_20", 20, 180),
)


async def get_credit_pack(session: AsyncSession, *, code: str) -> CreditPack | None:
    result = await session.execute(
        select(CreditPack).where(CreditPack.code == code, CreditPack.is_active.is_(True))
    )
    return result.scalar_one_or_none()


async def grant_design_credits(
    session: AsyncSession,
    *,
    user_id: UUID,
    credits: int,
    payment_id: UUID | None = None,
    pack: CreditPack | None = None,
    stars_amount: int | None = None,
) -> User:
    if credits <= 0:
        raise ValueError("invalid_credit_amount")
    user = (
        await session.execute(select(User).where(User.id == user_id).with_for_update())
    ).scalar_one_or_none()
    if user is None:
        raise ValueError("user_not_found")
    user.design_credits += credits
    session.add(
        BillingLedger(
            event_type="DESIGN_CREDITS_GRANTED",
            user_id=user.id,
            payment_id=payment_id,
            plan_id=None,
            amount=Decimal(stars_amount) if stars_amount is not None else None,
            currency="XTR" if stars_amount is not None else None,
            stars_amount=stars_amount,
            ledger_metadata={
                "credit_pack": pack.code if pack is not None else None,
                "credits": credits,
            },
        )
    )
    await session.flush()
    return user
