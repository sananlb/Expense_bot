#!/bin/bash

# Скрипт автоматической настройки сервера для expense_bot

echo "=== Setting up Expense Bot Server ==="

# Обновляем код из репозитория
echo "1. Pulling latest code from GitHub..."
git pull

# Активируем виртуальное окружение
echo "2. Activating virtual environment..."
source venv/bin/activate

# Обновляем Python зависимости
echo "3. Installing Python dependencies..."
pip install -r requirements.txt

# Проверяем и устанавливаем системные зависимости для Playwright
echo "4. Checking system dependencies for Playwright..."

# Список необходимых пакетов
PACKAGES="libpango-1.0-0 libcairo2 libgbm-dev libasound2 libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libxkbcommon0 libgtk-3-0"

# Проверяем какие пакеты отсутствуют
MISSING_PACKAGES=""
for package in $PACKAGES; do
    if ! dpkg -l | grep -q "^ii  $package"; then
        MISSING_PACKAGES="$MISSING_PACKAGES $package"
    fi
done

# Устанавливаем недостающие пакеты
if [ -n "$MISSING_PACKAGES" ]; then
    echo "Installing missing packages:$MISSING_PACKAGES"
    sudo apt-get update
    sudo apt-get install -y $MISSING_PACKAGES
else
    echo "All system dependencies are already installed."
fi

# Устанавливаем браузеры Playwright
echo "5. Installing Playwright browsers..."
playwright install chromium

# Применяем миграции Django
echo "6. Applying Django migrations..."
python manage.py migrate

echo "=== Setup complete! ==="
echo "To run the bot, use: python run_bot.py"