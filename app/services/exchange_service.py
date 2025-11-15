# ============================================
# FILE: app/services/exchange_service.py
# ============================================
"""
Сервіс курсів валют (ПриватБанк).
"""

import asyncio
import logging
import time
from typing import Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)


class ExchangeService:
    """Отримує та кешує курси валют з ПриватБанку."""

    PRIVAT_API_URL = "https://api.privatbank.ua/p24api/pubinfo?json&exchange&coursid=11"

    def __init__(self, ttl_seconds: int = 600):
        self._ttl = ttl_seconds
        self._rates: Dict[str, float] = {}
        self._last_fetch: float = 0.0
        self._lock = asyncio.Lock()

    async def convert_to_uah(self, amount: float, currency: str) -> Optional[float]:
        """Конвертує передану суму у гривні, використовуючи поточний курс."""
        if amount is None:
            return None
        currency = (currency or "").upper()
        if not currency:
            return None
        rate = await self.get_rate(currency)
        if rate is None:
            return None
        return amount * rate

    async def get_rate(self, currency: str) -> Optional[float]:
        """Повертає курс продажу для вказаної валюти відносно гривні."""
        currency = (currency or "").upper()
        if not currency:
            return None
        if currency == "UAH":
            return 1.0

        await self._ensure_rates()
        return self._rates.get(currency)

    async def _ensure_rates(self):
        now = time.time()
        if self._rates and (now - self._last_fetch) < self._ttl:
            return

        async with self._lock:
            # повторна перевірка, поки ми чекали на lock
            now = time.time()
            if self._rates and (now - self._last_fetch) < self._ttl:
                return

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(self.PRIVAT_API_URL, timeout=10) as resp:
                        resp.raise_for_status()
                        payload = await resp.json()
            except Exception as exc:
                logger.warning("Не вдалося отримати курс ПриватБанку: %s", exc)
                return

            rates = {}
            for item in payload:
                code = (item.get("ccy") or "").upper()
                if not code:
                    continue
                try:
                    rate = float(item.get("sale"))
                except (TypeError, ValueError):
                    continue
                if rate <= 0:
                    continue
                rates[code] = rate

            if rates:
                self._rates = rates
                self._last_fetch = time.time()
                logger.info("Курси ПриватБанку оновлено: %s", list(rates.keys()))


# Singleton
exchange_service = ExchangeService()
