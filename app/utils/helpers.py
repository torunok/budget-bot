# ============================================
# FILE: app/utils/helpers.py (ULTRA DEBUG VERSION)
# ============================================
"""
Допоміжні функції з детальним логуванням
"""

from datetime import datetime, timedelta
from typing import List, Dict
import pytz
import logging

logger = logging.getLogger(__name__)


def get_period_dates(period: str) -> tuple:
    """Повертає діапазон дат для періоду (UTC aware)"""
    # Київський час (UTC+2 зимовий, UTC+3 літній)
    kyiv_tz = pytz.timezone('Europe/Kiev')
    
    # Поточний час в Києві
    now_kyiv = datetime.now(kyiv_tz)
    
    # Конвертуємо в UTC для порівняння
    now_utc = now_kyiv.astimezone(pytz.UTC)
    
    logger.info(f"🕐 Current time:")
    logger.info(f"   Kyiv: {now_kyiv}")
    logger.info(f"   UTC:  {now_utc}")
    
    if period == 'today':
        # Початок дня в Києві (00:00)
        start_kyiv = now_kyiv.replace(hour=0, minute=0, second=0, microsecond=0)
        # Конвертуємо в UTC
        start_utc = start_kyiv.astimezone(pytz.UTC)
        end_utc = now_utc
        
        logger.info(f"📅 Today period:")
        logger.info(f"   Start (Kyiv): {start_kyiv}")
        logger.info(f"   Start (UTC):  {start_utc}")
        logger.info(f"   End (UTC):    {end_utc}")
        
        return (start_utc, end_utc)
    
    elif period == 'yesterday':
        yesterday_kyiv = now_kyiv - timedelta(days=1)
        start_kyiv = yesterday_kyiv.replace(hour=0, minute=0, second=0, microsecond=0)
        end_kyiv = yesterday_kyiv.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        start_utc = start_kyiv.astimezone(pytz.UTC)
        end_utc = end_kyiv.astimezone(pytz.UTC)
        
        return (start_utc, end_utc)
    
    elif period == '7days':
        start_utc = now_utc - timedelta(days=7)
        return (start_utc, now_utc)
    
    elif period == '14days':
        start_utc = now_utc - timedelta(days=14)
        return (start_utc, now_utc)
    
    elif period == 'month':
        start_kyiv = now_kyiv.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_utc = start_kyiv.astimezone(pytz.UTC)
        return (start_utc, now_utc)
    
    elif period == 'year':
        start_kyiv = now_kyiv.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        start_utc = start_kyiv.astimezone(pytz.UTC)
        return (start_utc, now_utc)
    
    else:
        # Default: today
        start_kyiv = now_kyiv.replace(hour=0, minute=0, second=0, microsecond=0)
        start_utc = start_kyiv.astimezone(pytz.UTC)
        return (start_utc, now_utc)


def filter_transactions_by_period(transactions: List[Dict], period: str) -> List[Dict]:
    """Фільтрує транзакції за періодом (з підтримкою timezone)"""
    start_date, end_date = get_period_dates(period)
    
    logger.info(f"🔍 Filtering {len(transactions)} transactions for period '{period}'")
    logger.info(f"   Range: {start_date} to {end_date}")
    
    filtered = []
    
    for idx, t in enumerate(transactions):
        try:
            # Парсимо дату з транзакції
            date_str = t.get('date', '')
            
            if not date_str:
                logger.warning(f"   Transaction {idx}: No date field")
                continue
            
            # Підтримка різних форматів
            if isinstance(date_str, str):
                # Спроба з ISO format (з timezone)
                try:
                    t_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except ValueError:
                    try:
                        # Спроба без timezone
                        t_date = datetime.fromisoformat(date_str)
                        # Додаємо UTC якщо немає timezone
                        if t_date.tzinfo is None:
                            t_date = pytz.UTC.localize(t_date)
                    except ValueError:
                        logger.warning(f"   Transaction {idx}: Invalid date format: {date_str}")
                        continue
            else:
                logger.warning(f"   Transaction {idx}: Date is not string: {type(date_str)}")
                continue
            
            # Логуємо перші 3 транзакції для діагностики
            if idx < 3:
                logger.info(f"   Transaction {idx}:")
                logger.info(f"      Date string: {date_str}")
                logger.info(f"      Parsed date: {t_date}")
                logger.info(f"      In range: {start_date <= t_date <= end_date}")
                logger.info(f"      Amount: {t.get('amount')}")
            
            # Порівнюємо з start_date та end_date
            if start_date <= t_date <= end_date:
                filtered.append(t)
                if idx < 3:
                    logger.info(f"      ✅ INCLUDED")
            else:
                if idx < 3:
                    logger.info(f"      ❌ EXCLUDED")
                    if t_date < start_date:
                        logger.info(f"         Reason: {t_date} < {start_date}")
                    else:
                        logger.info(f"         Reason: {t_date} > {end_date}")
                
        except (ValueError, KeyError, TypeError) as e:
            logger.warning(f"   Transaction {idx}: Error parsing: {e}")
            continue
    
    logger.info(f"   ✅ Filtered result: {len(filtered)} transactions")
    
    return filtered


def get_emoji_for_category(category: str) -> str:
    """Повертає емодзі для категорії"""
    category_emojis = {
        'їжа': '🍕',
        'продукти': '🛒',
        'транспорт': '🚗',
        'розваги': '🎬',
        'здоров\'я': '💊',
        'освіта': '📚',
        'одяг': '👕',
        'комунальні': '🏠',
        'зарплата': '💰',
        'подарунки': '🎁',
        'спорт': '⚽',
        'краса': '💄',
        'інтернет': '🌐',
        'телефон': '📱',
        'кафе': '☕',
        'ресторан': '🍽️',
    }
    
    return category_emojis.get(category.lower(), '📌')