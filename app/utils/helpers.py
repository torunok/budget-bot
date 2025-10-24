# ============================================
# FILE: app/utils/helpers.py
# ============================================
"""
Допоміжні функції
"""

from datetime import datetime, timedelta
from typing import List, Dict


def get_period_dates(period: str) -> tuple:
    """Повертає діапазон дат для періоду"""
    now = datetime.now()
    
    periods = {
        'today': (now.replace(hour=0, minute=0, second=0), now),
        'yesterday': (
            (now - timedelta(days=1)).replace(hour=0, minute=0, second=0),
            (now - timedelta(days=1)).replace(hour=23, minute=59, second=59)
        ),
        '7days': (now - timedelta(days=7), now),
        '14days': (now - timedelta(days=14), now),
        'month': (now.replace(day=1, hour=0, minute=0, second=0), now),
        'year': (now.replace(month=1, day=1, hour=0, minute=0, second=0), now),
    }
    
    return periods.get(period, (now.replace(hour=0, minute=0, second=0), now))


def filter_transactions_by_period(transactions: List[Dict], period: str) -> List[Dict]:
    """Фільтрує транзакції за періодом"""
    start_date, end_date = get_period_dates(period)
    
    filtered = []
    for t in transactions:
        try:
            t_date = datetime.fromisoformat(t['date'])
            if start_date <= t_date <= end_date:
                filtered.append(t)
        except (ValueError, KeyError):
            continue
    
    return filtered


def get_emoji_for_category(category: str) -> str:
    """Повертає емодзі для категорії"""
    category_emojis = {
        'їжа': '🍕',
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
    }
    
    return category_emojis.get(category.lower(), '📌')