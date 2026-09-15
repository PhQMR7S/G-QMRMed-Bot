from gqmrmed.ai.design_preferences import extract_design_preferences


def test_design_preferences_follow_explicit_user_direction() -> None:
    prefs = extract_design_preferences(
        "صمم DKA بمخطط انسيابي، أزرق وذهبي، خلفية #F7F9FC، "
        "تشريح واقعي، خط كبير، وبطاقات مستديرة."
    )

    assert prefs.layout == "flow"
    assert prefs.background == "#F7F9FC"
    assert "#4C9FB0" in prefs.palette
    assert "#C49A5A" in prefs.palette
    assert prefs.illustration_style == "realistic clinical"
    assert prefs.font_scale == 1.15
    assert prefs.card_radius == 34


def test_design_preferences_default_to_master_language_without_options() -> None:
    prefs = extract_design_preferences("تكيس المبايض")

    assert prefs.layout == "balanced"
    assert prefs.density == "balanced"
    assert prefs.palette is None
    assert prefs.show_footer is True
