from gqmrmed.bot.premium_emoji_runtime import render


def test_render_uses_exact_alt_from_bank() -> None:
    settings = {
        "telegram_emoji.ids": '["100","200"]',
        "telegram_emoji.alt:100": "🩺",
        "telegram_emoji.alt:200": "🔬",
        "telegram_emoji.slot:100": "medical",
        "telegram_emoji.slot:200": "medical",
    }
    assert render(settings, "medical") == '<tg-emoji emoji-id="100">🩺</tg-emoji>'


def test_render_falls_back_to_captured_bank_when_slot_is_unbound() -> None:
    settings = {
        "telegram_emoji.ids": '["100","200","300"]',
        "telegram_emoji.alt:100": "🩺",
        "telegram_emoji.alt:200": "🎨",
        "telegram_emoji.alt:300": "⭐",
        "telegram_emoji.slot:100": "medical",
        "telegram_emoji.slot:200": "design",
        "telegram_emoji.slot:300": "plans",
    }
    rendered = render(settings, "medical")
    assert rendered == '<tg-emoji emoji-id="100">🩺</tg-emoji>'


def test_render_never_emits_empty_custom_emoji_markup() -> None:
    settings = {
        "telegram_emoji.ids": '["100"]',
        "telegram_emoji.alt:100": "🧪",
        "telegram_emoji.slot:100": "medical",
    }
    rendered = render(settings, "brand")
    assert rendered == '<tg-emoji emoji-id="100">🧪</tg-emoji>'
    assert "> </tg-emoji>" not in rendered
