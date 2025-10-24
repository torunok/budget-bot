# 💰 Budget Telegram Bot

Професійний телеграм-бот для ведення особистого бюджету з AI-аналізом та розширеною аналітикою.

## 🚀 Функції

- ✅ Облік витрат та доходів
- ✅ Статистика за різні періоди
- ✅ AI-аналіз фінансів (Gemini)
- ✅ Управління підписками
- ✅ Нагадування про внесення даних
- ✅ Експорт у CSV/Excel/PDF
- ✅ Мультивалютність
- ✅ Графіки та візуалізація

## 📦 Технології

- Python 3.11+
- aiogram 3.4
- Google Sheets API
- Gemini AI
- APScheduler
- pandas, matplotlib, reportlab

## 🛠️ Установка

### Локально

1. Клонуйте репозиторій:

```bash
git clone https://github.com/yourusername/budget-bot.git
cd budget-bot
```

2. Створіть віртуальне середовище:

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# або
venv\Scripts\activate  # Windows
```

3. Встановіть залежності:

```bash
pip install -r requirements.txt
```

4. Налаштуйте змінні оточення:

```bash
cp .env.example .env
# Відредагуйте .env файл
```

5. Додайте `service_account.json` для Google Sheets

6. Запустіть бота:

```bash
python -m app.main
```

### Деплой на Render.com

1. Підключіть GitHub репозиторій до Render
2. Використовуйте `render.yaml` для автоматичного деплою
3. Додайте всі змінні оточення в Dashboard
4. Завантажте `service_account.json` через Render CLI або вручну

## 📁 Структура проекту

```
budget_bot/
├── app/
│   ├── config/          # Конфігурація
│   ├── core/            # Ядро бота
│   ├── handlers/        # Обробники команд
│   ├── services/        # Бізнес-логіка
│   ├── keyboards/       # Клавіатури
│   ├── utils/           # Утиліти
│   ├── middlewares/     # Middleware
│   └── scheduler/       # Заплановані задачі
├── logs/                # Логи
├── requirements.txt
├── render.yaml
└── README.md
```

## 🔧 Конфігурація

Всі налаштування в `app/config/settings.py`

## 📝 Ліцензія

MIT License

## 👨‍💻 Автор

Your Name - [@Torunok](https://t.me/Torunok)
