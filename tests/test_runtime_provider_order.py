from types import SimpleNamespace

from gqmrmed.services import runtime


def test_requested_provider_order_is_not_overridden_by_implicit_cloud_order() -> None:
    settings = SimpleNamespace(
        ai_provider_order="openai,gemini_free",
        comfyui_workflow_json=None,
        telegram_bot_token="x",
        redis_url="redis://localhost",
        research_api_key=None,
        research_email=None,
        ollama_model="qwen3:8b",
        ollama_base_url="http://ollama:11434",
        ollama_timeout_seconds=1,
        gemini_api_key="gemini-key",
        gemini_text_model="gemini-3.6-flash",
        gemini_timeout_seconds=1,
        openrouter_api_key=None,
        openrouter_model="x",
        openrouter_base_url="https://x",
        openrouter_timeout_seconds=1,
        groq_api_key=None,
        groq_model="x",
        groq_base_url="https://x",
        groq_timeout_seconds=1,
        huggingface_token=None,
        huggingface_text_model="x",
        huggingface_base_url="https://x",
        huggingface_timeout_seconds=1,
        ai_compatible_api_key=None,
        ai_compatible_base_url=None,
        ai_compatible_model=None,
        ai_api_key="openai-key",
        ai_base_url="https://api.openai.com/v1",
        ai_model="gpt-5.6-luna",
        ai_allow_paid=True,
        image_provider_order="procedural",
        image_width=1024,
        image_height=1536,
        openai_image_model="gpt-image-2",
        openai_image_quality="medium",
        openai_image_timeout_seconds=1,
        huggingface_image_model="x",
        huggingface_image_provider="x",
        comfyui_base_url="http://comfyui:8188",
        comfyui_timeout_seconds=1,
        result_storage_dir="/tmp",
        s3_endpoint=None,
        s3_access_key_id=None,
        s3_secret_access_key=None,
        s3_bucket="x",
        s3_region=None,
        media_transcription_model="x",
        media_max_bytes=1,
        media_temp_dir="/tmp",
    )

    original = runtime.ProviderRouter
    captured: dict[str, object] = {}

    class CaptureRouter:
        def __init__(self, providers, **kwargs):
            captured["names"] = [meta.name for meta, _ in providers]

    runtime.ProviderRouter = CaptureRouter  # type: ignore[assignment]
    try:
        runtime.build_worker(settings, SimpleNamespace())
    except Exception:
        pass
    finally:
        runtime.ProviderRouter = original  # type: ignore[assignment]

    assert captured["names"] == ["openai", "gemini_free"]
