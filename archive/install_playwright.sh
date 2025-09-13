#!/bin/bash

# Скрипт установки Playwright и его зависимостей

echo "Installing Playwright dependencies..."

# Активируем виртуальное окружение
source venv/bin/activate

# Устанавливаем системные зависимости для Playwright
echo "Installing system dependencies..."
apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libcairo2 \
    libgbm-dev \
    libasound2 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libxkbcommon0 \
    libgtk-3-0 \
    libxshmfence1 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libx11-6 \
    libxcb1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libxdamage1 \
    libxcomposite1 \
    libxkbcommon0 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0

# Устанавливаем браузеры Playwright
echo "Installing Playwright browsers..."
playwright install chromium
playwright install-deps chromium

echo "Playwright installation complete!"