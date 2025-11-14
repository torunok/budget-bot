# ============================================
# FILE: app/services/sheets_service.py (COMPLETE FIXED)
# ============================================
"""
Сервіс для роботи з Google Sheets - БЕЗ агресивного очищення кешу
"""

import logging
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
import gspread
from gspread.exceptions import WorksheetNotFound, APIError
from gspread.utils import rowcol_to_a1
import json

from app.config.settings import config

logger = logging.getLogger(__name__)


class SheetsService:
    """Сервіс для роботи з Google Sheets"""

    TRANSACTION_COLUMNS = [
        'date', 'user_id', 'amount', 'category', 'note',
        'nickname', 'balance', 'currency', 'Is_Subscription',
        'subscription_name', 'subscription_due_date'
    ]
    GOAL_COLUMNS = [
        'goal_name', 'target_amount', 'current_amount',
        'deadline', 'completed', 'created_date'
    ]
    REQUIRED_COLUMNS = TRANSACTION_COLUMNS + ['record_type'] + GOAL_COLUMNS
    TRANSACTION_RECORD_TYPE = 'transaction'
    GOAL_RECORD_TYPE = 'goal'
    DEFAULT_GOAL_DEADLINE = "Без дедлайну"
    
    def __init__(self):
        try:
            creds_json = config.GOOGLE_SERVICE_ACCOUNT_JSON
            
            if not creds_json:
                raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON is not set or empty.")
            
            creds_dict = json.loads(creds_json)
            self.gc = gspread.service_account_from_dict(creds_dict) 
            self.spreadsheet = self.gc.open_by_key(config.SPREADSHEET_ID)
            
            logger.info("✅ Connected to Google Sheets")
            
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {e}")
            logger.error("Ensure GOOGLE_SERVICE_ACCOUNT_JSON and SPREADSHEET_ID are correctly set.")
            raise
    
    def _ensure_required_columns(self, ws) -> List[str]:
        headers = ws.row_values(1)
        if not headers:
            ws.append_row(self.REQUIRED_COLUMNS.copy())
            return self.REQUIRED_COLUMNS.copy()
        
        missing = [col for col in self.REQUIRED_COLUMNS if col not in headers]
        if missing:
            headers.extend(missing)
            extra_cols = len(headers) - ws.col_count
            if extra_cols > 0:
                ws.add_cols(extra_cols)
            ws.update('A1', [headers])
            logger.info(f"Added missing columns to worksheet '{ws.title}': {missing}")
        return headers
    
    @staticmethod
    def _header_index_map(headers: List[str]) -> Dict[str, int]:
        return {name: idx + 1 for idx, name in enumerate(headers)}
    
    def _build_row(self, headers: List[str], values: Dict[str, Any]) -> List[Any]:
        row = [''] * len(headers)
        column_map = self._header_index_map(headers)
        for key, value in values.items():
            col_idx = column_map.get(key)
            if col_idx:
                row[col_idx - 1] = value
        return row
    
    def _batch_update_cells(self, ws, headers: List[str], updates: List[Tuple[int, str, Any]]):
        if not updates:
            return
        column_map = self._header_index_map(headers)
        data = []
        for row, column_name, value in updates:
            col_idx = column_map.get(column_name)
            if not col_idx:
                continue
            data.append({
                'range': rowcol_to_a1(row, col_idx),
                'values': [[value]]
            })
        if data:
            ws.batch_update(data)
    
    def update_transaction_fields(
        self,
        nickname: str,
        row_index: int,
        values: Dict[str, Any],
        legacy_titles: Optional[List[str]] = None,
        recalculate: bool = False
    ):
        """Оновлює кілька полів транзакції за назвами колонок."""
        if not values:
            return
        ws = self.get_or_create_worksheet(nickname, legacy_titles)
        headers = self._ensure_required_columns(ws)
        updates = []
        for column_name, column_value in values.items():
            if column_name in headers:
                updates.append((row_index, column_name, column_value))
        self._batch_update_cells(ws, headers, updates)
        if recalculate or 'amount' in values:
            self.recalculate_balances(nickname, legacy_titles)
    
    def _get_goal_rows(self, ws, headers: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        headers = headers or self._ensure_required_columns(ws)
        all_values = ws.get_all_values(value_render_option='UNFORMATTED_VALUE')
        if len(all_values) < 2:
            return []
        
        sheet_headers = all_values[0]
        if sheet_headers != headers:
            headers = sheet_headers
        try:
            record_type_idx = headers.index('record_type')
        except ValueError:
            return []
        
        goals = []
        for row_idx, row in enumerate(all_values[1:], start=2):
            row_type = ''
            if record_type_idx < len(row):
                row_type = str(row[record_type_idx]).strip().lower()
            if row_type != self.GOAL_RECORD_TYPE:
                continue
            goal = {}
            for col_idx, header in enumerate(headers):
                goal[header] = row[col_idx] if col_idx < len(row) else ""
            goal['_row'] = row_idx
            goals.append(goal)
        return goals
    
    def _find_goal_row(self, ws, headers: Optional[List[str]], goal_name: str) -> int:
        goals = self._get_goal_rows(ws, headers)
        for goal in goals:
            if goal.get('goal_name') == goal_name:
                return goal['_row']
        raise ValueError(f"Goal '{goal_name}' for '{ws.title}' not found")
    
    def _append_goal_row(
        self,
        ws,
        headers: Optional[List[str]],
        nickname: str,
        goal_name: str,
        target_amount: float,
        deadline: Optional[str],
        current_amount: float = 0.0,
        completed: bool = False,
        created_date: Optional[str] = None
    ):
        headers = headers or self._ensure_required_columns(ws)
        payload = {
            'record_type': self.GOAL_RECORD_TYPE,
            'nickname': nickname,
            'goal_name': goal_name,
            'target_amount': target_amount,
            'current_amount': current_amount,
            'deadline': deadline or self.DEFAULT_GOAL_DEADLINE,
            'completed': completed,
            'created_date': created_date or datetime.now().strftime("%Y-%m-%d")
        }
        ws.append_row(self._build_row(headers, payload))
    
    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        if value in ("", None):
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            try:
                return float(str(value).replace(",", "."))
            except (TypeError, ValueError):
                return default
    
    @staticmethod
    def _normalize_completed(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        return text in {"true", "1", "yes", "y", "completed"}
    
    def get_or_create_worksheet(self, nickname: str, legacy_titles: Optional[List[str]] = None):
        """Отримує або створює аркуш користувача"""
        try:
            ws = self.spreadsheet.worksheet(nickname)
            self._ensure_required_columns(ws)
            return ws
            
        except WorksheetNotFound:
            if legacy_titles:
                for legacy in legacy_titles:
                    if not legacy:
                        continue
                    try:
                        ws = self.spreadsheet.worksheet(legacy)
                        ws.update_title(nickname)
                        self._ensure_required_columns(ws)
                        logger.info(f"Renamed worksheet '{legacy}' -> '{nickname}'")
                        return ws
                    except WorksheetNotFound:
                        continue
            logger.info(f"Creating new worksheet for '{nickname}'")
            ws = self.spreadsheet.add_worksheet(
                title=nickname,
                rows=1000,
                cols=len(self.REQUIRED_COLUMNS)
            )
            headers = self.REQUIRED_COLUMNS.copy()
            ws.append_row(headers)
            initial_row = self._build_row(headers, {
                'record_type': self.TRANSACTION_RECORD_TYPE,
                'date': "initial",
                'user_id': "0",
                'amount': 0,
                'category': "initial",
                'note': "initial",
                'nickname': nickname,
                'balance': "0.0",
                'currency': config.DEFAULT_CURRENCY,
                'Is_Subscription': False,
            })
            ws.append_row(initial_row)
            return ws

    def append_transaction(
        self,
        user_id: int,
        nickname: str,
        amount: float,
        category: str = config.DEFAULT_CATEGORY,
        note: str = "",
        is_subscription: bool = False,
        subscription_name: Optional[str] = None,
        subscription_due_date: Optional[str] = None,
        legacy_titles: Optional[List[str]] = None,
        user_display_name: Optional[str] = None
    ) -> int:
        """Додає нову транзакцію"""
        ws = self.get_or_create_worksheet(nickname, legacy_titles)
        headers = self._ensure_required_columns(ws)
        timestamp = datetime.now().isoformat()
        
        current_balance, currency = self.get_current_balance(nickname, legacy_titles)
        new_balance = current_balance + amount
        
        row = self._build_row(headers, {
            'record_type': self.TRANSACTION_RECORD_TYPE,
            'date': timestamp,
            'user_id': str(user_id),
            'amount': amount,
            'category': category,
            'note': note,
            'nickname': user_display_name or nickname,
            'balance': new_balance,
            'currency': currency,
            'Is_Subscription': is_subscription,
            'subscription_name': subscription_name or "",
            'subscription_due_date': subscription_due_date or ""
        })
        ws.append_row(row)
        
        try:
            row_count = len(ws.get_all_values())
        except Exception:
            row_count = len(ws.col_values(1))
        
        logger.info(f"✅ Added transaction for {nickname}: {amount} {currency}")
        return row_count

    def get_current_balance(self, nickname: str, legacy_titles: Optional[List[str]] = None) -> Tuple[float, str]:
        """Отримує поточний баланс та валюту"""
        ws = self.get_or_create_worksheet(nickname, legacy_titles)
        
        try:
            all_values = ws.get_all_values(value_render_option='UNFORMATTED_VALUE')
            
            if len(all_values) < 2:
                logger.warning(f"No transactions for {nickname}, returning default balance")
                return 0.0, config.DEFAULT_CURRENCY
            
            headers = all_values[0]
            column_map = self._header_index_map(headers)
            record_type_idx = column_map.get('record_type', 0) - 1 if column_map.get('record_type') else None
            balance_idx = column_map.get('balance', 0) - 1
            currency_idx = column_map.get('currency', 0) - 1
            
            for row in reversed(all_values[1:]):
                if record_type_idx is not None and record_type_idx >= 0:
                    if record_type_idx < len(row):
                        row_type = str(row[record_type_idx]).strip().lower()
                        if row_type and row_type != self.TRANSACTION_RECORD_TYPE:
                            continue
                if balance_idx < 0 or balance_idx >= len(row):
                    continue
                balance = self._safe_float(row[balance_idx], 0.0)
                currency = row[currency_idx] if currency_idx >= 0 and currency_idx < len(row) and row[currency_idx] else config.DEFAULT_CURRENCY
                logger.info(f"✅ Balance for {nickname}: {balance} {currency}")
                return balance, currency
            
            logger.warning(f"No transaction rows found for {nickname}, returning default balance")
            return 0.0, config.DEFAULT_CURRENCY
            
        except (ValueError, IndexError, TypeError) as e:
            logger.error(f"Error getting balance for {nickname}: {e}", exc_info=True)
            return 0.0, config.DEFAULT_CURRENCY
    
    def recalculate_balances(self, nickname: str, legacy_titles: Optional[List[str]] = None):
        """Повністю перераховує колонку balance для користувача."""
        ws = self.get_or_create_worksheet(nickname, legacy_titles)
        headers = self._ensure_required_columns(ws)
        try:
            all_values = ws.get_all_values(value_render_option='UNFORMATTED_VALUE')
        except APIError as e:
            logger.error(f"Error loading worksheet for balance recalculation: {e}", exc_info=True)
            return
        if len(all_values) < 2:
            return
        column_map = self._header_index_map(headers)
        amount_idx = column_map.get('amount', 0) - 1
        balance_idx = column_map.get('balance', 0) - 1
        record_type_idx = column_map.get('record_type', 0) - 1 if column_map.get('record_type') else None
        if amount_idx < 0 or balance_idx < 0:
            logger.warning("Cannot recalculate balances: missing amount or balance columns")
            return
        
        running_balance = 0.0
        updates = []
        for row_idx, row in enumerate(all_values[1:], start=2):
            if record_type_idx is not None and record_type_idx >= 0:
                if record_type_idx < len(row):
                    row_type = str(row[record_type_idx]).strip().lower()
                    if row_type and row_type != self.TRANSACTION_RECORD_TYPE:
                        continue
            amount = self._safe_float(row[amount_idx], 0.0) if amount_idx < len(row) else 0.0
            running_balance += amount
            updates.append((row_idx, 'balance', running_balance))
        
        self._batch_update_cells(ws, headers, updates)
    
    def update_balance(self, nickname: str, new_balance: float, currency: str, legacy_titles: Optional[List[str]] = None):
        """Оновлює баланс користувача"""
        ws = self.get_or_create_worksheet(nickname, legacy_titles)
        headers = self._ensure_required_columns(ws)
        
        try:
            all_values = ws.get_all_values(value_render_option='UNFORMATTED_VALUE')
        except APIError as e:
            logger.error(f"Error loading worksheet for balance update: {e}", exc_info=True)
            return
        
        if len(all_values) < 2:
            logger.warning(f"No rows to update balance for {nickname}")
            return
        
        headers = all_values[0]
        column_map = self._header_index_map(headers)
        record_type_idx = column_map.get('record_type', 0) - 1 if column_map.get('record_type') else None
        
        target_row = None
        for row_idx in range(len(all_values), 1, -1):
            row = all_values[row_idx - 1]
            if record_type_idx is not None and record_type_idx >= 0:
                if record_type_idx < len(row):
                    row_type = str(row[record_type_idx]).strip().lower()
                    if row_type and row_type != self.TRANSACTION_RECORD_TYPE:
                        continue
            target_row = row_idx
            break
        
        if not target_row:
            logger.warning(f"No transaction rows to update balance for {nickname}")
            return
        
        updates = [
            (target_row, 'balance', new_balance),
            (target_row, 'currency', currency)
        ]
        self._batch_update_cells(ws, headers, updates)
        logger.info(f"✅ Updated balance for {nickname}: {new_balance} {currency}")
    
    def get_all_transactions(self, nickname: str, legacy_titles: Optional[List[str]] = None) -> List[Dict]:
        """Отримує всі транзакції користувача"""
        ws = self.get_or_create_worksheet(nickname, legacy_titles)
        
        try:
            # Використовуємо get_all_values для свіжих даних
            all_values = ws.get_all_values(value_render_option='UNFORMATTED_VALUE')
            
            if len(all_values) < 2:
                logger.warning(f"No transactions for {nickname}")
                return []
            
            headers = all_values[0]
            rows = all_values[1:]
            column_map = self._header_index_map(headers)
            record_type_idx = column_map.get('record_type', 0) - 1 if column_map.get('record_type') else None
            
            # Конвертуємо в список словників
            transactions = []
            for row_idx, row in enumerate(rows, start=2):
                if record_type_idx is not None and record_type_idx >= 0:
                    row_type = ''
                    if record_type_idx < len(row):
                        row_type = str(row[record_type_idx]).strip().lower()
                    if row_type and row_type != self.TRANSACTION_RECORD_TYPE:
                        continue
                transaction = {}
                for col_idx, header in enumerate(headers):
                    if col_idx < len(row):
                        transaction[header] = row[col_idx]
                    else:
                        transaction[header] = None
                transaction['_row'] = row_idx
                transactions.append(transaction)
            
            logger.info(f"✅ Loaded {len(transactions)} transactions for {nickname}")
            
            # 🔍 ДІАГНОСТИКА: Показуємо останні 3 транзакції
            if transactions:
                logger.info(f"📊 Last 3 transactions:")
                for t in transactions[-3:]:
                    logger.info(f"   {t.get('date')} | {t.get('amount')} | {t.get('category')}")
            
            return transactions
            
        except Exception as e:
            logger.error(f"❌ Error getting transactions: {e}", exc_info=True)
            # Fallback до старого методу
            records = ws.get_all_records()
            transactions = []
            for idx, record in enumerate(records, start=2):
                record_type = str(record.get('record_type', '')).strip().lower()
                if record_type and record_type != self.TRANSACTION_RECORD_TYPE:
                    continue
                record['_row'] = idx
                transactions.append(record)
            return transactions
    
    def get_subscriptions(self, nickname: str, legacy_titles: Optional[List[str]] = None) -> List[Dict]:
        """Отримує всі підписки користувача"""
        transactions = self.get_all_transactions(nickname, legacy_titles)
        subscriptions = [t for t in transactions if str(t.get('Is_Subscription', '')).upper() == 'TRUE']
        logger.info(f"Found {len(subscriptions)} subscriptions for {nickname}")
        return subscriptions
    
    def update_transaction(
        self,
        nickname: str,
        row_index: int,
        column_index: int,
        value,
        legacy_titles: Optional[List[str]] = None
    ):
        """Оновлює значення в транзакції"""
        ws = self.get_or_create_worksheet(nickname, legacy_titles)
        ws.update_cell(row_index, column_index, value)
        logger.info(f"Updated transaction at row {row_index}, col {column_index}")
        if column_index == 3:  # amount column
            self.recalculate_balances(nickname, legacy_titles)

    def delete_transaction(self, nickname: str, row_index: int, legacy_titles: Optional[List[str]] = None):
        """Видаляє транзакцію"""
        ws = self.get_or_create_worksheet(nickname, legacy_titles)
        ws.delete_rows(row_index)
        logger.info(f"Deleted transaction at row {row_index} for {nickname}")
        self.recalculate_balances(nickname, legacy_titles)
    
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

    def _goal_sheet_title(self, nickname: str) -> str:
        """Формує безпечну назву аркуша для цілей користувача"""
        base = nickname or "anonymous"
        safe = re.sub(r'[^A-Za-z0-9 _-]', '_', base)[:80]
        return f"{safe}_goals"
    
    def _migrate_legacy_goals(
        self,
        nickname: str,
        ws=None,
        headers: Optional[List[str]] = None
    ) -> List[Dict]:
        """Переносить старі цілі у основний аркуш користувача"""
        ws = ws or self.get_or_create_worksheet(nickname)
        headers = headers or self._ensure_required_columns(ws)
        migrated = False
        
        legacy_sources = []
        try:
            per_user_ws = self.spreadsheet.worksheet(self._goal_sheet_title(nickname))
            legacy_sources.append(("per_user", per_user_ws))
        except WorksheetNotFound:
            per_user_ws = None
        try:
            global_ws = self.spreadsheet.worksheet("user_goals")
            legacy_sources.append(("global", global_ws))
        except WorksheetNotFound:
            global_ws = None
        
        for source_type, source_ws in legacy_sources:
            values = source_ws.get_all_values()
            if len(values) < 2:
                continue
            
            header_row = values[0]
            rows_to_delete = []
            for idx, row in enumerate(values[1:], start=2):
                if source_type == "global":
                    if not row or row[0] != nickname:
                        continue
                record = {}
                for col_idx, header in enumerate(header_row):
                    record[header] = row[col_idx] if col_idx < len(row) else ""
                
                self._append_goal_row(
                    ws,
                    headers,
                    nickname=nickname,
                    goal_name=record.get('goal_name', 'Без назви'),
                    target_amount=self._safe_float(record.get('target_amount')),
                    deadline=record.get('deadline') or self.DEFAULT_GOAL_DEADLINE,
                    current_amount=self._safe_float(record.get('current_amount')),
                    completed=self._normalize_completed(record.get('completed')),
                    created_date=record.get('created_date') or datetime.now().strftime("%Y-%m-%d")
                )
                migrated = True
                if source_type == "global":
                    rows_to_delete.append(idx)
            
            if source_type == "global" and rows_to_delete:
                for row_idx in sorted(rows_to_delete, reverse=True):
                    source_ws.delete_rows(row_idx)
            if source_type == "per_user" and migrated:
                try:
                    self.spreadsheet.del_worksheet(source_ws)
                except Exception as e:
                    logger.warning(f"Could not delete legacy goals sheet {source_ws.title}: {e}")
        
        if migrated:
            logger.info(f"Migrated legacy goals for {nickname}")
            return self._get_goal_rows(ws, headers)
        return []
    
    def get_goals(self, nickname: str) -> List[Dict]:
        """Отримує всі цілі користувача"""
        ws = self.get_or_create_worksheet(nickname)
        headers = self._ensure_required_columns(ws)
        all_goals = self._get_goal_rows(ws, headers)
        if not all_goals:
            all_goals = self._migrate_legacy_goals(nickname, ws, headers)
        for goal in all_goals:
            goal['completed'] = self._normalize_completed(goal.get('completed'))
        return all_goals
    
    def add_goal(
        self, 
        nickname: str, 
        goal_name: str, 
        target_amount: float,
        deadline: Optional[str] = None,
        current_amount: float = 0
    ):
        """Додає нову ціль"""
        ws = self.get_or_create_worksheet(nickname)
        headers = self._ensure_required_columns(ws)
        self._append_goal_row(
            ws,
            headers,
            nickname=nickname,
            goal_name=goal_name,
            target_amount=target_amount,
            deadline=deadline,
            current_amount=current_amount,
            completed=False
        )
        logger.info(f"Goal added: {goal_name} for {nickname}")
    
    def update_goal_progress(
        self,
        nickname: str,
        goal_name: str,
        new_amount: float,
        completed: bool = False
    ):
        """Оновлює прогрес цілі"""
        ws = self.get_or_create_worksheet(nickname)
        headers = self._ensure_required_columns(ws)
        try:
            row_index = self._find_goal_row(ws, headers, goal_name)
            updates = [
                (row_index, 'current_amount', new_amount),
                (row_index, 'completed', completed)
            ]
            self._batch_update_cells(ws, headers, updates)
            logger.info(f"Goal progress updated: {goal_name} - {new_amount}")
            
        except Exception as e:
            logger.error(f"Error updating goal: {e}")
            raise

    def update_goal_details(
        self,
        nickname: str,
        goal_name: str,
        new_name: Optional[str] = None,
        target_amount: Optional[float] = None,
        deadline: Optional[str] = None,
        completed: Optional[bool] = None
    ):
        """Оновлює деталі цілі"""
        ws = self.get_or_create_worksheet(nickname)
        headers = self._ensure_required_columns(ws)
        
        try:
            row_index = self._find_goal_row(ws, headers, goal_name)
            updates: List[Tuple[int, str, Any]] = []
            
            if new_name is not None:
                updates.append((row_index, 'goal_name', new_name))
            if target_amount is not None:
                updates.append((row_index, 'target_amount', target_amount))
            if deadline is not None:
                updates.append((row_index, 'deadline', deadline or self.DEFAULT_GOAL_DEADLINE))
            if completed is not None:
                updates.append((row_index, 'completed', completed))
            
            self._batch_update_cells(ws, headers, updates)
            
            logger.info(
                f"Goal details updated for {goal_name}: "
                f"name={new_name}, target={target_amount}, deadline={deadline}, completed={completed}"
            )
        except Exception as e:
            logger.error(f"Error updating goal details: {e}")
            raise
    
    def delete_goal(self, nickname: str, goal_name: str):
        """Видаляє ціль"""
        ws = self.get_or_create_worksheet(nickname)
        headers = self._ensure_required_columns(ws)
        
        try:
            row_index = self._find_goal_row(ws, headers, goal_name)
            ws.delete_rows(row_index)
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
            all_values = ws.get_all_values()
            for idx, row in enumerate(all_values[1:], start=2):
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
        
        existing_budgets = ws.get_all_records()
        for idx, budget in enumerate(existing_budgets, start=2):
            if budget.get('nickname') == nickname and budget.get('category') == category:
                ws.update_cell(idx, 3, budget_amount)
                ws.update_cell(idx, 4, 0)
                logger.info(f"Budget updated: {category} - {budget_amount}")
                return
        
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
                    
                    budget_limit = float(row[2])
                    if new_spent > budget_limit:
                        logger.warning(f"Budget exceeded for {category}: {new_spent}/{budget_limit}")
                        return True
                    
                    return False
        except Exception as e:
            logger.error(f"Error updating budget: {e}")
        
        return False

    def reset_monthly_budgets(self):
        """Скидає витрати для місячних бюджетів"""
        ws = self.get_budgets_worksheet()
        
        try:
            all_budgets = ws.get_all_values()
            for idx, row in enumerate(all_budgets[1:], start=2):
                if row[4] == "monthly":
                    ws.update_cell(idx, 4, 0)
            
            logger.info("Monthly budgets reset")
            
        except Exception as e:
            logger.error(f"Error resetting budgets: {e}")


# Singleton instance
sheets_service = SheetsService()
