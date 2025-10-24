# ============================================
# FILE: app/handlers/__init__.py
# ============================================
"""
Реєстрація всіх хендлерів
"""

from aiogram import Dispatcher
from .start import router as start_router # Імпортуємо роутер з start.py
from .transactions import router as transactions_router 
from .statistics import router as statistics_router
from .subscriptions import router as subscriptions_router
from .settings import router as settings_router
from .support import router as support_router
from .ai_analysis import router as ai_analysis_router


def register_all_handlers(dp: Dispatcher):
    """Реєструє всі хендлери в диспетчері"""
    
    # Створюємо список роутерів (порядок важливий!)
    all_routers = [
        # Більш специфічні роутери (наприклад, для команд або певних станів) - спочатку
        start_router,
        transactions_router,
        statistics_router,
        subscriptions_router,
        ai_analysis_router,
        settings_router,
        support_router,
        # Загальні обробники тексту мають бути в кінці (якщо є)
    ]

    # Включаємо кожен роутер у диспетчер
    for router in all_routers:
        # aiogram 3.x вимагає, щоб до диспетчера додавалися роутери (або головний роутер)
        dp.include_router(router)
        print(f"✅ Router included: {router.name}") # Логуємо для перевірки
        
    print(f"✅ Всі {len(all_routers)} роутерів успішно зареєстровані в диспетчері.")
