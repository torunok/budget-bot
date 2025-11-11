#File: app/handlers/__init__.py

"""
Реєстрація всіх хендлерів
"""

import logging
from aiogram import Dispatcher
# Імпортуємо всі роутери
from .start import router as start_router 
from .transactions import router as transactions_router 
from .statistics import router as statistics_router
from .subscriptions import router as subscriptions_router
from .settings import router as settings_router
from .support import router as support_router
from .ai_analysis import router as ai_analysis_router
from .goals import router as goals_router


# 🔥 ВИПРАВЛЕНО 🔥: Тепер функція приймає об'єкт logger для коректного виведення інформації.
def register_all_handlers(dp: Dispatcher, logger: logging.Logger):
    """Реєструє всі роутери у головному диспетчері."""
    
    # Створюємо список роутерів (порядок важливий!)
    all_routers = [
        # Більш специфічні роутери (наприклад, для команд) - спочатку
        start_router,
        transactions_router,
        statistics_router,
        subscriptions_router,
        goals_router,
        ai_analysis_router,
        settings_router,
        support_router,
        # Загальні обробники тексту мають бути в кінці
    ]

    # Включаємо кожен роутер у диспетчер
    for router in all_routers:
        dp.include_router(router)
        # ✅ ВИПРАВЛЕНО: Використовуємо переданий 'logger' замість помилкового 'dp.logger'
        logger.info(f"✅ Router included: {router.name}") 
        
    # ✅ ВИПРАВЛЕНО: Використовуємо переданий 'logger'
    logger.info(f"✅ Всі {len(all_routers)} роутерів успішно зареєстровані в диспетчері.")
