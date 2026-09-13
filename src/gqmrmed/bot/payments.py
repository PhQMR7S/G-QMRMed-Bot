"""Telegram Stars checkout handlers for paid digital subscriptions."""

from uuid import uuid4

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Message, PreCheckoutQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.bot.service import provision_user
from gqmrmed.db.models import PaymentStatus, Plan, PlanCode, User
from gqmrmed.services.payments import create_stars_payment, finalize_stars_payment

router = Router(name="gqmrmed-payments")

TERMS_TEXT = (
    "شروط شراء اشتراك GQMRMed 🩺\n\n"
    "1) الخدمة رقمية، وجميع المشتريات داخل Telegram تتم حصراً عبر Telegram Stars (XTR).\n"
    "2) الخطة تُفعّل بعد استلام Telegram لإشعار successful_payment والتحقق منه على الخادم.\n"
    "3) حدود الاستخدام: FREE = 3 تصاميم/يوم، PLUS = 8 تصاميم/يوم، PRO = 15 تصميماً/يوم.\n"
    "4) كل طلب تصميم ناجح يستهلك وحدة واحدة فقط، حتى لو نتج عنه أكثر من صفحة.\n"
    "5) إذا فشل التوليد قبل نجاحه تُعاد وحدة الاستخدام المحجوزة.\n"
    "6) لا تعتمد على لقطة شاشة أو رسالة دفع غير ناجحة كإثبات للاشتراك.\n"
    "7) للاستفسارات ومشاكل الدفع استخدم /paysupport.\n\n"
    "بالضغط على «أوافق وأتابع» أنت تؤكد قراءة هذه الشروط والموافقة عليها."
)


def _terms_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="أوافق وأتابع شراء PLUS",
                    callback_data="stars:PLUS",
                ),
                InlineKeyboardButton(
                    text="أوافق وأتابع شراء PRO",
                    callback_data="stars:PRO",
                ),
            ]
        ]
    )


@router.message(Command("terms"))
async def terms_handler(message: Message) -> None:
    """Display the purchase terms before any Stars invoice is created."""
    await message.answer(TERMS_TEXT, reply_markup=_terms_keyboard())


@router.message(Command("paysupport"))
async def payment_support_handler(message: Message) -> None:
    """Provide the required payment support route."""
    await message.answer(
        "لدعم المدفوعات، أرسل رقم العملية/الإيصال أو تفاصيل المشكلة إلى دعم GQMRMed عبر @ID29i.\n"
        "لا ترسل مفاتيح سرية أو كلمات مرور أو بيانات بطاقات كاملة."
    )


@router.callback_query(F.data.regexp(r"^stars:(PLUS|PRO)$"))
async def stars_plan_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Create a single-chat, server-tracked Stars invoice after terms acceptance."""
    if callback.data is None or callback.message is None:
        await callback.answer("تعذر إنشاء الفاتورة.", show_alert=True)
        return
    plan_code = callback.data.split(":", 1)[1]
    async with session.begin():
        user = await provision_user(
            session,
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
            language=callback.from_user.language_code,
        )
        if not user.is_active:
            await callback.answer("الحساب غير نشط.", show_alert=True)
            return
        plan = (
            await session.execute(
                select(Plan).where(
                    Plan.code == plan_code,
                    Plan.is_active.is_(True),
                    Plan.code != PlanCode.FREE.value,
                )
            )
        ).scalar_one_or_none()
        if plan is None or plan.stars_price is None:
            await callback.answer("الخطة غير متاحة حالياً.", show_alert=True)
            return
        payload = f"gqmrmed:stars:{plan.code}:{uuid4().hex}"
        await create_stars_payment(
            session,
            user_id=user.id,
            plan=plan,
            invoice_payload=payload,
        )

    await callback.answer("تم تجهيز الفاتورة.")
    await callback.message.answer_invoice(
        title=f"GQMRMed {plan.name}",
        description=(
            f"اشتراك {plan.name}: {plan.daily_limit} تصاميم يومياً لمدة {plan.duration_days} يوماً."
        ),
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=plan.name, amount=plan.stars_price)],
    )


@router.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery, session: AsyncSession) -> None:
    """Validate the exact server-side order before Telegram completes checkout."""
    from gqmrmed.services.payments import get_payment_by_invoice_payload

    payment = await get_payment_by_invoice_payload(session, invoice_payload=query.invoice_payload)
    if (
        payment is None
        or payment.provider != "telegram_stars"
        or payment.status != PaymentStatus.PENDING.value
        or payment.stars_amount != query.total_amount
        or query.currency != "XTR"
    ):
        await query.answer(ok=False, error_message="الفاتورة غير صالحة أو انتهت صلاحيتها.")
        return

    user = await session.get(User, payment.user_id)
    if user is None or user.telegram_id != query.from_user.id:
        await query.answer(ok=False, error_message="هذه الفاتورة ليست لهذا الحساب.")
        return
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message, session: AsyncSession) -> None:
    """Settle only the verified successful_payment update and grant access once."""
    successful = message.successful_payment
    if successful is None or message.from_user is None:
        return
    try:
        async with session.begin():
            payment = await finalize_stars_payment(
                session,
                invoice_payload=successful.invoice_payload,
                transaction_id=successful.telegram_payment_charge_id,
                telegram_user_id=message.from_user.id,
                total_amount=successful.total_amount,
            )
    except ValueError:
        await message.answer(
            "تم استلام إشعار دفع غير متوافق مع الطلب. لم يتم منح الاشتراك تلقائياً؛ تواصل مع /paysupport."
        )
        return

    await message.answer(
        "تم استلام الدفع وتفعيل الاشتراك بنجاح ✅\n"
        f"رقم العملية: {payment.transaction_id}\n"
        "يمكنك الآن البدء بإرسال طلبات التصميم."
    )
