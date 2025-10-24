# ============================================
# FILE: app/handlers/__init__.py
# ============================================
"""
Реєстрація всіх хендлерів
"""

from aiogram import Dispatcher
from . import (
    start,
    transactions,
    statistics,
    subscriptions,
    settings,
    support,
    ai_analysis,
)


def register_all_handlers(dp: Dispatcher):
    """Реєструє всі хендлери в диспетчері"""
    
    # Порядок важливий! Більш специфічні хендлери - спочатку
    start.register_handlers(dp)
    transactions.register_handlers(dp)
    statistics.register_handlers(dp)
    subscriptions.register_handlers(dp)
    ai_analysis.register_handlers(dp)
    settings.register_handlers(dp)
    support.register_handlers(dp)