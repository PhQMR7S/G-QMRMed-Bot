from gqmrmed.bot import premium_emoji_runtime as runtime


def _prime(settings: dict[str, str]) -> None:
    runtime._BUTTON_SETTINGS.clear()
    runtime._BUTTON_SETTINGS.update(settings)
    ids = [
        key.split(":", 2)[2]
        for key, value in settings.items()
        if key.startswith("telegram_emoji.alt:") and value
    ]
    runtime._refresh_button_pool(ids, settings)


def test_button_factory_attaches_stable_semantic_custom_emoji() -> None:
    settings = {
        "telegram_emoji.alt:100": "🩺",
        "telegram_emoji.slot:100": "medical",
        "telegram_emoji.alt:200": "🔬",
        "telegram_emoji.slot:200": "research",
        "telegram_emoji.alt:300": "🎨",
        "telegram_emoji.slot:300": "design",
    }
    _prime(settings)

    first = runtime._button_factory(text="المستخدمون", callback_data="adm:users")
    second = runtime._button_factory(text="بحث", callback_data="adm:overview")
    first_again = runtime._button_factory(text="المستخدمون", callback_data="adm:users")

    assert first.icon_custom_emoji_id == "100"
    assert second.icon_custom_emoji_id == "200"
    assert first_again.icon_custom_emoji_id == first.icon_custom_emoji_id


def test_button_factory_uses_all_captured_icons_as_deterministic_fallbacks() -> None:
    settings = {
        "telegram_emoji.alt:1": "🩺",
        "telegram_emoji.alt:2": "🔬",
        "telegram_emoji.alt:3": "🎨",
    }
    _prime(settings)

    first = runtime._button_factory(text="A", callback_data="fallback:a")
    second = runtime._button_factory(text="B", callback_data="fallback:b")
    first_again = runtime._button_factory(text="A", callback_data="fallback:a")

    assert first.icon_custom_emoji_id in {"1", "2", "3"}
    assert second.icon_custom_emoji_id in {"1", "2", "3"}
    assert first_again.icon_custom_emoji_id == first.icon_custom_emoji_id
    assert set(runtime._BUTTON_EMOJI_IDS) == {"1", "2", "3"}
