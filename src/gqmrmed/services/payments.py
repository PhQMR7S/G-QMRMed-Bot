"""Payment lifecycle helpers for manual and provider-backed payment flows."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.db.models import Payment, PaymentStatus, Plan


async def create_payment(
    session: AsyncSession,
    *,
    user_id: UUID,
    plan: Plan,
    provider: str,
    transaction_id: str | None,
    amount: Decimal,
    currency: str = "USD",
) -> Payment:
    """Create an idempotent pending payment record."""
    if amount < 0:
        raise ValueError("invalid_payment_amount")
    provider = provider.strip().lower()
    if not provider:
        raise ValueError("invalid_payment_provider")
    transaction_id = transaction_id.strip() if transaction_id else None
    if transaction_id:
        existing = (
            await session.execute(
                select(Payment).where(
                    Payment.provider == provider,
                    Payment.transaction_id == transaction_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
    payment = Payment(
        user_id=user_id,
        plan_id=plan.id,
        provider=provider,
        transaction_id=transaction_id,
        amount=amount,
        currency=currency.upper(),
        status=PaymentStatus.PENDING.value,
    )
    session.add(payment)
    await session.flush()
    return payment


async def set_payment_status(
    session: AsyncSession,
    *,
    payment_id: UUID,
    status: PaymentStatus,
    approved_by: UUID | None = None,
) -> Payment:
    """Transition a payment under a row lock and record the approving admin."""
    result = await session.execute(
        select(Payment).where(Payment.id == payment_id).with_for_update()
    )
    payment = result.scalar_one_or_none()
    if payment is None:
        raise ValueError("payment_not_found")
    current = PaymentStatus(payment.status)
    allowed = {
        PaymentStatus.PENDING: {
            PaymentStatus.APPROVED,
            PaymentStatus.REJECTED,
        },
        PaymentStatus.APPROVED: {PaymentStatus.REFUNDED},
        PaymentStatus.REJECTED: set(),
        PaymentStatus.REFUNDED: set(),
    }
    if status != current and status not in allowed[current]:
        raise ValueError("invalid_payment_transition")
    payment.status = status.value
    if status == PaymentStatus.APPROVED:
        payment.approved_by = approved_by
    await session.flush()
    return payment
