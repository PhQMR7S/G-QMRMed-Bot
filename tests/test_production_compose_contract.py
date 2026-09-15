import pathlib  # noqa: I001


COMPOSE = pathlib.Path("compose.production.yml").read_text(encoding="utf-8")
RELEASE_GATE = pathlib.Path("scripts/release-gate.sh").read_text(encoding="utf-8")


def test_production_worker_receives_all_supported_provider_settings() -> None:
    required = (
        "AI_PROVIDER_ORDER",
        "AI_API_KEY",
        "OPENROUTER_API_KEY",
        "GROQ_API_KEY",
        "HUGGINGFACE_TOKEN",
        "GEMINI_API_KEY",
        "CLOUDFLARE_API_TOKEN",
        "DASHSCOPE_API_KEY",
        "NARAROUTER_API_KEY",
        "IMAGE_PROVIDER_ORDER",
        "OPENAI_IMAGE_MODEL",
        "HUGGINGFACE_IMAGE_MODEL",
        "COMFYUI_WORKFLOW_JSON",
    )
    for name in required:
        assert f"{name}: ${{{name}" in COMPOSE


def test_openai_key_is_optional_when_an_alternative_provider_is_selected() -> None:
    assert "AI_API_KEY: ${AI_API_KEY:-}" in COMPOSE
    assert "AI_API_KEY: ${AI_API_KEY:?" not in COMPOSE


def test_release_gate_rejects_unknown_provider_names() -> None:
    assert 'fail "unknown AI synthesis provider in AI_PROVIDER_ORDER: $provider"' in RELEASE_GATE
    assert 'fail "unknown image provider in IMAGE_PROVIDER_ORDER: $provider"' in RELEASE_GATE


def test_s3_region_is_optional_when_s3_is_enabled() -> None:
    assert "s3_values=(S3_ENDPOINT S3_ACCESS_KEY_ID S3_SECRET_ACCESS_KEY S3_BUCKET)" in RELEASE_GATE
