# ============================================
# FILE: app/middlewares/__init__.py
# ============================================
"""
Middleware для обробки запитів
"""

from aiogram import Dispatcher
from .logging_middleware import LoggingMiddleware
from .throttling_middleware import ThrottlingMiddleware


def setup_middlewares(dp: Dispatcher):
    """Налаштовує всі middleware"""
    
    # Логування всіх запитів
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())
    
    # Обмеження кількості запитів
    dp.message.middleware(ThrottlingMiddleware())
    dp.callback_query.middleware(ThrottlingMiddleware())