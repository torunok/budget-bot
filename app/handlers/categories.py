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

from app.core.states import BudgetState
from app.services.sheets_service import sheets_service
from app.keyboards.reply import get_main_menu_keyboard
from app.utils.validators import validate_amount, validate_category
from app.utils.formatters import format_currency

logger = logging.getLogger(__name__)
router = Router()
BUDGET_CANCEL_COMMANDS = {"0", "скасувати", "відміна", "cancel"}
BUDGET_DELETE_COMMANDS = {"видалити", "delete", "remove"}


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
    """Показує бюджети за категоріями"""
    nickname = callback.from_user.username or "anonymous"
    try:
        text, keyboard = _build_budget_overview(nickname)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    except Exception as exc:
        logger.error('Error showing budgets: %s', exc, exc_info=True)
        await callback.answer('❌ Помилка', show_alert=True)


def _build_budget_overview(nickname: str) -> tuple[str, InlineKeyboardMarkup]:
    try:
        transactions = sheets_service.get_all_transactions(nickname)
    except Exception as exc:
        logger.error("Unable to load transactions for budgets: %s", exc, exc_info=True)
        transactions = []
    budgets = sheets_service.get_budget_status(nickname, transactions=transactions)

    if not budgets:
        text = (
            "💰 <b>Бюджети по категоріях</b>\n\n"
            "Поки що бюджети не задані.\n"
            "Створи ліміт для категорії, щоб бот попереджав про перевитрати."
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Встановити бюджет", callback_data="set_budget")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_categories")]
        ])
        return text, keyboard

    lines = ["💰 <b>Бюджети по категоріях</b>\n"]
    for budget in budgets:
        category = budget.get('category', 'Без назви')
        limit = float(budget.get('limit', budget.get('budget_amount', 0)) or 0)
        spent = float(budget.get('calculated_spent', budget.get('current_spent', 0)) or 0)
        percentage = budget.get('percentage')
        if percentage is None:
            percentage = (spent / limit * 100) if limit > 0 else 0
        period = (budget.get('period') or 'monthly')

        if percentage < 70:
            status = "✅"
        elif percentage < 90:
            status = "⚠️"
        else:
            status = "🔴"

        lines.append(
            f"\n{status} <b>{category}</b> ({period})\n"
            f"   Витрачено: {format_currency(spent)} / {format_currency(limit)}\n"
            f"   {create_budget_bar(percentage)} {percentage:.1f}%"
        )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Додати", callback_data="set_budget"),
            InlineKeyboardButton(text="✏️ Змінити", callback_data="edit_budget")
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_categories")]
    ])
    return "\n".join(lines), keyboard


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


# ==================== КЕРУВАННЯ БЮДЖЕТАМИ ====================

@router.callback_query(F.data == "set_budget")
async def start_set_budget(callback: CallbackQuery, state: FSMContext):
    """Запускає сценарій створення бюджету"""
    await state.clear()
    await callback.message.answer(
        "📌 <b>Новий бюджет</b>\n\n"
        "Введи назву категорії, для якої хочеш встановити ліміт."
    )
    await state.set_state(BudgetState.set_category)
    await callback.answer()


@router.message(BudgetState.set_category)
async def process_budget_category(message: Message, state: FSMContext):
    """Зберігає категорію для бюджету"""
    is_valid, category, error = validate_category(message.text)
    if not is_valid:
        await message.reply(f"❌ {error}")
        return

    await state.update_data(budget_category=category)
    await message.answer(
        f"Категорія: <b>{category}</b>\n"
        "Вкажи місячний ліміт у гривнях."
    )
    await state.set_state(BudgetState.set_amount)


@router.message(BudgetState.set_amount)
async def process_budget_amount(message: Message, state: FSMContext):
    """Створює бюджет з введеною сумою"""
    is_valid, amount, error = validate_amount(message.text)
    if not is_valid or amount <= 0:
        await message.reply(f"❌ {error or 'Сума має бути більшою за 0.'}")
        return

    data = await state.get_data()
    category = data.get("budget_category")
    nickname = message.from_user.username or "anonymous"

    try:
        sheets_service.set_category_budget(nickname, category, abs(amount))
        await message.answer(
            f"✅ Бюджет для <b>{category}</b> встановлено: {format_currency(abs(amount))} на місяць."
        )
        text, keyboard = _build_budget_overview(nickname)
        await message.answer(text, reply_markup=keyboard)
    except Exception as exc:
        logger.error("Error setting budget: %s", exc, exc_info=True)
        await message.reply("❌ Не вдалося зберегти бюджет.")
    finally:
        await state.clear()


@router.callback_query(F.data == "edit_budget")
async def start_edit_budget(callback: CallbackQuery, state: FSMContext):
    """Показує список бюджетів для редагування"""
    nickname = callback.from_user.username or "anonymous"
    try:
        budgets = sheets_service.get_budget_status(nickname)
        if not budgets:
            await callback.answer("Немає створених бюджетів.", show_alert=True)
            return

        lines = ["✏️ <b>Оберіть бюджет для редагування</b>\n"]
        for idx, budget in enumerate(budgets, start=1):
            limit = float(budget.get('limit', budget.get('budget_amount', 0)) or 0)
            spent = float(budget.get('calculated_spent', 0) or 0)
            lines.append(
                f"{idx}. {budget.get('category', 'Без назви')} — "
                f"{format_currency(spent)} / {format_currency(limit)}"
            )

        lines.append("\nВідправ номер бюджету або 0 для скасування.")
        await callback.message.edit_text("\n".join(lines))
        await state.update_data(budget_list=budgets, budget_owner=nickname)
        await state.set_state(BudgetState.edit_select)
        await callback.answer()
    except Exception as exc:
        logger.error("Error loading budgets for edit: %s", exc, exc_info=True)
        await callback.answer("❌ Помилка завантаження бюджетів", show_alert=True)


@router.message(BudgetState.edit_select)
async def select_budget_to_edit(message: Message, state: FSMContext):
    """Отримує номер бюджету для оновлення"""
    text = message.text.strip()
    if text.lower() in BUDGET_CANCEL_COMMANDS:
        await state.clear()
        await message.answer("Операцію скасовано.", reply_markup=get_categories_menu())
        return

    if not text.isdigit():
        await message.reply("Введи номер бюджету з списку.")
        return

    idx = int(text)
    data = await state.get_data()
    budgets = data.get("budget_list") or []

    if idx < 1 or idx > len(budgets):
        await message.reply("Невірний номер. Спробуй ще раз.")
        return

    selected = budgets[idx - 1]
    await state.update_data(selected_budget=selected)
    await state.set_state(BudgetState.edit_amount)
    await message.answer(
        f"Обрано <b>{selected.get('category')}</b>.\n"
        "Введи новий ліміт у гривнях або напиши 'видалити'.\n"
        "0 — скасувати."
    )


@router.message(BudgetState.edit_amount)
async def process_budget_edit(message: Message, state: FSMContext):
    """Оновлює або видаляє обраний бюджет"""
    text = message.text.strip()
    data = await state.get_data()
    nickname = data.get("budget_owner") or message.from_user.username or "anonymous"
    selected = data.get("selected_budget") or {}
    category = selected.get("category")

    if text.lower() in BUDGET_CANCEL_COMMANDS:
        await state.clear()
        await message.answer("Зміни скасовано.", reply_markup=get_categories_menu())
        return

    try:
        if text.lower() in BUDGET_DELETE_COMMANDS:
            sheets_service.delete_category_budget(nickname, category)
            await message.answer(f"🗑️ Бюджет для <b>{category}</b> видалено.")
        else:
            is_valid, amount, error = validate_amount(text)
            if not is_valid or amount <= 0:
                await message.reply(f"❌ {error or 'Сума має бути більшою за 0.'}")
                return
            sheets_service.set_category_budget(nickname, category, abs(amount))
            await message.answer(
                f"✅ Ліміт для <b>{category}</b> оновлено: {format_currency(abs(amount))}."
            )

        text_output, keyboard = _build_budget_overview(nickname)
        await message.answer(text_output, reply_markup=keyboard)
    except Exception as exc:
        logger.error("Error editing budget: %s", exc, exc_info=True)
        await message.reply("❌ Не вдалося оновити бюджет.")
    finally:
        await state.clear()
