# ============================================
# FILE: app/services/sheets_service.py
# ============================================
"""
Сервіс для роботи з Google Sheets
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
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

    def get_goals_worksheet(self):
        """Отримує або створює аркуш цілей"""
        worksheet_title = "user_goals"
        try:
            return self.spreadsheet.worksheet(worksheet_title)
        except WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(title=worksheet_title, rows=1000, cols=7)
            ws.append_row([
                "nickname", "goal_name", "target_amount", 
                "current_amount", "deadline", "completed", "created_date"
            ])
            return ws

    def get_goals(self, nickname: str) -> List[Dict]:
        """Отримує всі цілі користувача"""
        ws = self.get_goals_worksheet()
        all_goals = ws.get_all_records()
        return [g for g in all_goals if g.get('nickname') == nickname]

    def add_goal(
        self, 
        nickname: str, 
        goal_name: str, 
        target_amount: float,
        deadline: Optional[str] = None,
        current_amount: float = 0
    ):
        """Додає нову ціль"""
        ws = self.get_goals_worksheet()
        created_date = datetime.now().strftime("%Y-%m-%d")
        
        row = [
            nickname,
            goal_name,
            target_amount,
            current_amount,
            deadline or "Без дедлайну",
            False,
            created_date
        ]
        
        ws.append_row(row)
        logger.info(f"Goal added: {goal_name} for {nickname}")

    def update_goal_progress(
        self,
        nickname: str,
        goal_name: str,
        new_amount: float,
        completed: bool = False
    ):
        """Оновлює прогрес цілі"""
        ws = self.get_goals_worksheet()
        
        try:
            # Знаходимо ціль
            cell = ws.find(goal_name)
            if not cell:
                raise ValueError(f"Goal {goal_name} not found")
            
            row_index = cell.row
            
            # Оновлюємо current_amount (колонка 4)
            ws.update_cell(row_index, 4, new_amount)
            
            # Оновлюємо completed (колонка 6)
            ws.update_cell(row_index, 6, completed)
            
            logger.info(f"Goal progress updated: {goal_name} - {new_amount}")
            
        except Exception as e:
            logger.error(f"Error updating goal: {e}")
            raise

    def delete_goal(self, nickname: str, goal_name: str):
        """Видаляє ціль"""
        ws = self.get_goals_worksheet()
        
        try:
            cell = ws.find(goal_name)
            if cell:
                ws.delete_rows(cell.row)
                logger.info(f"Goal deleted: {goal_name}")
        except Exception as e:
            logger.error(f"Error deleting goal: {e}")
            raise

    def get_categories_worksheet(self):
        """Отримує або створює аркуш категорій"""
        worksheet_title = "custom_categories"
        try:
            return self.spreadsheet.worksheet(worksheet_title)
        except WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(title=worksheet_title, rows=1000, cols=4)
            ws.append_row(["nickname", "category_name", "emoji", "is_expense"])
            return ws

    def get_user_categories(self, nickname: str, is_expense: bool = True) -> List[Dict]:
        """Отримує користувацькі категорії"""
        ws = self.get_categories_worksheet()
        all_categories = ws.get_all_records()
        
        return [
            c for c in all_categories 
            if c.get('nickname') == nickname 
            and c.get('is_expense') == is_expense
        ]

    def add_custom_category(
        self,
        nickname: str,
        category_name: str,
        emoji: str = "📌",
        is_expense: bool = True
    ):
        """Додає власну категорію"""
        ws = self.get_categories_worksheet()
        
        # Перевіряємо чи не існує вже
        existing = self.get_user_categories(nickname, is_expense)
        if any(c.get('category_name') == category_name for c in existing):
            raise ValueError("Категорія вже існує")
        
        row = [nickname, category_name, emoji, is_expense]
        ws.append_row(row)
        logger.info(f"Custom category added: {category_name} for {nickname}")

    def delete_custom_category(self, nickname: str, category_name: str):
        """Видаляє власну категорію"""
        ws = self.get_categories_worksheet()
        
        try:
            # Шукаємо комбінацію nickname + category_name
            all_values = ws.get_all_values()
            for idx, row in enumerate(all_values[1:], start=2):  # Skip header
                if row[0] == nickname and row[1] == category_name:
                    ws.delete_rows(idx)
                    logger.info(f"Category deleted: {category_name}")
                    return
            
            raise ValueError("Категорія не знайдена")
            
        except Exception as e:
            logger.error(f"Error deleting category: {e}")
            raise

    def get_budgets_worksheet(self):
        """Отримує або створює аркуш бюджетів"""
        worksheet_title = "category_budgets"
        try:
            return self.spreadsheet.worksheet(worksheet_title)
        except WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(title=worksheet_title, rows=1000, cols=5)
            ws.append_row([
                "nickname", "category", "budget_amount", 
                "current_spent", "period"
            ])
            return ws

    def set_category_budget(
        self,
        nickname: str,
        category: str,
        budget_amount: float,
        period: str = "monthly"
    ):
        """Встановлює бюджет для категорії"""
        ws = self.get_budgets_worksheet()
        
        # Перевіряємо чи існує бюджет
        existing_budgets = ws.get_all_records()
        for idx, budget in enumerate(existing_budgets, start=2):
            if budget.get('nickname') == nickname and budget.get('category') == category:
                # Оновлюємо існуючий
                ws.update_cell(idx, 3, budget_amount)
                ws.update_cell(idx, 4, 0)  # Скидаємо витрати
                logger.info(f"Budget updated: {category} - {budget_amount}")
                return
        
        # Додаємо новий
        row = [nickname, category, budget_amount, 0, period]
        ws.append_row(row)
        logger.info(f"Budget set: {category} - {budget_amount}")

    def get_category_budgets(self, nickname: str) -> List[Dict]:
        """Отримує всі бюджети користувача"""
        ws = self.get_budgets_worksheet()
        all_budgets = ws.get_all_records()
        return [b for b in all_budgets if b.get('nickname') == nickname]

    def update_budget_spending(self, nickname: str, category: str, amount: float):
        """Оновлює витрати по бюджету"""
        ws = self.get_budgets_worksheet()
        
        try:
            all_budgets = ws.get_all_values()
            for idx, row in enumerate(all_budgets[1:], start=2):
                if row[0] == nickname and row[1] == category:
                    current_spent = float(row[3] or 0)
                    new_spent = current_spent + abs(amount)
                    ws.update_cell(idx, 4, new_spent)
                    
                    # Перевіряємо чи не перевищено бюджет
                    budget_limit = float(row[2])
                    if new_spent > budget_limit:
                        logger.warning(f"Budget exceeded for {category}: {new_spent}/{budget_limit}")
                        return True  # Бюджет перевищено
                    
                    return False
        except Exception as e:
            logger.error(f"Error updating budget: {e}")
        
        return False

    def reset_monthly_budgets(self):
        """Скидає витрати для місячних бюджетів (викликається scheduler)"""
        ws = self.get_budgets_worksheet()
        
        try:
            all_budgets = ws.get_all_values()
            for idx, row in enumerate(all_budgets[1:], start=2):
                if row[4] == "monthly":  # period column
                    ws.update_cell(idx, 4, 0)  # current_spent column
            
            logger.info("Monthly budgets reset")
            
        except Exception as e:
            logger.error(f"Error resetting budgets: {e}")

    def get_analytics_data(self, nickname: str, period_days: int = 30) -> Dict:
        """Отримує аналітичні дані для AI аналізу"""
        transactions = self.get_all_transactions(nickname)
        
        # Фільтруємо за період
        cutoff_date = datetime.now() - timedelta(days=period_days)
        period_transactions = [
            t for t in transactions
            if datetime.fromisoformat(t['date']) >= cutoff_date
        ]
        
        # Підраховуємо метрики
        total_income = sum(float(t['amount']) for t in period_transactions if float(t.get('amount', 0)) > 0)
        total_expense = sum(abs(float(t['amount'])) for t in period_transactions if float(t.get('amount', 0)) < 0)
        
        # Категорії
        expense_by_category = defaultdict(float)
        income_by_category = defaultdict(float)
        
        for t in period_transactions:
            amount = float(t.get('amount', 0))
            category = t.get('category', 'Інше')
            
            if amount < 0:
                expense_by_category[category] += abs(amount)
            else:
                income_by_category[category] += amount
        
        # Середнє за день
        avg_daily_expense = total_expense / period_days if period_days > 0 else 0
        avg_daily_income = total_income / period_days if period_days > 0 else 0
        
        return {
            'total_income': total_income,
            'total_expense': total_expense,
            'balance_change': total_income - total_expense,
            'expense_by_category': dict(expense_by_category),
            'income_by_category': dict(income_by_category),
            'avg_daily_expense': avg_daily_expense,
            'avg_daily_income': avg_daily_income,
            'transaction_count': len(period_transactions),
            'top_expense_category': max(expense_by_category.items(), key=lambda x: x[1])[0] if expense_by_category else None,
            'savings_rate': ((total_income - total_expense) / total_income * 100) if total_income > 0 else 0
        }


# Singleton instance
sheets_service = SheetsService()