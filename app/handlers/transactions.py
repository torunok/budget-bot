#FILE: app/handlers/transactions.py#

#Обробники для транзакцій (витрати/доходи)

"""
Обробники для транзакцій (витрати/доходи)
"""
import logging
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app.core.states import UserState
from app.services.sheets_service import sheets_service
from app.keyboards.inline import get_transaction_edit_keyboard
from app.keyboards.reply import get_main_menu_keyboard
from app.utils.validators import parse_transaction_input, validate_amount
from app.utils.formatters import format_currency

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "📉 Додати витрату")
async def add_expense_handler(message: Message, state: FSMContext):
    """Початок додавання витрати"""
    await message.answer(
        "💸 Введи суму та призначення витрати:\n\n"
        "Наприклад: <code>150 їжа супермаркет</code>",
        reply_markup=get_main_menu_keyboard()
    )
    await state.set_state(UserState.add_expense)


@router.message(F.text == "📈 Додати дохід")
async def add_income_handler(message: Message, state: FSMContext):
    """Початок додавання доходу"""
    await message.answer(
        "💰 Введи суму та призначення доходу:\n\n"
        "Наприклад: <code>5000 зарплата</code>",
        reply_markup=get_main_menu_keyboard()
    )
    await state.set_state(UserState.add_income)


@router.message(UserState.add_expense)
@router.message(UserState.add_income)
async def process_transaction(message: Message, state: FSMContext):
    """Обробка введеної транзакції"""
    current_state = await state.get_state()
    is_expense = current_state == UserState.add_expense
    
    amount, note = parse_transaction_input(message.text)
    
    if amount is None:
        await message.reply(
            "❌ Некоректна сума. Спробуй ще раз:\n"
            "Наприклад: <code>150 їжа</code>"
        )
        return
    
    # Визначаємо категорію (перше слово з опису)
    category = note.split()[0] if note else "Інше"
    
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
        
        await state.update_data(
            last_transaction_row=row_index,
            transaction_type="expense" if is_expense else "income"
        )
        
        transaction_type = "витрата" if is_expense else "дохід"
        emoji = "📉" if is_expense else "📈"
        
        await message.reply(
            f"{emoji} <b>Додано {transaction_type}</b>\n\n"
            f"Сума: {format_currency(abs(amount))}\n"
            f"Категорія: {category}\n"
            f"Опис: {note or '—'}\n\n"
            f"Хочеш щось змінити?",
            reply_markup=get_transaction_edit_keyboard()
        )
        
        await state.set_state(None)
        
    except Exception as e:
        logger.error(f"Error adding transaction: {e}", exc_info=True)
        await message.reply("❌ Помилка при додаванні транзакції. Спробуй ще раз.")


def register_handlers(router_main):
    """Реєструє хендлери транзакцій"""
    router_main.include_router(router)


