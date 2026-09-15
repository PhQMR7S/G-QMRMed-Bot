"""Telegram handlers for onboarding and generation intake."""

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.bot.service import create_user_generation, provision_user
from gqmrmed.contracts.generation import GenerationRequest, InputType
from gqmrmed.db.models import Plan, User
from gqmrmed.services.subscriptions import activate_code
from gqmrmed.services.usage import QuotaExceededError

router = Router(name="gqmrmed")

WELCOME_TEXT = (
    "🩺 <b>GQMRMed</b>\n"
    "<i>Medical Design Intelligence</i>\n\n"
    "حوّل المعلومة الطبية إلى تصميم بصري منظم، واضح، وقابل للمشاركة.\n\n"
    "أرسل <b>موضوعاً أو نصاً أو صورة أو ملفاً أو صوتاً أو فيديو</b>، "
    "وسيتولى النظام مراحل البحث والتحقق والتركيب البصري.\n\n"
    "🎁 <b>FREE</b> · تصميم واحد يومياً\n"
    "اختر من القائمة أدناه للبدء."
)


def _start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✦ إنشاء تصميم", callback_data="menu:generate"),
                InlineKeyboardButton(text="▣ الخطط", callback_data="menu:plans"),
            ],
            [
                InlineKeyboardButton(text="ⓘ طريقة الاستخدام", callback_data="menu:help"),
                InlineKeyboardButton(text="⌁ الشروط والدعم", callback_data="menu:terms"),
            ],
        ]
    )


def _back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="‹ القائمة الرئيسية", callback_data="menu:home")]]
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


def _with_chat_metadata(request: GenerationRequest, message: Message) -> GenerationRequest:
    """Attach only the Telegram routing metadata required for async delivery."""
    if message.chat.id <= 0:
        raise ValueError("telegram_chat_id_required")
    metadata = dict(request.metadata or {})
    metadata["telegram_chat_id"] = message.chat.id
    metadata["telegram_message_id"] = message.message_id
    return request.model_copy(update={"metadata": metadata})


@router.message(CommandStart())
async def start_handler(message: Message, session: AsyncSession) -> None:
    """Register the user and show the polished onboarding menu."""
    async with session.begin():
        user = await _user_from_message(session, message)
    if not user.is_active:
        await message.answer("هذا الحساب غير نشط حالياً.")
        return
    await message.answer(WELCOME_TEXT, parse_mode="HTML", reply_markup=_start_keyboard())


@router.callback_query(F.data == "menu:home")
async def menu_home_callback(callback: CallbackQuery) -> None:
    if callback.message is not None:
        await callback.message.edit_text(WELCOME_TEXT, parse_mode="HTML", reply_markup=_start_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu:generate")
async def menu_generate_callback(callback: CallbackQuery) -> None:
    if callback.message is not None:
        await callback.message.edit_text(
            "✦ <b>إنشاء تصميم طبي</b>\n\n"
            "أرسل الآن الموضوع أو النص أو الصورة أو الملف أو الصوت أو الفيديو الذي تريد تحويله إلى تصميم.\n\n"
            "يمكنك أيضاً إرسال النص مباشرة دون اختيار أي أمر إضافي.",
            parse_mode="HTML",
            reply_markup=_back_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:help")
async def menu_help_callback(callback: CallbackQuery) -> None:
    if callback.message is not None:
        await callback.message.edit_text(
            "ⓘ <b>طريقة الاستخدام</b>\n\n"
            "1. اختر «إنشاء تصميم».\n"
            "2. أرسل المحتوى الطبي.\n"
            "3. يجري النظام البحث والتحقق والتركيب البصري.\n"
            "4. يصلك التصميم النهائي داخل Telegram.\n\n"
            "<b>المدخلات:</b> نص · صورة · ملف · صوت · فيديو",
            parse_mode="HTML",
            reply_markup=_back_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:terms")
async def menu_terms_callback(callback: CallbackQuery) -> None:
    if callback.message is not None:
        await callback.message.edit_text(
            "⌁ <b>الاشتراكات والدعم</b>\n\n"
            "الخطة المجانية تمنح <b>تصميماً واحداً يومياً</b>.\n"
            "للاشتراكات المدفوعة استخدم «الخطط».\n"
            "لشروط الشراء قبل الدفع استخدم /terms.\n"
            "لدعم المدفوعات استخدم /paysupport.",
            parse_mode="HTML",
            reply_markup=_back_keyboard(),
        )
    await callback.answer()


async def _show_plans(target: Message, session: AsyncSession, *, edit: bool = False, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    result = await session.execute(select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.price.asc(), Plan.code.asc()))
    plans = result.scalars().all()
    lines = ["▣ <b>خطط GQMRMed</b>\n"]
    for plan in plans:
        limit = "غير محدود" if plan.daily_limit is None else f"{plan.daily_limit}/اليوم"
        duration = "مستمر" if plan.duration_days is None else f"{plan.duration_days} يوم"
        stars = "—" if plan.stars_price is None else f"{plan.stars_price} ⭐"
        lines.append(f"<b>{plan.name}</b> · ${plan.price} · {duration} · {limit} · {stars}")
    lines.append("\nلشراء خطة مدفوعة استخدم /terms.")
    text = "\n".join(lines)
    if edit:
        await target.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await target.answer(text, parse_mode="HTML")


@router.callback_query(F.data == "menu:plans")
async def menu_plans_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.message is None:
        await callback.answer("تعذر عرض الخطط.", show_alert=True)
        return
    await _show_plans(callback.message, session, edit=True, reply_markup=_back_keyboard())
    await callback.answer()


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(
        "ⓘ <b>مساعدة GQMRMed</b>\n\n"
        "أرسل أي محتوى طبي تريد تحويله إلى تصميم.\n\n"
        "/start — القائمة الرئيسية\n"
        "/plans — الخطط\n"
        "/terms — شروط الشراء والموافقة قبل الدفع\n"
        "/activate CODE — تفعيل كود إداري صالح\n"
        "/paysupport — دعم المدفوعات\n"
        "/help — المساعدة",
        parse_mode="HTML",
    )


@router.message(Command("plans"))
async def plans_handler(message: Message, session: AsyncSession) -> None:
    await _show_plans(message, session)


@router.message(Command("buy"))
async def buy_handler(message: Message) -> None:
    await message.answer(
        "لأن GQMRMed خدمة رقمية داخل Telegram، يتم الدفع داخل Telegram حصراً عبر Telegram Stars.\n\n"
        "استخدم /terms ثم اختر PLUS أو PRO."
    )


@router.message(Command("activate"))
async def activate_handler(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip():
        await message.answer("أرسل الكود بهذا الشكل:\n/activate GQMR-PLUS-XXXXXX-XXXXXX")
        return
    try:
        async with session.begin():
            user = await _user_from_message(session, message)
            if not user.is_active:
                raise PermissionError("user_inactive")
            subscription = await activate_code(session, user_id=user.id, raw_code=parts[1])
    except PermissionError:
        await message.answer("هذا الحساب غير نشط حالياً.")
        return
    except ValueError as exc:
        messages = {
            "invalid_or_used_activation_code": "الكود غير صالح أو مستخدم مسبقاً.",
            "activation_code_expired": "انتهت صلاحية كود التفعيل.",
            "plan_unavailable": "الخطة المرتبطة بالكود غير متاحة حالياً.",
            "invalid_subscription_duration": "مدة الاشتراك غير صالحة.",
        }
        await message.answer(messages.get(str(exc), "تعذر تفعيل الكود."))
        return
    expires = subscription.expires_at.isoformat() if subscription.expires_at else "غير محدد"
    await message.answer(f"تم تفعيل الاشتراك بنجاح ✅\nينتهي: {expires}")


async def _submit_generation(message: Message, session: AsyncSession, *, request: GenerationRequest) -> None:
    request = _with_chat_metadata(request, message)
    try:
        async with session.begin():
            user = await _user_from_message(session, message)
            await create_user_generation(session, user=user, request=request)
    except QuotaExceededError:
        await message.answer("انتهت حصتك اليومية حسب خطتك الحالية.\nاستخدم /plans لعرض حدود الخطط المتاحة.")
    except PermissionError:
        await message.answer("هذا الحساب غير نشط حالياً.")


@router.message()
async def content_handler(message: Message, session: AsyncSession) -> None:
    """Accept text and Telegram media as normalized generation input."""
    text = (message.text or message.caption or "").strip() or None
    request: GenerationRequest | None = None
    if message.photo:
        photo = message.photo[-1]
        request = GenerationRequest(input_type=InputType.MIXED if text else InputType.IMAGE, text=text, storage_key=f"telegram://photo/{photo.file_id}", mime_type="image/jpeg", metadata={"telegram_file_id": photo.file_id, "width": photo.width, "height": photo.height})
    elif message.document:
        document = message.document
        request = GenerationRequest(input_type=InputType.MIXED if text else InputType.DOCUMENT, text=text, storage_key=f"telegram://document/{document.file_id}", mime_type=document.mime_type, metadata={"telegram_file_id": document.file_id, "file_name": document.file_name, "file_size": document.file_size})
    elif message.audio:
        audio = message.audio
        request = GenerationRequest(input_type=InputType.MIXED if text else InputType.AUDIO, text=text, storage_key=f"telegram://audio/{audio.file_id}", mime_type=audio.mime_type or "audio/mpeg", metadata={"telegram_file_id": audio.file_id, "file_name": audio.file_name, "duration": audio.duration, "file_size": audio.file_size})
    elif message.voice:
        voice = message.voice
        request = GenerationRequest(input_type=InputType.MIXED if text else InputType.AUDIO, text=text, storage_key=f"telegram://voice/{voice.file_id}", mime_type=voice.mime_type or "audio/ogg", metadata={"telegram_file_id": voice.file_id, "duration": voice.duration, "file_size": voice.file_size})
    elif message.video:
        video = message.video
        request = GenerationRequest(input_type=InputType.MIXED if text else InputType.VIDEO, text=text, storage_key=f"telegram://video/{video.file_id}", mime_type=video.mime_type or "video/mp4", metadata={"telegram_file_id": video.file_id, "width": video.width, "height": video.height, "duration": video.duration, "file_size": video.file_size})
    elif text:
        request = GenerationRequest(input_type=InputType.TEXT, text=text)
    if request is None:
        await message.answer("أرسل نصاً أو صورة أو ملفاً أو صوتاً أو فيديو.")
        return
    await _submit_generation(message, session, request=request)
