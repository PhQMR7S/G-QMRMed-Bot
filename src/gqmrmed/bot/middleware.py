"""Database session middleware for aiogram handlers."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from gqmrmed.db.session import SessionFactory


class DbSessionMiddleware(BaseMiddleware):
    """Provide one short-lived SQLAlchemy session per Telegram update."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with SessionFactory() as session:
            data["session"] = session
            return await handler(event, data)
