#File: app/handlers/support.py

"""
Обробники для підтримки та відгуків
"""
import logging
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app.core.states import UserState
from app.services.sheets_service import sheets_service
from app.keyboards.inline import get_support_menu
from app.keyboards.reply import get_main_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "💬 Підтримка")
async def show_support(message: Message):
    """Показує меню підтримки"""
    await message.answer(
        "💬 <b>Підтримка</b>\n\n"
        "Маєш питання або пропозиції?\n"
        "Обирай, як зв'язатися:",
        reply_markup=get_support_menu()
    )


@router.callback_query(F.data == "leave_feedback")
async def start_feedback(callback: CallbackQuery, state: FSMContext):
    """Початок залишення відгуку"""
    await callback.message.edit_text(
        "📝 <b>Залиш свій відгук</b>\n\n"
        "Напиши, що тобі подобається,\n"
        "що можна покращити, або які\n"
        "функції ти хотів би бачити.\n\n"
        "Твоя думка дуже важлива! 💙"
    )
    
    await state.set_state(UserState.add_feedback)
    await callback.answer()


@router.message(UserState.add_feedback)
async def process_feedback(message: Message, state: FSMContext):
    """Обробка відгуку"""
    feedback_text = message.text.strip()
    username = message.from_user.username or "anonymous"
    
    try:
        sheets_service.append_feedback(username, feedback_text)
        
        await message.answer(
            "✅ <b>Дякую за відгук!</b>\n\n"
            "Твоя думка допоможе зробити\n"
            "бота кращим! 🚀",
            reply_markup=get_main_menu_keyboard()
        )
        
        logger.info(f"Feedback received from {username}")
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error saving feedback: {e}", exc_info=True)
        await message.answer(
            "❌ Помилка збереження відгуку.\n"
            "Спробуй написати адміну напряму.",
            reply_markup=get_main_menu_keyboard()
        )


def register_handlers(router_main):
    """Реєструє хендлери підтримки"""
    router_main.include_router(router)