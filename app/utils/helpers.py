# ============================================
# FILE: app/utils/helpers.py
# ============================================
"""
Допоміжні функції
"""

from datetime import datetime, timedelta
from typing import List, Dict
import pytz


def get_period_dates(period: str) -> tuple:
    """Повертає діапазон дат для періоду (UTC aware)"""
    # Використовуємо UTC для консистентності
    now = datetime.now(pytz.UTC)
    
    periods = {
        'today': (now.replace(hour=0, minute=0, second=0, microsecond=0), now),
        'yesterday': (
            (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0),
            (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
        ),
        '7days': (now - timedelta(days=7), now),
        '14days': (now - timedelta(days=14), now),
        'month': (now.replace(day=1, hour=0, minute=0, second=0, microsecond=0), now),
        'year': (now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0), now),
    }
    
    return periods.get(period, (now.replace(hour=0, minute=0, second=0, microsecond=0), now))


def filter_transactions_by_period(transactions: List[Dict], period: str) -> List[Dict]:
    """Фільтрує транзакції за періодом (з підтримкою timezone)"""
    start_date, end_date = get_period_dates(period)
    
    filtered = []
    for t in transactions:
        try:
            # Парсимо дату з транзакції
            date_str = t.get('date', '')
            
            # Підтримка різних форматів
            if isinstance(date_str, str):
                # Спроба з ISO format (з timezone)
                try:
                    t_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except ValueError:
                    # Спроба без timezone
                    t_date = datetime.fromisoformat(date_str)
                    # Додаємо UTC якщо немає timezone
                    if t_date.tzinfo is None:
                        t_date = pytz.UTC.localize(t_date)
            else:
                continue
            
            # Порівнюємо з start_date та end_date
            if start_date <= t_date <= end_date:
                filtered.append(t)
                
        except (ValueError, KeyError, TypeError) as e:
            # Логуємо помилку але продовжуємо
            import logging
            logging.warning(f"Error parsing date for transaction: {e}")
            continue
    
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