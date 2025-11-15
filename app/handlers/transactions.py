# ============================================
# FILE: app/handlers/transactions.py (COMPLETE FULL VERSION)
# ============================================
"""
Обробники для транзакцій (витрати/доходи) - ПОВНА ВЕРСІЯ
"""
import logging
from typing import List
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.core.states import UserState, TransactionState
from app.services.sheets_service import sheets_service
from app.keyboards.inline import get_transaction_edit_keyboard
from app.keyboards.reply import get_main_menu_keyboard
from app.utils.validators import validate_amount, validate_category
from app.utils.formatters import format_currency, format_transaction_list

logger = logging.getLogger(__name__)
router = Router()

BUDGET_WARN_THRESHOLD = 70
BUDGET_ALERT_THRESHOLD = 90

CATEGORY_CALLBACK_PREFIX = "txcat"
CANCEL_COMMANDS = {"0", "скасувати", "відміна", "cancel", "stop", "стоп"}
DEFAULT_EXPENSE_CATEGORIES = [
    "Продукти",
    "Транспорт",
    "Розваги",
    "Комунальні",
    "Заощадження",
    "Інше",
]
DEFAULT_INCOME_CATEGORIES = [
    "Зарплата",
    "Бонус",
    "Фріланс",
    "Подарунки",
    "Інше",
]


def _gather_category_options(nickname: str, is_expense: bool) -> List[str]:
    """Повертає список категорій для вибору."""
    try:
        user_categories = sheets_service.get_user_categories(nickname, is_expense=is_expense)
    except Exception as exc:
        logger.error("Error loading categories for %s: %s", nickname, exc, exc_info=True)
        user_categories = []

    seen = set()
    options: List[str] = []
    for category in user_categories:
        name = (category.get('category_name') or "").strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        options.append(name)

    if options:
        return options

    return list(DEFAULT_EXPENSE_CATEGORIES if is_expense else DEFAULT_INCOME_CATEGORIES)


def _build_category_keyboard(categories: List[str]) -> InlineKeyboardMarkup:
    """Створює клавіатуру для вибору категорії."""
    rows = []
    row = []
    for idx, category in enumerate(categories):
        row.append(InlineKeyboardButton(text=category, callback_data=f"{CATEGORY_CALLBACK_PREFIX}:{idx}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton(text="➕ Додати категорію", callback_data=f"{CATEGORY_CALLBACK_PREFIX}:add")])
    rows.append([InlineKeyboardButton(text="❌ Скасувати", callback_data=f"{CATEGORY_CALLBACK_PREFIX}:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _build_budget_alert(nickname: str, category: str, currency: str) -> str:
    """Повертає попередження, якщо бюджет по категорії близький до ліміту."""
    try:
        budgets = sheets_service.get_budget_status(nickname)
    except Exception as exc:
        logger.error("Budget warning skipped: %s", exc, exc_info=True)
        return ""

    normalized_category = (category or "").strip().lower()
    for budget in budgets:
        budget_category = (budget.get('category') or "").strip()
        if budget_category.lower() != normalized_category:
            continue

        limit_amount = float(budget.get('limit', budget.get('budget_amount', 0)) or 0)
        if limit_amount <= 0:
            return ""

        spent = float(budget.get('calculated_spent', budget.get('current_spent', 0)) or 0)
        percentage = float(budget.get('percentage') or 0)
        if not percentage and spent and limit_amount:
            percentage = spent / limit_amount * 100

        if percentage < BUDGET_WARN_THRESHOLD:
            return ""

        remaining = max(limit_amount - spent, 0)
        period = (budget.get('period') or "строк").lower()
        period_label = {
            "monthly": "цього місяця",
            "weekly": "цього тижня",
            "yearly": "цього року",
        }.get(period, "за вибраний період")

        if percentage >= 100:
            heading = "🔴 <b>Бюджет перевищено</b>"
        elif percentage >= BUDGET_ALERT_THRESHOLD:
            heading = "🔴 <b>Майже вичерпано бюджет</b>"
        else:
            heading = "⚠️ <b>Бюджет майже використано</b>"

        lines = [
            heading,
            (
                f"Категорія «{budget_category or category}» витратила "
                f"{format_currency(spent, currency)} з "
                f"{format_currency(limit_amount, currency)} {period_label}."
            ),
        ]
        if remaining > 0:
            lines.append(f"Залишок: {format_currency(remaining, currency)}.")
        return "\n".join(lines)

    return ""


# ==================== ДОДАВАННЯ ТРАНЗАКЦІЙ ====================


async def _start_transaction_flow(message: Message, state: FSMContext, transaction_type: str):
    """Починає покроковий сценарій додавання транзакції."""
    await state.set_state(None)
    await state.update_data(transaction_type=transaction_type)

    if transaction_type == "expense":
        prefix = "💸 <b>Додаємо витрату</b>\n"
    else:
        prefix = "💰 <b>Додаємо дохід</b>\n"

    await message.answer(
        prefix +
        "Введи лише суму (наприклад: <code>150</code> або <code>150.75</code>).\n"
        "Надішли 0 або «скасувати», щоб відмінити додавання.",
        reply_markup=get_main_menu_keyboard()
    )
    await state.set_state(TransactionState.waiting_amount)


@router.message(F.text == "📉 Додати витрату")
async def add_expense_handler(message: Message, state: FSMContext):
    """Початок додавання витрати"""
    await _start_transaction_flow(message, state, "expense")


@router.message(F.text == "📈 Додати дохід")
async def add_income_handler(message: Message, state: FSMContext):
    """Початок додавання доходу"""
    await _start_transaction_flow(message, state, "income")


@router.message(TransactionState.waiting_amount)
async def process_transaction_amount(message: Message, state: FSMContext):
    """Обробляє суму транзакції та показує категорії."""
    text = (message.text or "").strip()
    if text.lower() in CANCEL_COMMANDS:
        await state.set_state(None)
        await message.answer("Додавання транзакції скасовано.")
        return

    is_valid, amount_value, error = validate_amount(text)
    if not is_valid or amount_value is None:
        await message.reply(f"❌ {error}\nСпробуй ще раз, наприклад: <code>150</code>")
        return

    data = await state.get_data()
    transaction_type = data.get('transaction_type') or "expense"
    is_expense = transaction_type == "expense"

    if is_expense and amount_value > 0:
        amount_value = -amount_value
    elif not is_expense and amount_value < 0:
        amount_value = abs(amount_value)

    nickname = message.from_user.username or "anonymous"
    categories = _gather_category_options(nickname, is_expense=is_expense)

    await state.update_data(
        amount=amount_value,
        category=None,
        note="",
        category_options=categories,
    )
    await state.set_state(TransactionState.choosing_category)

    await message.answer(
        "📂 Обери категорію для цієї транзакції:",
        reply_markup=_build_category_keyboard(categories)
    )


@router.callback_query(TransactionState.choosing_category, F.data.startswith(f"{CATEGORY_CALLBACK_PREFIX}:"))
async def process_category_choice(callback: CallbackQuery, state: FSMContext):
    """Обробляє вибір категорії або додавання нової."""
    action = callback.data.split(":", maxsplit=1)[1]
    data = await state.get_data()

    if action == "cancel":
        await state.set_state(None)
        await callback.message.edit_text("Додавання транзакції скасовано.")
        await callback.answer()
        return

    if action == "add":
        await state.set_state(TransactionState.adding_custom_category)
        await callback.message.edit_text(
            "Введи назву нової категорії.\n"
            "Можна додати emoji. Надішли 0 або «скасувати», щоб повернутися."
        )
        await callback.answer()
        return

    categories = data.get('category_options') or []
    try:
        idx = int(action)
        selected_category = categories[idx]
    except (ValueError, IndexError):
        await callback.answer("Категорія не знайдена", show_alert=True)
        return

    await state.update_data(category=selected_category)
    await state.set_state(TransactionState.entering_description)
    await callback.message.edit_text(
        f"📂 Обрано категорію: <b>{selected_category}</b>\n\n"
        "📝 Введи опис транзакції (наприклад: <code>Булочка з маком</code>)\n"
        "Або надішли «-», щоб пропустити.",
    )
    await callback.answer()


@router.message(TransactionState.adding_custom_category)
async def process_custom_category(message: Message, state: FSMContext):
    """Додає нову категорію та одразу використовує її."""
    text = (message.text or "").strip()
    if text.lower() in CANCEL_COMMANDS:
        data = await state.get_data()
        categories = data.get('category_options') or []
        if not categories:
            nickname = message.from_user.username or "anonymous"
            is_expense = (data.get('transaction_type') or "expense") == "expense"
            categories = _gather_category_options(nickname, is_expense=is_expense)
            await state.update_data(category_options=categories)
        await state.set_state(TransactionState.choosing_category)
        await message.answer(
            "Добре, обери категорію зі списку:",
            reply_markup=_build_category_keyboard(categories)
        )
        return

    is_valid, category_name, error = validate_category(text)
    if not is_valid:
        await message.reply(f"❌ {error}")
        return

    data = await state.get_data()
    transaction_type = data.get('transaction_type') or "expense"
    is_expense = transaction_type == "expense"
    nickname = message.from_user.username or "anonymous"

    try:
        sheets_service.add_custom_category(nickname, category_name, is_expense=is_expense)
    except ValueError as exc:
        await message.reply(f"⚠️ {exc}")
        return
    except Exception as exc:
        logger.error("Error adding custom category: %s", exc, exc_info=True)
        await message.reply("❌ Не вдалося додати категорію. Спробуй пізніше.")
        return

    categories = data.get('category_options') or []
    if category_name not in categories:
        categories.append(category_name)
        await state.update_data(category_options=categories)

    await state.update_data(category=category_name)
    await state.set_state(TransactionState.entering_description)
    await message.answer(
        f"✅ Категорія «{category_name}» додана та вибрана.\n\n"
        "📝 Тепер введи опис транзакції або «-», щоб пропустити."
    )


@router.message(TransactionState.entering_description)
async def process_transaction_description(message: Message, state: FSMContext):
    """Отримує опис та створює транзакцію."""
    text = (message.text or "").strip()
    if text.lower() in CANCEL_COMMANDS:
        await state.set_state(None)
        await message.answer("Додавання транзакції скасовано.")
        return

    note = "" if text in {"", "-"} else text
    if len(note) > 200:
        await message.reply("❌ Опис занадто довгий. Максимум 200 символів.")
        return

    data = await state.get_data()
    transaction_type = data.get('transaction_type') or "expense"
    amount = data.get('amount')
    category = data.get('category')

    if amount is None:
        await message.answer("Спочатку введи суму.")
        await state.set_state(TransactionState.waiting_amount)
        return
    if not category:
        await message.answer("Спочатку обери категорію.")
        await state.set_state(TransactionState.choosing_category)
        return

    nickname = message.from_user.username or "anonymous"

    try:
        row_index = sheets_service.append_transaction(
            user_id=message.from_user.id,
            nickname=nickname,
            amount=amount,
            category=category,
            note=note
        )

        await state.update_data(
            last_transaction_row=row_index,
            transaction_type=transaction_type,
            amount=amount,
            category=category,
            note=note,
            category_options=[],
        )

        is_expense = transaction_type == "expense"
        transaction_label = "витрата" if is_expense else "дохід"
        emoji = "📉" if is_expense else "📈"

        balance, currency = sheets_service.get_current_balance(nickname)
        budget_alert = ""
        if is_expense:
            budget_alert = _build_budget_alert(nickname, category, currency)

        response_text = (
            f"{emoji} <b>Додано {transaction_label}</b>\n\n"
            f"💰 Сума: {format_currency(abs(amount), currency)}\n"
            f"📂 Категорія: {category}\n"
            f"📝 Опис: {note or '—'}\n"
            f"💳 Новий баланс: {format_currency(balance, currency)}\n\n"
            "Хочеш щось змінити?"
        )
        if budget_alert:
            response_text += f"\n\n{budget_alert}"

        await message.answer(
            response_text,
            reply_markup=get_transaction_edit_keyboard()
        )

        await state.set_state(None)

    except Exception as exc:
        logger.error("Error adding transaction: %s", exc, exc_info=True)
        await message.reply("❌ Помилка при додаванні транзакції. Спробуй ще раз.")


# ==================== РЕДАГУВАННЯ ТРАНЗАКЦІЙ ====================

@router.callback_query(F.data == "edit_amount")
async def edit_amount_handler(callback: CallbackQuery, state: FSMContext):
    """Початок редагування суми"""
    data = await state.get_data()
    current_amount = data.get('amount', 0)
    
    await callback.message.edit_text(
        f"✏️ <b>Редагування суми</b>\n\n"
        f"Поточна сума: {format_currency(abs(current_amount))}\n\n"
        f"Введи нову суму:"
    )
    await state.set_state(UserState.edit_amount)
    await callback.answer()


@router.message(UserState.edit_amount)
async def process_edit_amount(message: Message, state: FSMContext):
    """Обробка нової суми"""
    is_valid, amount, error = validate_amount(message.text)
    
    if not is_valid:
        await message.reply(f"❌ {error}")
        return
    
    data = await state.get_data()
    row_index = data.get('last_transaction_row')
    transaction_type = data.get('transaction_type')
    nickname = message.from_user.username or "anonymous"
    
    # Визначаємо знак
    if transaction_type == "expense" and amount > 0:
        amount = -amount
    elif transaction_type == "income" and amount < 0:
        amount = abs(amount)
    
    try:
        # Оновлюємо в Google Sheets (колонка 3 = amount)
        sheets_service.update_transaction(nickname, row_index, 3, amount)
        
        balance, currency = sheets_service.get_current_balance(nickname)
        await state.update_data(amount=amount)
        
        category = data.get('category', 'Інше')
        note = data.get('note', '')
        
        await message.answer(
            f"✅ <b>Сума оновлена!</b>\n\n"
            f"💰 Нова сума: {format_currency(abs(amount), currency)}\n"
            f"📂 Категорія: {category}\n"
            f"📝 Опис: {note or '—'}\n"
            f"💳 Новий баланс: {format_currency(balance, currency)}\n\n"
            f"Що ще змінити?",
            reply_markup=get_transaction_edit_keyboard()
        )
        
        await state.set_state(None)
        
    except Exception as e:
        logger.error(f"Error updating amount: {e}", exc_info=True)
        await message.reply("❌ Помилка при оновленні суми")


@router.callback_query(F.data == "edit_category")
async def edit_category_handler(callback: CallbackQuery, state: FSMContext):
    """Початок редагування категорії"""
    data = await state.get_data()
    current_category = data.get('category', 'Інше')
    
    await callback.message.edit_text(
        f"✏️ <b>Редагування категорії</b>\n\n"
        f"Поточна категорія: <b>{current_category}</b>\n\n"
        f"Введи нову категорію:\n"
        f"Наприклад: <code>Їжа</code>, <code>Транспорт</code>, <code>Розваги</code>"
    )
    await state.set_state(UserState.edit_category)
    await callback.answer()


@router.message(UserState.edit_category)
async def process_edit_category(message: Message, state: FSMContext):
    """Обробка нової категорії"""
    new_category = message.text.strip().capitalize()
    
    if len(new_category) > 50:
        await message.reply("❌ Категорія занадто довга. Максимум 50 символів.")
        return
    
    data = await state.get_data()
    row_index = data.get('last_transaction_row')
    nickname = message.from_user.username or "anonymous"
    
    try:
        # Оновлюємо в Google Sheets (колонка 4 = category)
        sheets_service.update_transaction(nickname, row_index, 4, new_category)
        
        await state.update_data(category=new_category)
        
        amount = data.get('amount', 0)
        note = data.get('note', '')
        balance, currency = sheets_service.get_current_balance(nickname)
        
        await message.answer(
            f"✅ <b>Категорія оновлена!</b>\n\n"
            f"📂 Нова категорія: {new_category}\n"
            f"💰 Сума: {format_currency(abs(amount), currency)}\n"
            f"📝 Опис: {note or '—'}\n\n"
            f"Що ще змінити?",
            reply_markup=get_transaction_edit_keyboard()
        )
        
        await state.set_state(None)
        
    except Exception as e:
        logger.error(f"Error updating category: {e}", exc_info=True)
        await message.reply("❌ Помилка при оновленні категорії")


@router.callback_query(F.data == "edit_description")
async def edit_description_handler(callback: CallbackQuery, state: FSMContext):
    """Початок редагування опису"""
    data = await state.get_data()
    current_note = data.get('note', '')
    
    await callback.message.edit_text(
        f"✏️ <b>Редагування опису</b>\n\n"
        f"Поточний опис: <i>{current_note or 'немає'}</i>\n\n"
        f"Введи новий опис або '-' щоб видалити:"
    )
    await state.set_state(UserState.edit_description)
    await callback.answer()


@router.message(UserState.edit_description)
async def process_edit_description(message: Message, state: FSMContext):
    """Обробка нового опису"""
    new_note = message.text.strip()
    
    if new_note == "-":
        new_note = ""
    
    if len(new_note) > 200:
        await message.reply("❌ Опис занадто довгий. Максимум 200 символів.")
        return
    
    data = await state.get_data()
    row_index = data.get('last_transaction_row')
    nickname = message.from_user.username or "anonymous"
    
    try:
        # Оновлюємо в Google Sheets (колонка 5 = note)
        sheets_service.update_transaction(nickname, row_index, 5, new_note)
        
        await state.update_data(note=new_note)
        
        amount = data.get('amount', 0)
        category = data.get('category', 'Інше')
        balance, currency = sheets_service.get_current_balance(nickname)
        
        await message.answer(
            f"✅ <b>Опис оновлено!</b>\n\n"
            f"📝 Новий опис: {new_note or '—'}\n"
            f"💰 Сума: {format_currency(abs(amount), currency)}\n"
            f"📂 Категорія: {category}\n\n"
            f"Що ще змінити?",
            reply_markup=get_transaction_edit_keyboard()
        )
        
        await state.set_state(None)
        
    except Exception as e:
        logger.error(f"Error updating description: {e}", exc_info=True)
        await message.reply("❌ Помилка при оновленні опису")


# ==================== ВИДАЛЕННЯ ТРАНЗАКЦІЇ ====================

@router.callback_query(F.data == "delete_transaction")
async def delete_transaction_confirm(callback: CallbackQuery, state: FSMContext):
    """Підтвердження видалення транзакції"""
    data = await state.get_data()
    amount = data.get('amount', 0)
    category = data.get('category', '')
    
    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Так, видалити", callback_data="confirm_delete"),
            InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_delete")
        ]
    ])
    
    await callback.message.edit_text(
        f"🗑️ <b>Підтвердження видалення</b>\n\n"
        f"Ти впевнений, що хочеш видалити цю транзакцію?\n\n"
        f"💰 Сума: {format_currency(abs(amount))}\n"
        f"📂 Категорія: {category}\n\n"
        f"⚠️ Цю дію не можна буде скасувати!",
        reply_markup=confirm_keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "confirm_delete")
async def process_delete_transaction(callback: CallbackQuery, state: FSMContext):
    """Видалення транзакції"""
    data = await state.get_data()
    row_index = data.get('last_transaction_row')
    nickname = callback.from_user.username or "anonymous"
    
    try:
        # Видаляємо транзакцію
        sheets_service.delete_transaction(nickname, row_index)
        
        balance, currency = sheets_service.get_current_balance(nickname)
        
        await callback.message.edit_text(
            f"✅ <b>Транзакція видалена</b>\n\n"
            f"💳 Новий баланс: {format_currency(balance, currency)}"
        )
        
        await state.clear()
        
        # Повертаємо головне меню
        await callback.message.answer(
            "Обирай наступну дію:",
            reply_markup=get_main_menu_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error deleting transaction: {e}", exc_info=True)
        await callback.message.edit_text("❌ Помилка при видаленні транзакції")
    
    await callback.answer()


@router.callback_query(F.data == "cancel_delete")
async def cancel_delete_transaction(callback: CallbackQuery, state: FSMContext):
    """Скасування видалення"""
    data = await state.get_data()
    amount = data.get('amount', 0)
    category = data.get('category', '')
    note = data.get('note', '')
    balance, currency = sheets_service.get_current_balance(
        callback.from_user.username or "anonymous"
    )
    
    await callback.message.edit_text(
        f"💰 <b>Транзакція збережена</b>\n\n"
        f"Сума: {format_currency(abs(amount), currency)}\n"
        f"Категорія: {category}\n"
        f"Опис: {note or '—'}\n\n"
        f"Що ще змінити?",
        reply_markup=get_transaction_edit_keyboard()
    )
    await callback.answer("Видалення скасовано")


# ==================== ЗАВЕРШЕННЯ РЕДАГУВАННЯ ====================

@router.callback_query(F.data == "finish_editing")
async def finish_editing_handler(callback: CallbackQuery, state: FSMContext):
    """Завершення редагування транзакції"""
    data = await state.get_data()
    amount = data.get('amount', 0)
    category = data.get('category', '')
    note = data.get('note', '')
    balance, currency = sheets_service.get_current_balance(
        callback.from_user.username or "anonymous"
    )
    
    await callback.message.edit_text(
        f"✅ <b>Транзакція збережена</b>\n\n"
        f"💰 Сума: {format_currency(abs(amount), currency)}\n"
        f"📂 Категорія: {category}\n"
        f"📝 Опис: {note or '—'}\n"
        f"💳 Поточний баланс: {format_currency(balance, currency)}"
    )
    
    await state.clear()
    
    await callback.message.answer(
        "Обирай наступну дію:",
        reply_markup=get_main_menu_keyboard()
    )
    
    await callback.answer("✅ Готово!")


# ==================== ПЕРЕГЛЯД ОСТАННІХ ТРАНЗАКЦІЙ ====================

@router.callback_query(F.data == "view_recent_transactions")
async def view_recent_transactions(callback: CallbackQuery):
    """Показує останні 10 транзакцій"""
    nickname = callback.from_user.username or "anonymous"
    
    try:
        transactions = sheets_service.get_all_transactions(nickname)
        
        if not transactions:
            await callback.answer("Транзакцій поки немає", show_alert=True)
            return
        
        # Беремо останні 10 (в зворотному порядку)
        recent = list(reversed(transactions))[:10]
        
        formatted = format_transaction_list(recent, limit=10)
        balance, currency = sheets_service.get_current_balance(nickname)
        
        await callback.message.edit_text(
            f"📜 <b>Останні транзакції</b>\n\n"
            f"{formatted}\n\n"
            f"💳 Поточний баланс: {format_currency(balance, currency)}"
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error viewing transactions: {e}", exc_info=True)
        await callback.answer("❌ Помилка", show_alert=True)
