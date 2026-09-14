"""Runtime Premium Emoji resolver shared by all Telegram UI surfaces."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.db.models import SystemSetting

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


def _classify(alt: str | None) -> str:
    value = alt or ""
    groups = {
        "medical": {"⚕️", "🩺", "💊", "🧬", "🧪", "🔬", "🫀", "🫁", "🧠", "🏥"},
        "research": {"🔎", "🔍", "📚", "📖", "📊", "📈", "📋", "📝", "ℹ️"},
        "design": {"🎨", "🖌️", "🖊️", "✏️", "🖼️", "📐", "🧩"},
        "ai": {"🤖", "💡", "✨", "⚙️"},
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
    """Load bindings plus the complete captured bank and exact Telegram alts."""
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
    for item in bank:
        emoji_id = str(item.get("id") or "")
        alt = str(item.get("alt") or "")
        if emoji_id and alt:
            settings[f"{PREFIX}alt:{emoji_id}"] = alt
            settings[f"{PREFIX}slot:{emoji_id}"] = str(
                item.get("slot") or _classify(alt)
            )
    settings[f"{PREFIX}count"] = str(len(bank))
    settings[f"{PREFIX}ids"] = json.dumps(
        [str(item.get("id")) for item in bank if item.get("id")],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return settings


def _bank_ids(settings: Mapping[str, str]) -> list[str]:
    raw = settings.get(f"{PREFIX}ids", "[]")
    try:
        ids = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [str(value) for value in ids if value]


def render(settings: dict[str, str], slot: str) -> str:
    """Render a valid custom-emoji entity, selecting a contextual bank entry."""
    ids = _bank_ids(settings)
    bound = settings.get(f"{PREFIX}{slot}")
    candidates = [
        emoji_id
        for emoji_id in ids
        if settings.get(f"{PREFIX}slot:{emoji_id}") == slot
        and settings.get(f"{PREFIX}alt:{emoji_id}")
    ]
    if bound and settings.get(f"{PREFIX}alt:{bound}"):
        emoji_id = bound
    elif candidates:
        index = sum(ord(char) for char in slot) % len(candidates)
        emoji_id = candidates[index]
    else:
        valid_ids = [emoji_id for emoji_id in ids if settings.get(f"{PREFIX}alt:{emoji_id}")]
        if not valid_ids:
            return ""
        index = sum(ord(char) for char in slot) % len(valid_ids)
        emoji_id = valid_ids[index]
    alt = settings.get(f"{PREFIX}alt:{emoji_id}")
    return f'<tg-emoji emoji-id="{emoji_id}">{alt}</tg-emoji>' if alt else ""


def patch_modules() -> None:
    """Patch UI modules to use the shared resolver without duplicating DB logic."""
    from gqmrmed.bot import admin_ui, professional_ui

    admin_ui._emoji_settings = emoji_settings
    admin_ui._emoji = render
    professional_ui._emoji_settings = emoji_settings
    professional_ui._emoji = render


__all__ = ["emoji_settings", "render", "patch_modules"]
