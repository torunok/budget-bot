# ============================================
# FILE: app/services/chart_service.py (NEW)
# ============================================
"""
Сервіс для генерації графіків та візуалізації
"""

import io
import logging
from datetime import datetime, timedelta
from typing import List, Dict
from collections import defaultdict

import matplotlib
matplotlib.use('Agg')  # Для серверного використання
import matplotlib.pyplot as plt
from matplotlib import font_manager
import seaborn as sns
import numpy as np

from app.config.settings import config
from app.utils.helpers import parse_sheet_datetime

logger = logging.getLogger(__name__)

# Налаштування стилю
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (10, 6)
plt.rcParams['figure.dpi'] = 100

# Для підтримки кирилиці
try:
    font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    prop = font_manager.FontProperties(fname=font_path)
    plt.rcParams['font.family'] = prop.get_name()
except:
    logger.warning("Could not load DejaVu font, cyrillic may not display correctly")


class ChartService:
    """Сервіс для створення фінансових графіків"""
    
    @staticmethod
    def create_pie_chart(transactions: List[Dict], chart_type: str = "expense") -> io.BytesIO:
        """Створює кругову діаграму витрат/доходів по категоріях"""
        
        # Фільтруємо за типом
        if chart_type == "expense":
            filtered = [t for t in transactions if float(t.get('amount', 0)) < 0]
        else:
            filtered = [t for t in transactions if float(t.get('amount', 0)) > 0]
        
        if not filtered:
            return ChartService._create_no_data_chart("Немає даних для відображення")
        
        # Групуємо по категоріях
        category_totals = defaultdict(float)
        for t in filtered:
            category = t.get('category', 'Інше')
            amount = abs(float(t.get('amount', 0)))
            category_totals[category] += amount
        
        # Сортуємо та беремо топ-7
        sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
        
        if len(sorted_categories) > 7:
            top_7 = sorted_categories[:7]
            other_sum = sum(v for _, v in sorted_categories[7:])
            if other_sum > 0:
                top_7.append(("Інше", other_sum))
            data = top_7
        else:
            data = sorted_categories
        
        labels = [cat for cat, _ in data]
        values = [val for _, val in data]
        
        # Кольори
        colors = sns.color_palette("husl", len(labels))
        
        # Створюємо графік
        fig, ax = plt.subplots(figsize=(10, 8))
        
        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            autopct='%1.1f%%',
            colors=colors,
            startangle=90,
            textprops={'fontsize': 10}
        )
        
        # Покращуємо читабельність
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontsize(9)
            autotext.set_weight('bold')
        
        title = "Витрати по категоріях" if chart_type == "expense" else "Доходи по категоріях"
        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
        
        plt.tight_layout()
        
        # Зберігаємо в буфер
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight', dpi=150)
        buffer.seek(0)
        plt.close(fig)
        
        return buffer
    
    @staticmethod
    def create_line_chart(transactions: List[Dict], period_days: int = 30) -> io.BytesIO:
        """Створює лінійний графік витрат та доходів за період"""
        
        if not transactions:
            return ChartService._create_no_data_chart("Немає даних для відображення")
        
        # Фільтруємо за період
        cutoff_date = datetime.now() - timedelta(days=period_days)
        filtered = []
        for t in transactions:
            parsed = parse_sheet_datetime(t.get('date'))
            if not parsed:
                continue
            if parsed >= cutoff_date:
                filtered.append((t, parsed))
        
        if not filtered:
            return ChartService._create_no_data_chart(f"Немає даних за останні {period_days} днів")
        
        # Групуємо по датах
        daily_expense = defaultdict(float)
        daily_income = defaultdict(float)
        
        for t, parsed in filtered:
            date = parsed.date()
            amount = float(t.get('amount', 0))
            
            if amount < 0:
                daily_expense[date] += abs(amount)
            else:
                daily_income[date] += amount
        
        # Створюємо повний діапазон дат
        all_dates = []
        current_date = cutoff_date.date()
        end_date = datetime.now().date()
        
        while current_date <= end_date:
            all_dates.append(current_date)
            current_date += timedelta(days=1)
        
        expenses = [daily_expense.get(d, 0) for d in all_dates]
        incomes = [daily_income.get(d, 0) for d in all_dates]
        
        # Створюємо графік
        fig, ax = plt.subplots(figsize=(12, 6))
        
        ax.plot(all_dates, expenses, marker='o', linewidth=2, 
                label='Витрати', color='#e74c3c', markersize=4)
        ax.plot(all_dates, incomes, marker='o', linewidth=2, 
                label='Доходи', color='#27ae60', markersize=4)
        
        ax.set_xlabel('Дата', fontsize=12)
        ax.set_ylabel('Сума (UAH)', fontsize=12)
        ax.set_title(f'Динаміка фінансів за {period_days} днів', fontsize=14, fontweight='bold')
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3)
        
        # Форматування дат на осі X
        fig.autofmt_xdate()
        
        plt.tight_layout()
        
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight', dpi=150)
        buffer.seek(0)
        plt.close(fig)
        
        return buffer
    
    @staticmethod
    def create_bar_comparison(transactions: List[Dict], currency: str = "UAH") -> io.BytesIO:
        """Створює порівняльну діаграму доходів vs витрат по місяцях"""
        
        if not transactions:
            return ChartService._create_no_data_chart("Немає даних для відображення")
        
        # Групуємо по місяцях
        monthly_data = defaultdict(lambda: {'income': 0, 'expense': 0})
        
        for t in transactions:
            parsed = parse_sheet_datetime(t.get('date'))
            if not parsed:
                continue
            month_key = parsed.strftime('%Y-%m')
            amount = float(t.get('amount', 0))
            
            if amount < 0:
                monthly_data[month_key]['expense'] += abs(amount)
            else:
                monthly_data[month_key]['income'] += amount
        
        # Беремо останні 6 місяців
        sorted_months = sorted(monthly_data.keys())[-6:]
        
        if not sorted_months:
            return ChartService._create_no_data_chart("Недостатньо даних")
        
        months_labels = [datetime.strptime(m, '%Y-%m').strftime('%B %Y') for m in sorted_months]
        incomes = [monthly_data[m]['income'] for m in sorted_months]
        expenses = [monthly_data[m]['expense'] for m in sorted_months]
        
        # Створюємо графік
        fig, ax = plt.subplots(figsize=(12, 6))
        
        x = range(len(months_labels))
        width = 0.35
        
        bars1 = ax.bar([i - width/2 for i in x], incomes, width, 
                       label='Доходи', color='#27ae60', alpha=0.8)
        bars2 = ax.bar([i + width/2 for i in x], expenses, width, 
                       label='Витрати', color='#e74c3c', alpha=0.8)
        
        ax.set_xlabel('Місяць', fontsize=12)
        ax.set_ylabel(f'Сума ({currency})', fontsize=12)
        ax.set_title('Порівняння доходів та витрат', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(months_labels, rotation=45, ha='right')
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3, axis='y')
        
        # Додаємо значення над стовпцями
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{height:,.0f}',
                           ha='center', va='bottom', fontsize=8)
        
        plt.tight_layout()
        
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight', dpi=150)
        buffer.seek(0)
        plt.close(fig)
        
        return buffer
    
    @staticmethod
    def create_balance_history(transactions: List[Dict], currency: str = "UAH") -> io.BytesIO:
        """Створює графік історії балансу"""
        
        if not transactions:
            return ChartService._create_no_data_chart("Немає даних для відображення")
        
        # Сортуємо за датою
        valid = []
        for t in transactions:
            parsed = parse_sheet_datetime(t.get('date'))
            if parsed:
                valid.append((t, parsed))
        sorted_transactions = sorted(valid, key=lambda x: x[1])
        
        dates = []
        balances = []
        
        for t, parsed in sorted_transactions:
            date = parsed
            balance = float(t.get('balance', 0))
            dates.append(date)
            balances.append(balance)
        
        # Створюємо графік
        fig, ax = plt.subplots(figsize=(12, 6))
        
        ax.plot(dates, balances, linewidth=2.5, color='#3498db', marker='')
        ax.fill_between(dates, balances, alpha=0.3, color='#3498db')
        
        ax.set_xlabel('Дата', fontsize=12)
        ax.set_ylabel(f'Баланс ({currency})', fontsize=12)
        ax.set_title('Історія балансу', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        # Додаємо горизонтальну лінію на 0
        ax.axhline(y=0, color='red', linestyle='--', linewidth=1, alpha=0.5)
        
        # Форматування дат
        fig.autofmt_xdate()
        
        plt.tight_layout()
        
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight', dpi=150)
        buffer.seek(0)
        plt.close(fig)
        
        return buffer
    
    @staticmethod
    def create_category_trend(transactions: List[Dict], category: str, period_days: int = 90) -> io.BytesIO:
        """Створює тренд витрат по конкретній категорії"""
        
        # Фільтруємо за категорією та періодом
        cutoff_date = datetime.now() - timedelta(days=period_days)
        filtered = []
        for t in transactions:
            if t.get('category') != category:
                continue
            parsed = parse_sheet_datetime(t.get('date'))
            if not parsed or parsed < cutoff_date:
                continue
            if float(t.get('amount', 0)) >= 0:
                continue
            filtered.append((t, parsed))
        
        if not filtered:
            return ChartService._create_no_data_chart(f"Немає витрат по категорії '{category}'")
        
        # Групуємо по тижнях
        weekly_data = defaultdict(float)
        
        for t, parsed in filtered:
            date = parsed
            week_start = date - timedelta(days=date.weekday())
            week_key = week_start.strftime('%Y-%m-%d')
            amount = abs(float(t.get('amount', 0)))
            weekly_data[week_key] += amount
        
        sorted_weeks = sorted(weekly_data.keys())
        week_labels = [datetime.strptime(w, '%Y-%m-%d').strftime('%d.%m') for w in sorted_weeks]
        amounts = [weekly_data[w] for w in sorted_weeks]
        
        # Створюємо графік
        fig, ax = plt.subplots(figsize=(12, 6))
        
        ax.bar(week_labels, amounts, color='#9b59b6', alpha=0.7)
        
        # Додаємо лінію тренду
        if len(amounts) > 2:
            z = np.polyfit(range(len(amounts)), amounts, 1)
            p = np.poly1d(z)
            ax.plot(week_labels, p(range(len(amounts))), "r--", 
                   linewidth=2, label='Тренд', alpha=0.7)
        
        ax.set_xlabel('Тиждень', fontsize=12)
        ax.set_ylabel('Сума (UAH)', fontsize=12)
        ax.set_title(f'Витрати по категорії: {category}', fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight', dpi=150)
        buffer.seek(0)
        plt.close(fig)
        
        return buffer
    
    @staticmethod
    def _create_no_data_chart(message: str) -> io.BytesIO:
        """Створює заглушку, коли немає даних"""
        fig, ax = plt.subplots(figsize=(8, 6))
        
        ax.text(0.5, 0.5, message, 
               horizontalalignment='center',
               verticalalignment='center',
               transform=ax.transAxes,
               fontsize=16,
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        ax.axis('off')
        
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight', dpi=100)
        buffer.seek(0)
        plt.close(fig)
        
        return buffer


# Singleton
chart_service = ChartService()
