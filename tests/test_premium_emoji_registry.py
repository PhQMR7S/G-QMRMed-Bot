from gqmrmed.bot.premium_emoji_registry import SLOTS, _classify, _render


def test_premium_emoji_slots_are_stable() -> None:
    assert SLOTS == (
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


def test_classification_maps_known_semantic_alts() -> None:
    assert _classify("🩺") == "medical"
    assert _classify("🔬") == "medical"
    assert _classify("📚") == "research"
    assert _classify("🤖") == "ai"
    assert _classify("🎨") == "design"
    assert _classify("✅") == "success"
    assert _classify("⚠️") == "warning"
    assert _classify("💬") == "support"
    assert _classify("⭐") == "plans"
    assert _classify("➕") == "create"


def test_unknown_alt_defaults_to_brand() -> None:
    assert _classify(None) == "brand"
    assert _classify("unknown") == "brand"


def test_render_uses_telegram_custom_emoji_markup() -> None:
    rendered = _render(["123", "456"])
    assert rendered == '<tg-emoji emoji-id="123"> </tg-emoji> <tg-emoji emoji-id="456"> </tg-emoji> '
