# ============================================
# FILE: app/keyboards/reply.py
# ============================================
"""
Reply клавіатури (постійні кнопки)
"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Головне меню"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📉 Додати витрату"),
                KeyboardButton(text="📈 Додати дохід")
            ],
            [
                KeyboardButton(text="📊 Статистика"),
                KeyboardButton(text="🤖 AI Аналіз")
            ],
            [
                KeyboardButton(text="📝 Підписки"),
                KeyboardButton(text="🎯 Цілі")
            ],
            [
                KeyboardButton(text="💬 Підтримка"),
                KeyboardButton(text="⚙️ Налаштування")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавіатура для скасування"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Скасувати")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )