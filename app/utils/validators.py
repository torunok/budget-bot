# ============================================
# FILE: app/utils/validators.py
# ============================================
"""
Валідатори для введених даних
"""

import re
from datetime import datetime
from typing import Tuple, Optional

DATE_INPUT_FORMATS = ("%d.%m.%Y", "%d-%m-%Y")


def validate_amount(text: str) -> Tuple[bool, Optional[float], str]:
    """Валідує суму транзакції"""
    text = text.strip().replace(",", ".")
    
    # Видаляємо пробіли та + -
    text = text.replace(" ", "").replace("+", "").replace("-", "")
    
    try:
        amount = float(text)
        if amount == 0:
            return False, None, "Сума не може бути нульовою"
        if amount > 1000000000:  # 1 млрд ліміт
            return False, None, "Сума занадто велика"
        return True, amount, ""
    except ValueError:
        return False, None, "Некоректна сума. Введіть число (наприклад: 150 або 150.50)"


def validate_date(date_str: str, date_formats = DATE_INPUT_FORMATS) -> Tuple[bool, Optional[datetime], str]:
    """Валідує дату у форматі день.місяць.рік (підтримує також старий запис з дефісами)"""
    text = date_str.strip()
    
    for date_format in date_formats:
        try:
            date_obj = datetime.strptime(text, date_format)
            if date_obj.year < 2000 or date_obj.year > 2100:
                return False, None, "Некоректний рік"
            return True, date_obj, ""
        except ValueError:
            continue
    
    example = "31.12.2025"
    return False, None, f"Некоректний формат дати. Використовуйте: день.місяць.рік (наприклад: {example})"


def validate_category(category: str) -> Tuple[bool, str, str]:
    """Валідує категорію"""
    category = category.strip()
    
    if not category:
        return False, "", "Категорія не може бути порожньою"
    
    if len(category) > 50:
        return False, "", "Категорія занадто довга (макс. 50 символів)"
    
    # Видаляємо небезпечні символи
    safe_category = re.sub(r'[<>\"\'\\]', '', category)
    
    return True, safe_category, ""


def parse_transaction_input(text: str) -> Tuple[Optional[float], str]:
    """Парсить введення транзакції (сума + опис)"""
    parts = text.strip().split(maxsplit=1)
    
    if not parts:
        return None, ""
    
    is_valid, amount, _ = validate_amount(parts[0])
    
    if not is_valid:
        return None, ""
    
    note = parts[1] if len(parts) > 1 else ""
    
    return amount, note
