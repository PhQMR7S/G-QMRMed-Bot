"""Telegram live progress presentation for generation jobs."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any
from uuid import UUID

from aiogram import Bot
from sqlalchemy import select

from gqmrmed.contracts.generation import GenerationProgress, GenerationStage
from gqmrmed.db.models import GenerationJob, User
from gqmrmed.db.session import SessionFactory
from gqmrmed.services.jobs import set_progress_message_id

_STAGE_LABELS = {
    GenerationStage.RESEARCHING: ("🔎", "البحث الطبي والتحقق من المصادر"),
    GenerationStage.SYNTHESIZING: ("🧠", "تركيب المحتوى الطبي"),
    GenerationStage.ARCHITECTURE: ("📐", "بناء الهيكل البصري"),
    GenerationStage.GENERATING: ("🎨", "توليد العناصر البصرية"),
    GenerationStage.RENDERING: ("🖼", "إخراج التصميم النهائي"),
    GenerationStage.QUALITY_CONTROL: ("✅", "المراجعة النهائية"),
}


def _progress_bar(value: int, *, width: int = 10) -> str:
    filled = round(value / 100 * width)
    return "█" * filled + "░" * (width - filled)


def format_progress_message(
    stage: GenerationStage,
    progress: int,
    *,
    elapsed_seconds: int = 0,
) -> str:
    """Render one stable Arabic Telegram progress message."""
    payload = GenerationProgress(
        stage=stage,
        progress=progress,
        elapsed_seconds=elapsed_seconds,
    )
    icon, label = _STAGE_LABELS[payload.stage]
    elapsed = f"{payload.elapsed_seconds // 60:02d}:{payload.elapsed_seconds % 60:02d}"
    return (
        "⏳ <b>جاري إنشاء التصميم الطبي</b>\n\n"
        f"{icon} <b>{label}</b>\n"
        f"<code>{_progress_bar(payload.progress)}</code> {payload.progress}%\n"
        f"⏱ الوقت المنقضي: {elapsed}"
    )


class TelegramProgressSink:
    """Edit one Telegram message throughout a generation job."""

    def __init__(
        self,
        bot: Bot,
        *,
        session_factory: Callable[[], Any] = SessionFactory,
    ) -> None:
        self._bot = bot
        self._session_factory = session_factory
        self._message_ids: dict[UUID, int] = {}
        self._started_at: dict[UUID, float] = {}

    async def __call__(
        self,
        job: GenerationJob,
        stage: GenerationStage,
        progress: int,
    ) -> None:
        job_id = job.id
        started = self._started_at.setdefault(job_id, time.monotonic())
        elapsed = max(0, int(time.monotonic() - started))
        message_id = self._message_ids.get(job_id)
        if message_id is None:
            raw_id = (job.input_metadata or {}).get("telegram_progress_message_id")
            message_id = raw_id if isinstance(raw_id, int) and raw_id > 0 else None

        chat_id = (job.input_metadata or {}).get("telegram_chat_id")
        if not isinstance(chat_id, int) or chat_id <= 0:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(User.telegram_id).where(User.id == job.user_id)
                )
                chat_id = result.scalar_one_or_none()
        if not isinstance(chat_id, int) or chat_id <= 0:
            raise ValueError("telegram_chat_id_unavailable")

        text = format_progress_message(stage, progress, elapsed_seconds=elapsed)
        if message_id is None:
            sent = await self._bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
            )
            message_id = sent.message_id
            self._message_ids[job_id] = message_id
            async with self._session_factory() as session:
                async with session.begin():
                    await set_progress_message_id(session, job_id, message_id)
            return

        await self._bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode="HTML",
        )


__all__ = ["TelegramProgressSink", "format_progress_message"]
