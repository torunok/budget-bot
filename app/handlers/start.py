#File: app/handlers/start.py

"""
Обробник команди /start
"""

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from app.keyboards.reply import get_main_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обробник команди /start"""
    logger.info(f"User @{message.from_user.username} started the bot")
    
    welcome_text = (
        "👋 <b>Вітаю у фінансовому помічнику!</b>\n\n"
        "Я допоможу тобі:\n\n"
        "📉 <b>Вести облік витрат</b> - швидко записуй всі покупки\n"
        "📈 <b>Відстежувати доходи</b> - контролюй фінансові надходження\n"
        "📊 <b>Аналізувати бюджет</b> - дивись статистику за різні періоди\n"
        "🤖 <b>Отримувати AI-аналіз</b> - розумні рекомендації по оптимізації\n"
        "📝 <b>Керувати підписками</b> - не забувай про регулярні платежі\n"
        "🎯 <b>Досягати цілей</b> - встановлюй та відстежуй фінансові цілі\n\n"
        "Просто обирай дію з меню нижче! 👇"
    )
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_menu_keyboard()
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Довідка по боту"""
    help_text = (
        "📖 <b>Як користуватися ботом:</b>\n\n"
        
        "<b>📉 Додати витрату:</b>\n"
        "Введи суму та призначення, наприклад:\n"
        "<code>150 їжа супермаркет</code>\n\n"
        
        "<b>📈 Додати дохід:</b>\n"
        "Так само - сума та опис:\n"
        "<code>5000 зарплата</code>\n\n"
        
        "<b>📊 Статистика:</b>\n"
        "Переглядай витрати за різні періоди,\n"
        "редагуй транзакції, змінюй баланс\n\n"
        
        "<b>🤖 AI Аналіз:</b>\n"
        "Отримуй розумні поради щодо\n"
        "оптимізації твого бюджету\n\n"
        
        "<b>📝 Підписки:</b>\n"
        "Додавай регулярні платежі та\n"
        "отримуй нагадування\n\n"
        
        "Потрібна допомога? Пиши в підтримку! 💬"
    )
    
    await message.answer(help_text)


def register_handlers(router_main):
    """Реєструє хендлери"""
    router_main.include_router(router)