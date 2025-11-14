"""
Корисні допоміжні функції та структури.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging
import pytz

logger = logging.getLogger(__name__)


# ----------------------- ЧАСОВІ ДІАПАЗОНИ ----------------------- #

def _kyiv_now() -> datetime:
    return datetime.now(pytz.timezone("Europe/Kiev"))


def get_period_dates(period: str) -> Tuple[datetime, datetime]:
    """Повертає діапазон дат (UTC) для заданого періоду."""
    now_kyiv = _kyiv_now()
    now_utc = now_kyiv.astimezone(pytz.UTC)

    if period == "today":
        start = now_kyiv.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.UTC)
        return start, now_utc
    if period == "yesterday":
        yesterday = now_kyiv - timedelta(days=1)
        start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.UTC)
        end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999).astimezone(pytz.UTC)
        return start, end
    if period == "7days":
        return now_utc - timedelta(days=7), now_utc
    if period == "14days":
        return now_utc - timedelta(days=14), now_utc
    if period == "month":
        start = now_kyiv.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.UTC)
        return start, now_utc
    if period == "year":
        start = now_kyiv.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.UTC)
        return start, now_utc
    start = now_kyiv.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.UTC)
    return start, now_utc


def filter_transactions_by_period(transactions: List[Dict], period: str) -> List[Dict]:
    """Фільтрує транзакції згідно з діапазоном періоду."""
    start, end = get_period_dates(period)
    results: List[Dict] = []
    for idx, tx in enumerate(transactions):
        date_str = tx.get("date", "")
        if not date_str or date_str == "initial":
            continue
        try:
            parsed = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
        except ValueError:
            logger.warning("Помилковий формат дати в транзакції %s: %s", idx, date_str)
            continue

        if parsed.tzinfo is None:
            parsed = pytz.UTC.localize(parsed)

        if start <= parsed <= end:
            results.append(tx)
    return results


# ----------------------- ВІДОБРАЖЕННЯ ----------------------- #

def get_emoji_for_category(category: str) -> str:
    mapping = {
        "їжа": "🍕",
        "продукти": "🛒",
        "транспорт": "🚗",
        "розваги": "🎬",
        "здоров'я": "💊",
        "освіта": "📚",
        "одяг": "👕",
        "комунальні": "🏠",
        "зарплата": "💰",
        "подарунки": "🎁",
        "спорт": "⚽",
        "краса": "💄",
        "інтернет": "🌐",
        "телефон": "📱",
        "кафе": "☕",
        "ресторан": "🍽️",
        "робота": "💼",
        "інше": "📌",
    }
    return mapping.get(category.lower(), "📌")


# ----------------------- ДОПОМОЖНІ СТРУКТУРИ ----------------------- #

@dataclass
class SheetContext:
    sheet_title: str
    legacy_titles: List[str]
    display_name: str


def build_sheet_context(user) -> SheetContext:
    """Формує службовий контекст для конкретного користувача."""
    sheet_title = f"user_{user.id}"
    username = getattr(user, "username", None)
    candidates = [title for title in [username, "anonymous"] if title]
    legacy = []
    seen = set()
    for title in candidates:
        if title not in seen:
            legacy.append(title)
            seen.add(title)
    display_name = username or sheet_title
    return SheetContext(sheet_title=sheet_title, legacy_titles=legacy, display_name=display_name)
