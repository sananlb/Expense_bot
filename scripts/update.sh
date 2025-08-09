#!/bin/bash

# Скрипт для обновления ExpenseBot с GitHub
# Использование: ./scripts/update.sh

set -e  # Остановиться при ошибке

echo "🚀 Обновление ExpenseBot..."

# Переходим в директорию проекта
cd ~/expense_bot

# Сохраняем локальные изменения в .env если есть
if [ -f .env ]; then
    cp .env .env.backup
    echo "📦 Создана резервная копия .env"
fi

# Получаем обновления из GitHub
echo "📥 Загрузка обновлений из GitHub..."
git pull

# Восстанавливаем .env из бэкапа
if [ -f .env.backup ]; then
    cp .env.backup .env
    echo "✅ Восстановлен файл .env"
fi

# Проверяем и настраиваем nginx (только если конфиг изменился)
if [ -f nginx/expensebot.conf ]; then
    # Проверяем, отличается ли конфиг от установленного
    if ! cmp -s nginx/expensebot.conf /etc/nginx/sites-available/expensebot 2>/dev/null; then
        echo "🔧 Обновление конфигурации nginx..."
        sudo cp nginx/expensebot.conf /etc/nginx/sites-available/expensebot
        sudo ln -sf /etc/nginx/sites-available/expensebot /etc/nginx/sites-enabled/
        sudo nginx -t && sudo systemctl reload nginx
        echo "✅ Nginx обновлен"
    else
        echo "✅ Конфигурация nginx актуальна"
    fi
fi

# Останавливаем контейнеры
echo "🛑 Остановка контейнеров..."
docker-compose down

# Пересобираем образы если изменился Dockerfile или requirements
echo "🔨 Проверка необходимости пересборки..."
if git diff HEAD~1 HEAD --name-only | grep -E "(Dockerfile|requirements\.txt|package\.json)" > /dev/null; then
    echo "📦 Пересборка Docker образов..."
    docker-compose build
fi

# Запускаем контейнеры
echo "🚀 Запуск контейнеров..."
docker-compose up -d

# Ждем запуска
echo "⏳ Ожидание запуска сервисов..."
sleep 10

# Проверяем статус
echo "📊 Проверка статуса..."
docker-compose ps

# Проверяем доступность админки
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/admin/ | grep -q "302\|200"; then
    echo "✅ Админка доступна: http://expensebot.duckdns.org/admin/"
else
    echo "⚠️  Админка может быть недоступна, проверьте логи:"
    echo "   docker logs expense_bot_web"
fi

echo ""
echo "✨ Обновление завершено!"
echo ""
echo "📝 Полезные команды:"
echo "  docker logs expense_bot_web -f     # Логи веб-сервера"
echo "  docker logs expense_bot_app -f     # Логи бота"
echo "  docker-compose ps                  # Статус контейнеров"
echo "  docker exec -it expense_bot_web python manage.py createsuperuser  # Создать админа"