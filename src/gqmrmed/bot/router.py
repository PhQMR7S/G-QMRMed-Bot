"""Telegram handlers for onboarding and generation intake."""

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.bot.service import create_user_generation, provision_user
from gqmrmed.contracts.generation import GenerationRequest, InputType
from gqmrmed.db.models import Plan, User
from gqmrmed.services.subscriptions import activate_code
from gqmrmed.services.usage import QuotaExceededError

router = Router(name="gqmrmed")

WELCOME_TEXT = (
    "مرحباً بك في GQMRMed 🩺\n\n"
    "أرسل موضوعاً طبياً، نصاً، صورة، ملفاً، صوتاً أو فيديو، "
    "وسيعالجه النظام كطلب تصميم طبي.\n\n"
    "الخطة المجانية: 3 تصاميم يومياً.\n"
    "استخدم /plans لعرض الخطط أو /activate CODE لتفعيل اشتراك."
)


async def _user_from_message(session: AsyncSession, message: Message) -> User:
    """Provision the Telegram identity using only Telegram profile fields."""
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


@router.message(CommandStart())
async def start_handler(message: Message, session: AsyncSession) -> None:
    """Register the user and show the minimal onboarding message."""
    async with session.begin():
        user = await _user_from_message(session, message)
    if not user.is_active:
        await message.answer("هذا الحساب غير نشط حالياً.")
        return
    await message.answer(WELCOME_TEXT)


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    """Show the supported input and command surface."""
    await message.answer(
        "أرسل أي محتوى طبي تريد تحويله إلى تصميم.\n\n"
        "/start — بدء الاستخدام\n"
        "/plans — الخطط\n"
        "/activate CODE — تفعيل كود اشتراك\n"
        "/help — المساعدة"
    )


@router.message(Command("plans"))
async def plans_handler(message: Message, session: AsyncSession) -> None:
    """Display the active public plans."""
    result = await session.execute(
        select(Plan)
        .where(Plan.is_active.is_(True))
        .order_by(Plan.price.asc(), Plan.code.asc())
    )
    plans = result.scalars().all()
    lines = ["الخطط المتاحة:"]
    for plan in plans:
        limit = "غير محدود" if plan.daily_limit is None else f"{plan.daily_limit}/اليوم"
        duration = "مستمر" if plan.duration_days is None else f"{plan.duration_days} يوم"
        lines.append(f"• {plan.name}: ${plan.price} — {duration} — {limit}")
    await message.answer("\n".join(lines))


@router.message(Command("activate"))
async def activate_handler(message: Message, session: AsyncSession) -> None:
    """Consume a single-use activation code safely."""
    if message.from_user is None:
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip():
        await message.answer("أرسل الكود بهذا الشكل:\n/activate GQMR-PLUS-XXXX-XXXX")
        return

    try:
        async with session.begin():
            user = await _user_from_message(session, message)
            if not user.is_active:
                raise PermissionError("user_inactive")
            subscription = await activate_code(
                session,
                user_id=user.id,
                raw_code=parts[1],
            )
    except PermissionError:
        await message.answer("هذا الحساب غير نشط حالياً.")
        return
    except ValueError as exc:
        code = str(exc)
        messages = {
            "invalid_or_used_activation_code": "الكود غير صالح أو مستخدم مسبقاً.",
            "activation_code_expired": "انتهت صلاحية كود التفعيل.",
            "plan_unavailable": "الخطة المرتبطة بالكود غير متاحة حالياً.",
            "invalid_subscription_duration": "مدة الاشتراك غير صالحة.",
        }
        await message.answer(messages.get(code, "تعذر تفعيل الكود."))
        return

    expires = subscription.expires_at.isoformat() if subscription.expires_at else "غير محدد"
    await message.answer(f"تم تفعيل الاشتراك بنجاح ✅\nينتهي: {expires}")


async def _submit_generation(
    message: Message,
    session: AsyncSession,
    *,
    request: GenerationRequest,
) -> None:
    """Create a job and atomically reserve one usage slot."""
    try:
        async with session.begin():
            user = await _user_from_message(session, message)
            queued = await create_user_generation(session, user=user, request=request)
    except QuotaExceededError:
        await message.answer(
            "انتهت حصتك اليومية المجانية (3 تصاميم).\n"
            "استخدم /plans لعرض الخطط المتاحة."
        )
        return
    except PermissionError:
        await message.answer("هذا الحساب غير نشط حالياً.")
        return

    await message.answer(
        "تم استلام الطلب ووضعه في قائمة الانتظار ⏳\n"
        f"رقم الطلب: {queued.job_id}"
    )


@router.message()
async def content_handler(message: Message, session: AsyncSession) -> None:
    """Accept text and Telegram media as normalized generation input."""
    text = (message.text or message.caption or "").strip() or None
    request: GenerationRequest | None = None

    if message.photo:
        item = message.photo[-1]
        request = GenerationRequest(
            input_type=InputType.MIXED if text else InputType.IMAGE,
            text=text,
            storage_key=f"telegram://photo/{item.file_id}",
            mime_type="image/jpeg",
            metadata={
                "telegram_file_id": item.file_id,
                "telegram_message_id": message.message_id,
                "width": item.width,
                "height": item.height,
            },
        )
    elif message.document:
        item = message.document
        request = GenerationRequest(
            input_type=InputType.MIXED if text else InputType.DOCUMENT,
            text=text,
            storage_key=f"telegram://document/{item.file_id}",
            mime_type=item.mime_type,
            metadata={
                "telegram_file_id": item.file_id,
                "telegram_message_id": message.message_id,
                "file_name": item.file_name,
                "file_size": item.file_size,
            },
        )
    elif message.audio:
        item = message.audio
        request = GenerationRequest(
            input_type=InputType.MIXED if text else InputType.AUDIO,
            text=text,
            storage_key=f"telegram://audio/{item.file_id}",
            mime_type=item.mime_type or "audio/mpeg",
            metadata={
                "telegram_file_id": item.file_id,
                "telegram_message_id": message.message_id,
                "file_name": item.file_name,
                "duration": item.duration,
                "file_size": item.file_size,
            },
        )
    elif message.voice:
        item = message.voice
        request = GenerationRequest(
            input_type=InputType.MIXED if text else InputType.AUDIO,
            text=text,
            storage_key=f"telegram://voice/{item.file_id}",
            mime_type=item.mime_type or "audio/ogg",
            metadata={
                "telegram_file_id": item.file_id,
                "telegram_message_id": message.message_id,
                "duration": item.duration,
                "file_size": item.file_size,
            },
        )
    elif message.video:
        item = message.video
        request = GenerationRequest(
            input_type=InputType.MIXED if text else InputType.VIDEO,
            text=text,
            storage_key=f"telegram://video/{item.file_id}",
            mime_type=item.mime_type or "video/mp4",
            metadata={
                "telegram_file_id": item.file_id,
                "telegram_message_id": message.message_id,
                "width": item.width,
                "height": item.height,
                "duration": item.duration,
                "file_size": item.file_size,
            },
        )
    elif text:
        request = GenerationRequest(input_type=InputType.TEXT, text=text)

    if request is None:
        await message.answer("أرسل نصاً أو صورة أو ملفاً أو صوتاً أو فيديو.")
        return

    await _submit_generation(message, session, request=request)
