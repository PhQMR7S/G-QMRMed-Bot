"""Owner-only Telegram Premium Emoji capture and registry."""

from __future__ import annotations

import json
from typing import Any

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.db.models import SystemSetting

OWNER_TELEGRAM_ID = 6246913670
PREFIX = "telegram_emoji."
BANK_KEY = f"{PREFIX}bank"
SLOTS = (
    "brand",
    "medical",
    "create",
    "plans",
    "research",
    "ai",
    "design",
    "success",
    "warning",
    "support",
    "free",
    "plus",
    "pro",
)

router = Router(name="gqmrmed-premium-emoji-registry")


def _is_owner(message: Message) -> bool:
    return message.from_user is not None and message.from_user.id == OWNER_TELEGRAM_ID


def _ids(message: Message) -> list[str]:
    result: list[str] = []
    for entity in message.entities or []:
        if entity.type == "custom_emoji" and entity.custom_emoji_id:
            if entity.custom_emoji_id not in result:
                result.append(entity.custom_emoji_id)
    return result


def _has_custom_emoji(entities: Any) -> bool:
    return any(
        entity.type == "custom_emoji" and entity.custom_emoji_id for entity in entities or []
    )


async def _setting(session: AsyncSession, key: str) -> SystemSetting | None:
    return (
        await session.execute(select(SystemSetting).where(SystemSetting.key == key))
    ).scalar_one_or_none()


async def _load_bank(session: AsyncSession) -> list[dict[str, Any]]:
    setting = await _setting(session, BANK_KEY)
    if setting is None or not setting.value:
        return []
    try:
        value = json.loads(setting.value)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


async def _save_bank(session: AsyncSession, bank: list[dict[str, Any]]) -> None:
    setting = await _setting(session, BANK_KEY)
    value = json.dumps(bank, ensure_ascii=False, separators=(",", ":"))
    if setting is None:
        session.add(SystemSetting(key=BANK_KEY, value=value))
    else:
        setting.value = value


def _classify(alt: str | None) -> str:
    value = alt or ""
    medical = {"⚕️", "🩺", "💊", "🧬", "🧪", "🔬", "🫀", "🫁", "🧠", "🏥"}
    research = {"🔎", "🔍", "📚", "📖", "📊", "📈", "📋", "📝", "ℹ️"}
    design = {"🎨", "🖌️", "🖊️", "✏️", "🖼️", "📐", "🧩"}
    ai = {"🤖", "🧠", "💡", "✨", "⚙️"}
    success = {"✅", "✔️", "☑️", "👍", "🎉"}
    warning = {"⚠️", "❗", "❌", "⛔", "🚫"}
    support = {"❓", "💬", "📞", "🆘", "🙋", "ℹ️"}
    plans = {"⭐", "🌟", "💎", "👑", "🏆"}
    create = {"➕", "🪄", "🛠️", "🔧"}
    if value in medical:
        return "medical"
    if value in research:
        return "research"
    if value in design:
        return "design"
    if value in ai:
        return "ai"
    if value in success:
        return "success"
    if value in warning:
        return "warning"
    if value in support:
        return "support"
    if value in plans:
        return "plans"
    if value in create:
        return "create"
    return "brand"


async def _enrich(bot: Bot, ids: list[str]) -> list[dict[str, Any]]:
    if not ids:
        return []
    stickers = await bot.get_custom_emoji_stickers(custom_emoji_ids=ids[:200])
    by_id = {sticker.custom_emoji_id: sticker for sticker in stickers if sticker.custom_emoji_id}
    return [
        {
            "id": emoji_id,
            "alt": by_id[emoji_id].emoji if emoji_id in by_id else None,
            "set_name": by_id[emoji_id].set_name if emoji_id in by_id else None,
            "slot": _classify(by_id[emoji_id].emoji if emoji_id in by_id else None),
        }
        for emoji_id in ids
    ]


def _render(ids: list[str]) -> str:
    return "".join(f'<tg-emoji emoji-id="{emoji_id}"> </tg-emoji> ' for emoji_id in ids)


@router.message(F.from_user.id == OWNER_TELEGRAM_ID, F.entities.func(_has_custom_emoji))
async def capture_owner_premium_emojis(
    message: Message, session: AsyncSession, bot: Bot
) -> None:
    """Capture every custom-emoji ID in a new owner message without touching normal input."""
    ids = _ids(message)
    if not ids or (message.text or "").startswith("/"):
        return
    bank = await _load_bank(session)
    known = {str(item.get("id")) for item in bank}
    fresh = [item for item in await _enrich(bot, ids) if str(item["id"]) not in known]
    if not fresh:
        return
    bank.extend(fresh)
    await _save_bank(session, bank)
    await session.commit()
    await message.answer(
        f"تم التقاط {len(fresh)} من رموز Premium Emoji وحفظها في مكتبة GQMRMed.\n"
        f"الإجمالي المسجل: {len(bank)}.\n\n"
        "أصبح التصنيف الدلالي جاهزاً للاستخدام داخل واجهة البوت.",
        parse_mode="HTML",
    )


@router.message(Command("emoji_catalog"))
async def emoji_catalog(message: Message, session: AsyncSession) -> None:
    if not _is_owner(message):
        return
    bank = await _load_bank(session)
    if not bank:
        await message.answer("مكتبة Premium Emoji فارغة.")
        return
    chunks: list[str] = []
    for start in range(0, len(bank), 10):
        items = bank[start : start + 10]
        lines = ["<b>مكتبة Premium Emoji</b>"]
        for index, item in enumerate(items, start=start + 1):
            emoji_id = str(item.get("id", ""))
            alt = str(item.get("alt") or "—")
            set_name = str(item.get("set_name") or "—")
            slot = str(item.get("slot") or "brand")
            lines.append(
                f"<b>{index}</b> · <code>{emoji_id}</code> · "
                f"alt: <code>{alt}</code> · slot: <code>{slot}</code> · "
                f"set: <code>{set_name}</code>"
            )
        lines.extend(["", _render([str(item["id"]) for item in items])])
        chunks.append("\n".join(lines))
    for chunk in chunks:
        await message.answer(chunk, parse_mode="HTML")


@router.message(Command("emoji_status"))
async def emoji_status(message: Message, session: AsyncSession) -> None:
    """Show an owner-only integrity report for the Premium Emoji registry."""
    if not _is_owner(message):
        return

    bank = await _load_bank(session)
    ids = [str(item.get("id")) for item in bank if item.get("id")]
    unique_ids = set(ids)
    valid_rows = [item for item in bank if item.get("id")]
    slot_counts = {slot: 0 for slot in SLOTS}
    for item in valid_rows:
        slot = str(item.get("slot") or "brand")
        if slot not in slot_counts:
            slot = "brand"
        slot_counts[slot] += 1

    bound: dict[str, str] = {}
    for slot in SLOTS:
        setting = await _setting(session, f"{PREFIX}{slot}")
        if setting is not None and setting.value:
            bound[slot] = str(setting.value)

    missing_slots = [slot for slot in SLOTS if slot not in bound]
    duplicate_count = len(ids) - len(unique_ids)
    missing_metadata = sum(
        1
        for item in valid_rows
        if not item.get("alt") and not item.get("set_name")
    )

    lines = [
        "<b>Premium Emoji Registry — Status</b>",
        "",
        f"الإجمالي: <b>{len(bank)}</b>",
        f"IDs فريدة: <b>{len(unique_ids)}</b>",
        f"تكرارات: <b>{duplicate_count}</b>",
        f"سجلات بدون Telegram metadata: <b>{missing_metadata}</b>",
        f"المساحات المرتبطة: <b>{len(bound)}/{len(SLOTS)}</b>",
        "",
        "<b>التصنيف</b>",
    ]
    for slot in SLOTS:
        lines.append(f"{slot}: {slot_counts[slot]}")

    if missing_slots:
        lines.extend(["", "<b>مساحات غير مرتبطة</b>", ", ".join(missing_slots)])
    else:
        lines.extend(["", "<b>الحالة: مكتملة</b> ✅"])

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("emoji_autobind"))
async def emoji_autobind(message: Message, session: AsyncSession) -> None:
    if not _is_owner(message):
        return
    bank = await _load_bank(session)
    if not bank:
        await message.answer("لا توجد Premium Emoji مسجلة بعد.")
        return
    selected: dict[str, str] = {}
    for item in bank:
        slot = str(item.get("slot") or "brand")
        if slot not in selected:
            selected[slot] = str(item["id"])
    for slot in SLOTS:
        if slot not in selected:
            continue
        key = f"{PREFIX}{slot}"
        setting = await _setting(session, key)
        if setting is None:
            session.add(SystemSetting(key=key, value=selected[slot]))
        else:
            setting.value = selected[slot]
    await session.commit()
    await message.answer(
        "اكتمل التصنيف الأولي الدلالي لمكتبة Premium Emoji.\n"
        f"تم ربط {len(selected)} مساحة من أصل {len(SLOTS)}.\n\n"
        "يمكن مراجعة المكتبة والـIDs عبر /emoji_catalog و/emoji_status.",
        parse_mode="HTML",
    )
