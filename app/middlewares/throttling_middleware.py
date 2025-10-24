#app/middlewares/throttling_middleware.py

"""
Middleware для обмеження кількості запитів
"""

import time
from typing import Callable, Dict, Any, Awaitable
from collections import defaultdict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from app.config.settings import config


class ThrottlingMiddleware(BaseMiddleware):
    """Обмежує кількість запитів від користувача"""
    
    def __init__(self, rate_limit: int = config.RATE_LIMIT_MESSAGES):
        super().__init__()
        self.rate_limit = rate_limit  # запитів на хвилину
        self.user_requests: Dict[int, list] = defaultdict(list)
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        
        user_id = event.from_user.id
        current_time = time.time()
        
        # Очищаємо старі запити (старші 1 хвилини)
        self.user_requests[user_id] = [
            req_time for req_time in self.user_requests[user_id]
            if current_time - req_time < 60
        ]
        
        # Перевіряємо ліміт
        if len(self.user_requests[user_id]) >= self.rate_limit:
            if isinstance(event, Message):
                await event.answer(
                    "⚠️ Забагато запитів. Будь ласка, зачекайте хвилину.",
                    show_alert=True if isinstance(event, CallbackQuery) else False
                )
            return
        
        # Додаємо поточний запит
        self.user_requests[user_id].append(current_time)
        
        return await handler(event, data)