from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from gqmrmed.db.models import PaymentStatus, PlanCode, SubscriptionStatus
from gqmrmed.services.payments import create_payment, create_stars_payment, set_payment_status


class FakeResult:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object:
        return self.value

    def all(self) -> list[object]:
        return self.value if isinstance(self.value, list) else []


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
        code=code.value,
        price=Decimal("15.00") if code == PlanCode.PLUS else Decimal("50.00"),
        stars_price=1200 if code == PlanCode.PLUS else 3850,
        duration_days=30 if code == PlanCode.PLUS else 90,
        daily_limit=2 if code == PlanCode.PLUS else 3,
        is_active=True,
    )


def make_payment(plan: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        plan_id=plan.id,
        credit_pack_id=None,
        subscription_id=None,
        activation_code_id=None,
        provider="manual",
        transaction_id=None,
        invoice_payload=None,
        stars_amount=None,
        amount=Decimal("15.00"),
        currency="USD",
        status=PaymentStatus.PENDING.value,
        approved_by=None,
    )


@pytest.mark.asyncio
async def test_create_payment_rejects_free_plan_and_wrong_amount() -> None:
    free = make_plan(PlanCode.FREE)
    free.price = Decimal("0.00")
    free.stars_price = None
    free.duration_days = None
    free.daily_limit = 1
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
            amount=Decimal("14.99"),
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
        amount=Decimal("15.00"),
    )

    assert result is existing
    assert session.calls == 1


@pytest.mark.asyncio
async def test_create_stars_payment_uses_canonical_star_price() -> None:
    plan = make_plan()
    session = FakeSession(None)
    result = await create_stars_payment(
        session,
        user_id=uuid4(),
        plan=plan,
        invoice_payload="gqmrmed:stars:PLUS:test",
    )
    assert result.provider == "telegram_stars"
    assert result.currency == "XTR"
    assert result.stars_amount == 1200
    assert result.amount == Decimal("1200")
    assert len(session.added) == 2


@pytest.mark.asyncio
async def test_approval_grants_subscription_and_is_replay_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = make_plan()
    payment = make_payment(plan)
    subscription = SimpleNamespace(
        id=uuid4(),
        user_id=payment.user_id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE.value,
    )
    grant_calls: list[tuple[object, object, object]] = []

    async def fake_grant_paid_subscription(
        session: FakeSession, *, user_id: object, plan: object
    ) -> SimpleNamespace:
        grant_calls.append((session, user_id, plan))
        session.add(subscription)
        return subscription

    monkeypatch.setattr(
        "gqmrmed.services.payments.grant_paid_subscription",
        fake_grant_paid_subscription,
    )

    session = FakeSession(payment, plan)
    result = await set_payment_status(
        session,
        payment_id=payment.id,
        status=PaymentStatus.APPROVED,
    )

    assert result is payment
    assert payment.status == PaymentStatus.APPROVED.value
    assert payment.subscription_id == subscription.id
    assert len(grant_calls) == 1
    assert grant_calls[0][1:] == (payment.user_id, plan)
    assert len(session.added) == 2
    assert session.calls == 2

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
    session = FakeSession(payment, plan, subscription)

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
