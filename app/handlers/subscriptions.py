#FILE: app/handlers/subscriptions.py

"""
Обробники для управління підписками
"""

import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app.core.states import SubscriptionState
from app.services.sheets_service import sheets_service
from app.keyboards.inline import get_subscriptions_menu
from app.keyboards.reply import get_main_menu_keyboard
from app.utils.validators import validate_amount, validate_date
from app.utils.formatters import format_currency

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "📝 Підписки")
async def show_subscriptions_menu(message: Message):
    """Показує меню підписок"""
    await message.answer(
        "📝 <b>Управління підписками</b>\n\n"
        "Тут ти можеш:\n"
        "• Додавати нові підписки\n"
        "• Переглядати всі активні підписки\n"
        "• Редагувати або видаляти підписки\n\n"
        "Бот автоматично нагадає про платежі!",
        reply_markup=get_subscriptions_menu()
    )


@router.callback_query(F.data == "add_subscription")
async def add_subscription_start(callback: CallbackQuery, state: FSMContext):
    """Початок додавання підписки"""
    await callback.message.delete()
    
    msg = await callback.message.answer(
        "📝 <b>Додавання підписки</b>\n\n"
        "Крок 1/4: Введи назву підписки\n"
        "Наприклад: <code>Netflix</code>"
    )
    
    await state.update_data(last_bot_message_id=msg.message_id)
    await state.set_state(SubscriptionState.add_name)
    await callback.answer()


@router.message(SubscriptionState.add_name)
async def process_subscription_name(message: Message, state: FSMContext):
    """Обробка назви підписки"""
    name = message.text.strip()
    
    if len(name) > 50:
        await message.reply("❌ Назва занадто довга. Максимум 50 символів.")
        return
    
    await state.update_data(name=name)
    
    data = await state.get_data()
    last_msg_id = data.get('last_bot_message_id')
    
    try:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=last_msg_id,
            text=(
                f"📝 <b>Додавання підписки</b>\n\n"
                f"Назва: <b>{name}</b>\n\n"
                f"Крок 2/4: Введи суму платежу\n"
                f"Наприклад: <code>199</code>"
            )
        )
    except:
        pass
    
    await state.set_state(SubscriptionState.add_amount)


@router.message(SubscriptionState.add_amount)
async def process_subscription_amount(message: Message, state: FSMContext):
    """Обробка суми підписки"""
    is_valid, amount, error = validate_amount(message.text)
    
    if not is_valid:
        await message.reply(f"❌ {error}")
        return
    
    data = await state.get_data()
    name = data.get('name')
    
    await state.update_data(amount=amount)
    
    last_msg_id = data.get('last_bot_message_id')
    
    try:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=last_msg_id,
            text=(
                f"📝 <b>Додавання підписки</b>\n\n"
                f"Назва: <b>{name}</b>\n"
                f"Сума: <b>{format_currency(amount)}</b>\n\n"
                f"Крок 3/4: Введи категорію\n"
                f"Наприклад: <code>Розваги</code>"
            )
        )
    except:
        pass
    
    await state.set_state(SubscriptionState.add_category)


@router.message(SubscriptionState.add_category)
async def process_subscription_category(message: Message, state: FSMContext):
    """Обробка категорії підписки"""
    category = message.text.strip()
    
    data = await state.get_data()
    name = data.get('name')
    amount = data.get('amount')
    
    await state.update_data(category=category)
    
    last_msg_id = data.get('last_bot_message_id')
    
    try:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=last_msg_id,
            text=(
                f"📝 <b>Додавання підписки</b>\n\n"
                f"Назва: <b>{name}</b>\n"
                f"Сума: <b>{format_currency(amount)}</b>\n"
                f"Категорія: <b>{category}</b>\n\n"
                f"Крок 4/4: Введи дату наступного списання\n"
                f"Формат: <code>день-місяць-рік</code>\n"
                f"Наприклад: <code>15-12-2024</code>"
            )
        )
    except:
        pass
    
    await state.set_state(SubscriptionState.add_date)


@router.message(SubscriptionState.add_date)
async def process_subscription_date(message: Message, state: FSMContext):
    """Обробка дати підписки"""
    is_valid, date_obj, error = validate_date(message.text)
    
    if not is_valid:
        await message.reply(f"❌ {error}")
        return
    
    data = await state.get_data()
    name = data.get('name')
    amount = data.get('amount')
    category = data.get('category')
    nickname = message.from_user.username or "anonymous"
    
    try:
        # Додаємо підписку (витрата з прапорцем Is_Subscription)
        sheets_service.append_transaction(
            user_id=message.from_user.id,
            nickname=nickname,
            amount=-abs(amount),
            category=category,
            note=f"Підписка: {name}",
            is_subscription=True
        )
        
        last_msg_id = data.get('last_bot_message_id')
        
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=last_msg_id,
                text=(
                    f"✅ <b>Підписку додано!</b>\n\n"
                    f"📝 Назва: <b>{name}</b>\n"
                    f"💰 Сума: <b>{format_currency(amount)}</b>\n"
                    f"📂 Категорія: <b>{category}</b>\n"
                    f"📅 Дата: <b>{message.text}</b>\n\n"
                    f"Я нагадаю тобі про платіж!"
                )
            )
        except:
            await message.answer(
                f"✅ <b>Підписку додано!</b>\n\n"
                f"📝 {name} - {format_currency(amount)}"
            )
        
        await message.answer(
            "Обирай наступну дію:",
            reply_markup=get_main_menu_keyboard()
        )
        
        await state.clear()
        
        logger.info(f"Subscription added: {name} for {nickname}")
        
    except Exception as e:
        logger.error(f"Error adding subscription: {e}", exc_info=True)
        await message.reply("❌ Помилка при додаванні підписки")


@router.callback_query(F.data == "view_subscriptions")
async def view_subscriptions(callback: CallbackQuery):
    """Показує всі підписки"""
    nickname = callback.from_user.username or "anonymous"
    
    try:
        subscriptions = sheets_service.get_subscriptions(nickname)
        
        if not subscriptions:
            await callback.message.edit_text(
                "📝 У тебе поки немає підписок.\n\n"
                "Додай першу підписку, щоб я міг нагадувати про платежі!",
                reply_markup=get_subscriptions_menu()
            )
            await callback.answer()
            return
        
        text_lines = ["📝 <b>Твої підписки:</b>\n"]
        
        total_monthly = 0
        
        for sub in subscriptions:
            name = sub.get('note', 'Без назви').replace('Підписка: ', '')
            amount = abs(float(sub.get('amount', 0)))
            category = sub.get('category', 'Інше')
            date = sub.get('date', '')
            
            total_monthly += amount
            
            text_lines.append(
                f"\n• <b>{name}</b>\n"
                f"  💰 {format_currency(amount)}\n"
                f"  📂 {category}\n"
                f"  📅 Дата: {date}"
            )
        
        text_lines.append(f"\n\n💳 <b>Загалом на місяць:</b> {format_currency(total_monthly)}")
        
        await callback.message.edit_text(
            "\n".join(text_lines),
            reply_markup=get_subscriptions_menu()
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error viewing subscriptions: {e}", exc_info=True)
        await callback.answer("❌ Помилка", show_alert=True)


