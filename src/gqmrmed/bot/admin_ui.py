"""Owner-only in-bot administration panel for GQMRMed."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.bot.service import provision_user
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
    SubscriptionStatus,
    User,
)
from gqmrmed.services.activation import create_activation_code
from gqmrmed.services.payments import set_payment_status

router = Router(name="gqmrmed-admin-ui")
OWNER_TELEGRAM_ID = 6246913670


def _owner(message: Message | CallbackQuery) -> bool:
    return message.from_user is not None and message.from_user.id == OWNER_TELEGRAM_ID


def _kb(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
    async def count(model: type[object], *conditions: object) -> int:
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
    today = datetime.now(UTC).date()
    today_jobs = int(await session.scalar(select(func.count()).select_from(GenerationJob).where(func.date(GenerationJob.created_at) == today)) or 0)
    today_users = int(await session.scalar(select(func.count()).select_from(User).where(func.date(User.created_at) == today)) or 0)
    return (
        "<b>لوحة معلومات GQMRMed</b>\n\n"
        f"المستخدمون: {c['users']}\n"
        f"النشطون: {c['active']}\n"
        f"الموقوفون: {c['blocked']}\n"
        f"مستخدمون جدد اليوم: {today_users}\n\n"
        f"الخطط النشطة: {c['plans']}\n"
        f"أكواد غير مستخدمة: {c['codes']}\n"
        f"مدفوعات معلقة: {c['pending']}\n\n"
        f"وظائف اليوم: {today_jobs}\n"
        f"في الانتظار: {c['queued']}\n"
        f"قيد التنفيذ: {c['running']}\n"
        f"الفاشلة: {c['failed']}"
    )


async def _send_panel(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    await callback.answer()


@router.message(Command("admin"))
async def admin_start(message: Message, session: AsyncSession) -> None:
    if not _owner(message):
        await message.answer("هذا القسم متاح لمالك البوت فقط.")
        return
    await message.answer(await _overview_text(session), parse_mode="HTML", reply_markup=_home_kb())


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
    users = (await session.execute(select(User).order_by(User.created_at.desc()).limit(12))).scalars().all()
    rows: list[list[InlineKeyboardButton]] = []
    lines = ["<b>إدارة المستخدمين</b>", ""]
    for user in users:
        name = user.first_name or user.username or str(user.telegram_id)
        state = "نشط" if user.is_active else "موقوف"
        lines.append(f"{name} · {user.telegram_id} · {state}")
        rows.append([InlineKeyboardButton(text=f"{name} · {user.telegram_id}", callback_data=f"adm:user:{user.id}")])
    rows.extend([
        [InlineKeyboardButton(text="بحث برقم Telegram", callback_data="adm:userhelp")],
        [InlineKeyboardButton(text="لوحة الإدارة", callback_data="adm:home")],
    ])
    await _send_panel(callback, "\n".join(lines), _kb(rows))


@router.callback_query(F.data == "adm:userhelp")
async def admin_user_help(callback: CallbackQuery) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    await _send_panel(callback, "<b>بحث وإدارة مستخدم</b>\n\nاستخدم:\n/admin_user TELEGRAM_ID\n\nثم ستظهر لك بيانات المستخدم وأدوات الإيقاف والحظر وإلغاء الحظر وإضافة الرصيد.", _back())


async def _user_text(session: AsyncSession, user: User) -> str:
    subs = (await session.execute(select(Subscription).where(Subscription.user_id == user.id).order_by(Subscription.created_at.desc()).limit(3))).scalars().all()
    used = int(await session.scalar(select(func.coalesce(func.sum(DailyUsage.committed), 0)).where(DailyUsage.user_id == user.id)) or 0)
    jobs = int(await session.scalar(select(func.count()).select_from(GenerationJob).where(GenerationJob.user_id == user.id)) or 0)
    plans = ", ".join(str(s.status) for s in subs) or "لا يوجد"
    return (
        "<b>ملف المستخدم</b>\n\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"الاسم: {user.first_name or '-'} {user.last_name or ''}\n"
        f"Username: @{user.username or '-'}\n"
        f"الحالة: {'نشط' if user.is_active else 'موقوف'}\n"
        f"الرصيد: {user.design_credits}\n"
        f"الاستخدام المتراكم: {used}\n"
        f"وظائف التوليد: {jobs}\n"
        f"الاشتراكات الأخيرة: {plans}"
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
    user = await _set_user_state(session, UUID(raw_id), active=(None if action != "adm:user_toggle" else None), banned=(action == "adm:user_ban"))
    if user is not None and action == "adm:user_toggle":
        user.is_active = not user.is_active
    elif user is not None and action == "adm:user_unban":
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
    plans = (await session.execute(select(Plan).order_by(Plan.price.asc(), Plan.code.asc()))).scalars().all()
    lines = ["<b>إدارة الخطط والاشتراكات</b>", ""]
    rows: list[list[InlineKeyboardButton]] = []
    for plan in plans:
        state = "مفعلة" if plan.is_active else "موقوفة"
        price = f"{plan.stars_price} Stars" if plan.stars_price is not None else "مجانية"
        lines.append(f"{plan.code} · {plan.name} · {plan.daily_limit or '∞'}/يوم · {price} · {state}")
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
    await callback.answer("تم تحديث الخطة.")
    await admin_plans(callback, session)


@router.callback_query(F.data == "adm:codes")
async def admin_codes(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    plans = (await session.execute(select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.code))).scalars().all()
    rows = [[InlineKeyboardButton(text=f"إنشاء {p.code} · 30 يوم", callback_data=f"adm:code:{p.id}:30")] for p in plans]
    rows += [[InlineKeyboardButton(text=f"إنشاء {p.code} · 150 يوم", callback_data=f"adm:code:{p.id}:150")] for p in plans]
    rows += [[InlineKeyboardButton(text=f"إنشاء {p.code} · 365 يوم", callback_data=f"adm:code:{p.id}:365")] for p in plans]
    rows.append([InlineKeyboardButton(text="عرض الأكواد غير المستخدمة", callback_data="adm:code_list")])
    rows.append([InlineKeyboardButton(text="لوحة الإدارة", callback_data="adm:home")])
    await _send_panel(callback, "<b>إدارة أكواد الاشتراك</b>\n\nاختر الخطة والمدة لإنشاء كود جديد. الأكواد تُحفظ كـhash ولا يمكن استعادتها من قاعدة البيانات.", _kb(rows))


@router.callback_query(F.data.regexp(r"^adm:code:[0-9a-f-]{36}:(30|150|365)$"))
async def admin_create_code(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    if not callback.data:
        return
    _, _, raw_plan, raw_days = callback.data.split(":")
    plan = await session.get(Plan, UUID(raw_plan))
    if plan is None or not plan.is_active:
        await callback.answer("الخطة غير متاحة.", show_alert=True)
        return
    async with session.begin():
        _, plaintext = await create_activation_code(session, plan=plan, duration_days=int(raw_days), created_by=None)
    await _send_panel(callback, f"<b>تم إنشاء كود اشتراك</b>\n\nالخطة: {plan.code}\nالمدة: {raw_days} يوم\n\nالكود:\n<code>{plaintext}</code>\n\nأرسله للمستخدم المستحق فقط.", _back())


@router.callback_query(F.data == "adm:code_list")
async def admin_code_list(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    codes = (await session.execute(select(ActivationCode).where(ActivationCode.status == ActivationCodeStatus.UNUSED.value).order_by(ActivationCode.created_at.desc()).limit(30))).scalars().all()
    await _send_panel(callback, f"<b>الأكواد غير المستخدمة</b>\n\nعددها المعروض: {len(codes)}\n\nالأكواد لا يمكن عرض نصها الأصلي بعد الإنشاء لأنها مخزنة بشكل آمن كـhash.", _back())


@router.callback_query(F.data == "adm:credits")
async def admin_credits(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    packs = (await session.execute(select(CreditPack).order_by(CreditPack.stars_price))).scalars().all()
    lines = ["<b>حصص التصميم</b>", ""]
    for p in packs:
        lines.append(f"{p.code} · {p.credits} تصميم · {p.stars_price} Stars · {'مفعلة' if p.is_active else 'موقوفة'}")
    lines.append("\nتغيير الأسعار أو عدد التصاميم يتم عبر إعدادات قاعدة البيانات/إدارة الخطط الموثقة؛ لا توجد أسعار مخفية داخل البوت.")
    await _send_panel(callback, "\n".join(lines), _back())


@router.callback_query(F.data == "adm:payments")
async def admin_payments(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    payments = (await session.execute(select(Payment).order_by(Payment.created_at.desc()).limit(20))).scalars().all()
    lines = ["<b>المدفوعات</b>", ""]
    for p in payments:
        lines.append(f"{str(p.id)[:8]} · {p.status} · {p.provider} · {p.stars_amount or p.amount} · {p.currency}")
    lines.append("\nالدفع عبر Telegram Stars يُعتمد آلياً بعد successful_payment؛ لا يمكن اعتماد فاتورة Stars يدوياً.")
    await _send_panel(callback, "\n".join(lines), _back())


@router.callback_query(F.data == "adm:jobs")
async def admin_jobs(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    jobs = (await session.execute(select(GenerationJob).order_by(GenerationJob.created_at.desc()).limit(15))).scalars().all()
    lines = ["<b>مراقبة وظائف التوليد</b>", ""]
    for job in jobs:
        stage = job.stage or "-"
        lines.append(f"{str(job.id)[:8]} · {job.status} · {job.progress}% · {stage}")
    await _send_panel(callback, "\n".join(lines), _back())


@router.callback_query(F.data == "adm:broadcast")
async def admin_broadcast_help(callback: CallbackQuery) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    await _send_panel(callback, "<b>الإرسال الجماعي</b>\n\nأرسل:\n<code>/broadcast نص الإعلان</code>\n\nسيتم إرسال الرسالة إلى المستخدمين النشطين فقط، مع تجاهل الحسابات التي تمنع البوت وتسجيل نتيجة الإرسال.", _back())


@router.message(Command("broadcast"))
async def admin_broadcast(message: Message, session: AsyncSession) -> None:
    if not _owner(message):
        await message.answer("غير مصرح.")
        return
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer("الاستخدام: /broadcast نص الإعلان")
        return
    user_ids = (await session.execute(select(User.telegram_id).where(User.is_active.is_(True)))).scalars().all()
    await message.answer(f"تم بدء الإرسال إلى {len(user_ids)} مستخدم نشط.\n\nالنص: {text[:500]}")
    asyncio.create_task(_broadcast(message, list(user_ids), text))


async def _broadcast(message: Message, user_ids: list[int], text: str) -> None:
    bot = message.bot
    sent = failed = 0
    for telegram_id in user_ids:
        try:
            await bot.send_message(telegram_id, text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.06)
    try:
        await bot.send_message(OWNER_TELEGRAM_ID, f"انتهى الإرسال الجماعي.\nنجح: {sent}\nفشل: {failed}")
    except Exception:
        pass


@router.callback_query(F.data == "adm:message")
async def admin_message_help(callback: CallbackQuery) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    await _send_panel(callback, "<b>مراسلة مستخدم</b>\n\nاستخدم:\n<code>/admin_message TELEGRAM_ID نص الرسالة</code>", _back())


@router.callback_query(F.data.regexp(r"^adm:user_message:-?[0-9]+$"))
async def admin_user_message_help(callback: CallbackQuery) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    telegram_id = callback.data.rsplit(":", 1)[1] if callback.data else ""
    await _send_panel(callback, f"<b>مراسلة المستخدم</b>\n\nاستخدم:\n<code>/admin_message {telegram_id} نص الرسالة</code>", _back())


@router.message(Command("admin_message"))
async def admin_message(message: Message) -> None:
    if not _owner(message):
        await message.answer("غير مصرح.")
        return
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3 or not parts[1].lstrip("-").isdigit():
        await message.answer("الاستخدام: /admin_message TELEGRAM_ID نص الرسالة")
        return
    try:
        await message.bot.send_message(int(parts[1]), parts[2])
    except Exception as exc:
        await message.answer(f"فشل الإرسال: {type(exc).__name__}")
        return
    await message.answer("تم إرسال الرسالة.")


@router.callback_query(F.data == "adm:emoji")
async def admin_emoji(callback: CallbackQuery) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    await _send_panel(callback, "<b>Premium Emoji</b>\n\nإدارة الربط من داخل البوت:\n<code>/emoji_status</code>\n\nلربط رمز بمساحة:\n<code>/emoji_bind SLOT PremiumEmoji</code>\n\nالمساحات تشمل الهوية، الطب، الإنشاء، الخطط، البحث، الذكاء الاصطناعي، التصميم، النجاح، التحذير، الدعم وFREE/PLUS/PRO.", _back())


@router.callback_query(F.data == "adm:home")
async def admin_home_duplicate(callback: CallbackQuery, session: AsyncSession) -> None:
    # Kept unreachable intentionally? This handler name conflicts with admin_home above.
    return
