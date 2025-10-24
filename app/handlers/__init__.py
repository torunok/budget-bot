"""
Реєстрація всіх хендлерів
"""

from aiogram import Dispatcher
# Імпортуємо роутери
from .start import router as start_router 
from .transactions import router as transactions_router 
from .statistics import router as statistics_router
from .subscriptions import router as subscriptions_router
from .settings import router as settings_router
from .support import router as support_router
from .ai_analysis import router as ai_analysis_router


def register_all_handlers(dp: Dispatcher):
    """Реєструє всі роутери у головному диспетчері."""
    
    # Створюємо список роутерів (порядок важливий!)
    all_routers = [
        # Більш специфічні роутери - спочатку
        start_router,
        transactions_router,
        statistics_router,
        subscriptions_router,
        ai_analysis_router,
        settings_router,
        support_router,
        # Загальні обробники тексту мають бути в кінці
    ]

    # Включаємо кожен роутер у диспетчер
    for router in all_routers:
        dp.include_router(router)
        # Використовуємо dp.logger для стандартного логування aiogram, а не print
        dp.logger.info(f"✅ Router included: {router.name}") 
        
    dp.logger.info(f"✅ Всі {len(all_routers)} роутерів успішно зареєстровані в диспетчері.")
