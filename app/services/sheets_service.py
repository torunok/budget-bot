# ============================================
# FILE: app/services/sheets_service.py
# ============================================
"""
Сервіс для роботи з Google Sheets
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import gspread
from gspread.exceptions import WorksheetNotFound, APIError

import json

from app.config.settings import config

logger = logging.getLogger(__name__)


class SheetsService:
    """Сервіс для роботи з Google Sheets"""
    
    def __init__(self):
        try:
            # >>> ЗМІНА: АУТЕНТИФІКАЦІЯ ЧЕРЕЗ СЛОВНИК
            # 1. Парсимо JSON-рядок, отриманий зі змінної оточення
            creds_json = config.GOOGLE_SERVICE_ACCOUNT_JSON
            
            if not creds_json:
                raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON is not set or empty.")
            
            creds_dict = json.loads(creds_json)
            
            # 2. Аутентифікація через словник
            self.gc = gspread.service_account_from_dict(creds_dict) 
            
            self.spreadsheet = self.gc.open_by_key(config.SPREADSHEET_ID)
            logger.info("✅ Connected to Google Sheets")
            
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {e}")
            # >>> Додаткова інформація про помилку аутентифікації
            logger.error("Ensure GOOGLE_SERVICE_ACCOUNT_JSON and SPREADSHEET_ID are correctly set in Render environment.")
            raise
    
    def get_or_create_worksheet(self, nickname: str):
        """Отримує або створює аркуш для користувача"""
        try:
            ws = self.spreadsheet.worksheet(nickname)
            headers = ws.row_values(1)
            
            # Перевірка та додавання відсутніх колонок
            required_columns = ['date', 'user_id', 'amount', 'category', 'note', 
                              'nickname', 'balance', 'currency', 'Is_Subscription']
            
            if not all(col in headers for col in required_columns):
                logger.warning(f"Adding missing columns to worksheet '{nickname}'")
                ws.clear()
                ws.append_row(required_columns)
                ws.append_row(["initial", "0", "0", "initial", "initial", 
                             nickname, "0.0", config.DEFAULT_CURRENCY, False])
            
            return ws
            
        except WorksheetNotFound:
            logger.info(f"Creating new worksheet for '{nickname}'")
            ws = self.spreadsheet.add_worksheet(title=nickname, rows=1000, cols=9)
            ws.append_row(['date', 'user_id', 'amount', 'category', 'note', 
                          'nickname', 'balance', 'currency', 'Is_Subscription'])
            ws.append_row(["initial", "0", "0", "initial", "initial", 
                          nickname, "0.0", config.DEFAULT_CURRENCY, False])
            return ws
    
    def append_transaction(
        self,
        user_id: int,
        nickname: str,
        amount: float,
        category: str = config.DEFAULT_CATEGORY,
        note: str = "",
        is_subscription: bool = False
    ) -> int:
        """Додає нову транзакцію"""
        ws = self.get_or_create_worksheet(nickname)
        timestamp = datetime.now().isoformat()
        
        current_balance, currency = self.get_current_balance(nickname)
        new_balance = current_balance + amount
        
        row = [timestamp, str(user_id), amount, category, note, 
               nickname, new_balance, currency, is_subscription]
        ws.append_row(row)
        
        logger.info(f"Added transaction for {nickname}: {amount} {currency}")
        return len(ws.get_all_values())
    
    def get_current_balance(self, nickname: str) -> Tuple[float, str]:
        """Отримує поточний баланс та валюту"""
        ws = self.get_or_create_worksheet(nickname)
        last_row_index = len(ws.col_values(1))
        
        try:
            balance = float(ws.cell(last_row_index, 7).value)
            currency = ws.cell(last_row_index, 8).value or config.DEFAULT_CURRENCY
            return balance, currency
        except (ValueError, IndexError, TypeError) as e:
            logger.error(f"Error getting balance for {nickname}: {e}")
            return 0.0, config.DEFAULT_CURRENCY
    
    def update_balance(self, nickname: str, new_balance: float, currency: str):
        """Оновлює баланс користувача"""
        ws = self.get_or_create_worksheet(nickname)
        last_row_index = len(ws.col_values(1))
        
        ws.update_cell(last_row_index, 7, new_balance)
        ws.update_cell(last_row_index, 8, currency)
        logger.info(f"Updated balance for {nickname}: {new_balance} {currency}")
    
    def get_all_transactions(self, nickname: str) -> List[Dict]:
        """Отримує всі транзакції користувача"""
        ws = self.get_or_create_worksheet(nickname)
        return ws.get_all_records()
    
    def get_subscriptions(self, nickname: str) -> List[Dict]:
        """Отримує всі підписки користувача"""
        transactions = self.get_all_transactions(nickname)
        return [t for t in transactions if str(t.get('Is_Subscription', '')).lower() == 'true']
    
    def update_transaction(self, nickname: str, row_index: int, column_index: int, value):
        """Оновлює значення в транзакції"""
        ws = self.get_or_create_worksheet(nickname)
        ws.update_cell(row_index, column_index, value)
        logger.info(f"Updated transaction at row {row_index}, col {column_index}")
    
    def delete_transaction(self, nickname: str, row_index: int):
        """Видаляє транзакцію"""
        ws = self.get_or_create_worksheet(nickname)
        ws.delete_rows(row_index)
        logger.info(f"Deleted transaction at row {row_index} for {nickname}")
    
    def get_feedback_worksheet(self):
        """Отримує або створює аркуш відгуків"""
        worksheet_title = "feedback_and_suggestions"
        try:
            return self.spreadsheet.worksheet(worksheet_title)
        except WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(title=worksheet_title, rows=1000, cols=3)
            ws.append_row(["timestamp", "username", "feedback"])
            return ws
    
    def append_feedback(self, username: str, feedback: str):
        """Додає відгук"""
        ws = self.get_feedback_worksheet()
        timestamp = datetime.now().isoformat()
        ws.append_row([timestamp, username, feedback])
        logger.info(f"Feedback added from {username}")
    
    def get_reminders_worksheet(self):
        """Отримує або створює аркуш налаштувань нагадувань"""
        worksheet_title = "reminder_settings"
        try:
            return self.spreadsheet.worksheet(worksheet_title)
        except WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(title=worksheet_title, rows=1000, cols=2)
            ws.append_row(["user_id", "status"])
            return ws
    
    def add_reminder_user(self, user_id: int):
        """Додає користувача до нагадувань"""
        ws = self.get_reminders_worksheet()
        current_users = ws.col_values(1)
        if str(user_id) not in current_users:
            ws.append_row([str(user_id), "enabled"])
            logger.info(f"User {user_id} enabled reminders")
    
    def remove_reminder_user(self, user_id: int):
        """Видаляє користувача з нагадувань"""
        ws = self.get_reminders_worksheet()
        try:
            cell = ws.find(str(user_id))
            ws.delete_rows(cell.row)
            logger.info(f"User {user_id} disabled reminders")
        except:
            pass
    
    def get_reminder_users(self) -> List[int]:
        """Отримує список користувачів з увімкненими нагадуваннями"""
        ws = self.get_reminders_worksheet()
        user_ids = ws.col_values(1)[1:]  # Skip header
        return [int(uid) for uid in user_ids if uid]


# Singleton instance
sheets_service = SheetsService()