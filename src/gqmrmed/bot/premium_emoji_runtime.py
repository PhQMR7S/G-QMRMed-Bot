"""Runtime Premium Emoji resolver shared by all Telegram UI surfaces."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import InlineKeyboardButton, TelegramObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.db.models import SystemSetting

PREFIX = "telegram_emoji."
BANK_KEY = f"{PREFIX}bank"

_ORIGINAL_INLINE_BUTTON = InlineKeyboardButton
_BUTTON_EMOJI_IDS: list[str] = []
_BUTTON_SETTINGS: dict[str, str] = {}


def _classify(alt: str | None) -> str:
    value = alt or ""
    groups = {
        "medical": {"⚕️", "🩺", "💊", "🧬", "🧪", "🔬", "🫀", "🫁", "🧠", "🏥"},
        "research": {"🔎", "🔍", "📚", "📖", "📊", "📈", "📋", "📝", "ℹ️"},
        "design": {"🎨", "🖌️", "🖊️", "✏️", "🖼️", "📐", "🧩"},
        "ai": {"🤖", "🧠", "💡", "✨", "⚙️"},
        "success": {"✅", "✔️", "☑️", "👍", "🎉"},
        "warning": {"⚠️", "❗", "❌", "⛔", "🚫"},
        "support": {"❓", "💬", "📞", "🆘", "🙋"},
        "plans": {"⭐", "🌟", "💎", "👑", "🏆"},
        "create": {"➕", "🪄", "🛠️", "🔧"},
    }
    for slot, values in groups.items():
        if value in values:
            return slot
    return "brand"


async def emoji_settings(session: AsyncSession) -> dict[str, str]:
    """Load the complete captured bank and exact Telegram-provided alts."""
    rows = (
        await session.execute(
            select(SystemSetting).where(SystemSetting.key.like(f"{PREFIX}%"))
        )
    ).scalars().all()
    settings = {row.key: row.value for row in rows}
    raw_bank = settings.get(BANK_KEY)
    bank: list[dict[str, Any]] = []
    if raw_bank:
        try:
            parsed = json.loads(raw_bank)
        except json.JSONDecodeError:
            parsed = []
        if isinstance(parsed, list):
            bank = [item for item in parsed if isinstance(item, dict)]

    ids: list[str] = []
    for item in bank:
        emoji_id = str(item.get("id") or "")
        alt = str(item.get("alt") or "")
        if emoji_id:
            ids.append(emoji_id)
        if emoji_id and alt:
            settings[f"{PREFIX}alt:{emoji_id}"] = alt
            settings[f"{PREFIX}slot:{emoji_id}"] = str(
                item.get("slot") or _classify(alt)
            )

    settings[f"{PREFIX}count"] = str(len(ids))
    settings[f"{PREFIX}ids"] = json.dumps(ids, ensure_ascii=False, separators=(",", ":"))
    _refresh_button_pool(ids, settings)
    _BUTTON_SETTINGS.clear()
    _BUTTON_SETTINGS.update(settings)
    return settings


def _bank_ids(settings: Mapping[str, str]) -> list[str]:
    raw = settings.get(f"{PREFIX}ids", "[]")
    try:
        ids = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [str(value) for value in ids if value]


def _refresh_button_pool(ids: list[str], settings: Mapping[str, str]) -> None:
    """Refresh the captured button palette while preserving bank order and uniqueness."""
    global _BUTTON_EMOJI_IDS
    _BUTTON_EMOJI_IDS = [
        emoji_id
        for emoji_id in ids
        if settings.get(f"{PREFIX}alt:{emoji_id}")
    ]


def _button_slot(text: str | None, callback_data: str | None) -> str:
    """Resolve a stable semantic slot from a button's action, never randomly."""
    action = (callback_data or "").lower()
    text_value = (text or "").lower()
    exact = {
        "pro:generate": "create",
        "pro:plans": "plans",
        "pro:credits": "design",
        "pro:account": "brand",
        "pro:help": "research",
        "pro:payment": "plans",
        "pro:terms": "warning",
        "pro:support": "support",
        "pro:home": "brand",
        "adm:users": "medical",
        "adm:overview": "research",
        "adm:plans": "plans",
        "adm:codes": "success",
        "adm:credits": "design",
        "adm:payments": "plans",
        "adm:jobs": "ai",
        "adm:broadcast": "support",
        "adm:message": "support",
        "adm:emoji": "design",
        "adm:home": "brand",
        "menu:generate": "create",
        "menu:plans": "plans",
        "menu:help": "research",
        "menu:terms": "warning",
        "menu:home": "brand",
        "credits:terms": "warning",
        "credits:menu": "design",
    }
    if action in exact:
        return exact[action]
    if action.startswith(("adm:user_toggle:", "adm:user_unban:")):
        return "success"
    if action.startswith("adm:user_ban:"):
        return "warning"
    if action.startswith(("adm:user_credit:", "credits:")):
        return "design"
    if action.startswith(("adm:user_message:", "adm:message:")):
        return "support"
    if action.startswith("stars:"):
        return "plans"

    keyword_slots = (
        ("إنشاء", "create"),
        ("شراء", "plans"),
        ("خطة", "plans"),
        ("اشتراك", "plans"),
        ("دعم", "support"),
        ("مساعدة", "support"),
        ("بحث", "research"),
        ("تحقق", "research"),
        ("إدارة", "medical"),
        ("مستخدم", "medical"),
        ("دفع", "plans"),
        ("رصيد", "design"),
        ("حصة", "design"),
        ("حظر", "warning"),
        ("إيقاف", "warning"),
        ("تفعيل", "success"),
        ("عودة", "brand"),
        ("الرئيسية", "brand"),
    )
    for keyword, slot in keyword_slots:
        if keyword in text_value:
            return slot
    return "brand"


def _stable_button_emoji_id(
    settings: Mapping[str, str],
    *,
    text: str | None,
    callback_data: str | None,
) -> str | None:
    """Select one fixed icon for a button from its semantic emoji family."""
    if not _BUTTON_EMOJI_IDS:
        return None
    slot = _button_slot(text, callback_data)
    candidates = [
        emoji_id
        for emoji_id in _BUTTON_EMOJI_IDS
        if settings.get(f"{PREFIX}slot:{emoji_id}") == slot
    ]
    if not candidates:
        bound = settings.get(f"{PREFIX}{slot}")
        if bound in _BUTTON_EMOJI_IDS:
            candidates = [bound]
    if not candidates:
        candidates = list(_BUTTON_EMOJI_IDS)

    identity = f"{slot}|{callback_data or ''}|{text or ''}".encode("utf-8")
    digest = hashlib.sha256(identity).digest()
    return candidates[int.from_bytes(digest[:8], "big") % len(candidates)]


def _button_factory(*args: Any, **kwargs: Any) -> InlineKeyboardButton:
    """Construct every inline button with a stable Telegram custom-emoji icon."""
    kwargs = dict(kwargs)
    if kwargs.get("icon_custom_emoji_id") is None:
        text = kwargs.get("text")
        callback_data = kwargs.get("callback_data")
        kwargs["icon_custom_emoji_id"] = _stable_button_emoji_id(
            _BUTTON_SETTINGS,
            text=text if isinstance(text, str) else None,
            callback_data=callback_data if isinstance(callback_data, str) else None,
        )
    return _ORIGINAL_INLINE_BUTTON(*args, **kwargs)


def render(settings: dict[str, str], slot: str) -> str:
    """Render a valid custom-emoji entity using a deterministic contextual choice."""
    ids = _bank_ids(settings)
    candidates = [
        emoji_id
        for emoji_id in ids
        if settings.get(f"{PREFIX}slot:{emoji_id}") == slot
        and settings.get(f"{PREFIX}alt:{emoji_id}")
    ]
    if not candidates:
        bound = settings.get(f"{PREFIX}{slot}")
        if bound and settings.get(f"{PREFIX}alt:{bound}"):
            candidates = [bound]
    if not candidates:
        candidates = [
            emoji_id
            for emoji_id in ids
            if settings.get(f"{PREFIX}alt:{emoji_id}")
        ]
    if not candidates:
        return ""

    index = int.from_bytes(
        hashlib.sha256(slot.encode("utf-8")).digest()[:8],
        "big",
    ) % len(candidates)
    emoji_id = candidates[index]
    alt = settings.get(f"{PREFIX}alt:{emoji_id}")
    return f'<tg-emoji emoji-id="{emoji_id}">{alt}</tg-emoji>' if alt else ""


class PremiumEmojiMiddleware(BaseMiddleware):
    """Load the shared emoji palette before every handler that can build a UI."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session = data.get("session")
        if isinstance(session, AsyncSession):
            await emoji_settings(session)
        return await handler(event, data)


def patch_modules() -> None:
    """Install the shared renderer and deterministic button factory."""
    from gqmrmed.bot import admin_ui, payments, professional_ui, progress, router

    for module in (admin_ui, payments, professional_ui, router):
        setattr(module, "InlineKeyboardButton", _button_factory)
    admin_ui._emoji_settings = emoji_settings
    admin_ui._emoji = render
    professional_ui._emoji_settings = emoji_settings
    professional_ui._emoji = render
    progress._emoji = render


__all__ = [
    "PremiumEmojiMiddleware",
    "emoji_settings",
    "patch_modules",
    "render",
]
