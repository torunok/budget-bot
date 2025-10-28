# ============================================
# Dockerfile
# ============================================

# Python 3.11 slim image
FROM python:3.11-slim

# Metadata
LABEL maintainer="your_email@example.com"
LABEL description="Budget Telegram Bot"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (для кешування шарів)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose port (Render встановить свій)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')"

# Run application
CMD ["python", "main.py"]