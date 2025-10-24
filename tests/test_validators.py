#File: tests/test_validators.py

"""
Тести для валідаторів
"""
import pytest
from app.utils.validators import (
    validate_amount,
    validate_date,
    validate_category,
    parse_transaction_input
)


class TestValidateAmount:
    
    def test_valid_amount(self):
        is_valid, amount, error = validate_amount("150")
        assert is_valid == True
        assert amount == 150.0
        assert error == ""
    
    def test_valid_amount_with_comma(self):
        is_valid, amount, error = validate_amount("150,50")
        assert is_valid == True
        assert amount == 150.50
    
    def test_valid_amount_with_dot(self):
        is_valid, amount, error = validate_amount("150.50")
        assert is_valid == True
        assert amount == 150.50
    
    def test_zero_amount(self):
        is_valid, amount, error = validate_amount("0")
        assert is_valid == False
        assert amount == None
    
    def test_negative_amount(self):
        is_valid, amount, error = validate_amount("-150")
        assert is_valid == True
        assert amount == 150.0  # Знак видаляється валідатором
    
    def test_invalid_amount(self):
        is_valid, amount, error = validate_amount("abc")
        assert is_valid == False
        assert amount == None
    
    def test_large_amount(self):
        is_valid, amount, error = validate_amount("2000000000")
        assert is_valid == False  # Більше 1 млрд


class TestValidateDate:
    
    def test_valid_date(self):
        is_valid, date_obj, error = validate_date("15-12-2024")
        assert is_valid == True
        assert date_obj.day == 15
        assert date_obj.month == 12
        assert date_obj.year == 2024
    
    def test_invalid_format(self):
        is_valid, date_obj, error = validate_date("2024-12-15")
        assert is_valid == False
    
    def test_invalid_year(self):
        is_valid, date_obj, error = validate_date("15-12-1999")
        assert is_valid == False


class TestValidateCategory:
    
    def test_valid_category(self):
        is_valid, category, error = validate_category("Їжа")
        assert is_valid == True
        assert category == "Їжа"
    
    def test_empty_category(self):
        is_valid, category, error = validate_category("")
        assert is_valid == False
    
    def test_long_category(self):
        is_valid, category, error = validate_category("A" * 51)
        assert is_valid == False
    
    def test_category_with_special_chars(self):
        is_valid, category, error = validate_category("Їжа<script>")
        assert is_valid == True
        assert "<script>" not in category  # Небезпечні символи видалені


class TestParseTransactionInput:
    
    def test_amount_with_description(self):
        amount, note = parse_transaction_input("150 їжа супермаркет")
        assert amount == 150.0
        assert note == "їжа супермаркет"
    
    def test_amount_only(self):
        amount, note = parse_transaction_input("150")
        assert amount == 150.0
        assert note == ""
    
    def test_invalid_input(self):
        amount, note = parse_transaction_input("їжа")
        assert amount == None
        assert note == ""
    
    def test_amount_with_comma(self):
        amount, note = parse_transaction_input("150,50 транспорт")
        assert amount == 150.50
        assert note == "транспорт"