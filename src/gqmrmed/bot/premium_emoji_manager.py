"""Owner-only visual manager for the captured Telegram Premium Emoji library."""

from __future__ import annotations

import json
from typing import Any

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.bot.premium_emoji_registry import OWNER_TELEGRAM_ID, PREFIX, SLOTS
from gqmrmed.bot.premium_emoji_runtime import emoji_settings
from gqmrmed.db.models import SystemSetting

router = Router(name="gqmrmed-premium-emoji-manager")
BANK_KEY = f"{PREFIX}bank"
PAGE_SIZE = 12
SLOT_LABELS = {
    "brand": "الهوية",
    "medical": "الطب",
    "create": "الإنشاء",
    "plans": "الخطط",
    "research": "البحث",
    "ai": "الذكاء الاصطناعي",
    "design": "التصميم",
    "success": "النجاح",
    "warning": "التحذير",
    "support": "الدعم",
    "free": "FREE",
    "plus": "PLUS",
    "pro": "PRO",
}


def _owner(query: CallbackQuery | Message) -> bool:
    return query.from_user is not None and query.from_user.id == OWNER_TELEGRAM_ID


def _kb(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _emoji_button(
    text: str,
    callback_data: str,
    emoji_id: str | None = None,
) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text,
        callback_data=callback_data,
        icon_custom_emoji_id=emoji_id,
    )


async def _load_bank(session: AsyncSession) -> list[dict[str, Any]]:
    setting = (
        await session.execute(select(SystemSetting).where(SystemSetting.key == BANK_KEY))
    ).scalar_one_or_none()
    if setting is None or not setting.value:
        return []
    try:
        value = json.loads(setting.value)
    except json.JSONDecodeError:
        return []
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


async def _bound(session: AsyncSession) -> dict[str, str]:
    rows = (
        await session.execute(select(SystemSetting).where(SystemSetting.key.like(f"{PREFIX}%")))
    ).scalars().all()
    return {
        row.key.removeprefix(PREFIX): row.value
        for row in rows
        if row.key.removeprefix(PREFIX) in SLOTS and row.value
    }


async def _set_slot(session: AsyncSession, slot: str, emoji_id: str) -> None:
    key = f"{PREFIX}{slot}"
    setting = (
        await session.execute(select(SystemSetting).where(SystemSetting.key == key))
    ).scalar_one_or_none()
    if setting is None:
        session.add(SystemSetting(key=key, value=emoji_id))
    else:
        setting.value = emoji_id


def _bank_item(bank: list[dict[str, Any]], emoji_id: str) -> dict[str, Any] | None:
    return next((item for item in bank if str(item.get("id") or "") == emoji_id), None)


def _render_emoji(item: dict[str, Any] | None) -> str:
    if not item:
        return ""
    emoji_id = str(item.get("id") or "")
    alt = str(item.get("alt") or "")
    return f'<tg-emoji emoji-id="{emoji_id}">{alt}</tg-emoji>' if emoji_id and alt else ""


async def _show(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    await callback.answer()


async def _home(session: AsyncSession) -> tuple[str, InlineKeyboardMarkup]:
    bank = await _load_bank(session)
    bound = await _bound(session)
    lines = [
        "<b>🎨 مدير Premium Emoji الاحترافي</b>",
        "",
        f"المكتبة: <b>{len(bank)}</b> Emoji",
        f"المربوط يدوياً: <b>{len(bound)}/{len(SLOTS)}</b>",
        "",
        "اختر أي قسم ثم اختر الـPremium Emoji الذي تريده. الاختيار يُحفظ ويُستخدم بثبات في واجهات وأزرار البوت.",
        "",
    ]
    rows: list[list[InlineKeyboardButton]] = []
    for index in range(0, len(SLOTS), 2):
        row: list[InlineKeyboardButton] = []
        for slot in SLOTS[index : index + 2]:
            item = _bank_item(bank, bound.get(slot, ""))
            icon = str(item.get("id")) if item else None
            state = "✓" if item else "—"
            row.append(_emoji_button(f"{state} {SLOT_LABELS[slot]}", f"pem:list:{slot}:0", icon))
        rows.append(row)
    rows.extend(
        [
            [_emoji_button("📚 عرض المكتبة كاملة", "pem:catalog:0")],
            [_emoji_button("⚡ ربط تلقائي ذكي", "pem:auto")],
            [_emoji_button("🔄 تحديث الحالة", "pem:home")],
            [_emoji_button("↩️ لوحة الإدارة", "adm:home")],
        ]
    )
    return "\n".join(lines), _kb(rows)


@router.callback_query(F.data == "adm:emoji")
async def open_manager(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    text, markup = await _home(session)
    await _show(callback, text, markup)


@router.callback_query(F.data == "pem:home")
async def manager_home(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    text, markup = await _home(session)
    await _show(callback, text, markup)


@router.callback_query(
    F.data.regexp(
        r"^pem:list:(brand|medical|create|plans|research|ai|design|success|warning|support|free|plus|pro):[0-9]+$"
    )
)
async def emoji_picker(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    if not callback.data:
        return
    _, _, slot, page_raw = callback.data.split(":")
    page = max(int(page_raw), 0)
    bank = await _load_bank(session)
    bound = await _bound(session)
    total_pages = max((len(bank) + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    page = min(page, total_pages - 1)
    start = page * PAGE_SIZE
    items = bank[start : start + PAGE_SIZE]
    current = bound.get(slot)
    current_item = _bank_item(bank, current or "")

    lines = [
        f"<b>اختيار Premium Emoji — {SLOT_LABELS[slot]}</b>",
        "",
        f"الحالي: {_render_emoji(current_item) or 'غير مرتبط'}",
        f"صفحة <b>{page + 1}/{total_pages}</b> · اختر أي Emoji من المكتبة:",
        "",
    ]
    rows: list[list[InlineKeyboardButton]] = []
    for offset in range(0, len(items), 3):
        row: list[InlineKeyboardButton] = []
        for local_index, item in enumerate(items[offset : offset + 3], start=offset):
            emoji_id = str(item.get("id") or "")
            alt = str(item.get("alt") or "?")
            absolute = start + local_index
            marker = "✓" if emoji_id == current else ""
            label = f"{marker} #{absolute + 1} {alt}"
            row.append(_emoji_button(label, f"pem:pick:{slot}:{absolute}", emoji_id))
        rows.append(row)

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(_emoji_button("‹ السابق", f"pem:list:{slot}:{page - 1}"))
    if page + 1 < total_pages:
        nav.append(_emoji_button("التالي ›", f"pem:list:{slot}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([_emoji_button("↩️ الأقسام", "pem:home")])
    await _show(callback, "\n".join(lines), _kb(rows))


@router.callback_query(
    F.data.regexp(
        r"^pem:pick:(brand|medical|create|plans|research|ai|design|success|warning|support|free|plus|pro):[0-9]+$"
    )
)
async def emoji_pick(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    if not callback.data:
        return
    _, _, slot, index_raw = callback.data.split(":")
    index = int(index_raw)
    bank = await _load_bank(session)
    if index < 0 or index >= len(bank):
        await callback.answer("هذا الـEmoji لم يعد موجوداً في المكتبة.", show_alert=True)
        return
    emoji_id = str(bank[index].get("id") or "")
    if not emoji_id:
        await callback.answer("سجل Emoji غير صالح.", show_alert=True)
        return
    await _set_slot(session, slot, emoji_id)
    await session.commit()
    await emoji_settings(session)
    await callback.answer("تم حفظ اختيارك 🔥")
    await emoji_picker(callback, session)


@router.callback_query(F.data == "pem:auto")
async def emoji_auto(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    bank = await _load_bank(session)
    if not bank:
        await callback.answer("المكتبة فارغة.", show_alert=True)
        return
    for slot in SLOTS:
        candidates = [item for item in bank if str(item.get("slot") or "brand") == slot]
        if not candidates:
            candidates = bank
        await _set_slot(session, slot, str(candidates[0].get("id") or ""))
    await session.commit()
    await emoji_settings(session)
    text, markup = await _home(session)
    await _show(callback, text, markup)


@router.callback_query(F.data.regexp(r"^pem:catalog:[0-9]+$"))
async def emoji_catalog_page(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _owner(callback):
        await callback.answer("غير مصرح.", show_alert=True)
        return
    page = int(callback.data.rsplit(":", 1)[1]) if callback.data else 0
    bank = await _load_bank(session)
    total_pages = max((len(bank) + 19) // 20, 1)
    page = min(max(page, 0), total_pages - 1)
    start = page * 20
    items = bank[start : start + 20]
    lines = [f"<b>📚 مكتبة Premium Emoji</b> · {len(bank)}", ""]
    for index, item in enumerate(items, start=start + 1):
        lines.append(f"{index}. {_render_emoji(item)} <code>{item.get('alt') or '—'}</code>")
    rows: list[list[InlineKeyboardButton]] = []
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(_emoji_button("‹ السابق", f"pem:catalog:{page - 1}"))
    if page + 1 < total_pages:
        nav.append(_emoji_button("التالي ›", f"pem:catalog:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([_emoji_button("↩️ الأقسام", "pem:home")])
    await _show(callback, "\n".join(lines), _kb(rows))
