# ============================================
# FILE: app/middlewares/logging_middleware.py
# ============================================
"""
Middleware для логування запитів
"""

import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """Логує всі вхідні повідомлення та callback"""
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        
        user = event.from_user
        
        if isinstance(event, Message):
            logger.info(
                f"Message from @{user.username} (ID: {user.id}): {event.text[:50] if event.text else 'No text'}"
            )
        elif isinstance(event, CallbackQuery):
            logger.info(
                f"Callback from @{user.username} (ID: {user.id}): {event.data}"
            )
        
        try:
            return await handler(event, data)
        except Exception as e:
            logger.error(f"Error handling event from {user.id}: {e}", exc_info=True)
            raise