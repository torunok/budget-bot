# ============================================
# FILE: app/core/states.py
# ============================================
"""
FSM стани для діалогів
"""

from aiogram.fsm.state import State, StatesGroup


class UserState(StatesGroup):
    """Стани для роботи з транзакціями"""
    add_expense = State()
    add_income = State()
    edit_amount = State()
    edit_category = State()
    edit_description = State()
    edit_balance = State()
    select_period = State()
    select_transaction_type = State()
    select_category_to_edit = State()
    select_transaction_to_edit = State()
    add_feedback = State()
    waiting_for_export_period = State()
    setting_savings_goal = State()


class SubscriptionState(StatesGroup):
    """Стани для роботи з підписками"""
    add_name = State()
    add_amount = State()
    add_original_amount = State()
    add_category = State()
    add_date = State()
    select_to_edit = State()
    edit_name = State()
    edit_amount = State()
    edit_original_amount = State()
    edit_category = State()
    edit_date = State()


class TransactionState(StatesGroup):
    """Стани для покрокового додавання транзакцій"""
    waiting_amount = State()
    choosing_category = State()
    adding_custom_category = State()
    entering_description = State()


class BudgetState(StatesGroup):
    """States for budgets"""
    set_category = State()
    set_amount = State()
    edit_select = State()
    edit_amount = State()

class AnalyticsState(StatesGroup):
    """Стани для аналітики"""
    select_chart_type = State()
    select_comparison_period = State()


class AIAnalysisState(StatesGroup):
    """States for AI analysis"""
    awaiting_start_date = State()
    awaiting_end_date = State()


class BudgetGoalState(StatesGroup):
    """Стани для цілей заощаджень"""
    set_goal_name = State()
    set_goal_amount = State()
    set_goal_deadline = State()
    awaiting_contribution = State()
    edit_goal_name = State()
    edit_goal_amount = State()
    edit_goal_deadline = State()
    edit_goal_progress = State()
    delete_goal_confirmation = State()

