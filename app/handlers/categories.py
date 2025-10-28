# ============================================
# FILE: app/handlers/categories.py (NEW)
# ============================================
"""
Обробники для управління категоріями
"""

import logging
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.services.sheets_service import sheets_service
from app.keyboards.reply import get_main_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()


def get_categories_menu() -> InlineKeyboardMarkup:
    """Меню управління категоріями"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Мої категорії", callback_data="view_categories"),
            InlineKeyboardButton(text="➕ Додати", callback_data="add_category")
        ],
        [
            InlineKeyboardButton(text="✏️ Редагувати", callback_data="edit_category"),
            InlineKeyboardButton(text="🗑️ Видалити", callback_data="delete_category")
        ],
        [
            InlineKeyboardButton(text="💰 Бюджети", callback_data="category_budgets")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_settings")
        ]
    ])


@router.callback_query(F.data == "manage_categories")
async def show_categories_menu(callback: CallbackQuery):
    """Показує меню категорій"""
    await callback.message.edit_text(
        "📂 <b>Управління категоріями</b>\n\n"
        "Тут ти можеш:\n"
        "• Переглянути свої категорії\n"
        "• Додати нові категорії\n"
        "• Встановити бюджети\n"
        "• Персоналізувати облік\n\n"
        "Обирай дію:",
        reply_markup=get_categories_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "view_categories")
async def view_categories(callback: CallbackQuery):
    """Показує всі категорії користувача"""
    nickname = callback.from_user.username or "anonymous"
    
    try:
        expense_categories = sheets_service.get_user_categories(nickname, is_expense=True)
        income_categories = sheets_service.get_user_categories(nickname, is_expense=False)
        
        text_lines = ["📂 <b>Твої категорії:</b>\n"]
        
        # Витрати
        text_lines.append("\n<b>📉 Категорії витрат:</b>")
        if expense_categories:
            for cat in expense_categories:
                emoji = cat.get('emoji', '📌')
                name = cat.get('category_name', '')
                text_lines.append(f"  {emoji} {name}")
        else:
            text_lines.append("  <i>Використовуються стандартні категорії</i>")
        
        # Доходи
        text_lines.append("\n<b>📈 Категорії доходів:</b>")
        if income_categories:
            for cat in income_categories:
                emoji = cat.get('emoji', '💰')
                name = cat.get('category_name', '')
                text_lines.append(f"  {emoji} {name}")
        else:
            text_lines.append("  <i>Використовуються стандартні категорії</i>")
        
        # Стандартні категорії
        text_lines.append("\n\n<b>💡 Стандартні категорії:</b>")
        default_categories = [
            "Їжа 🍕", "Транспорт 🚗", "Розваги 🎬",
            "Здоров'я 💊", "Освіта 📚", "Одяг 👕",
            "Комунальні 🏠", "Інтернет 🌐", "Інше 📌"
        ]
        text_lines.append("  " + ", ".join(default_categories))
        
        await callback.message.edit_text(
            "\n".join(text_lines),
            reply_markup=get_categories_menu()
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error viewing categories: {e}", exc_info=True)
        await callback.answer("❌ Помилка", show_alert=True)


# ==================== БЮДЖЕТИ ПО КАТЕГОРІЯХ ====================

@router.callback_query(F.data == "category_budgets")
async def show_category_budgets(callback: CallbackQuery):
    """Показує бюджети по категоріях"""
    nickname = callback.from_user.username or "anonymous"
    
    try:
        budgets = sheets_service.get_category_budgets(nickname)
        
        if not budgets:
            await callback.message.edit_text(
                "💰 <b>Бюджети по категоріях</b>\n\n"
                "У тебе поки немає встановлених бюджетів.\n\n"
                "Встанови ліміт на витрати для кожної категорії,\n"
                "і бот буде попереджати про перевитрати!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Встановити бюджет", callback_data="set_budget")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_categories")]
                ])
            )
            await callback.answer()
            return
        
        text_lines = ["💰 <b>Бюджети по категоріях</b>\n"]
        
        for budget in budgets:
            category = budget.get('category', '')
            limit = float(budget.get('budget_amount', 0))
            spent = float(budget.get('current_spent', 0))
            period = budget.get('period', 'monthly')
            
            percentage = (spent / limit * 100) if limit > 0 else 0
            
            # Статус
            if percentage < 70:
                status = "✅"
            elif percentage < 90:
                status = "⚠️"
            else:
                status = "🔴"
            
            progress_bar = create_budget_bar(percentage)
            
            text_lines.append(
                f"\n{status} <b>{category}</b> ({period})\n"
                f"   Витрачено: {spent:.0f} / {limit:.0f} UAH\n"
                f"   {progress_bar} {percentage:.1f}%"
            )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Додати", callback_data="set_budget"),
                InlineKeyboardButton(text="✏️ Змінити", callback_data="edit_budget")
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_categories")]
        ])
        
        await callback.message.edit_text(
            "\n".join(text_lines),
            reply_markup=keyboard
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing budgets: {e}", exc_info=True)
        await callback.answer("❌ Помилка", show_alert=True)


def create_budget_bar(percentage: float, length: int = 10) -> str:
    """Створює прогрес-бар для бюджету"""
    filled = int(percentage / 100 * length)
    
    if percentage < 70:
        color = "🟩"
    elif percentage < 90:
        color = "🟨"
    else:
        color = "🟥"
    
    empty = length - filled
    return color * filled + "⬜" * empty