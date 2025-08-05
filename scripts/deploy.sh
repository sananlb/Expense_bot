#!/bin/bash
# Скрипт деплоя Expense Bot на сервер

set -e  # Останавливаемся при ошибках

echo "======================================"
echo "  Expense Bot Deployment Script"
echo "======================================"

# Переменные
PROJECT_DIR="/home/deploy/expense_bot"
VENV_PATH="$PROJECT_DIR/venv"
SERVICE_NAME="expense-bot"

# Функция для вывода сообщений
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Проверка, что мы в правильной директории
if [ ! -f "$PROJECT_DIR/manage.py" ]; then
    log "Ошибка: Не найден manage.py. Убедитесь, что вы в директории проекта."
    exit 1
fi

cd "$PROJECT_DIR"

# 1. Остановка бота
log "Остановка бота..."
sudo systemctl stop $SERVICE_NAME || true

# 2. Получение обновлений из git
log "Получение обновлений из git..."
git pull origin master

# 3. Активация виртуального окружения
log "Активация виртуального окружения..."
source "$VENV_PATH/bin/activate"

# 4. Обновление зависимостей
log "Обновление зависимостей..."
pip install --upgrade pip
pip install -r requirements.txt

# 5. Применение миграций
log "Применение миграций базы данных..."
python manage.py migrate --noinput

# 6. Сбор статических файлов
log "Сбор статических файлов..."
python manage.py collectstatic --noinput

# 7. Проверка конфигурации
log "Проверка конфигурации Django..."
python manage.py check

# 8. Создание резервной копии базы данных
log "Создание резервной копии базы данных..."
./scripts/backup_db.sh

# 9. Запуск бота
log "Запуск бота..."
sudo systemctl start $SERVICE_NAME

# 10. Проверка статуса
sleep 3
if sudo systemctl is-active --quiet $SERVICE_NAME; then
    log "✅ Бот успешно запущен!"
else
    log "❌ Ошибка запуска бота. Проверьте логи: sudo journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi

log "======================================"
log "  Деплой завершён успешно!"
log "======================================"