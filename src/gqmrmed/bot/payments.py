"""Telegram Stars checkout handlers for subscriptions and design-credit packs."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Message, PreCheckoutQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.bot.premium_emoji_runtime import emoji_settings
from gqmrmed.bot.service import provision_user
from gqmrmed.db.models import CreditPack, PaymentStatus, Plan, PlanCode, User
from gqmrmed.services.payments import create_stars_credit_payment, create_stars_payment, finalize_stars_payment, get_payment_by_invoice_payload

router = Router(name="gqmrmed-payments")

TERMS_TEXT = (
    "<b>شروط شراء GQMRMed</b>\n\n"
    "1) الخدمة رقمية، وجميع المشتريات داخل Telegram تتم حصراً عبر Telegram Stars (XTR).\n"
    "2) الاشتراك أو حصة التصاميم لا تُمنح إلا بعد استلام successful_payment والتحقق منه على الخادم.\n"
    "3) FREE = تصميم واحد يومياً، PLUS = تصميمان، PRO = 3 تصاميم يومياً.\n"
    "4) حصة التصميم المشتراة هي رصيد إضافي مستقل عن الاشتراك، ولا تنتهي تلقائياً.\n"
    "5) عند وجود حصة يومية متاحة تُستهلك أولاً، ثم يُستخدم رصيد التصاميم المشتراة.\n"
    "6) كل طلب تصميم ناجح يستهلك وحدة واحدة فقط. وإذا فشل التوليد قبل نجاحه تُعاد الوحدة المحجوزة.\n"
    "7) لا تعتمد على لقطة شاشة أو رسالة دفع غير ناجحة كإثبات للشراء.\n"
    "8) للدعم استخدم /paysupport.\n\n"
    "بالضغط على زر الشراء أنت تؤكد قراءة هذه الشروط والموافقة عليها قبل إنشاء فاتورة الدفع."
)


def _terms_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="أوافق وأتابع PLUS", callback_data="stars:PLUS"),
                InlineKeyboardButton(text="أوافق وأتابع PRO", callback_data="stars:PRO"),
            ],
            [InlineKeyboardButton(text="أوافق وأتابع شراء حصص التصميم", callback_data="credits:menu")],
        ]
    )


def _credits_entry_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="عرض الشروط والموافقة والمتابعة", callback_data="credits:menu")],
        ]
    )


def _credit_keyboard(packs: Sequence[CreditPack]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{pack.credits} تصاميم · {pack.stars_price} Stars",
                callback_data=f"credits:{pack.code}",
            )
        ]
        for pack in packs
    ]
    rows.append([InlineKeyboardButton(text="الشروط", callback_data="credits:terms")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("terms"))
async def terms_handler(message: Message, session: AsyncSession) -> None:
    await emoji_settings(session)
    await message.answer(TERMS_TEXT, parse_mode="HTML", reply_markup=_terms_keyboard())


@router.message(Command("credits"))
async def credits_handler(message: Message, session: AsyncSession) -> None:
    await emoji_settings(session)
    result = await session.execute(
        select(CreditPack)
        .where(CreditPack.is_active.is_(True))
        .order_by(CreditPack.stars_price.asc())
    )
    packs = result.scalars().all()
    lines = [
        "<b>حصص التصميم</b>",
        "",
        "اشترِ رصيد تصاميم إضافياً بدون اشتراك.",
        "الرصيد لا يستبدل الخطة؛ ويُستخدم بعد استنفاد الحصة اليومية المتاحة.",
        "",
    ]
    for pack in packs:
        per_design = pack.stars_price / pack.credits
        lines.append(
            f"<b>{pack.name}</b> · {pack.credits} تصاميم · {pack.stars_price} Stars · "
            f"{per_design:.2f} Stars/تصميم"
        )
    lines.append("\nيجب قراءة الشروط والموافقة عليها قبل إنشاء الفاتورة.")
    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=_credits_entry_keyboard(),
    )


@router.message(Command("paysupport"))
async def payment_support_handler(message: Message) -> None:
    await message.answer(
        "لدعم المدفوعات، أرسل رقم العملية أو تفاصيل المشكلة إلى دعم GQMRMed عبر @ID29i.\n"
        "لا ترسل كلمات مرور أو مفاتيح سرية أو بيانات بطاقة كاملة."
    )


@router.callback_query(F.data == "credits:menu")
async def credit_menu_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    await emoji_settings(session)
    if not isinstance(callback.message, Message):
        await callback.answer("تعذر عرض الحصص.", show_alert=True)
        return
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
        user.terms_accepted_at = datetime.now(UTC)
        result = await session.execute(
            select(CreditPack)
            .where(CreditPack.is_active.is_(True))
            .order_by(CreditPack.stars_price.asc())
        )
        packs = result.scalars().all()
    await callback.message.edit_text(
        "<b>حصص التصميم الإضافية</b>\n\n"
        "تم تسجيل موافقتك على الشروط. اختر الحصة التي تريد شراءها:",
        parse_mode="HTML",
        reply_markup=_credit_keyboard(packs),
    )
    await callback.answer()


@router.callback_query(F.data == "credits:terms")
async def credit_terms_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    await emoji_settings(session)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            TERMS_TEXT,
            parse_mode="HTML",
            reply_markup=_terms_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^credits:(DESIGN_5|DESIGN_12|DESIGN_20)$"))
async def credit_pack_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.data is None or not isinstance(callback.message, Message):
        await callback.answer("تعذر إنشاء الفاتورة.", show_alert=True)
        return
    pack_code = callback.data.split(":", 1)[1]
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
        if user.terms_accepted_at is None:
            await callback.answer(
                "يجب قراءة الشروط والموافقة عليها أولاً من /terms.",
                show_alert=True,
            )
            return
        pack = (
            await session.execute(
                select(CreditPack).where(
                    CreditPack.code == pack_code,
                    CreditPack.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if pack is None:
            await callback.answer("الحصة غير متاحة حالياً.", show_alert=True)
            return
        payload = f"gqmrmed:credit:{pack.code}:{uuid4().hex}"
        await create_stars_credit_payment(
            session,
            user_id=user.id,
            credit_pack=pack,
            invoice_payload=payload,
        )
    await callback.answer("تم تجهيز الفاتورة.")
    await callback.message.answer_invoice(
        title=f"GQMRMed {pack.name}",
        description=f"حصة إضافية: {pack.credits} تصاميم بدون مدة انتهاء تلقائية.",
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=pack.name, amount=pack.stars_price)],
    )


@router.callback_query(F.data.regexp(r"^stars:(PLUS|PRO)$"))
async def stars_plan_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.data is None or not isinstance(callback.message, Message):
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
        user.terms_accepted_at = datetime.now(UTC)
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
        description=f"اشتراك {plan.name}: {plan.daily_limit} تصاميم يومياً لمدة {plan.duration_days} يوماً.",
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=plan.name, amount=plan.stars_price)],
    )


@router.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery, session: AsyncSession) -> None:
    payment = await get_payment_by_invoice_payload(
        session,
        invoice_payload=query.invoice_payload,
    )
    stale = (
        payment is not None
        and payment.created_at is not None
        and datetime.now(UTC) - payment.created_at > timedelta(minutes=30)
    )
    if (
        payment is None
        or stale
        or payment.provider != "telegram_stars"
        or payment.status != PaymentStatus.PENDING.value
        or payment.stars_amount != query.total_amount
        or query.currency != "XTR"
    ):
        await query.answer(
            ok=False,
            error_message="الفاتورة غير صالحة أو انتهت صلاحيتها.",
        )
        return
    user = await session.get(User, payment.user_id)
    if user is None or user.telegram_id != query.from_user.id:
        await query.answer(
            ok=False,
            error_message="هذه الفاتورة ليست لهذا الحساب.",
        )
        return
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message, session: AsyncSession) -> None:
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
            "تم استلام إشعار دفع غير متوافق مع الطلب. لم يتم منح الاشتراك أو الرصيد تلقائياً؛ "
            "تواصل مع /paysupport."
        )
        return
    if payment.credit_pack_id is not None:
        await message.answer(
            "تم شراء حصة التصاميم بنجاح.\n"
            f"تمت إضافة الرصيد إلى حسابك. رقم العملية: {payment.transaction_id}\n"
            "سيُستخدم الرصيد تلقائياً بعد استنفاد الحصة اليومية المتاحة."
        )
    else:
        await message.answer(
            "تم استلام الدفع وتفعيل الاشتراك بنجاح.\n"
            f"رقم العملية: {payment.transaction_id}\n"
            "يمكنك الآن البدء بإرسال طلبات التصميم."
        )
