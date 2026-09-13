from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from gqmrmed.db.models import PaymentStatus, PlanCode, SubscriptionStatus
from gqmrmed.services.payments import create_payment, set_payment_status


class FakeResult:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object:
        return self.value


class FakeSession:
    def __init__(self, *results: object) -> None:
        self.results = list(results)
        self.calls = 0
        self.added: list[object] = []

    async def execute(self, _statement: object) -> FakeResult:
        value = self.results[self.calls]
        self.calls += 1
        return FakeResult(value)

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        return None


def make_plan(code: PlanCode = PlanCode.PLUS) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        code=code,
        price=Decimal("5.00") if code == PlanCode.PLUS else Decimal("0.00"),
        duration_days=30 if code == PlanCode.PLUS else None,
        is_active=True,
    )


def make_payment(plan: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        plan_id=plan.id,
        subscription_id=None,
        provider="manual",
        transaction_id=None,
        amount=Decimal("5.00"),
        currency="USD",
        status=PaymentStatus.PENDING.value,
        approved_by=None,
    )


@pytest.mark.asyncio
async def test_create_payment_rejects_free_plan_and_wrong_amount() -> None:
    free = make_plan(PlanCode.FREE)
    with pytest.raises(ValueError, match="invalid_payment_amount"):
        await create_payment(
            FakeSession(),
            user_id=uuid4(),
            plan=free,
            provider="manual",
            transaction_id=None,
            amount=Decimal("0.00"),
        )

    paid = make_plan()
    with pytest.raises(ValueError, match="invalid_payment_amount"):
        await create_payment(
            FakeSession(),
            user_id=uuid4(),
            plan=paid,
            provider="manual",
            transaction_id=None,
            amount=Decimal("4.99"),
        )


@pytest.mark.asyncio
async def test_create_payment_returns_existing_transaction() -> None:
    plan = make_plan()
    existing = make_payment(plan)
    session = FakeSession(existing)

    result = await create_payment(
        session,
        user_id=existing.user_id,
        plan=plan,
        provider="MANUAL",
        transaction_id=" tx-123 ",
        amount=Decimal("5.00"),
    )

    assert result is existing
    assert session.calls == 1


@pytest.mark.asyncio
async def test_approval_grants_subscription_and_is_replay_safe() -> None:
    plan = make_plan()
    payment = make_payment(plan)
    user = SimpleNamespace(id=payment.user_id)
    session = FakeSession(payment, plan, user, None)

    result = await set_payment_status(
        session,
        payment_id=payment.id,
        status=PaymentStatus.APPROVED,
    )

    assert result is payment
    assert payment.status == PaymentStatus.APPROVED.value
    assert payment.subscription_id is not None
    assert len(session.added) == 1
    assert session.calls == 4

    replay_session = FakeSession(payment)
    replay = await set_payment_status(
        replay_session,
        payment_id=payment.id,
        status=PaymentStatus.APPROVED,
    )
    assert replay is payment
    assert replay_session.calls == 1


@pytest.mark.asyncio
async def test_refund_cancels_only_linked_active_subscription() -> None:
    plan = make_plan()
    payment = make_payment(plan)
    subscription = SimpleNamespace(
        id=uuid4(),
        user_id=payment.user_id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE.value,
    )
    payment.status = PaymentStatus.APPROVED.value
    payment.subscription_id = subscription.id
    session = FakeSession(payment, subscription)

    result = await set_payment_status(
        session,
        payment_id=payment.id,
        status=PaymentStatus.REFUNDED,
    )

    assert result is payment
    assert payment.status == PaymentStatus.REFUNDED.value
    assert subscription.status == SubscriptionStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_invalid_terminal_transition_is_rejected() -> None:
    plan = make_plan()
    payment = make_payment(plan)
    payment.status = PaymentStatus.REJECTED.value
    session = FakeSession(payment)

    with pytest.raises(ValueError, match="invalid_payment_transition"):
        await set_payment_status(
            session,
            payment_id=payment.id,
            status=PaymentStatus.APPROVED,
        )
