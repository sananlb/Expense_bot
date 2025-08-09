#!/bin/bash

# Скрипт первоначальной установки ExpenseBot на сервере
# Запускать один раз после клонирования репозитория

set -e  # Остановиться при ошибке

echo "🚀 Установка ExpenseBot..."

# Проверяем наличие необходимых программ
command -v docker >/dev/null 2>&1 || { echo "❌ Docker не установлен"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "❌ Docker Compose не установлен"; exit 1; }
command -v nginx >/dev/null 2>&1 || { echo "⚠️  Nginx не установлен, устанавливаем..."; sudo apt-get update && sudo apt-get install -y nginx; }

# Переходим в директорию проекта
cd ~/expense_bot

# Создаем .env из примера если не существует
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "📝 Создан файл .env из примера"
        echo "⚠️  ВАЖНО: Отредактируйте файл .env и добавьте ваши настройки!"
        echo "   nano .env"
    else
        echo "❌ Файл .env.example не найден"
        exit 1
    fi
fi

# Настраиваем nginx
if [ -f nginx/expensebot.conf ]; then
    echo "🔧 Настройка nginx..."
    sudo cp nginx/expensebot.conf /etc/nginx/sites-available/expensebot
    sudo ln -sf /etc/nginx/sites-available/expensebot /etc/nginx/sites-enabled/
    sudo rm -f /etc/nginx/sites-enabled/default
    sudo nginx -t && sudo systemctl reload nginx
    echo "✅ Nginx настроен"
fi

# Создаем необходимые директории
mkdir -p logs media staticfiles

# Собираем и запускаем контейнеры
echo "🔨 Сборка Docker образов..."
docker-compose build

echo "🚀 Запуск контейнеров..."
docker-compose up -d

# Ждем запуска
echo "⏳ Ожидание запуска сервисов..."
sleep 15

# Создаем суперпользователя
echo ""
echo "👤 Создание суперпользователя для админки..."
docker exec -it expense_bot_web python manage.py createsuperuser

# Проверяем статус
echo ""
echo "📊 Статус контейнеров:"
docker-compose ps

echo ""
echo "✨ Установка завершена!"
echo ""
echo "🌐 Доступные адреса:"
echo "  Админка: http://expensebot.duckdns.org/admin/"
echo "  Альтернативный: http://80.66.87.178/admin/"
echo ""
echo "📝 Полезные команды:"
echo "  ./scripts/update.sh                # Обновить из GitHub"
echo "  docker-compose logs -f             # Смотреть все логи"
echo "  docker logs expense_bot_web -f     # Логи веб-сервера"
echo "  docker logs expense_bot_app -f     # Логи бота"