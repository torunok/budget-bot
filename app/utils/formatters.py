# ============================================
# FILE: app/utils/formatters.py
# ============================================
"""
Форматери для повідомлень
"""

from datetime import datetime
from typing import List, Dict, Optional
from collections import defaultdict

from app.utils.helpers import parse_sheet_datetime

DISPLAY_DATE_FORMAT = "%d.%m.%Y"


def format_currency(amount: float, currency: str = "UAH") -> str:
    """Форматує суму з валютою"""
    return f"{amount:,.2f} {currency}".replace(",", " ")


def format_date(date_value: Optional[str], date_format: str = DISPLAY_DATE_FORMAT) -> str:
    """Форматує дату в стандартному форматі бота"""
    if not date_value:
        return ""
    
    if isinstance(date_value, datetime):
        dt = date_value
    else:
        raw = str(date_value).strip()
        if not raw:
            return ""
        
        dt = parse_sheet_datetime(raw)
        if dt is None:
            return raw
    
    return dt.strftime(date_format)


def format_transaction_list(transactions: List[Dict], limit: int = 10) -> str:
    """Форматує список транзакцій для відображення"""
    if not transactions:
        return "Транзакцій не знайдено"
    
    lines = []
    for t in transactions[:limit]:
        date = format_date(t.get('date', ''), DISPLAY_DATE_FORMAT) or "—"
        amount = float(t.get('amount', 0))
        category = t.get('category', 'Інше')
        note = t.get('note', '')
        
        emoji = "📉" if amount < 0 else "📈"
        currency = t.get('currency') or "UAH"
        lines.append(f"{emoji} {date} | {format_currency(abs(amount), currency)} | {category}")
        if note:
            lines.append(f"   ↳ {note[:50]}")
    
    if len(transactions) > limit:
        lines.append(f"\n... та ще {len(transactions) - limit} транзакцій")
    
    return "\n".join(lines)


def format_statistics(transactions: List[Dict], currency: str = "UAH") -> str:
    """Форматує статистику по транзакціях"""
    if not transactions:
        return "Немає даних для аналізу"
    
    total_income = sum(float(t['amount']) for t in transactions if float(t.get('amount', 0)) > 0)
    total_expense = sum(abs(float(t['amount'])) for t in transactions if float(t.get('amount', 0)) < 0)
    
    # Групування по категоріях
    income_by_category = defaultdict(float)
    expense_by_category = defaultdict(float)
    
    for t in transactions:
        amount = float(t.get('amount', 0))
        category = t.get('category', 'Інше')
        
        if amount > 0:
            income_by_category[category] += amount
        else:
            expense_by_category[category] += abs(amount)
    
    # Форматування
    lines = [
        f"📈 <b>Доходи:</b> {format_currency(total_income, currency)}",
        format_category_breakdown(income_by_category, total_income, currency),
        "",
        f"📉 <b>Витрати:</b> {format_currency(total_expense, currency)}",
        format_category_breakdown(expense_by_category, total_expense, currency),
        "",
        f"💰 <b>Різниця:</b> {format_currency(total_income - total_expense, currency)}"
    ]
    
    return "\n".join(lines)


def format_category_breakdown(categories: Dict[str, float], total: float, currency: str) -> str:
    """Форматує розбивку по категоріях з відсотками"""
    if not categories:
        return "   —"
    
    # Сортуємо за сумою
    sorted_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)
    
    lines = []
    for category, amount in sorted_cats[:5]:  # Топ-5 категорій
        percent = (amount / total * 100) if total > 0 else 0
        lines.append(f"   • {category}: {format_currency(amount, currency)} ({percent:.1f}%)")
    
    if len(sorted_cats) > 5:
        other_amount = sum(amount for _, amount in sorted_cats[5:])
        other_percent = (other_amount / total * 100) if total > 0 else 0
        lines.append(f"   • Інше: {format_currency(other_amount, currency)} ({other_percent:.1f}%)")
    
    return "\n".join(lines)


def split_long_message(text: str, max_length: int = 4096) -> List[str]:
    """Розбиває довге повідомлення на частини"""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current_part = ""
    
    for line in text.split('\n'):
        if len(current_part) + len(line) + 1 > max_length:
            parts.append(current_part)
            current_part = line
        else:
            current_part += '\n' + line if current_part else line
    
    if current_part:
        parts.append(current_part)
    
    return parts
