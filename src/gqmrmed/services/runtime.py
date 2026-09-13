"""Runtime dependency assembly for the standalone bot and worker."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from aiogram import Bot
from redis.asyncio import Redis

from gqmrmed.ai.openai_responses import OpenAIResponsesConfig, OpenAIResponsesSynthesizer
from gqmrmed.ai.providers import (
    OllamaConfig,
    OllamaSynthesizer,
    OpenAICompatibleChatSynthesizer,
    OpenAICompatibleConfig,
    OpenRouterFreeSynthesizer,
    ProviderDescriptor,
    ProviderRouter,
    TextSynthesisProvider,
)
from gqmrmed.bot.progress import TelegramProgressSink
from gqmrmed.config import Settings
from gqmrmed.db.session import SessionFactory
from gqmrmed.generation.providers import (
    ComfyUIConfig,
    ComfyUIImageProvider,
    HuggingFaceImageConfig,
    HuggingFaceImageProvider,
    ImageGenerationProvider,
    ProceduralMedicalIllustrationProvider,
)
from gqmrmed.research.pubmed import PubMedConfig, PubMedResearchProvider
from gqmrmed.services.media_extractors import LocalMediaExtractor, OpenAIMediaExtractor
from gqmrmed.services.media_ingestion import MediaIngestionConfig, MediaIngestor
from gqmrmed.services.media_routing import RoutingMediaExtractor
from gqmrmed.services.production_pipeline import (
    ProductionGenerationPipeline,
    ProductionPipelineConfig,
)
from gqmrmed.services.redis_queue import RedisJobQueue
from gqmrmed.services.result_store import (
    FilesystemResultStore,
    S3ResultStore,
    TelegramResultDelivery,
)
from gqmrmed.services.telegram_media import TelegramMediaSource
from gqmrmed.services.worker import GenerationWorker


def build_worker(settings: Settings, bot: Bot) -> GenerationWorker:
    """Assemble the research, free-first AI routing, image and delivery chain."""
    workflow: dict[str, object] | None = None
    if settings.comfyui_workflow_json:
        try:
            parsed_workflow = json.loads(settings.comfyui_workflow_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("COMFYUI_WORKFLOW_JSON must be valid JSON") from exc
        if not isinstance(parsed_workflow, dict):
            raise RuntimeError("COMFYUI_WORKFLOW_JSON must contain an API-format workflow object")
        workflow = cast(dict[str, object], parsed_workflow)

    research = PubMedResearchProvider(
        PubMedConfig(api_key=settings.research_api_key, email=settings.research_email)
    )
    providers: list[tuple[ProviderDescriptor, TextSynthesisProvider]] = []
    order = [item.strip().lower() for item in settings.ai_provider_order.split(",") if item.strip()]
    for name in order:
        if name == "ollama":
            providers.append(
                (
                    ProviderDescriptor(
                        name="ollama", model=settings.ollama_model, cost_tier="local"
                    ),
                    OllamaSynthesizer(
                        OllamaConfig(
                            base_url=settings.ollama_base_url,
                            model=settings.ollama_model,
                            timeout_seconds=settings.ollama_timeout_seconds,
                        )
                    ),
                )
            )
        elif name == "openrouter_free" and settings.openrouter_api_key:
            providers.append(
                (
                    ProviderDescriptor(
                        name="openrouter_free",
                        model=settings.openrouter_model,
                        cost_tier="free",
                    ),
                    OpenRouterFreeSynthesizer(
                        OpenAICompatibleConfig(
                            api_key=settings.openrouter_api_key,
                            base_url=settings.openrouter_base_url,
                            model=settings.openrouter_model,
                            timeout_seconds=settings.openrouter_timeout_seconds,
                            extra_headers=(("X-Title", "GQMRMed"),),
                        )
                    ),
                )
            )
        elif name == "groq_free" and settings.groq_api_key:
            providers.append(
                (
                    ProviderDescriptor(
                        name="groq_free",
                        model=settings.groq_model,
                        cost_tier="free",
                    ),
                    OpenAICompatibleChatSynthesizer(
                        OpenAICompatibleConfig(
                            api_key=settings.groq_api_key,
                            base_url=settings.groq_base_url,
                            model=settings.groq_model,
                            timeout_seconds=settings.groq_timeout_seconds,
                        )
                    ),
                )
            )
        elif name == "huggingface_free" and settings.huggingface_token:
            providers.append(
                (
                    ProviderDescriptor(
                        name="huggingface_free",
                        model=settings.huggingface_text_model,
                        cost_tier="free",
                    ),
                    OpenAICompatibleChatSynthesizer(
                        OpenAICompatibleConfig(
                            api_key=settings.huggingface_token,
                            base_url=settings.huggingface_base_url,
                            model=settings.huggingface_text_model,
                            timeout_seconds=settings.huggingface_timeout_seconds,
                        )
                    ),
                )
            )
        elif (
            name == "openai_compatible"
            and settings.ai_compatible_api_key
            and settings.ai_compatible_base_url
            and settings.ai_compatible_model
        ):
            providers.append(
                (
                    ProviderDescriptor(
                        name="openai_compatible",
                        model=settings.ai_compatible_model,
                        cost_tier="paid",
                    ),
                    OpenAICompatibleChatSynthesizer(
                        OpenAICompatibleConfig(
                            api_key=settings.ai_compatible_api_key,
                            base_url=settings.ai_compatible_base_url,
                            model=settings.ai_compatible_model,
                        )
                    ),
                )
            )
        elif name == "openai" and settings.ai_api_key:
            providers.append(
                (
                    ProviderDescriptor(
                        name="openai", model=settings.ai_model, cost_tier="paid"
                    ),
                    OpenAIResponsesSynthesizer(
                        OpenAIResponsesConfig(
                            api_key=settings.ai_api_key,
                            base_url=settings.ai_base_url,
                            model=settings.ai_model,
                        )
                    ),
                )
            )
    if not providers:
        raise RuntimeError("no_synthesis_provider_configured")

    rich_media = (
        OpenAIMediaExtractor(
            api_key=settings.ai_api_key,
            model=settings.ai_model,
            transcription_model=settings.media_transcription_model,
            base_url=settings.ai_base_url,
        )
        if settings.ai_api_key
        else None
    )
    media_ingestor = MediaIngestor(
        TelegramMediaSource(bot),
        MediaIngestionConfig(max_bytes=settings.media_max_bytes),
        RoutingMediaExtractor(LocalMediaExtractor(), rich_media),
    )

    synthesis = ProviderRouter(providers, allow_paid=settings.ai_allow_paid)
    image: ImageGenerationProvider
    if settings.huggingface_token:
        image = HuggingFaceImageProvider(
            HuggingFaceImageConfig(
                token=settings.huggingface_token,
                model=settings.huggingface_image_model,
                provider=settings.huggingface_image_provider,
                timeout_seconds=settings.huggingface_timeout_seconds,
            )
        )
    elif workflow is not None:
        image = ComfyUIImageProvider(
            ComfyUIConfig(
                base_url=settings.comfyui_base_url,
                timeout_seconds=settings.comfyui_timeout_seconds,
                workflow=workflow,
            )
        )
    else:
        image = ProceduralMedicalIllustrationProvider()

    pipeline = ProductionGenerationPipeline(
        research_provider=research.search,
        synthesis_provider=synthesis,
        image_provider=image,
        config=ProductionPipelineConfig(
            width=settings.image_width, height=settings.image_height
        ),
    )
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    queue = RedisJobQueue(redis)

    result_store: FilesystemResultStore | S3ResultStore
    if settings.s3_endpoint:
        if not settings.s3_access_key_id or not settings.s3_secret_access_key:
            raise RuntimeError("complete S3 credentials are required when S3 is configured")
        result_store = S3ResultStore(
            endpoint=settings.s3_endpoint,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
            bucket=settings.s3_bucket,
            region=settings.s3_region,
        )
    else:
        result_store = FilesystemResultStore(Path(settings.result_storage_dir))

    return GenerationWorker(
        queue=queue,
        session_factory=SessionFactory,
        pipeline=pipeline,
        result_store=result_store,
        progress_sink=TelegramProgressSink(bot),
        delivery_sink=TelegramResultDelivery(bot),
        media_ingestor=media_ingestor,
        media_temp_dir=settings.media_temp_dir,
    )


__all__ = ["build_worker"]
