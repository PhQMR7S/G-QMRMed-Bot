from gqmrmed.services.long_text import LongTextEngine


def test_parse_chunk_deduplicate_and_rank_long_text() -> None:
    text = """# DKA
Diabetic ketoacidosis is an emergency. Treatment requires fluids and insulin.

## Symptoms
Symptoms include nausea, vomiting, abdominal pain and dehydration.

## Duplicate
Symptoms include nausea, vomiting, abdominal pain and dehydration.

## Management
Monitor potassium and glucose. Treatment must account for potassium shifts.
"""

    plan = LongTextEngine(chunk_target_chars=200).build_plan(text)

    assert plan.usage_units == 1
    assert plan.visual_identity == "gqmrmed-medical"
    assert plan.mode == "single"
    assert plan.page_count == 1
    assert len(plan.chunks) == 3
    assert any("potassium" in chunk.text.lower() for chunk in plan.chunks)
    assert plan.topics
    assert plan.chunks[0].priority >= plan.chunks[-1].priority


def test_short_text_stays_single_page_and_preserves_identity() -> None:
    plan = LongTextEngine().build_plan("# Anemia\nIron deficiency causes fatigue.", visual_identity="clinical-blue")

    assert plan.mode == "single"
    assert plan.page_count == 1
    assert plan.visual_identity == "clinical-blue"
    assert plan.usage_units == 1


def test_long_text_selects_multi_page() -> None:
    text = "\n\n".join(f"## Section {i}\n" + ("Clinical management and diagnosis details. " * 50) for i in range(8))
    plan = LongTextEngine().build_plan(text)

    assert plan.mode == "multi_page"
    assert plan.page_count > 1


def test_empty_text_is_rejected() -> None:
    try:
        LongTextEngine().build_plan("   ")
    except ValueError as exc:
        assert str(exc) == "long_text_required"
    else:
        raise AssertionError("empty text should be rejected")
