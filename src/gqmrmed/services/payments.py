"""Payment lifecycle helpers for manual and provider-backed payment flows."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.db.models import Payment, PaymentStatus, Plan, PlanCode, Subscription, SubscriptionStatus


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
    """Create an idempotent pending payment record for a paid plan."""
    if plan.code == PlanCode.FREE or amount < 0 or amount != Decimal(plan.price):
        raise ValueError("invalid_payment_amount")
    if not currency.strip():
        raise ValueError("invalid_payment_currency")
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


async def _activate_paid_subscription(
    session: AsyncSession,
    *,
    payment: Payment,
    plan: Plan,
) -> Subscription:
    """Create the subscription granted by a newly approved payment."""
    if plan.code == PlanCode.FREE or plan.duration_days is None or plan.duration_days <= 0:
        raise ValueError("plan_not_paid_or_invalid_duration")
    now = datetime.now(UTC)
    result = await session.execute(
        select(Subscription)
        .where(
            Subscription.user_id == payment.user_id,
            Subscription.status == SubscriptionStatus.ACTIVE.value,
            Subscription.expires_at.is_not(None),
            Subscription.expires_at > now,
        )
        .order_by(Subscription.expires_at.desc())
        .limit(1)
        .with_for_update()
    )
    existing = result.scalar_one_or_none()
    start = now if existing is None or existing.expires_at is None else existing.expires_at
    subscription = Subscription(
        user_id=payment.user_id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE.value,
        starts_at=start,
        expires_at=start + timedelta(days=plan.duration_days),
        activated_at=now,
    )
    session.add(subscription)
    await session.flush()
    payment.subscription_id = subscription.id
    return subscription


async def set_payment_status(
    session: AsyncSession,
    *,
    payment_id: UUID,
    status: PaymentStatus,
    approved_by: UUID | None = None,
) -> Payment:
    """Transition a payment under a row lock and grant/revoke its paid access."""
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
    if status == PaymentStatus.APPROVED and current != PaymentStatus.APPROVED:
        plan = (
            await session.execute(
                select(Plan).where(Plan.id == payment.plan_id, Plan.is_active.is_(True))
            )
        ).scalar_one_or_none()
        if plan is None:
            raise ValueError("plan_unavailable")
        await _activate_paid_subscription(session, payment=payment, plan=plan)
    elif status == PaymentStatus.REFUNDED and payment.subscription_id is not None:
        subscription = (
            await session.execute(
                select(Subscription)
                .where(Subscription.id == payment.subscription_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if subscription is not None and subscription.status == SubscriptionStatus.ACTIVE.value:
            subscription.status = SubscriptionStatus.CANCELLED.value
    payment.status = status.value
    if status == PaymentStatus.APPROVED:
        payment.approved_by = approved_by
    await session.flush()
    return payment
