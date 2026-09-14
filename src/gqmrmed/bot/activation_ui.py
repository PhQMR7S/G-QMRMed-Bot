"""User-facing activation-code flow for Telegram."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.bot.service import provision_user
from gqmrmed.db.models import Plan
from gqmrmed.services.subscriptions import activate_code

router = Router(name="gqmrmed-activation-ui")


class ActivationStates(StatesGroup):
    waiting_for_code = State()


def _plans_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔑 إدخال كود التفعيل", callback_data="pro:activate")],
            [InlineKeyboardButton(text="القائمة الرئيسية", callback_data="pro:home")],
        ]
    )


def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="إلغاء والعودة للرئيسية", callback_data="pro:activate_cancel")]
        ]
    )


@router.callback_query(F.data == "pro:plans")
async def activation_plans_entry(callback: CallbackQuery, session: AsyncSession) -> None:
    plans = (
        await session.execute(
            select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.price.asc(), Plan.code.asc())
        )
    ).scalars().all()
    lines = ["💳 <b>الخطط والاشتراكات</b>", ""]
    for plan in plans:
        limit = "غير محدود" if plan.daily_limit is None else f"{plan.daily_limit} تصاميم يومياً"
        duration = "مستمر" if plan.duration_days is None else f"{plan.duration_days} يوماً"
        stars = "بدون رسوم" if plan.stars_price is None else f"{plan.stars_price} Telegram Stars"
        lines.extend(
            [
                f"<b>{plan.name}</b>",
                f"الحد اليومي: {limit} · المدة: {duration}",
                f"السعر: {stars}",
                "",
            ]
        )
    lines.extend(
        [
            "🔑 <b>لديك كود تفعيل؟</b>",
            "أدخل الكود وسيحدد النظام الخطة المرتبطة به تلقائياً.",
            "الكود صالح للاستخدام مرة واحدة فقط.",
        ]
    )
    if callback.message is not None:
        await callback.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=_plans_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "pro:activate")
async def activation_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ActivationStates.waiting_for_code)
    if callback.message is not None:
        await callback.message.edit_text(
            "🔑 <b>تفعيل الاشتراك بكود</b>\n\n"
            "أرسل كود التفعيل الآن كما استلمته.\n\n"
            "سيتم التحقق من الكود وربطه بالخطة الخاصة به تلقائياً.\n"
            "⚠️ كل كود يُستخدم مرة واحدة فقط.",
            parse_mode="HTML",
            reply_markup=_cancel_keyboard(),
        )
    await callback.answer()


@router.message(ActivationStates.waiting_for_code)
async def activation_submit(message: Message, state: FSMContext, session: AsyncSession) -> None:
    raw_code = (message.text or "").strip()
    if not raw_code:
        await message.answer("❌ أرسل كود التفعيل كنص.", reply_markup=_cancel_keyboard())
        return
    if len(raw_code) > 256:
        await message.answer("❌ كود التفعيل غير صالح.", reply_markup=_cancel_keyboard())
        return
    if message.from_user is None:
        return

    try:
        async with session.begin():
            user = await provision_user(
                session,
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                language=message.from_user.language_code,
            )
            subscription = await activate_code(
                session,
                user_id=user.id,
                raw_code=raw_code,
            )
            plan = await session.get(Plan, subscription.plan_id)
    except ValueError as exc:
        errors = {
            "invalid_or_used_activation_code": "❌ الكود غير صحيح أو تم استخدامه مسبقاً.",
            "activation_code_expired": "⏰ انتهت صلاحية كود التفعيل.",
            "plan_unavailable": "⚠️ الخطة المرتبطة بهذا الكود غير متاحة حالياً.",
            "invalid_subscription_duration": "⚠️ مدة الاشتراك المرتبطة بالكود غير صالحة.",
            "user_not_found": "❌ تعذر العثور على حسابك.",
        }
        await message.answer(errors.get(str(exc), "❌ تعذر تفعيل الكود حالياً، حاول مرة أخرى."))
        return

    await state.clear()
    plan_name = plan.name if plan is not None else "الخطة المرتبطة بالكود"
    expiry = subscription.expires_at.strftime("%Y-%m-%d %H:%M UTC")
    await message.answer(
        "🎉 <b>تم تفعيل الاشتراك بنجاح!</b>\n\n"
        f"الخطة: <b>{plan_name}</b>\n"
        f"ينتهي الاشتراك: <b>{expiry}</b>\n\n"
        "🔐 تم استهلاك كود التفعيل، ولا يمكن استخدامه مرة أخرى.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="حسابي ورصيدي", callback_data="pro:account")],
                [InlineKeyboardButton(text="إنشاء تصميم", callback_data="pro:generate")],
                [InlineKeyboardButton(text="القائمة الرئيسية", callback_data="pro:home")],
            ]
        ),
    )


@router.callback_query(F.data == "pro:activate_cancel")
async def activation_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message is not None:
        await callback.message.edit_text(
            "تم إلغاء إدخال كود التفعيل.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="القائمة الرئيسية", callback_data="pro:home")]
                ]
            ),
        )
    await callback.answer()
