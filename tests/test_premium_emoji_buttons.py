from gqmrmed.bot import premium_emoji_runtime as runtime


def test_button_factory_attaches_captured_custom_emoji() -> None:
    settings = {
        "telegram_emoji.alt:100": "🩺",
        "telegram_emoji.alt:200": "🔬",
        "telegram_emoji.alt:300": "🎨",
    }
    runtime._refresh_button_pool(["100", "200", "300"], settings)

    first = runtime._button_factory(text="إنشاء تصميم", callback_data="pro:generate")
    second = runtime._button_factory(text="الخطط", callback_data="pro:plans")

    assert first.icon_custom_emoji_id == "100"
    assert second.icon_custom_emoji_id == "200"


def test_button_factory_uses_every_captured_icon_before_repeating() -> None:
    settings = {
        "telegram_emoji.alt:1": "🩺",
        "telegram_emoji.alt:2": "🔬",
        "telegram_emoji.alt:3": "🎨",
    }
    runtime._refresh_button_pool(["1", "2", "3"], settings)

    ids = [
        runtime._button_factory(text=str(index), callback_data=str(index)).icon_custom_emoji_id
        for index in range(3)
    ]

    assert ids == ["1", "2", "3"]
    repeated = runtime._button_factory(text="again", callback_data="again")
    assert repeated.icon_custom_emoji_id == "1"
