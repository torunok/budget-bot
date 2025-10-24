# ============================================
# FILE: app/config/settings.py
# ============================================
"""
Конфігурація додатку
Всі налаштування та змінні оточення
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Завантаження змінних оточення
load_dotenv()

# Базові шляхи
BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Налаштування логування
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOGS_DIR / "bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class Config:
    """Основна конфігурація додатку"""
    
    # Telegram Bot
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    WEBHOOK_SECRET_TOKEN = os.getenv("WEBHOOK_SECRET_TOKEN")
    
    # Webhook налаштування
    WEB_SERVER_HOST = "0.0.0.0"
    WEB_SERVER_PORT = int(os.getenv("PORT", 8080))
    WEBHOOK_PATH = "/webhook"
    BASE_WEBHOOK_URL = os.getenv("BASE_WEBHOOK_URL")
    
    @property
    def WEBHOOK_URL(self):
        return f"{self.BASE_WEBHOOK_URL}{self.WEBHOOK_PATH}"
    
    # Google Sheets
    SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
    # >>> ЗМІНА 1: Нова змінна для вмісту JSON-файлу
    GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    
    # AI сервіси
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    # Redis (для кешування)
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    CACHE_TTL = int(os.getenv("CACHE_TTL", 3600))  # 1 година
    
    # Sentry (моніторинг помилок)
    SENTRY_DSN = os.getenv("SENTRY_DSN")
    SENTRY_ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
    
    # Налаштування додатку
    DEFAULT_CATEGORY = "Інше"
    DEFAULT_CURRENCY = "UAH"
    SUPPORTED_CURRENCIES = ["UAH", "USD", "EUR", "CRYPTO"]
    
    # Налаштування нагадувань
    REMINDER_TIMES = [
        {"hour": 9, "minute": 0},   # Ранкове нагадування
        {"hour": 13, "minute": 0},  # Обідня перевірка
        {"hour": 20, "minute": 0}   # Вечірнє нагадування
    ]
    
    # Обмеження
    MAX_MESSAGE_LENGTH = 4096
    MAX_TRANSACTIONS_DISPLAY = 10
    RATE_LIMIT_MESSAGES = 30  # повідомлень на хвилину
    
    # Функції (увімкнути/вимкнути)
    ENABLE_AI_ANALYSIS = True
    ENABLE_EXPORT = True
    ENABLE_ADVANCED_ANALYTICS = True
    ENABLE_FAMILY_BUDGETS = False  # Майбутня функція
    
    def validate(self):
        """Перевірка наявності обов'язкових змінних"""
        required_vars = [
            "BOT_TOKEN",
            "WEBHOOK_SECRET_TOKEN",
            "SPREADSHEET_ID",
            "BASE_WEBHOOK_URL",
            "GOOGLE_SERVICE_ACCOUNT_JSON" # >>> ЗМІНА 3: Додаємо перевірку на нову змінну
        ]
        
        missing = []
        for var in required_vars:
            if not getattr(self, var):
                missing.append(var)
        
        if missing:
            logger.error(f"Missing required environment variables: {', '.join(missing)}")
            sys.exit(1)
        
        logger.info("Configuration validated successfully")


class DevelopmentConfig(Config):
    """Конфігурація для розробки"""
    ENABLE_FAMILY_BUDGETS = True  # Тестування нових функцій
    LOG_LEVEL = "DEBUG"


class ProductionConfig(Config):
    """Конфігурація для продакшену"""
    LOG_LEVEL = "INFO"


# Вибір конфігурації залежно від оточення
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")

if ENVIRONMENT == "development":
    config = DevelopmentConfig()
else:
    config = ProductionConfig()

# Валідація конфігурації при імпорті
config.validate()

# Ініціалізація Sentry для моніторингу помилок
if config.SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=config.SENTRY_DSN,
            environment=config.SENTRY_ENVIRONMENT,
            traces_sample_rate=0.1,
        )
        logger.info("Sentry initialized successfully")
    except ImportError:
        logger.warning("Sentry SDK not installed, skipping initialization")


# Експорт для зручності
__all__ = ['config', 'logger']