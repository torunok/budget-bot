# ============================================
# FILE: app/handlers/transactions.py (COMPLETE FULL VERSION)
# ============================================
"""
Обробники для транзакцій (витрати/доходи) - ПОВНА ВЕРСІЯ
"""
import logging
from datetime import datetime, timedelta, timezone
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.core.states import UserState
from app.services.sheets_service import sheets_service
from app.keyboards.inline import get_transaction_edit_keyboard
from app.keyboards.reply import get_main_menu_keyboard
from app.utils.validators import parse_transaction_input, validate_amount
from app.utils.formatters import format_currency, format_transaction_list

logger = logging.getLogger(__name__)
router = Router()

TRANSACTION_INPUT_TIMEOUT = timedelta(minutes=1)


def _new_input_deadline() -> str:
    """Повертає ISO-рядок дедлайну для введення даних"""
    return (datetime.now(timezone.utc) + TRANSACTION_INPUT_TIMEOUT).isoformat()


def _is_input_timeout_expired(data: dict) -> bool:
    """Перевіряє, чи минув час очікування введення"""
    deadline = data.get('input_deadline')
    if not deadline:
        return False
    try:
        expires_at = datetime.fromisoformat(deadline)
    except (TypeError, ValueError):
        return False
    return datetime.now(timezone.utc) >= expires_at

# ==================== ДОДАВАННЯ ТРАНЗАКЦІЙ ====================

@router.message(F.text == "📉 Додати витрату")
async def add_expense_handler(message: Message, state: FSMContext):
    """Початок додавання витрати"""
    await message.answer(
        "💸 Введи суму та призначення витрати:\n\n"
        "Наприклад: <code>150 Продукти Булочка</code>\n"
        "або просто: <code>150 Продукти</code>",
        reply_markup=get_main_menu_keyboard()
    )
    await state.set_state(UserState.add_expense)
    await state.update_data(input_deadline=_new_input_deadline())


@router.message(F.text == "📈 Додати дохід")
async def add_income_handler(message: Message, state: FSMContext):
    """Початок додавання доходу"""
    await message.answer(
        "💰 Введи суму та призначення доходу:\n\n"
        "Наприклад: <code>5000 зарплата</code>\n"
        "або: <code>1500 фріланс</code>",
        reply_markup=get_main_menu_keyboard()
    )
    await state.set_state(UserState.add_income)
    await state.update_data(input_deadline=_new_input_deadline())


@router.message(UserState.add_expense)
@router.message(UserState.add_income)
async def process_transaction(message: Message, state: FSMContext):
    """Обробка введеної транзакції"""
    current_state = await state.get_state()
    is_expense = current_state == UserState.add_expense
    state_data = await state.get_data()
    if _is_input_timeout_expired(state_data):
        await state.clear()
        await message.reply(
            "⏰ Час на введення минув. Відправ команду знову, щоб додати транзакцію."
        )
        return
    
    amount, note = parse_transaction_input(message.text)
    
    if amount is None:
        await message.reply(
            "❌ Некоректна сума. Спробуй ще раз:\n"
            "Наприклад: <code>150 Продукти Булочка</code>"
        )
        return
    
    # Визначаємо категорію (перше слово з опису)
    category = note.split()[0].capitalize() if note else "Інше"
    
    # Додаємо знак до суми
    if is_expense and amount > 0:
        amount = -amount
    elif not is_expense and amount < 0:
        amount = abs(amount)
    
    nickname = message.from_user.username or "anonymous"
    
    try:
        row_index = sheets_service.append_transaction(
            user_id=message.from_user.id,
            nickname=nickname,
            amount=amount,
            category=category,
            note=note
        )
        
        # Зберігаємо дані для можливого редагування
        await state.update_data(
            last_transaction_row=row_index,
            transaction_type="expense" if is_expense else "income",
            amount=amount,
            category=category,
            note=note,
            input_deadline=None
        )
        
        transaction_type = "витрата" if is_expense else "дохід"
        emoji = "📉" if is_expense else "📈"
        
        # Отримуємо новий баланс
        balance, currency = sheets_service.get_current_balance(nickname)
        
        await message.reply(
            f"{emoji} <b>Додано {transaction_type}</b>\n\n"
            f"💰 Сума: {format_currency(abs(amount), currency)}\n"
            f"📂 Категорія: {category}\n"
            f"📝 Опис: {note or '—'}\n"
            f"💳 Новий баланс: {format_currency(balance, currency)}\n\n"
            f"Хочеш щось змінити?",
            reply_markup=get_transaction_edit_keyboard()
        )
        
        await state.set_state(None)
        
    except Exception as e:
        logger.error(f"Error adding transaction: {e}", exc_info=True)
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
