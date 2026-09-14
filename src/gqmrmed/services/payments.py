"""Payment lifecycle helpers for Telegram Stars subscriptions and design credits."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.db.models import BillingLedger, CreditPack, Payment, PaymentStatus, Plan, PlanCode, Subscription, SubscriptionStatus, User
from gqmrmed.services.credits import grant_design_credits
from gqmrmed.services.subscriptions import grant_paid_subscription


def _plan_code(plan: Plan) -> str:
    value = plan.code
    return value.value if isinstance(value, PlanCode) else str(value)


async def _ledger(session: AsyncSession, *, event_type: str, payment: Payment | None = None, subscription: Subscription | None = None, plan: Plan | None = None, user_id: UUID | None = None, amount: Decimal | None = None, currency: str | None = None, stars_amount: int | None = None, metadata: dict[str, object] | None = None) -> None:
    session.add(BillingLedger(event_type=event_type, user_id=user_id or (payment.user_id if payment is not None else None), payment_id=payment.id if payment is not None else None, subscription_id=subscription.id if subscription is not None else None, plan_id=plan.id if plan is not None else None, amount=amount, currency=currency, stars_amount=stars_amount, ledger_metadata=metadata))


async def create_payment(session: AsyncSession, *, user_id: UUID, plan: Plan | None, provider: str, transaction_id: str | None, amount: Decimal, currency: str = "USD", invoice_payload: str | None = None, stars_amount: int | None = None, credit_pack: CreditPack | None = None) -> Payment:
    provider = provider.strip().lower()
    if amount < 0 or (plan is None and credit_pack is None) or (plan is not None and credit_pack is not None):
        raise ValueError("invalid_payment_amount")
    if provider == "telegram_stars":
        if plan is None:
            assert credit_pack is not None
            expected: int | None = credit_pack.stars_price
        else:
            expected = plan.stars_price
        if currency.upper() != "XTR" or stars_amount != expected:
            raise ValueError("invalid_stars_price")
    elif plan is None or amount != Decimal(plan.price):
        raise ValueError("invalid_payment_amount")
    if not currency.strip():
        raise ValueError("invalid_payment_currency")

    transaction_id = transaction_id.strip() if transaction_id else None
    invoice_payload = invoice_payload.strip() if invoice_payload else None
    if transaction_id:
        existing = (await session.execute(select(Payment).where(Payment.provider == provider, Payment.transaction_id == transaction_id))).scalar_one_or_none()
        if existing is not None:
            return existing
    if invoice_payload:
        existing = (await session.execute(select(Payment).where(Payment.invoice_payload == invoice_payload))).scalar_one_or_none()
        if existing is not None:
            return existing

    payment = Payment(
        user_id=user_id,
        plan_id=plan.id if plan is not None else None,
        credit_pack_id=credit_pack.id if credit_pack is not None else None,
        transaction_id=transaction_id,
        invoice_payload=invoice_payload,
        stars_amount=stars_amount,
        provider=provider,
        amount=amount,
        currency=currency.upper(),
        status=PaymentStatus.PENDING.value,
    )
    session.add(payment)
    await session.flush()
    return payment


async def create_stars_payment(session: AsyncSession, *, user_id: UUID, plan: Plan, invoice_payload: str) -> Payment:
    if plan.stars_price is None:
        raise ValueError("plan_has_no_stars_price")
    return await create_payment(
        session,
        user_id=user_id,
        plan=plan,
        provider="telegram_stars",
        transaction_id=None,
        amount=Decimal("0"),
        currency="XTR",
        invoice_payload=invoice_payload,
        stars_amount=plan.stars_price,
    )


async def create_stars_credit_payment(session: AsyncSession, *, user_id: UUID, credit_pack: CreditPack, invoice_payload: str) -> Payment:
    return await create_payment(
        session,
        user_id=user_id,
        plan=None,
        credit_pack=credit_pack,
        provider="telegram_stars",
        transaction_id=None,
        amount=Decimal("0"),
        currency="XTR",
        invoice_payload=invoice_payload,
        stars_amount=credit_pack.stars_price,
    )


async def get_payment_by_invoice_payload(session: AsyncSession, *, invoice_payload: str) -> Payment | None:
    return (await session.execute(select(Payment).where(Payment.invoice_payload == invoice_payload))).scalar_one_or_none()


async def finalize_stars_payment(session: AsyncSession, *, invoice_payload: str, transaction_id: str, telegram_user_id: int, total_amount: int) -> Payment:
    payment = (await session.execute(select(Payment).where(Payment.invoice_payload == invoice_payload).with_for_update())).scalar_one_or_none()
    if payment is None:
        raise ValueError("payment_not_found")
    if payment.status == PaymentStatus.APPROVED.value:
        return payment
    if payment.provider != "telegram_stars" or payment.status != PaymentStatus.PENDING.value:
        raise ValueError("payment_not_pending")
    if payment.stars_amount != total_amount or payment.currency != "XTR":
        raise ValueError("payment_amount_mismatch")
    user = await session.get(User, payment.user_id, with_for_update=True)
    if user is None or user.telegram_id != telegram_user_id or not user.is_active:
        raise ValueError("payment_user_mismatch")

    if payment.credit_pack_id is not None:
        pack = await session.get(CreditPack, payment.credit_pack_id, with_for_update=True)
        if pack is None or not pack.is_active or pack.stars_price != total_amount:
            raise ValueError("credit_pack_unavailable_or_price_changed")
        await grant_design_credits(session, user_id=user.id, credit_pack=pack, payment=payment)
        payment.status = PaymentStatus.APPROVED.value
        payment.transaction_id = transaction_id
        await _ledger(
            session,
            event_type="CREDIT_PURCHASE_APPROVED",
            payment=payment,
            user_id=user.id,
            stars_amount=total_amount,
            currency="XTR",
            metadata={"credit_pack": pack.code, "credits": pack.credits},
        )
        await session.flush()
        return payment

    if payment.plan_id is None:
        raise ValueError("payment_target_missing")
    plan = await session.get(Plan, payment.plan_id, with_for_update=True)
    if plan is None or not plan.is_active or plan.stars_price != total_amount:
        raise ValueError("plan_unavailable_or_price_changed")
    subscription = await grant_paid_subscription(session, user_id=user.id, plan=plan)
    payment.status = PaymentStatus.APPROVED.value
    payment.transaction_id = transaction_id
    payment.subscription_id = subscription.id
    await _ledger(
        session,
        event_type="PAYMENT_APPROVED",
        payment=payment,
        subscription=subscription,
        plan=plan,
        user_id=user.id,
        stars_amount=total_amount,
        currency="XTR",
        metadata={"plan": _plan_code(plan)},
    )
    await session.flush()
    return payment


async def set_payment_status(session: AsyncSession, *, payment_id: UUID, status: PaymentStatus, approved_by: UUID | None = None) -> Payment:
    payment = await session.get(Payment, payment_id, with_for_update=True)
    if payment is None:
        raise ValueError("payment_not_found")
    if payment.provider == "telegram_stars" and status == PaymentStatus.APPROVED:
        raise ValueError("stars_must_be_settled_from_successful_payment")
    payment.status = status.value
    payment.approved_by = approved_by
    await session.flush()
    await _ledger(
        session,
        event_type=f"PAYMENT_{status.value}",
        payment=payment,
        user_id=payment.user_id,
        amount=payment.amount,
        currency=payment.currency,
        stars_amount=payment.stars_amount,
    )
    return payment
