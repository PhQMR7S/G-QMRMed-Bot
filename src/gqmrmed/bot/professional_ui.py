"""Professional Telegram UI, owner controls, and Premium Emoji registry."""

import json

from datetime import UTC, date

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.bot.service import provision_user
from gqmrmed.db.models import CreditPack, DailyUsage, Plan, Subscription, SystemSetting, User
from gqmrmed.services.entitlements import resolve_entitlement

router = Router(name="gqmrmed-professional-ui")
OWNER_TELEGRAM_ID = 6246913670
EMOJI_PREFIX = "telegram_emoji."
EMOJI_SLOTS = (
    "brand", "medical", "create", "plans", "research", "ai", "design",
    "success", "warning", "support", "free", "plus", "pro",
)


def _emoji(settings: dict[str, str], slot: str) -> str:
    """Render a Telegram Premium Emoji with its exact Telegram-provided alt."""
    emoji_id = settings.get(f"{EMOJI_PREFIX}{slot}")
    if not emoji_id:
        return ""
    alt = settings.get(f"{EMOJI_PREFIX}alt:{emoji_id}")
    if not alt:
        return ""
    return f'<tg-emoji emoji-id="{emoji_id}">{alt}</tg-emoji>'


async def _emoji_settings(session: AsyncSession) -> dict[str, str]:
    rows = (
        await session.execute(
            select(SystemSetting).where(SystemSetting.key.like(f"{EMOJI_PREFIX}%"))
        )
    ).scalars().all()
    settings = {row.key: row.value for row in rows}
    raw_bank = settings.get(f"{EMOJI_PREFIX}bank")
    if raw_bank:
        try:
            bank = json.loads(raw_bank)
        except json.JSONDecodeError:
            bank = []
        if isinstance(bank, list):
            for item in bank:
                if not isinstance(item, dict):
                    continue
                emoji_id = str(item.get("id") or "")
                alt = str(item.get("alt") or "")
                if emoji_id and alt:
                    settings[f"{EMOJI_PREFIX}alt:{emoji_id}"] = alt
    return settings


def _is_owner(user_id: int) -> bool:
    return user_id == OWNER_TELEGRAM_ID


def _main_keyboard(owner: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="إنشاء تصميم", callback_data="pro:generate"),
            InlineKeyboardButton(text="الخطط والاشتراكات", callback_data="pro:plans"),
        ],
        [
            InlineKeyboardButton(text="🔑 تفعيل كود", callback_data="pro:activate"),
            InlineKeyboardButton(text="حسابي ورصيدي", callback_data="pro:account"),
        ],
        [
            InlineKeyboardButton(text="حصص التصميم", callback_data="pro:credits"),
            InlineKeyboardButton(text="طريقة الاستخدام", callback_data="pro:help"),
        ],
        [
            InlineKeyboardButton(text="الدفع والفوترة", callback_data="pro:payment"),
            InlineKeyboardButton(text="الشروط والأحكام", callback_data="pro:terms"),
        ],
        [InlineKeyboardButton(text="الدعم", callback_data="pro:support")],
    ]
    if owner:
        rows.append([InlineKeyboardButton(text="لوحة الإدارة", callback_data="adm:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="القائمة الرئيسية", callback_data="pro:home")]]
    )


async def _user_from_message(session: AsyncSession, message: Message) -> User:
    if message.from_user is None:
        raise ValueError("telegram_user_required")
    return await provision_user(
        session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        language=message.from_user.language_code,
    )


async def _home_text(session: AsyncSession) -> str:
    e = await _emoji_settings(session)
    return (
        f"{_emoji(e, 'brand')} <b>GQMRMed</b>\n\n"
        f"{_emoji(e, 'medical')} إنشاء تصاميم طبية تعليمية باعتماد مسار البحث والتحقق.\n\n"
        f"{_emoji(e, 'create')} اختر الخدمة من القائمة أدناه."
    )


async def _plans_text(session: AsyncSession) -> str:
    e = await _emoji_settings(session)
    plans = (
        await session.execute(
            select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.price.asc(), Plan.code.asc())
        )
    ).scalars().all()
    lines = [f"{_emoji(e, 'plans')} <b>الخطط والاشتراكات</b>", ""]
    for plan in plans:
        limit = "غير محدود" if plan.daily_limit is None else f"{plan.daily_limit} تصاميم يومياً"
        duration = "مستمر" if plan.duration_days is None else f"{plan.duration_days} يوماً"
        stars = "بدون رسوم" if plan.stars_price is None else f"{plan.stars_price} Telegram Stars"
        slot = plan.code.lower() if plan.code.lower() in {"free", "plus", "pro"} else "plans"
        lines.extend(
            [
                f"{_emoji(e, slot)} <b>{plan.name}</b>",
                f"الحد اليومي: {limit} · المدة: {duration}",
                f"السعر: {stars}",
                "",
            ]
        )
    lines.append(f"{_emoji(e, 'plans')} الخدمات الرقمية داخل Telegram تُباع عبر Telegram Stars.")
    return "\n".join(lines)


TERMS_TEXT = (
    "<b>الشروط والأحكام</b>\n\n"
    "GQMRMed خدمة رقمية لإنشاء تصاميم ومحتوى طبي تعليمي. النتائج لا تُعد تشخيصاً طبياً ولا بديلاً عن الطبيب أو المرجع الطبي المتخصص.\n\n"
    "<b>الاستخدام</b>\nتُستخدم الحصة اليومية حسب الخطة الحالية. عند توفر حصة يومية تُستهلك أولاً، ثم يُستخدم رصيد التصاميم المشتراة.\n\n"
    "<b>الرصيد المشتَرى</b>\nالرصيد الإضافي مستقل عن الاشتراك ولا تنتهي صلاحيته تلقائياً. كل تصميم ناجح يستهلك وحدة واحدة؛ وإذا فشل التوليد قبل إتمامه تُعاد الوحدة المحجوزة.\n\n"
    "<b>الدفع</b>\nلأن الخدمة رقمية داخل Telegram، تتم المشتريات داخل Telegram باستخدام Telegram Stars (XTR). لا يُمنح الاشتراك أو الرصيد إلا بعد تحقق الخادم من successful_payment.\n\n"
    "<b>الدعم</b>\nللمشكلات المتعلقة بالدفع استخدم /paysupport. لا ترسل كلمات مرور أو مفاتيح سرية أو بيانات بطاقة كاملة."
)
PAYMENT_TEXT = (
    "<b>الدفع والفوترة</b>\n\n"
    "جميع مشتريات GQMRMed الرقمية داخل Telegram تتم عبر Telegram Stars (XTR).\n\n"
    "1. اختر الخطة أو حصة التصميم.\n"
    "2. اقرأ الشروط ثم اختر المتابعة.\n"
    "3. تظهر فاتورة Telegram الرسمية.\n"
    "4. أكمل الدفع من داخل Telegram.\n"
    "5. يتحقق الخادم من successful_payment ثم يفعّل الاشتراك أو يضيف الرصيد تلقائياً.\n\n"
    "لقطة الشاشة وحدها ليست إثباتاً لمنح الخدمة.\n"
    "للدعم: /paysupport"
)
HELP_TEXT = (
    "<b>طريقة الاستخدام</b>\n\n"
    "<b>1. أرسل المحتوى</b>\nموضوعاً أو نصاً أو صورة أو ملفاً أو صوتاً أو فيديو.\n\n"
    "<b>2. البحث والتحقق</b>\nيُحلَّل الإدخال، ثم تُبنى المادة الطبية اعتماداً على الأدلة المتاحة قبل التكوين البصري.\n\n"
    "<b>3. التوليد</b>\nتُجهَّز الصورة أو التصميم وفق المحتوى المعتمد.\n\n"
    "<b>4. النتيجة</b>\nيصلك التصميم النهائي داخل Telegram عند اكتمال المعالجة."
)


@router.message(CommandStart())
async def professional_start(message: Message, session: AsyncSession) -> None:
    async with session.begin():
        user = await _user_from_message(session, message)
    if not user.is_active:
        e = await _emoji_settings(session)
        await message.answer(
            f"{_emoji(e, 'warning')} <b>الحساب غير نشط</b>\n\nهذا الحساب غير نشط حالياً.",
            parse_mode="HTML",
        )
        return
    await message.answer(
        await _home_text(session),
        parse_mode="HTML",
        reply_markup=_main_keyboard(_is_owner(message.from_user.id)),
    )


@router.callback_query(F.data == "pro:home")
async def pro_home(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.message is not None:
        await callback.message.edit_text(
            await _home_text(session),
            parse_mode="HTML",
            reply_markup=_main_keyboard(_is_owner(callback.from_user.id)),
        )
    await callback.answer()


@router.callback_query(F.data == "pro:generate")
async def pro_generate(callback: CallbackQuery, session: AsyncSession) -> None:
    e = await _emoji_settings(session)
    if callback.message is not None:
        await callback.message.edit_text(
            f"{_emoji(e, 'create')} <b>إنشاء تصميم طبي</b>\n\n"
            f"{_emoji(e, 'ai')} أرسل الآن الموضوع أو النص أو الصورة أو الملف أو الصوت أو الفيديو.\n\n"
            "سيُحلَّل الطلب ويُمرَّر عبر البحث والتحقق ثم مسار التوليد حتى يصلك التصميم النهائي.",
            parse_mode="HTML",
            reply_markup=_back_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "pro:help")
async def pro_help(callback: CallbackQuery, session: AsyncSession) -> None:
    e = await _emoji_settings(session)
    if callback.message is not None:
        await callback.message.edit_text(
            f"{_emoji(e, 'research')} {HELP_TEXT}",
            parse_mode="HTML",
            reply_markup=_back_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "pro:terms")
async def pro_terms(callback: CallbackQuery, session: AsyncSession) -> None:
    e = await _emoji_settings(session)
    if callback.message is not None:
        await callback.message.edit_text(
            f"{_emoji(e, 'warning')} {TERMS_TEXT}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="الخطط والشراء", callback_data="pro:plans")],
                    [InlineKeyboardButton(text="الدفع والفوترة", callback_data="pro:payment")],
                    [InlineKeyboardButton(text="القائمة الرئيسية", callback_data="pro:home")],
                ]
            ),
        )
    await callback.answer()


@router.callback_query(F.data == "pro:payment")
async def pro_payment(callback: CallbackQuery, session: AsyncSession) -> None:
    e = await _emoji_settings(session)
    if callback.message is not None:
        await callback.message.edit_text(
            f"{_emoji(e, 'plans')} {PAYMENT_TEXT}",
            parse_mode="HTML",
            reply_markup=_back_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "pro:support")
async def pro_support(callback: CallbackQuery, session: AsyncSession) -> None:
    e = await _emoji_settings(session)
    if callback.message is not None:
        await callback.message.edit_text(
            f"{_emoji(e, 'support')} <b>الدعم</b>\n\n"
            "للدعم المتعلق بالدفع استخدم /paysupport.\n"
            "للمشكلات العامة أرسل وصف المشكلة ورقم العملية إن كانت متعلقة بالدفع.\n\n"
            "لا ترسل كلمات مرور أو مفاتيح سرية أو بيانات بطاقة كاملة.",
            parse_mode="HTML",
            reply_markup=_back_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "pro:plans")
async def pro_plans(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.message is not None:
        await callback.message.edit_text(
            await _plans_text(session),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="شراء PLUS", callback_data="stars:PLUS"),
                        InlineKeyboardButton(text="شراء PRO", callback_data="stars:PRO"),
                    ],
                    [InlineKeyboardButton(text="شراء حصص التصميم", callback_data="credits:menu")],
                    [InlineKeyboardButton(text="🔑 إدخال كود التفعيل", callback_data="pro:activate")],
                    [InlineKeyboardButton(text="الشروط والأحكام", callback_data="pro:terms")],
                    [InlineKeyboardButton(text="القائمة الرئيسية", callback_data="pro:home")],
                ]
            ),
        )
    await callback.answer("تم عرض الخطط")


@router.callback_query(F.data == "pro:credits")
async def pro_credits(callback: CallbackQuery, session: AsyncSession) -> None:
    e = await _emoji_settings(session)
    packs = (
        await session.execute(
            select(CreditPack).where(CreditPack.is_active.is_(True)).order_by(CreditPack.stars_price.asc())
        )
    ).scalars().all()
    lines = [
        f"{_emoji(e, 'design')} <b>حصص التصميم</b>",
        "",
        f"{_emoji(e, 'plus')} شراء رصيد إضافي بدون اشتراك:",
        "",
    ]
    rows: list[list[InlineKeyboardButton]] = []
    for pack in packs:
        per = pack.stars_price / pack.credits
        lines.append(
            f"<b>{pack.name}</b> · {pack.credits} تصاميم · "
            f"{pack.stars_price} Telegram Stars · {per:.2f} Stars/تصميم"
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"شراء {pack.credits} تصاميم · {pack.stars_price} Stars",
                    callback_data=f"credits:{pack.code}",
                )
            ]
        )
    rows.extend(
        [
            [InlineKeyboardButton(text="الشروط والأحكام", callback_data="pro:terms")],
            [InlineKeyboardButton(text="القائمة الرئيسية", callback_data="pro:home")],
        ]
    )
    if callback.message is not None:
        await callback.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )
    await callback.answer()


@router.callback_query(F.data == "pro:account")
async def pro_account(callback: CallbackQuery, session: AsyncSession) -> None:
    user = (
        await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
    ).scalar_one_or_none()
    if user is None:
        await callback.answer("لم يتم إنشاء الحساب بعد.", show_alert=True)
        return
    entitlement = await resolve_entitlement(session, user_id=user.id)
    usage = (
        await session.execute(
            select(DailyUsage).where(
                DailyUsage.user_id == user.id,
                DailyUsage.usage_date == date.today(),
            )
        )
    ).scalar_one_or_none()
    used = usage.committed if usage else 0
    reserved = usage.reserved if usage else 0
    limit = entitlement.daily_limit
    remaining = "غير محدود" if limit is None else str(max(limit - used - reserved, 0))
    expiry_text = "مستمر"
    if entitlement.subscription_id is not None:
        sub = await session.get(Subscription, entitlement.subscription_id)
        if sub and sub.expires_at:
            expiry_text = sub.expires_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    e = await _emoji_settings(session)
    text = (
        f"{_emoji(e, 'medical')} <b>حسابي ورصيدي</b>\n\n"
        f"{_emoji(e, 'plans')} الخطة الحالية: <b>{entitlement.plan.name}</b>\n"
        f"الاستخدام اليومي: {used}\n"
        f"المحجوز حالياً: {reserved}\n"
        f"{_emoji(e, 'success')} المتاح اليوم: {remaining}\n"
        f"{_emoji(e, 'design')} رصيد التصاميم الإضافي: <b>{user.design_credits}</b>\n"
        f"انتهاء الاشتراك: {expiry_text}"
    )
    if callback.message is not None:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_back_keyboard())
    await callback.answer()


@router.message(Command("activate"))
async def professional_activate_command(message: Message, session: AsyncSession) -> None:
    """Provide a command entry point for users who prefer Telegram commands."""
    del session
    await message.answer(
        "🔑 <b>تفعيل الاشتراك بكود</b>\n\n"
        "اضغط الزر أدناه ثم أرسل كود التفعيل.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="إدخال كود التفعيل", callback_data="pro:activate")],
                [InlineKeyboardButton(text="القائمة الرئيسية", callback_data="pro:home")],
            ]
        ),
    )


@router.message(Command("help"))
async def professional_help_command(message: Message, session: AsyncSession) -> None:
    e = await _emoji_settings(session)
    await message.answer(f"{_emoji(e, 'research')} {HELP_TEXT}", parse_mode="HTML")


@router.message(Command("plans"))
async def professional_plans_command(message: Message, session: AsyncSession) -> None:
    await message.answer(await _plans_text(session), parse_mode="HTML")


@router.message(Command("terms"))
async def professional_terms_command(message: Message, session: AsyncSession) -> None:
    e = await _emoji_settings(session)
    await message.answer(f"{_emoji(e, 'warning')} {TERMS_TEXT}", parse_mode="HTML")


@router.message(Command("paysupport"))
async def professional_support_command(message: Message, session: AsyncSession) -> None:
    e = await _emoji_settings(session)
    await message.answer(
        f"{_emoji(e, 'support')} <b>دعم المدفوعات</b>\n\n"
        "أرسل رقم العملية ووصف المشكلة إلى @ID29i.\n"
        "لا ترسل كلمات مرور أو مفاتيح سرية أو بيانات بطاقة كاملة.",
        parse_mode="HTML",
    )


def _custom_emoji_id(message: Message) -> str | None:
    for entity in message.entities or []:
        if entity.type == "custom_emoji" and entity.custom_emoji_id:
            return entity.custom_emoji_id
    return None


def _emoji_slot(message: Message) -> str | None:
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        return None
    slot = parts[1].strip()
    return slot if slot in EMOJI_SLOTS else None


@router.message(Command("emoji_bind"))
async def emoji_bind(message: Message, session: AsyncSession) -> None:
    if message.from_user is None or not _is_owner(message.from_user.id):
        await message.answer("هذا الأمر متاح لمالك البوت فقط.")
        return
    slot = _emoji_slot(message)
    emoji_id = _custom_emoji_id(message)
    if slot is None or emoji_id is None:
        await message.answer(
            "صيغة الربط:\n/emoji_bind <slot> <Premium Emoji>\n\n"
            "المساحات: " + ", ".join(EMOJI_SLOTS)
        )
        return
    key = f"{EMOJI_PREFIX}{slot}"
    async with session.begin():
        setting = (
            await session.execute(select(SystemSetting).where(SystemSetting.key == key))
        ).scalar_one_or_none()
        if setting is None:
            session.add(SystemSetting(key=key, value=emoji_id))
        else:
            setting.value = emoji_id
    e = await _emoji_settings(session)
    await message.answer(
        f"{_emoji(e, 'success')} <b>تم ربط Premium Emoji</b>\n\nالمساحة: <code>{slot}</code>",
        parse_mode="HTML",
    )


@router.message(Command("emoji_status"))
async def emoji_status(message: Message, session: AsyncSession) -> None:
    if message.from_user is None or not _is_owner(message.from_user.id):
        await message.answer("هذا الأمر متاح لمالك البوت فقط.")
        return
    settings = await _emoji_settings(session)
    lines = [f"{_emoji(settings, 'brand')} <b>حالة Premium Emoji</b>", ""]
    for slot in EMOJI_SLOTS:
        state = "مرتبط" if settings.get(f"{EMOJI_PREFIX}{slot}") else "غير مرتبط"
        lines.append(f"{_emoji(settings, slot)} <code>{slot}</code>: {state}")
    await message.answer("\n".join(lines), parse_mode="HTML")
