# ============================================
# FILE: app/services/ai_service.py
# ============================================
"""
Сервіс взаємодії з Gemini для AI-аналізу.
"""

import asyncio
import logging
import re
from typing import Any, Dict, List

from google import generativeai as genai

from app.config.settings import config

logger = logging.getLogger(__name__)


class AIService:
    """Основний сервіс для AI-аналізу."""

    def __init__(self):
        if config.GEMINI_API_KEY and config.ENABLE_AI_ANALYSIS:
            try:
                genai.configure(api_key=config.GEMINI_API_KEY)
                self.model = genai.GenerativeModel("gemini-2.5-flash")
                self.enabled = True
                logger.info("✅ Gemini AI initialized")
            except Exception as exc:
                logger.error("⚠️ Failed to initialize Gemini: %s", exc)
                self.enabled = False
        else:
            self.enabled = False
            logger.warning("AI analysis is disabled")

    async def analyze_finances(
        self, transactions: List[dict], context: Dict[str, Any]
    ) -> str:
        """Створює AI-висновок з урахуванням транзакцій та агрегатів."""
        if not self.enabled:
            return "🤖 AI-аналіз тимчасово недоступний."

        transactions_str = self._format_transactions(transactions)
        prompt = self._build_analysis_prompt(transactions_str, context)

        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            clean_text = re.sub(r"[*#]+", "", response.text)
            return clean_text.strip()
        except Exception as exc:
            logger.error("AI analysis error: %s", exc)
            return "⚠️ На жаль, не вдалося побудувати AI-аналітику. Спробуй пізніше."

    async def get_budget_recommendations(
        self, transactions: List[dict], income: float
    ) -> str:
        """AI-рекомендації щодо розподілу бюджету."""
        if not self.enabled:
            return "🤖 AI-рекомендації тимчасово недоступні."

        transactions_str = self._format_transactions(transactions)
        prompt = f"""
        Проаналізуй витрати користувача та підготуй короткі рекомендації.

        Щомісячний дохід: {income} UAH

        Транзакції:
        {transactions_str}

        Надішли 4 поради:
        1. Як оптимізувати найбільшу категорію.
        2. Де можна скоротити витрати без втрати якості життя.
        3. Яку частину доходу варто перекинути до резерву.
        4. Які довгострокові кроки варто закласти вже зараз.

        Будь конкретним і не перевищуй 500 символів.
        """

        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            return re.sub(r"[*#]+", "", response.text).strip()
        except Exception as exc:
            logger.error("Recommendations error: %s", exc)
            return "⚠️ Немає змоги отримати рекомендації прямо зараз."

    async def predict_expenses(self, transactions: List[dict]) -> str:
        """AI-прогноз витрат на основі останніх транзакцій."""
        if not self.enabled:
            return "🤖 Прогноз зараз недоступний."

        transactions_str = self._format_transactions(transactions[-30:])
        prompt = f"""
        Є історія останніх витрат користувача. Побудуй короткий прогноз на
        найближчий тиждень і поради, як утримати бюджет у межах плану.

        {transactions_str}

        Структура відповіді:
        1. Ймовірний обсяг витрат.
        2. Категорії, які зростатимуть найшвидше.
        3. Що варто контролювати або обмежити.
        """

        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            return re.sub(r"[*#]+", "", response.text).strip()
        except Exception as exc:
            logger.error("Prediction error: %s", exc)
            return "⚠️ Наразі не можу спрогнозувати витрати."

    def _format_transactions(self, transactions: List[dict]) -> str:
        """Готує транзакції у форматі: date | amount currency | category | note."""
        lines = []
        for item in transactions:
            date = item.get("date", "")
            amount = self._format_amount(item.get("amount"))
            currency = item.get("currency") or config.DEFAULT_CURRENCY
            category = item.get("category", "")
            note = (item.get("note") or "").strip()
            lines.append(f"{date} | {amount} {currency} | {category} | {note}")
        return "\n".join(lines)

    def _build_analysis_prompt(
        self, transactions_str: str, context: Dict[str, Any]
    ) -> str:
        """Будує адаптований промпт для фінансового аналізу."""
        aggregates = context.get("aggregates", {})
        currency = context.get("currency", config.DEFAULT_CURRENCY)

        def fmt(value, suffix=""):
            if value is None:
                return "-"
            try:
                number = float(value)
            except (TypeError, ValueError):
                return str(value)
            formatted = f"{number:.2f}".rstrip("0").rstrip(".")
            return f"{formatted}{suffix}"

        return f"""
        Ти — досвідчений фінансовий аналітик та консультант. 
        Проаналізуй транзакції українського користувача за конкретний період 
        і дай структурований, чіткий та максимально корисний аналіз.

        Це охоплює період: {context.get('period_start')} → {context.get('period_end')}
        {context.get('period_note')}

        Ось формат транзакцій (табличні рядки):
        date | amount currency | category | note

        Дані:
        Період: {context.get('period_start')} → {context.get('period_end')}
        Моя валюта: {currency}
        Кількість транзакцій: {context.get('transactions_count')}
        Нижче наведені останні {context.get('limited_count')} транзакцій за період:

        {transactions_str}

        Додаткові агрегати:
        - Загальні витрати: {fmt(aggregates.get('total_expenses'))} {currency}
        - Загальні доходи: {fmt(aggregates.get('total_income'))} {currency}
        - Співвідношення доходи/витрати: {fmt(aggregates.get('income_expense_ratio'))}
        - Savings rate: {fmt(aggregates.get('savings_rate'), '%')}
        - Середні витрати на день: {fmt(aggregates.get('average_daily_spend'))} {currency}
        - Середні витрати на місяць: {fmt(aggregates.get('average_monthly_spend'))} {currency}

        Категорії:
        - Топ категорії витрат:
        {context.get('top_categories')}

        Цілі:
        {context.get('goals_summary')}

        Бюджети:
        {context.get('budgets_summary')}

        Підписки:
        {context.get('subscriptions_summary')}

        Сформуй відповідь у структурованому вигляді:

        1) **Загальна картина**
           – короткий висновок у 2–3 реченнях з цифрами.

        2) **Ключові спостереження**
           – топ витрат, повторювані патерни, ризикові категорії.

        3) **Аномалії / проблеми**
           – що виглядає нетипово або завелике.

        4) **Конкретні рекомендації**
           – 5–7 порад з цифрами:
             • скільки можна економити,
             • що оптимізувати,
             • які категорії скоротити,
             • які цілі досягти швидше.

        5) **Фінальне резюме у 2 реченнях**
           – мотивуюче, чітке, практичне.

        Обов’язково будь лаконічним, структурованим та професійним. 
        Не повторюй зайвих даних. 
        Говори українською.
        """

    @staticmethod
    def _format_amount(value: Any) -> str:
        try:
            number = float(value or 0)
        except (TypeError, ValueError):
            return "0"
        formatted = f"{number:.2f}".rstrip("0").rstrip(".")
        return formatted or "0"


# Singleton
ai_service = AIService()
