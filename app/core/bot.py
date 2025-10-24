# ============================================
# FILE: app/core/bot.py
# ============================================
"""
Ініціалізація бота та диспетчера
"""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config.settings import config

# Ініціалізація бота
bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# Ініціалізація диспетчера
dp = Dispatcher()