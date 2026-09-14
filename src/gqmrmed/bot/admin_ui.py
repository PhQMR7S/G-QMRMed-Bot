"""Owner-only in-bot administration panel for GQMRMed."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.db.models import (
    ActivationCode,
    ActivationCodeStatus,
    CreditPack,
    DailyUsage,
    GenerationJob,
    JobStatus,
    Payment,
    PaymentStatus,
    Plan,
    Subscription,
    SystemSetting,
    User,
)
from gqmrmed.services.activation import create_activation_code

router = Router(name="gqmrmed-admin-ui")
OWNER_TELEGRAM_ID = 6246913670
EMOJI_PREFIX = "telegram_emoji."
EMOJI_SLOTS = (
    "brand", "medical", "create", "plans", "research", "ai", "design",
    "success", "warning", "support", "free", "plus", "pro",
)


def _owner(message: Message | CallbackQuery) -> bool:
    return message.from_user is not None and message.from_user.id == OWNER_TELEGRAM_ID


def _kb(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _emoji_settings(session: AsyncSession) -> dict[str, str]:
    rows = (
        await session.execute(
            select(SystemSetting).where(SystemSetting.key.like(f"{EMOJI_PREFIX}%"))
        )
    ).scalars().all()
    return {row.key: row.value for row in rows}


def _emoji(settings: dict[str, str], slot: str) -> str:
    emoji_id = settings.get(f"{EMOJI_PREFIX}{slot}")
    return f'<tg-emoji emoji-id="{emoji_id}"> </tg-emoji>' if emoji_id else ""


async def _home_kb_text(session: AsyncSession) -> str:
    e = await _emoji_settings(session)
    return (
        f"{_emoji(e, 'brand')} <b>GQMRMed — لوحة الإدارة</b>\n"
        f"{_emoji(e, 'medical')} إدارة المنصة والمستخدمين والتوليد والمدفوعات.\n\n"
        f"{_emoji(e, 'warning')} هذا القسم خاص بمالك البوت فقط."
    )


def _home_kb() -> InlineKeyboardMarkup:
    return _kb([
        [InlineKeyboardButton(text="المستخدمون", callback_data="adm:users"), InlineKeyboardButton(text="لوحة المعلومات", callback_data="adm:overview")],
        [InlineKeyboardButton(text="الخطط والاشتراكات", callback_data="adm:plans"), InlineKeyboardButton(text="أكواد الاشتراك", callback_data="adm:codes")],
        [InlineKeyboardButton(text="حصص التصميم", callback_data="adm:credits"), InlineKeyboardButton(text="المدفوعات", callback_data="adm:payments")],
        [InlineKeyboardButton(text="وظائف التوليد", callback_data="adm:jobs"), InlineKeyboardButton(text="الإرسال الجماعي", callback_data="adm:broadcast")],
        [InlineKeyboardButton(text="مراسلة مستخدم", callback_data="adm:message"), InlineKeyboardButton(text="Premium Emoji", callback_data="adm:emoji")],
        [InlineKeyboardButton(text="الرئيسية", callback_data="pro:home")],
    ])


def _back() -> InlineKeyboardMarkup:
    return _kb([[InlineKeyboardButton(text="لوحة الإدارة", callback_data="adm:home")]])


async def _counts(session: AsyncSession) -> dict[str, int]:
    async def count(model: type[object], *conditions: Any) -> int:
        stmt = select(func.count()).select_from(model)
        for condition in conditions:
            stmt = stmt.where(condition)
        return int(await session.scalar(stmt) or 0)

    return {
        "users": await count(User),
        "active": await count(User, User.is_active.is_(True)),
        "blocked": await count(User, User.is_active.is_(False)),
        "plans": await count(Plan, Plan.is_active.is_(True)),
        "codes": await count(ActivationCode, ActivationCode.status == ActivationCodeStatus.UNUSED.value),
        "pending": await count(Payment, Payment.status == PaymentStatus.PENDING.value),
        "queued": await count(GenerationJob, GenerationJob.status == JobStatus.QUEUED.value),
        "running": await count(GenerationJob, GenerationJob.status == JobStatus.RUNNING.value),
        "failed": await count(GenerationJob, GenerationJob.status == JobStatus.FAILED.value),
    }


async def _overview_text(session: AsyncSession) -> str:
    c = await _counts(session)
    e = await _emoji_settings(session)
    today = datetime.now(UTC).date()
    today_jobs = int(await session.scalar(select(func.count()).select_from(GenerationJob).where(func.date(GenerationJob.created_at) == today)) or 0)
    today_users = int(await session.scalar(select(func.count()).select_from(User).where(func.date(User.created_at) == today)) or 0)
    return (
        f"{_emoji(e, 'brand')} <b>لوحة معلومات GQMRMed</b>\n\n"
        f"{_emoji(e, 'medical')} المستخدمون: {c['users']}\n"
        f"{_emoji(e, 'success')} النشطون: {c['active']}\n"
        f"{_emoji(e, 'warning')} الموقوفون: {c['blocked']}\n"
        f"{_emoji(e, 'plus')} مستخدمون جدد اليوم: {today_users}\n\n"
        f"{_emoji(e, 'plans')} الخطط النشطة: {c['plans']}\n"
        f"{_emoji(e, 'pro')} أكواد غير مستخدمة: {c['codes']}\n"
        f"{_emoji(e, 'support')} مدفوعات معلقة: {c['pending']}\n\n"
        f"{_emoji(e, 'create')} وظائف اليوم: {today_jobs}\n"
        f"{_emoji(e, 'ai')} في الانتظار: {c['queued']}\n"
        f"{_emoji(e, 'research')} قيد التنفيذ: {c['running']}\n"
        f"{_emoji(e, 'design')} الفاشلة: {c['failed']}"
    )


async def _send_panel(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    await callback.answer()


@router.message(Command("admin"))
async def admin_start(message: Message, session: AsyncSession) -> None:
    if not _owner(message):
        e = await _emoji_settings(session)
        await message.answer(f"{_emoji(e, 'warning')} هذا القسم متاح لمالك البوت فقط.", parse_mode="HTML")
        return
    await message.answer(
        f"{await _overview_text(session)}\n\n{await _home_kb_text(session)}",
        parse_mode="HTML",
        reply_markup=_home_kb(),
    )


@router.callback_query(F.data == "adm:home")
async def admin_home(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    await _send_panel(callback, await _overview_text(session), _home_kb())


@router.callback_query(F.data == "adm:overview")
async def admin_overview(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    await _send_panel(callback, await _overview_text(session), _back())


@router.callback_query(F.data == "adm:users")
async def admin_users(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    e = await _emoji_settings(session)
    users = (await session.execute(select(User).order_by(User.created_at.desc()).limit(12))).scalars().all()
    rows: list[list[InlineKeyboardButton]] = []
    lines = [f"{_emoji(e, 'medical')} <b>إدارة المستخدمين</b>", ""]
    for user in users:
        name = user.first_name or user.username or str(user.telegram_id)
        state = "نشط" if user.is_active else "موقوف"
        lines.append(f"{_emoji(e, 'success' if user.is_active else 'warning')} {name} · {user.telegram_id} · {state}")
        rows.append([InlineKeyboardButton(text=f"{name} · {user.telegram_id}", callback_data=f"adm:user:{user.id}")])
    rows.extend([
        [InlineKeyboardButton(text="بحث برقم Telegram", callback_data="adm:userhelp")],
        [InlineKeyboardButton(text="لوحة الإدارة", callback_data="adm:home")],
    ])
    await _send_panel(callback, "\n".join(lines), _kb(rows))


@router.callback_query(F.data == "adm:userhelp")
async def admin_user_help(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    e = await _emoji_settings(session)
    await _send_panel(
        callback,
        f"{_emoji(e, 'research')} <b>بحث وإدارة مستخدم</b>\n\nاستخدم:\n/admin_user TELEGRAM_ID\n\nثم ستظهر لك بيانات المستخدم وأدوات الإيقاف والحظر وإلغاء الحظر وإضافة الرصيد.",
        _back(),
    )


async def _user_text(session: AsyncSession, user: User) -> str:
    e = await _emoji_settings(session)
    subs = (await session.execute(select(Subscription).where(Subscription.user_id == user.id).order_by(Subscription.created_at.desc()).limit(3))).scalars().all()
    used = int(await session.scalar(select(func.coalesce(func.sum(DailyUsage.committed), 0)).where(DailyUsage.user_id == user.id)) or 0)
    jobs = int(await session.scalar(select(func.count()).select_from(GenerationJob).where(GenerationJob.user_id == user.id)) or 0)
    plans = ", ".join(str(s.status) for s in subs) or "لا يوجد"
    return (
        f"{_emoji(e, 'medical')} <b>ملف المستخدم</b>\n\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"الاسم: {user.first_name or '-'} {user.last_name or ''}\n"
        f"Username: @{user.username or '-'}\n"
        f"{_emoji(e, 'success' if user.is_active else 'warning')} الحالة: {'نشط' if user.is_active else 'موقوف'}\n"
        f"{_emoji(e, 'design')} الرصيد: {user.design_credits}\n"
        f"الاستخدام المتراكم: {used}\n"
        f"{_emoji(e, 'create')} وظائف التوليد: {jobs}\n"
        f"{_emoji(e, 'plans')} الاشتراكات الأخيرة: {plans}"
    )


def _user_kb(user: User) -> InlineKeyboardMarkup:
    toggle = "إيقاف المستخدم" if user.is_active else "تفعيل المستخدم"
    return _kb([
        [InlineKeyboardButton(text=toggle, callback_data=f"adm:user_toggle:{user.id}"), InlineKeyboardButton(text="حظر", callback_data=f"adm:user_ban:{user.id}")],
        [InlineKeyboardButton(text="إلغاء الحظر", callback_data=f"adm:user_unban:{user.id}"), InlineKeyboardButton(text="إضافة رصيد", callback_data=f"adm:user_credit:{user.id}")],
        [InlineKeyboardButton(text="مراسلة", callback_data=f"adm:user_message:{user.telegram_id}"), InlineKeyboardButton(text="المستخدمون", callback_data="adm:users")],
        [InlineKeyboardButton(text="لوحة الإدارة", callback_data="adm:home")],
    ])


@router.callback_query(F.data.regexp(r"^adm:user:[0-9a-f-]{36}$"))
async def admin_user_detail(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    user_id = UUID(callback.data.rsplit(":", 1)[1]) if callback.data else None
    user = await session.get(User, user_id) if user_id else None
    if user is None:
        await callback.answer("المستخدم غير موجود.", show_alert=True)
        return
    await _send_panel(callback, await _user_text(session, user), _user_kb(user))


async def _set_user_state(session: AsyncSession, user_id: UUID, *, active: bool | None = None, banned: bool | None = None) -> User | None:
    user = await session.get(User, user_id)
    if user is None:
        return None
    if active is not None:
        user.is_active = active
    if banned is True:
        user.is_active = False
    if banned is False:
        user.is_active = True
    await session.flush()
    return user


@router.callback_query(F.data.regexp(r"^adm:user_(toggle|ban|unban):[0-9a-f-]{36}$"))
async def admin_user_state(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    if not callback.data:
        return
    action, raw_id = callback.data.rsplit(":", 1)
    if action == "adm:user_toggle":
        user = await session.get(User, UUID(raw_id))
        if user is not None:
            user.is_active = not user.is_active
            await session.flush()
    else:
        user = await _set_user_state(session, UUID(raw_id), banned=(action == "adm:user_ban"))
        if user is not None and action == "adm:user_unban":
            user.is_active = True
    await session.commit()
    if user is None:
        await callback.answer("المستخدم غير موجود.", show_alert=True)
        return
    await _send_panel(callback, await _user_text(session, user), _user_kb(user))


@router.message(Command("admin_user"))
async def admin_user_command(message: Message, session: AsyncSession) -> None:
    if not _owner(message):
        await message.answer("غير مصرح.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("الاستخدام: /admin_user TELEGRAM_ID")
        return
    user = (await session.execute(select(User).where(User.telegram_id == int(parts[1])))).scalar_one_or_none()
    if user is None:
        await message.answer("المستخدم غير موجود.")
        return
    await message.answer(await _user_text(session, user), parse_mode="HTML", reply_markup=_user_kb(user))


@router.callback_query(F.data == "adm:plans")
async def admin_plans(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    e = await _emoji_settings(session)
    plans = (await session.execute(select(Plan).order_by(Plan.price.asc(), Plan.code.asc()))).scalars().all()
    lines = [f"{_emoji(e, 'plans')} <b>إدارة الخطط والاشتراكات</b>", ""]
    rows: list[list[InlineKeyboardButton]] = []
    for plan in plans:
        state = "مفعلة" if plan.is_active else "موقوفة"
        price = f"{plan.stars_price} Stars" if plan.stars_price is not None else "مجانية"
        slot = plan.code.lower() if plan.code.lower() in {"free", "plus", "pro"} else "plans"
        lines.append(f"{_emoji(e, slot)} {plan.code} · {plan.name} · {plan.daily_limit or '∞'}/يوم · {price} · {state}")
        rows.append([InlineKeyboardButton(text=f"{plan.code} · {'إيقاف' if plan.is_active else 'تفعيل'}", callback_data=f"adm:plan_toggle:{plan.id}")])
    rows.append([InlineKeyboardButton(text="إنشاء كود اشتراك", callback_data="adm:codes")])
    rows.append([InlineKeyboardButton(text="لوحة الإدارة", callback_data="adm:home")])
    await _send_panel(callback, "\n".join(lines), _kb(rows))


@router.callback_query(F.data.regexp(r"^adm:plan_toggle:[0-9a-f-]{36}$"))
async def admin_plan_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    plan = await session.get(Plan, UUID(callback.data.rsplit(":", 1)[1])) if callback.data else None
    if plan is None:
        await callback.answer("الخطة غير موجودة.", show_alert=True)
        return
    plan.is_active = not plan.is_active
    await session.commit()
    await admin_plans(callback, session)


@router.callback_query(F.data == "adm:codes")
async def admin_codes(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    e = await _emoji_settings(session)
    codes = (await session.execute(select(ActivationCode).order_by(ActivationCode.created_at.desc()).limit(10))).scalars().all()
    lines = [f"{_emoji(e, 'pro')} <b>أكواد الاشتراك</b>", ""]
    rows: list[list[InlineKeyboardButton]] = []
    for code in codes:
        lines.append(f"{_emoji(e, 'success' if code.status == ActivationCodeStatus.UNUSED.value else 'warning')} {code.code_hash[:12]}… · {code.status} · {code.duration_days} يوم")
    for plan_code, days in (("PLUS", 30), ("PLUS", 150), ("PLUS", 365), ("PRO", 30), ("PRO", 150), ("PRO", 365)):
        rows.append([InlineKeyboardButton(text=f"إنشاء {plan_code} — {days} يوم", callback_data=f"adm:create_code:{plan_code}:{days}")])
    rows.append([InlineKeyboardButton(text="لوحة الإدارة", callback_data="adm:home")])
    await _send_panel(callback, "\n".join(lines), _kb(rows))


@router.callback_query(F.data.regexp(r"^adm:create_code:(PLUS|PRO):(30|150|365)$"))
async def admin_create_code(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    if not callback.data:
        return
    _, _, plan_code, days_raw = callback.data.split(":")
    plan = (await session.execute(select(Plan).where(Plan.code == plan_code))).scalar_one_or_none()
    if plan is None:
        await callback.answer("الخطة غير موجودة.", show_alert=True)
        return
    _, plaintext = await create_activation_code(session, plan=plan, duration_days=int(days_raw))
    await session.commit()
    e = await _emoji_settings(session)
    if isinstance(callback.message, Message):
        await callback.message.answer(
            f"{_emoji(e, 'success')} <b>تم إنشاء كود اشتراك</b>\n\n"
            f"الخطة: {plan_code}\nالمدة: {days_raw} يوم\n\nالكود:\n<code>{plaintext}</code>\n\nأرسل الكود للمستخدم المستحق فقط.",
            parse_mode="HTML",
        )
    await callback.answer("تم إنشاء الكود.")


@router.callback_query(F.data == "adm:credits")
async def admin_credits(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    e = await _emoji_settings(session)
    packs = (await session.execute(select(CreditPack).order_by(CreditPack.stars_price.asc()))).scalars().all()
    lines = [f"{_emoji(e, 'design')} <b>حصص التصميم</b>", ""]
    for pack in packs:
        state = "مفعلة" if pack.is_active else "موقوفة"
        lines.append(f"{_emoji(e, 'plus')} {pack.code} · {pack.credits} تصميم · {pack.stars_price} Stars · {state}")
    await _send_panel(callback, "\n".join(lines), _back())


@router.callback_query(F.data == "adm:payments")
async def admin_payments(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    e = await _emoji_settings(session)
    payments = (await session.execute(select(Payment).order_by(Payment.created_at.desc()).limit(12))).scalars().all()
    lines = [f"{_emoji(e, 'plans')} <b>المدفوعات</b>", ""]
    for payment in payments:
        lines.append(f"{_emoji(e, 'success' if payment.status == PaymentStatus.APPROVED.value else 'warning')} {payment.provider} · {payment.stars_amount or '-'} Stars · {payment.status} · {payment.created_at:%Y-%m-%d %H:%M}")
    await _send_panel(callback, "\n".join(lines), _back())


@router.callback_query(F.data == "adm:jobs")
async def admin_jobs(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    e = await _emoji_settings(session)
    jobs = (await session.execute(select(GenerationJob).order_by(GenerationJob.created_at.desc()).limit(12))).scalars().all()
    lines = [f"{_emoji(e, 'ai')} <b>وظائف التوليد</b>", ""]
    for job in jobs:
        slot = "success" if job.status == JobStatus.SUCCEEDED.value else "warning" if job.status == JobStatus.FAILED.value else "ai"
        lines.append(f"{_emoji(e, slot)} {job.id} · {job.status} · {job.progress}% · {job.stage or '-'}")
    await _send_panel(callback, "\n".join(lines), _back())


@router.callback_query(F.data == "adm:emoji")
async def admin_emoji(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    e = await _emoji_settings(session)
    lines = [f"{_emoji(e, 'brand')} <b>إدارة Premium Emoji</b>", ""]
    for slot in EMOJI_SLOTS:
        state = "مرتبط" if e.get(f"{EMOJI_PREFIX}{slot}") else "غير مرتبط"
        lines.append(f"{_emoji(e, slot)} <code>{slot}</code>: {state}")
    lines.extend([
        "",
        f"{_emoji(e, 'research')} لربط أي أيقونة أرسل: /emoji_bind SLOT ثم الـPremium Emoji في نفس الرسالة.",
        f"{_emoji(e, 'support')} الحالة الكاملة: /emoji_status",
    ])
    await _send_panel(callback, "\n".join(lines), _back())


@router.callback_query(F.data == "adm:broadcast")
async def admin_broadcast(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    e = await _emoji_settings(session)
    await _send_panel(
        callback,
        f"{_emoji(e, 'support')} <b>الإرسال الجماعي</b>\n\nاستخدم /broadcast ثم أرسل الرسالة التالية. سيتم الإرسال للمستخدمين النشطين مع تقرير بالنجاح والفشل.",
        _back(),
    )


@router.callback_query(F.data == "adm:message")
async def admin_message(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    e = await _emoji_settings(session)
    await _send_panel(
        callback,
        f"{_emoji(e, 'support')} <b>مراسلة مستخدم</b>\n\nاستخدم:\n/admin_message TELEGRAM_ID\nثم أرسل الرسالة التي تريد إرسالها.",
        _back(),
    )


@router.callback_query(F.data.regexp(r"^adm:user_credit:[0-9a-f-]{36}$"))
async def admin_user_credit_help(callback: CallbackQuery) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    await callback.answer("استخدم /admin_credit TELEGRAM_ID AMOUNT", show_alert=True)


@router.callback_query(F.data.regexp(r"^adm:user_message:[0-9]+$"))
async def admin_user_message_help(callback: CallbackQuery) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    await callback.answer("استخدم /admin_message TELEGRAM_ID ثم أرسل الرسالة.", show_alert=True)


@router.message(Command("admin_credit"))
async def admin_credit_command(message: Message, session: AsyncSession) -> None:
    if not _owner(message):
        await message.answer("غير مصرح.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit() or int(parts[2]) <= 0:
        await message.answer("الاستخدام: /admin_credit TELEGRAM_ID AMOUNT")
        return
    user = (await session.execute(select(User).where(User.telegram_id == int(parts[1])))).scalar_one_or_none()
    if user is None:
        await message.answer("المستخدم غير موجود.")
        return
    user.design_credits += int(parts[2])
    await session.commit()
    e = await _emoji_settings(session)
    await message.answer(
        f"{_emoji(e, 'success')} تمت إضافة {parts[2]} رصيد تصميم للمستخدم {parts[1]}.",
        parse_mode="HTML",
    )
