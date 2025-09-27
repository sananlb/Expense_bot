#!/bin/bash
# Первичная настройка резервного сервера для expense_bot
# Запускать на резервном сервере (45.95.2.84) один раз

set -e

echo "================================================"
echo "Первичная настройка резервного сервера"
echo "================================================"

# 1. Проверка Docker
echo "→ Проверка Docker..."
if ! command -v docker &> /dev/null; then
    echo "  ✗ Docker не установлен. Устанавливаем..."
    apt-get update
    apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io
    echo "  ✓ Docker установлен"
else
    echo "  ✓ Docker уже установлен: $(docker --version)"
fi

# 2. Проверка docker-compose
echo "→ Проверка docker-compose..."
if ! command -v docker-compose &> /dev/null; then
    echo "  ✗ docker-compose не установлен. Устанавливаем..."
    curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo "  ✓ docker-compose установлен"
else
    echo "  ✓ docker-compose уже установлен: $(docker-compose --version)"
fi

# 3. Создание необходимых директорий
echo "→ Создание директорий..."
mkdir -p /root/expense_bot_backups
mkdir -p /opt/expense_bot
mkdir -p /root/server_scripts/expense_bot
echo "  ✓ Директории созданы:"
echo "    - /root/expense_bot_backups  (для резервных копий)"
echo "    - /opt/expense_bot           (для проекта)"
echo "    - /root/server_scripts       (для скриптов)"

# 4. Создание скрипта развертывания
echo "→ Создание скрипта deploy_on_reserve.sh..."
cat > /root/server_scripts/expense_bot/deploy_on_reserve.sh << 'DEPLOY_SCRIPT'
#!/bin/bash
# Скрипт развертывания expense_bot на резервном сервере
# Запускать на резервном сервере (45.95.2.84)

set -e

# Конфигурация
BACKUP_DIR="/root/expense_bot_backups"
PROJECT_DIR="/opt/expense_bot"
TIMESTAMP="$1"

# Флаги управления
RESTORE_DB=false
START_SERVICES=false
FORCE_REBUILD=false

# Функция помощи
show_help() {
    echo "Использование: $0 <timestamp|latest> [опции]"
    echo ""
    echo "Опции:"
    echo "  --restore-db     Восстановить базу данных из дампа"
    echo "  --start          Запустить все сервисы после развертывания"
    echo "  --force-rebuild  Принудительно пересобрать Docker образы"
    echo "  --help           Показать эту справку"
    echo ""
    echo "Примеры:"
    echo "  $0 latest                    # Только обновить код"
    echo "  $0 latest --restore-db       # Обновить код и БД"
    echo "  $0 latest --start            # Обновить код и запустить"
    echo "  $0 latest --restore-db --start # Полное развертывание"
    exit 0
}

# Парсинг аргументов
if [ -z "$1" ] || [ "$1" == "--help" ]; then
    show_help
fi

shift # Удаляем первый аргумент (timestamp)
while [[ $# -gt 0 ]]; do
    case $1 in
        --restore-db)
            RESTORE_DB=true
            shift
            ;;
        --start)
            START_SERVICES=true
            shift
            ;;
        --force-rebuild)
            FORCE_REBUILD=true
            shift
            ;;
        *)
            echo "Неизвестная опция: $1"
            show_help
            ;;
    esac
done

echo "================================================"
echo "Развертывание ExpenseBot на резервном сервере"
echo "Версия: ${TIMESTAMP}"
echo "Восстановление БД: ${RESTORE_DB}"
echo "Запуск сервисов: ${START_SERVICES}"
echo "================================================"

# 1. Проверка файлов
echo "→ Проверка резервной копии..."
ARCHIVE_FILE="${BACKUP_DIR}/expense_bot_${TIMESTAMP}.tar.gz"
SQL_FILE="${BACKUP_DIR}/expense_bot_${TIMESTAMP}.sql"

# Если указан latest, используем последние файлы
if [ "$TIMESTAMP" == "latest" ]; then
    ARCHIVE_FILE="${BACKUP_DIR}/expense_bot_latest.tar.gz"
    SQL_FILE="${BACKUP_DIR}/expense_bot_latest.sql"
fi

if [ ! -f "$ARCHIVE_FILE" ]; then
    echo "  ✗ Архив не найден: $ARCHIVE_FILE"
    exit 1
fi
echo "  ✓ Архив найден"

if [ "$RESTORE_DB" == "true" ] && [ ! -f "$SQL_FILE" ]; then
    echo "  ✗ SQL дамп не найден: $SQL_FILE"
    exit 1
fi

# 2. Остановка сервисов (если запущены)
if [ -d "$PROJECT_DIR" ]; then
    echo "→ Остановка существующих контейнеров..."
    cd $PROJECT_DIR
    docker-compose down 2>/dev/null || true
    cd /
fi

# 3. Backup старой версии (если есть)
if [ -d "$PROJECT_DIR" ]; then
    echo "→ Архивирование предыдущей версии..."
    mv $PROJECT_DIR ${PROJECT_DIR}_backup_$(date +%Y%m%d_%H%M%S)
    echo "  ✓ Старая версия сохранена"
fi

# 4. Распаковка новой версии
echo "→ Распаковка проекта..."
mkdir -p /opt
cd /opt
tar -xzf $ARCHIVE_FILE
echo "  ✓ Проект распакован в $PROJECT_DIR"

# 5. Проверка .env
cd $PROJECT_DIR
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  ВНИМАНИЕ: Файл .env не найден!"
    echo "   Создайте файл .env с необходимыми переменными:"
    echo "   - BOT_TOKEN"
    echo "   - DB_NAME, DB_USER, DB_PASSWORD"
    echo "   - REDIS_PASSWORD"
    echo "   - ADMIN_TELEGRAM_ID"
    echo ""
    if [ "$START_SERVICES" == "true" ]; then
        echo "Отмена запуска из-за отсутствия .env"
        exit 1
    fi
fi

# 6. Создание директорий
echo "→ Создание необходимых директорий..."
mkdir -p logs media staticfiles
echo "  ✓ Директории созданы"

# 7. Сборка образов (если нужно)
if [ "$START_SERVICES" == "true" ] || [ "$FORCE_REBUILD" == "true" ]; then
    echo "→ Сборка Docker образов..."
    if [ "$FORCE_REBUILD" == "true" ]; then
        docker-compose build --no-cache
    else
        docker-compose build
    fi
    echo "  ✓ Образы готовы"
fi

# 8. Восстановление БД (если указано)
if [ "$RESTORE_DB" == "true" ]; then
    echo "→ Восстановление базы данных..."

    # Запуск только БД
    docker-compose up -d db
    echo "  Ожидание запуска PostgreSQL (10 сек)..."
    sleep 10

    # Создание БД если не существует
    docker exec expense_bot_db psql -U batman -c "CREATE DATABASE expense_bot;" 2>/dev/null || true

    # Восстановление дампа
    docker exec -i expense_bot_db psql -U batman expense_bot < $SQL_FILE
    echo "  ✓ База данных восстановлена"

    # Если не запускаем все сервисы, останавливаем БД
    if [ "$START_SERVICES" != "true" ]; then
        docker-compose stop db
    fi
fi

# 9. Запуск всех сервисов (если указано)
if [ "$START_SERVICES" == "true" ]; then
    echo "→ Запуск всех сервисов..."
    docker-compose up -d
    echo "  ✓ Сервисы запущены"

    echo ""
    echo "→ Проверка статуса:"
    docker-compose ps
fi

echo ""
echo "================================================"
echo "✓ Развертывание завершено!"
echo "================================================"

if [ "$START_SERVICES" != "true" ]; then
    echo ""
    echo "Сервисы НЕ запущены. Для запуска выполните:"
    echo "  cd $PROJECT_DIR && docker-compose up -d"
fi

if [ "$RESTORE_DB" != "true" ]; then
    echo ""
    echo "База данных НЕ восстановлена."
    echo "Используется существующая БД или будет создана новая."
fi

echo ""
echo "Полезные команды:"
echo "  cd $PROJECT_DIR"
echo "  docker-compose ps                    # Статус"
echo "  docker-compose logs -f bot           # Логи бота"
echo "  docker-compose restart bot           # Перезапуск бота"
echo "  docker-compose down                  # Остановить все"
DEPLOY_SCRIPT

chmod +x /root/server_scripts/expense_bot/deploy_on_reserve.sh
echo "  ✓ Скрипт deploy_on_reserve.sh создан"

# 5. Проверка портов
echo "→ Проверка занятых портов..."
echo "  Порты используемые expense_bot:"
echo "    - 8000 (Django admin panel)"
echo ""
echo "  Текущие занятые порты:"
netstat -tlpn | grep LISTEN | grep -E ':(8000|5432|6379)' || echo "    Нет конфликтов"

# 6. Создание шаблона .env
echo "→ Создание шаблона .env..."
cat > /root/expense_bot_backups/.env.template << 'ENV_TEMPLATE'
# Telegram Bot
BOT_TOKEN=your_bot_token_here
ADMIN_TELEGRAM_ID=your_telegram_id

# Database
DB_NAME=expense_bot
DB_USER=batman
DB_PASSWORD=your_db_password_here
DB_HOST=db
DB_PORT=5432

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password_here

# Django
SECRET_KEY=your_secret_key_here
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,45.95.2.84

# AI Services (optional)
OPENAI_API_KEY=
GOOGLE_API_KEY=

# Webhook (adjust for reserve server)
WEBHOOK_URL=http://45.95.2.84/webhook
ENV_TEMPLATE
echo "  ✓ Шаблон .env создан в /root/expense_bot_backups/.env.template"

echo ""
echo "================================================"
echo "✓ Первичная настройка завершена!"
echo "================================================"
echo ""
echo "Следующие шаги:"
echo ""
echo "1. Скопируйте .env файл с основного сервера или настройте:"
echo "   cp /root/expense_bot_backups/.env.template /opt/expense_bot/.env"
echo "   nano /opt/expense_bot/.env"
echo ""
echo "2. Выполните первое резервное копирование на основном сервере:"
echo "   ssh batman@80.66.87.178"
echo "   bash /home/batman/expense_bot/server_scripts/expense_bot/backup_to_reserve.sh"
echo ""
echo "3. Разверните проект на резервном сервере:"
echo "   bash /root/server_scripts/expense_bot/deploy_on_reserve.sh latest"
echo "   bash /root/server_scripts/expense_bot/deploy_on_reserve.sh latest --restore-db"
echo "   bash /root/server_scripts/expense_bot/deploy_on_reserve.sh latest --start"
echo ""
echo "Структура директорий:"
echo "  /root/expense_bot_backups/    - Резервные копии"
echo "  /opt/expense_bot/             - Рабочий проект"
echo "  /root/server_scripts/         - Скрипты управления"