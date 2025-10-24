# ============================================
# FILE: app/services/ai_service.py
# ============================================
"""
Сервіс для роботи з AI (Gemini)
"""

import asyncio
import logging
import re
from typing import List
from google import generativeai as genai

from app.config.settings import config

logger = logging.getLogger(__name__)


class AIService:
    """Сервіс для AI аналізу"""
    
    def __init__(self):
        if config.GEMINI_API_KEY and config.ENABLE_AI_ANALYSIS:
            try:
                genai.configure(api_key=config.GEMINI_API_KEY)
                self.model = genai.GenerativeModel("gemini-1.5-pro-latest")
                self.enabled = True
                logger.info("✅ Gemini AI initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Gemini: {e}")
                self.enabled = False
        else:
            self.enabled = False
            logger.warning("AI analysis is disabled")
    
    async def analyze_finances(self, transactions: List[dict]) -> str:
        """Аналізує фінанси користувача"""
        if not self.enabled:
            return "🤖 AI-аналіз тимчасово недоступний."
        
        # Формуємо дані для аналізу
        transactions_str = self._format_transactions(transactions)
        
        prompt = self._build_analysis_prompt(transactions_str)
        
        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt
            )
            
            # Очищаємо від markdown форматування
            clean_text = re.sub(r"[*#]+", "", response.text)
            return clean_text
            
        except Exception as e:
            logger.error(f"AI analysis error: {e}")
            return "Вибачте, виникла помилка при аналізі. Спробуйте пізніше."
    
    async def get_budget_recommendations(self, transactions: List[dict], income: float) -> str:
        """Отримує рекомендації по бюджету"""
        if not self.enabled:
            return "🤖 AI-рекомендації недоступні."
        
        transactions_str = self._format_transactions(transactions)
        
        prompt = f"""
        Проаналізуй фінансову ситуацію користувача та дай конкретні рекомендації.
        
        Місячний дохід: {income} UAH
        
        Транзакції:
        {transactions_str}
        
        Дай короткі, конкретні рекомендації:
        1. Оптимальний розподіл бюджету по категоріях
        2. На чому можна заощадити
        3. Скільки відкладати щомісяця
        4. Попередження про ризики
        
        Будь стислим та практичним. Максимум 500 слів.
        """
        
        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt
            )
            return re.sub(r"[*#]+", "", response.text)
        except Exception as e:
            logger.error(f"Recommendations error: {e}")
            return "Помилка отримання рекомендацій."
    
    async def predict_expenses(self, transactions: List[dict]) -> str:
        """Прогнозує майбутні витрати"""
        if not self.enabled:
            return "Прогноз недоступний."
        
        transactions_str = self._format_transactions(transactions[-30:])  # Last 30 transactions
        
        prompt = f"""
        На основі історії транзакцій за останній місяць, зроби прогноз витрат на наступний місяць.
        
        {transactions_str}
        
        Вкажи:
        1. Очікувані витрати по категоріях
        2. Загальна сума витрат
        3. Рекомендації для оптимізації
        
        Будь коротким та конкретним.
        """
        
        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt
            )
            return re.sub(r"[*#]+", "", response.text)
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return "Помилка прогнозування."
    
    def _format_transactions(self, transactions: List[dict]) -> str:
        """Форматує транзакції для AI"""
        lines = []
        for t in transactions:
            date = t.get('date', '')
            amount = t.get('amount', 0)
            category = t.get('category', '')
            note = t.get('note', '')
            lines.append(f"{date} | {amount} UAH | {category} | {note}")
        return "\n".join(lines)
    
    def _build_analysis_prompt(self, transactions_str: str) -> str:
        """Будує промпт для аналізу"""
        return f"""
        Ти - досвідчений фінансовий консультант. Проаналізуй фінанси користувача максимально детально.
        
        Транзакції:
        {transactions_str}
        
        Надай професійний аналіз:
        
        📊 ЗАГАЛЬНА КАРТИНА
        - Співвідношення доходів/витрат
        - Основні категорії витрат
        - Фінансова дисципліна
        
        💡 ГОЛОВНІ ВИСНОВКИ
        - Слабкі місця бюджету
        - Неефективні витрати
        - Можливості для оптимізації
        
        🎯 КОНКРЕТНІ РЕКОМЕНДАЦІЇ
        - Де економити (з цифрами)
        - Як перерозподілити бюджет
        - Цілі заощаджень
        
        ⚠️ ПОПЕРЕДЖЕННЯ
        - Фінансові ризики
        - Шкідливі звички витрат
        
        Пиши структуровано, лаконічно, з конкретними цифрами та порадами.
        Без згадки хто ти - просто роби свою роботу професійно.
        """


# Singleton
ai_service = AIService()