FROM python:3.11-slim

WORKDIR /app

# Встановлюємо залежності системи
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копіюємо requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо код
COPY . .

# Створюємо папку для логів
RUN mkdir -p logs

# Порт
EXPOSE 8080

# Запуск
CMD ["python", "-m", "app.main"]