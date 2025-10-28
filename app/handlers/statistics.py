# ============================================
# FILE: app/handlers/statistics.py 
# ============================================
"""
Обробники для статистики - ПОВНА ВЕРСІЯ
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.services.sheets_service import sheets_service
from app.services.chart_service import chart_service
from app.keyboards.inline import get_stats_period_keyboard
from app.utils.formatters import format_statistics, format_currency
from app.utils.helpers import filter_transactions_by_period
from app.utils.validators import validate_amount
from app.core.states import UserState

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "📊 Статистика")
async def show_statistics(message: Message):
    """Показує меню статистики"""
    nickname = message.from_user.username or "anonymous"
    
    try:
        balance, currency = sheets_service.get_current_balance(nickname)
        transactions = sheets_service.get_all_transactions(nickname)
        
        # Фільтруємо сьогоднішні транзакції
        today_transactions = filter_transactions_by_period(
            [t for t in transactions if not t.get('Is_Subscription')],
            'today'
        )
        
        stats_text = format_statistics(today_transactions, currency)
        
        message_text = (
            f"💰 <b>Поточний баланс:</b> {format_currency(balance, currency)}\n\n"
            f"<b>Сьогодні:</b>\n{stats_text}\n\n"
            f"Обери період для детальної статистики:"
        )
        
        await message.answer(
            message_text,
            reply_markup=get_stats_period_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error showing statistics: {e}", exc_info=True)
        await message.answer("❌ Помилка отримання статистики")


@router.callback_query(F.data.startswith("stats_"))
async def show_period_statistics(callback: CallbackQuery):
    """Показує статистику за обраний період"""
    period = callback.data.split("_")[1]
    nickname = callback.from_user.username or "anonymous"
    
    try:
        transactions = sheets_service.get_all_transactions(nickname)
        
        # Фільтруємо за періодом
        period_transactions = filter_transactions_by_period(
            [t for t in transactions if not t.get('Is_Subscription')],
            period
        )
        
        if not period_transactions:
            await callback.answer("За цей період немає транзакцій", show_alert=True)
            return
        
        balance, currency = sheets_service.get_current_balance(nickname)
        stats_text = format_statistics(period_transactions, currency)
        
        period_names = {
            'today': 'Сьогодні',
            'yesterday': 'Вчора',
            '7days': 'За 7 днів',
            '14days': 'За 14 днів',
            'month': 'За місяць',
            'year': 'За рік'
        }
        
        message_text = (
            f"📊 <b>Статистика: {period_names.get(period, period)}</b>\n\n"
            f"💰 Баланс: {format_currency(balance, currency)}\n\n"
            f"{stats_text}"
        )
        
        await callback.message.edit_text(
            message_text,
            reply_markup=get_stats_period_keyboard()
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing period statistics: {e}", exc_info=True)
        await callback.answer("❌ Помилка", show_alert=True)


# ==================== ГРАФІКИ ====================

@router.callback_query(F.data == "show_charts")
async def show_charts_menu(callback: CallbackQuery):
    """Показує меню вибору графіків"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🥧 Витрати по категоріях", callback_data="chart_pie_expense"),
            InlineKeyboardButton(text="💰 Доходи по категоріях", callback_data="chart_pie_income")
        ],
        [
            InlineKeyboardButton(text="📈 Динаміка (30 днів)", callback_data="chart_line_30"),
            InlineKeyboardButton(text="📊 Динаміка (90 днів)", callback_data="chart_line_90")
        ],
        [
            InlineKeyboardButton(text="📊 Порівняння по місяцях", callback_data="chart_bar_comparison")
        ],
        [
            InlineKeyboardButton(text="💳 Історія балансу", callback_data="chart_balance_history")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_stats")
        ]
    ])
    
    await callback.message.edit_text(
        "📊 <b>Графіки та візуалізація</b>\n\n"
        "Обери тип графіка:",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("chart_"))
async def generate_chart(callback: CallbackQuery):
    """Генерує обраний графік"""
    chart_type = callback.data.replace("chart_", "")
    nickname = callback.from_user.username or "anonymous"
    
    # Показуємо індикатор завантаження
    await callback.answer("⏳ Генерую графік...", show_alert=False)
    await callback.message.edit_text("📊 Генерую графік, зачекай...")
    
    try:
        transactions = sheets_service.get_all_transactions(nickname)
        balance, currency = sheets_service.get_current_balance(nickname)
        
        # Генуруємо відповідний графік
        if chart_type == "pie_expense":
            buffer = chart_service.create_pie_chart(transactions, "expense")
            caption = "🥧 Витрати по категоріях"
        
        elif chart_type == "pie_income":
            buffer = chart_service.create_pie_chart(transactions, "income")
            caption = "💰 Доходи по категоріях"
        
        elif chart_type == "line_30":
            buffer = chart_service.create_line_chart(transactions, 30)
            caption = "📈 Динаміка фінансів за 30 днів"
        
        elif chart_type == "line_90":
            buffer = chart_service.create_line_chart(transactions, 90)
            caption = "📊 Динаміка фінансів за 90 днів"
        
        elif chart_type == "bar_comparison":
            buffer = chart_service.create_bar_comparison(transactions, currency)
            caption = "📊 Порівняння доходів та витрат по місяцях"
        
        elif chart_type == "balance_history":
            buffer = chart_service.create_balance_history(transactions, currency)
            caption = "💳 Історія балансу"
        
        else:
            await callback.message.edit_text("❌ Невідомий тип графіка")
            return
        
        # Відправляємо графік
        photo = BufferedInputFile(buffer.getvalue(), filename="chart.png")
        
        await callback.message.answer_photo(
            photo=photo,
            caption=caption
        )
        
        # Повертаємо меню
        await show_charts_menu(callback)
        
        logger.info(f"Chart generated: {chart_type} for {nickname}")
        
    except Exception as e:
        logger.error(f"Error generating chart: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ Помилка при генерації графіка.\n"
            "Можливо, недостатньо даних."
        )


# ==================== РЕДАГУВАННЯ БАЛАНСУ ====================

@router.callback_query(F.data == "edit_balance_menu")
async def edit_balance_menu(callback: CallbackQuery):
    """Меню редагування балансу"""
    nickname = callback.from_user.username or "anonymous"
    balance, currency = sheets_service.get_current_balance(nickname)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Збільшити", callback_data="balance_increase"),
            InlineKeyboardButton(text="➖ Зменшити", callback_data="balance_decrease")
        ],
        [
            InlineKeyboardButton(text="🔄 Встановити точно", callback_data="balance_set")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_stats")
        ]
    ])
    
    await callback.message.edit_text(
        f"💳 <b>Редагування балансу</b>\n\n"
        f"Поточний баланс: {format_currency(balance, currency)}\n\n"
        f"⚠️ Використовуй цю функцію обережно!\n"
        f"Краще додавати транзакції через меню.\n\n"
        f"Що хочеш зробити?",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("balance_"))
async def balance_edit_start(callback: CallbackQuery, state: FSMContext):
    """Початок редагування балансу"""
    action = callback.data.replace("balance_", "")
    
    await state.update_data(balance_action=action)
    
    if action == "increase":
        text = "➕ <b>Збільшення балансу</b>\n\nНа яку суму збільшити?"
    elif action == "decrease":
        text = "➖ <b>Зменшення балансу</b>\n\nНа яку суму зменшити?"
    else:  # set
        text = "🔄 <b>Встановлення балансу</b>\n\nВведи нову суму балансу:"
    
    await callback.message.edit_text(text)
    await state.set_state(UserState.edit_balance)
    await callback.answer()


@router.message(UserState.edit_balance)
async def process_balance_edit(message: Message, state: FSMContext):
    """Обробка зміни балансу"""
    is_valid, amount, error = validate_amount(message.text)
    
    if not is_valid:
        await message.reply(f"❌ {error}")
        return
    
    data = await state.get_data()
    action = data.get('balance_action')
    nickname = message.from_user.username or "anonymous"
    
    try:
        balance, currency = sheets_service.get_current_balance(nickname)
        
        if action == "increase":
            new_balance = balance + amount
            change_text = f"збільшено на {format_currency(amount, currency)}"
        elif action == "decrease":
            new_balance = balance - amount
            change_text = f"зменшено на {format_currency(amount, currency)}"
        else:  # set
            new_balance = amount
            change_text = f"встановлено {format_currency(amount, currency)}"
        
        # Оновлюємо баланс
        sheets_service.update_balance(nickname, new_balance, currency)
        
        # Додаємо коригуючу транзакцію для історії
        adjustment = new_balance - balance
        sheets_service.append_transaction(
            user_id=message.from_user.id,
            nickname=nickname,
            amount=adjustment,
            category="Коригування",
            note=f"Ручне коригування балансу"
        )
        
        await message.answer(
            f"✅ <b>Баланс оновлено!</b>\n\n"
            f"Попередній: {format_currency(balance, currency)}\n"
            f"Новий: {format_currency(new_balance, currency)}\n\n"
            f"Зміна: {change_text}"
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error updating balance: {e}", exc_info=True)
        await message.reply("❌ Помилка при оновленні балансу")


# ==================== РЕДАГУВАННЯ ТРАНЗАКЦІЙ ====================

@router.callback_query(F.data == "edit_transactions")
async def edit_transactions_menu(callback: CallbackQuery):
    """Показує останні транзакції для редагування"""
    nickname = callback.from_user.username or "anonymous"
    
    try:
        transactions = sheets_service.get_all_transactions(nickname)
        
        if not transactions:
            await callback.answer("Немає транзакцій для редагування", show_alert=True)
            return
        
        # Беремо останні 10
        recent = list(reversed(transactions))[:10]
        
        buttons = []
        for idx, t in enumerate(recent):
            date = t.get('date', '')[:10]
            amount = float(t.get('amount', 0))
            category = t.get('category', '')
            note = t.get('note', '')[:20]
            
            emoji = "📉" if amount < 0 else "📈"
            text = f"{emoji} {date} | {abs(amount):.0f} | {category}"
            
            buttons.append([
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"edit_tr_{idx}"
                )
            ])
        
        buttons.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_stats")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await callback.message.edit_text(
            "✏️ <b>Редагування транзакцій</b>\n\n"
            "Обери транзакцію для редагування:",
            reply_markup=keyboard
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing transactions for edit: {e}", exc_info=True)
        await callback.answer("❌ Помилка", show_alert=True)


# ==================== НАЗАД ====================

@router.callback_query(F.data == "back_to_stats")
async def back_to_stats(callback: CallbackQuery):
    """Повернення до статистики"""
    await show_statistics(callback.message)
    await callback.answer()