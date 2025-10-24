#File: tests/test_formatters.py

"""
Тести для форматерів
"""
import pytest
from app.utils.formatters import (
    format_currency,
    format_date,
    split_long_message,
    format_category_breakdown
)


class TestFormatCurrency:
    
    def test_format_uah(self):
        result = format_currency(1500.50, "UAH")
        assert "1 500.50" in result
        assert "UAH" in result
    
    def test_format_usd(self):
        result = format_currency(100.00, "USD")
        assert "100.00" in result
        assert "USD" in result
    
    def test_large_amount(self):
        result = format_currency(1234567.89, "UAH")
        assert "1 234 567.89" in result


class TestFormatDate:
    
    def test_format_date(self):
        result = format_date("2024-12-15T10:30:00", "%d.%m.%Y")
        assert result == "15.12.2024"
    
    def test_format_date_with_time(self):
        result = format_date("2024-12-15T10:30:00", "%d.%m %H:%M")
        assert result == "15.12 10:30"
    
    def test_invalid_date(self):
        result = format_date("invalid", "%d.%m.%Y")
        assert result == "invalid"  # Повертає оригінал


class TestSplitLongMessage:
    
    def test_short_message(self):
        msg = "Short message"
        result = split_long_message(msg, max_length=100)
        assert len(result) == 1
        assert result[0] == msg
    
    def test_long_message(self):
        msg = "A" * 5000
        result = split_long_message(msg, max_length=4096)
        assert len(result) == 2
        assert len(result[0]) <= 4096
        assert len(result[1]) <= 4096
    
    def test_message_with_newlines(self):
        msg = "Line 1\n" * 1000
        result = split_long_message(msg, max_length=4096)
        assert len(result) >= 2


class TestFormatCategoryBreakdown:
    
    def test_empty_categories(self):
        result = format_category_breakdown({}, 1000, "UAH")
        assert result == "   —"
    
    def test_single_category(self):
        categories = {"Їжа": 500.0}
        result = format_category_breakdown(categories, 1000, "UAH")
        assert "Їжа" in result
        assert "500.00" in result
        assert "50.0%" in result
    
    def test_multiple_categories(self):
        categories = {
            "Їжа": 500.0,
            "Транспорт": 300.0,
            "Розваги": 200.0
        }
        result = format_category_breakdown(categories, 1000, "UAH")
        assert "Їжа" in result
        assert "Транспорт" in result
        assert "Розваги" in result
    
    def test_more_than_five_categories(self):
        categories = {f"Category{i}": 100.0 for i in range(10)}
        result = format_category_breakdown(categories, 1000, "UAH")
        assert "Інше" in result  # Має бути категорія "Інше" для решти