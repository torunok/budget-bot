#FILE: app/handlers/statistics.py#

"""
Обробники для статистики
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from app.services.sheets_service import sheets_service
from app.keyboards.inline import get_stats_period_keyboard
from app.utils.formatters import format_statistics, format_currency
from app.utils.helpers import filter_transactions_by_period

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

