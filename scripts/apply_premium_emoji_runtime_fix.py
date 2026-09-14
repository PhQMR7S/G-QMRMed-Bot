from pathlib import Path

path = Path("src/gqmrmed/bot/professional_ui.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "from datetime import UTC, date\n",
    "import json\n\nfrom datetime import UTC, date\n",
    1,
)
old = '''def _emoji(settings: dict[str, str], slot: str) -> str:\n    """Render a bound Telegram Premium Emoji; never use a Unicode fallback."""\n    emoji_id = settings.get(f"{EMOJI_PREFIX}{slot}")\n    return f'<tg-emoji emoji-id="{emoji_id}"> </tg-emoji>' if emoji_id else ""\n\n\nasync def _emoji_settings(session: AsyncSession) -> dict[str, str]:\n    rows = (\n        await session.execute(\n            select(SystemSetting).where(SystemSetting.key.like(f"{EMOJI_PREFIX}%"))\n        )\n    ).scalars().all()\n    return {row.key: row.value for row in rows}\n'''
new = '''def _emoji(settings: dict[str, str], slot: str) -> str:\n    """Render a Telegram Premium Emoji with its exact Telegram-provided alt."""\n    emoji_id = settings.get(f"{EMOJI_PREFIX}{slot}")\n    if not emoji_id:\n        return ""\n    alt = settings.get(f"{EMOJI_PREFIX}alt:{emoji_id}")\n    if not alt:\n        return ""\n    return f'<tg-emoji emoji-id="{emoji_id}">{alt}</tg-emoji>'\n\n\nasync def _emoji_settings(session: AsyncSession) -> dict[str, str]:\n    rows = (\n        await session.execute(\n            select(SystemSetting).where(SystemSetting.key.like(f"{EMOJI_PREFIX}%"))\n        )\n    ).scalars().all()\n    settings = {row.key: row.value for row in rows}\n    raw_bank = settings.get(f"{EMOJI_PREFIX}bank")\n    if raw_bank:\n        try:\n            bank = json.loads(raw_bank)\n        except json.JSONDecodeError:\n            bank = []\n        if isinstance(bank, list):\n            for item in bank:\n                if not isinstance(item, dict):\n                    continue\n                emoji_id = str(item.get("id") or "")\n                alt = str(item.get("alt") or "")\n                if emoji_id and alt:\n                    settings[f"{EMOJI_PREFIX}alt:{emoji_id}"] = alt\n    return settings\n'''
if old not in text:
    raise SystemExit("professional_ui.py target block not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
