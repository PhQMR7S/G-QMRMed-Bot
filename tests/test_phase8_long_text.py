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
    assert any(chunk.heading == "Symptoms" for chunk in plan.chunks)
    assert plan.topics
    assert plan.chunks[0].priority >= plan.chunks[-1].priority


def test_short_text_stays_single_page_and_preserves_identity() -> None:
    plan = LongTextEngine().build_plan(
        "# Anemia\nIron deficiency causes fatigue.",
        visual_identity="clinical-blue",
    )

    assert plan.mode == "single"
    assert plan.page_count == 1
    assert plan.visual_identity == "clinical-blue"
    assert plan.usage_units == 1


def test_long_text_selects_multi_page() -> None:
    sections = []
    topics = [
        "cardiology",
        "neurology",
        "endocrinology",
        "infectious disease",
        "hematology",
        "nephrology",
        "gastroenterology",
        "pulmonology",
    ]
    for index, topic in enumerate(topics):
        body = f"Clinical {topic} management and diagnosis details. " * 50
        sections.append(f"## Section {index}\n{body}")
    plan = LongTextEngine().build_plan("\n\n".join(sections))

    assert plan.mode == "multi_page"
    assert plan.page_count > 1
    assert plan.page_count == (
        sum(len(chunk.text) for chunk in plan.chunks) + 3_800 - 1
    ) // 3_800
    assert plan.usage_units == 1
    assert len({chunk.heading for chunk in plan.chunks}) > 1


def test_normalization_and_empty_text_handling() -> None:
    plan = LongTextEngine().build_plan("  # Anemia\r\n\r\n  Diagnosis is important.  ")

    assert plan.chunks
    assert plan.chunks[0].heading == "Anemia"
    assert "  " not in plan.chunks[0].text

    try:
        LongTextEngine().build_plan("   ")
    except ValueError as exc:
        assert str(exc) == "long_text_required"
    else:
        raise AssertionError("empty text should be rejected")


def test_invalid_configuration_is_rejected() -> None:
    for kwargs, error in [
        ({"chunk_target_chars": 199}, "chunk_target_too_small"),
        ({"chunk_target_chars": 900, "max_single_page_chars": 899}, "single_page_limit_too_small"),
        ({"chunk_target_chars": 900, "max_page_chars": 899}, "page_limit_too_small"),
        ({"dedup_similarity": 0}, "invalid_dedup_similarity"),
        ({"dedup_similarity": 1.1}, "invalid_dedup_similarity"),
    ]:
        try:
            LongTextEngine(**kwargs)
        except ValueError as exc:
            assert str(exc) == error
        else:
            raise AssertionError(f"expected {error}")
