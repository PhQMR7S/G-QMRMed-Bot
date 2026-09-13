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
    ProviderDescriptor,
    ProviderRouter,
    TextSynthesisProvider,
)
from gqmrmed.bot.progress import TelegramProgressSink
from gqmrmed.config import Settings
from gqmrmed.db.session import SessionFactory
from gqmrmed.generation.providers import ComfyUIConfig, ComfyUIImageProvider
from gqmrmed.research.pubmed import PubMedConfig, PubMedResearchProvider
from gqmrmed.services.media_extractors import LocalMediaExtractor, OpenAIMediaExtractor
from gqmrmed.services.media_ingestion import MediaIngestionConfig, MediaIngestor
from gqmrmed.services.media_routing import RoutingMediaExtractor
from gqmrmed.services.production_pipeline import (
    ProductionGenerationPipeline,
    ProductionPipelineConfig,
)
from gqmrmed.services.redis_queue import RedisJobQueue
from gqmrmed.services.result_store import FilesystemResultStore, TelegramResultDelivery
from gqmrmed.services.telegram_media import TelegramMediaSource
from gqmrmed.services.worker import GenerationWorker


def build_worker(settings: Settings, bot: Bot) -> GenerationWorker:
    """Assemble the real research, synthesis, media, image, rendering and delivery chain."""
    if not settings.comfyui_workflow_json:
        raise RuntimeError("COMFYUI_WORKFLOW_JSON is required for the generation worker")
    try:
        workflow = json.loads(settings.comfyui_workflow_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError("COMFYUI_WORKFLOW_JSON must be valid JSON") from exc
    if not isinstance(workflow, dict):
        raise RuntimeError("COMFYUI_WORKFLOW_JSON must contain an API-format workflow object")

    research = PubMedResearchProvider(
        PubMedConfig(api_key=settings.research_api_key, email=settings.research_email)
    )
    providers: list[tuple[ProviderDescriptor, TextSynthesisProvider]] = []
    order = [item.strip().lower() for item in settings.ai_provider_order.split(",") if item.strip()]
    for name in order:
        if name == "ollama":
            providers.append(
                (
                    ProviderDescriptor(name="ollama", model=settings.ollama_model),
                    OllamaSynthesizer(
                        OllamaConfig(
                            base_url=settings.ollama_base_url,
                            model=settings.ollama_model,
                            timeout_seconds=settings.ollama_timeout_seconds,
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
                    ProviderDescriptor(name="openai", model=settings.ai_model),
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

    synthesis = ProviderRouter(providers)
    image = ComfyUIImageProvider(
        ComfyUIConfig(
            base_url=settings.comfyui_base_url,
            timeout_seconds=settings.comfyui_timeout_seconds,
            workflow=cast(dict[str, object], workflow),
        )
    )
    pipeline = ProductionGenerationPipeline(
        research_provider=research.search,
        synthesis_provider=synthesis,
        image_provider=image,
        config=ProductionPipelineConfig(
            width=settings.image_width,
            height=settings.image_height,
        ),
    )
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    queue = RedisJobQueue(redis)
    return GenerationWorker(
        queue=queue,
        session_factory=SessionFactory,
        pipeline=pipeline,
        result_store=FilesystemResultStore(Path(settings.result_storage_dir)),
        progress_sink=TelegramProgressSink(bot),
        delivery_sink=TelegramResultDelivery(bot),
        media_ingestor=media_ingestor,
        media_temp_dir=settings.media_temp_dir,
    )


__all__ = ["build_worker"]
