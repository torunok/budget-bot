# 🚀 Інструкція з налаштування проекту

## 📁 Структура файлів

Всі файли створені як окремі артефакти. Ось повний список:

### Основні файли (Core)

1. `app/main.py` - Точка входу
2. `app/config/settings.py` - Конфігурація
3. `app/core/bot.py` - Бот
4. `app/core/states.py` - FSM стани

### Клавіатури (Keyboards)

5. `app/keyboards/reply.py`
6. `app/keyboards/inline.py`

### Сервіси (Services)

7. `app/services/sheets_service.py` - Google Sheets
8. `app/services/ai_service.py` - Gemini AI
9. `app/services/export_service.py` - Експорт

### Утиліти (Utils)

10. `app/utils/validators.py`
11. `app/utils/formatters.py`
12. `app/utils/helpers.py`

### Middleware

13. `app/middlewares/__init__.py`
14. `app/middlewares/logging_middleware.py`
15. `app/middlewares/throttling_middleware.py`

### Хендлери (Handlers)

16. `app/handlers/__init__.py`
17. `app/handlers/start.py`
18. `app/handlers/transactions.py`
19. `app/handlers/statistics.py`
20. `app/handlers/ai_analysis.py`
21. `app/handlers/subscriptions.py`
22. `app/handlers/settings.py`
23. `app/handlers/support.py`

### Планувальник (Scheduler)

24. `app/scheduler/tasks.py`

### **init**.py файли

25. `app/__init__.py`
26. `app/config/__init__.py`
27. `app/core/__init__.py`
28. `app/services/__init__.py`
29. `app/keyboards/__init__.py`
30. `app/utils/__init__.py`
31. `app/scheduler/__init__.py`

### Тести (Tests)

32. `tests/__init__.py`
33. `tests/test_validators.py`
34. `tests/test_formatters.py`
35. `pytest.ini`

### Конфігурація

36. `requirements.txt`
37. `.env.example`
38. `.gitignore`
39. `render.yaml`
40. `Dockerfile`
41. `Makefile`
42. `README.md`

---

## 📋 Покрокова інструкція

### Крок 1: Створення структури папок

```bash
mkdir -p budget_bot/app/{config,core,handlers,services,keyboards,utils,middlewares,scheduler}
mkdir -p budget_bot/tests
mkdir -p budget_bot/logs
cd budget_bot
```

### Крок 2: Копіювання файлів

Скопіюй кожен артефакт у відповідний файл згідно зі структурою вище.

**Наприклад:**

- Артефакт "app/main.py" → `app/main.py`
- Артефакт "app/config/settings.py" → `app/config/settings.py`
- І так далі...

### Крок 3: Створення порожніх **init**.py

Для пакетів, які ще не мають **init**.py, створи порожні файли:

```bash
touch app/__init__.py
touch app/config/__init__.py
touch app/core/__init__.py
touch app/services/__init__.py
touch app/keyboards/__init__.py
touch app/utils/__init__.py
touch app/middlewares/__init__.py
touch app/scheduler/__init__.py
touch app/handlers/__init__.py
touch tests/__init__.py
```

Або використай готовий артефакт "**init**.py файли".

### Крок 4: Налаштування середовища

1. **Створи віртуальне середовище:**

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# або
venv\Scripts\activate  # Windows
```

2. **Встанови залежності:**

```bash
pip install -r requirements.txt
```

3. **Налаштуй .env:**

```bash
cp .env.example .env
# Відредагуй .env та додай свої токени
```

4. **Додай service_account.json:**

- Завантаж з Google Cloud Console
- Помісти в корінь проекту
- **НЕ коміть в git!**

### Крок 5: Тестування локально

```bash
# Запусти бота
python -m app.main

# Або використай Makefile
make run
```

### Крок 6: Запуск тестів

```bash
# Всі тести
pytest

# З coverage
pytest --cov=app

# Або через Makefile
make test
```

---

## 🔧 Налаштування для Render.com

### 1. Підготовка репозиторію

```bash
git init
git add .
git commit -m "Initial commit: Budget Bot v1.0"
git remote add origin https://github.com/YOUR_USERNAME/budget-bot.git
git push -u origin main
```

### 2. Створення сервісу на Render

1. Зайди на [render.com](https://render.com)
2. New → Web Service
3. Connect GitHub repository
4. Render автоматично виявить `render.yaml`

### 3. Налаштування змінних оточення

В Render Dashboard додай:

```
BOT_TOKEN=your_bot_token
WEBHOOK_SECRET_TOKEN=random_secret_string
BASE_WEBHOOK_URL=https://your-app-name.onrender.com
SPREADSHEET_ID=your_spreadsheet_id
GEMINI_API_KEY=your_gemini_key (optional)
ENVIRONMENT=production
```

### 4. Завантаження service_account.json

**Через Render Dashboard:**

- Settings → Secret Files
- Add Secret File
- Filename: `service_account.json`
- Вставити вміст файлу

**Або через CLI:**

```bash
render files upload service_account.json --service YOUR_SERVICE_ID
```

### 5. Deploy

Render автоматично задеплоїть при push в main.

---

## 🎯 Перевірка роботи

1. **Health check:**

```bash
curl https://your-app.onrender.com/health
# Має повернути: OK
```

2. **Webhook info:**

```bash
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
```

3. **Перевірка логів:**

```bash
# Через CLI
render logs --tail

# Або в Dashboard → Logs
```

---

## 📊 Cronitor для пінгів

Щоб бот не "засинав" на free plan:

1. Зареєструйся на [cronitor.io](https://cronitor.io)
2. New Monitor → HTTP
3. URL: `https://your-app.onrender.com/health`
4. Schedule: Every 5 minutes
5. Save

Альтернатива: [UptimeRobot](https://uptimerobot.com)

---

## 🐛 Troubleshooting

### Бот не відповідає

```bash
# Перевір webhook
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo

# Перевір логи
render logs --tail
```

### Помилка з Google Sheets

- Перевір `service_account.json`
- Перевір права доступу в Google Sheets
- Перевір `SPREADSHEET_ID`

### Import помилки

- Перевір структуру папок
- Перевір всі `__init__.py` файли
- Переконайся, що запускаєш як модуль: `python -m app.main`

---

## ✅ Checklist

- [ ] Створено всі папки
- [ ] Скопійовано всі файли
- [ ] Створено `.env` з токенами
- [ ] Додано `service_account.json`
- [ ] Встановлено залежності
- [ ] Протестовано локально
- [ ] Створено GitHub репозиторій
- [ ] Налаштовано Render.com
- [ ] Додано змінні оточення
- [ ] Завантажено service_account.json
- [ ] Задеплоєно
- [ ] Налаштовано Cronitor
- [ ] Протестовано в Telegram

---

## 🎉 Готово!

Твій бот готовий до роботи!

Якщо виникнуть питання:

- 📚 Дивись `README.md`
- 🐛 Створи Issue на GitHub
- 💬 Напиши в підтримку

**Успіхів! 🚀**
