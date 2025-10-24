# ============================================
# FILE: app/keyboards/inline.py
# ============================================
"""
Inline клавіатури (кнопки під повідомленнями)
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.config.settings import config


def get_support_menu() -> InlineKeyboardMarkup:
    """Меню підтримки"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📩 Залишити побажання", callback_data="leave_feedback")],
        [InlineKeyboardButton(text="✏️ Зв'язатися з адміном", url="https://t.me/Torunok")]
    ])


def get_settings_menu() -> InlineKeyboardMarkup:
    """Меню налаштувань"""
    buttons = [
        [
            InlineKeyboardButton(text="📚 Як працює бот", callback_data="how_it_works"),
            InlineKeyboardButton(text="🔔 Нагадування", callback_data="reminders_menu")
        ],
        [
            InlineKeyboardButton(text="💱 Валюта", callback_data="currency_settings"),
            InlineKeyboardButton(text="📂 Категорії", callback_data="manage_categories")
        ]
    ]
    
    if config.ENABLE_EXPORT:
        buttons.append([
            InlineKeyboardButton(text="📥 Експорт даних", callback_data="export_data")
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_reminder_settings() -> InlineKeyboardMarkup:
    """Налаштування нагадувань"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Увімкнути", callback_data="enable_reminders"),
            InlineKeyboardButton(text="❌ Вимкнути", callback_data="disable_reminders")
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_settings")]
    ])


def get_transaction_edit_keyboard() -> InlineKeyboardMarkup:
    """Клавіатура для редагування транзакції"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Сума", callback_data="edit_amount"),
            InlineKeyboardButton(text="✏️ Категорія", callback_data="edit_category")
        ],
        [
            InlineKeyboardButton(text="📝 Опис", callback_data="edit_description"),
            InlineKeyboardButton(text="🗑️ Видалити", callback_data="delete_transaction")
        ],
        [InlineKeyboardButton(text="✅ Готово", callback_data="finish_editing")]
    ])


def get_stats_period_keyboard() -> InlineKeyboardMarkup:
    """Вибір періоду для статистики"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Сьогодні", callback_data="stats_today"),
            InlineKeyboardButton(text="Вчора", callback_data="stats_yesterday")
        ],
        [
            InlineKeyboardButton(text="7 днів", callback_data="stats_7days"),
            InlineKeyboardButton(text="14 днів", callback_data="stats_14days")
        ],
        [
            InlineKeyboardButton(text="Місяць", callback_data="stats_month"),
            InlineKeyboardButton(text="Рік", callback_data="stats_year")
        ],
        [
            InlineKeyboardButton(text="✏️ Редагувати", callback_data="edit_transactions"),
            InlineKeyboardButton(text="🔄 Баланс", callback_data="edit_balance_menu")
        ],
        [
            InlineKeyboardButton(text="📊 Графіки", callback_data="show_charts")
        ]
    ])


def get_subscriptions_menu() -> InlineKeyboardMarkup:
    """Меню підписок"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Додати", callback_data="add_subscription"),
            InlineKeyboardButton(text="📝 Всі підписки", callback_data="view_subscriptions")
        ],
        [
            InlineKeyboardButton(text="✏️ Редагувати", callback_data="edit_subscriptions")
        ]
    ])


def get_export_format_keyboard() -> InlineKeyboardMarkup:
    """Вибір формату експорту"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📄 CSV", callback_data="export_csv"),
            InlineKeyboardButton(text="📕 PDF", callback_data="export_pdf")
        ],
        [
            InlineKeyboardButton(text="📊 Excel", callback_data="export_excel")
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_settings")]
    ])


def get_currency_keyboard() -> InlineKeyboardMarkup:
    """Вибір валюти"""
    buttons = []
    for currency in config.SUPPORTED_CURRENCIES:
        buttons.append([
            InlineKeyboardButton(text=currency, callback_data=f"set_currency_{currency}")
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_settings")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)