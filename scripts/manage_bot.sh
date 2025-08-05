#!/bin/bash
# Скрипт управления Expense Bot на продакшен сервере

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Переменные
SERVICE_NAME="expense-bot"
PROJECT_DIR="/home/deploy/expense_bot"
VENV_PATH="$PROJECT_DIR/venv"

# Функция показа статуса
show_status() {
    echo -e "${YELLOW}=== Статус сервисов ===${NC}"
    echo ""
    
    # PostgreSQL
    if systemctl is-active --quiet postgresql; then
        echo -e "PostgreSQL:    ${GREEN}[RUNNING]${NC}"
    else
        echo -e "PostgreSQL:    ${RED}[STOPPED]${NC}"
    fi
    
    # Redis
    if systemctl is-active --quiet redis-server; then
        echo -e "Redis:         ${GREEN}[RUNNING]${NC}"
    else
        echo -e "Redis:         ${RED}[STOPPED]${NC}"
    fi
    
    # Bot
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo -e "Expense Bot:   ${GREEN}[RUNNING]${NC}"
        # Показываем uptime
        UPTIME=$(systemctl show -p ActiveEnterTimestamp $SERVICE_NAME | cut -d'=' -f2)
        if [ ! -z "$UPTIME" ]; then
            echo -e "  Uptime:      ${BLUE}$UPTIME${NC}"
        fi
    else
        echo -e "Expense Bot:   ${RED}[STOPPED]${NC}"
    fi
    
    echo ""
}

# Функция запуска бота
start_bot() {
    echo -e "${YELLOW}Запуск Expense Bot...${NC}"
    sudo systemctl start $SERVICE_NAME
    sleep 2
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo -e "${GREEN}✅ Бот успешно запущен!${NC}"
    else
        echo -e "${RED}❌ Ошибка запуска бота${NC}"
        echo "Проверьте логи: sudo journalctl -u $SERVICE_NAME -n 50"
    fi
}

# Функция остановки бота
stop_bot() {
    echo -e "${YELLOW}Остановка Expense Bot...${NC}"
    sudo systemctl stop $SERVICE_NAME
    echo -e "${GREEN}✅ Бот остановлен${NC}"
}

# Функция перезапуска
restart_bot() {
    echo -e "${YELLOW}Перезапуск Expense Bot...${NC}"
    sudo systemctl restart $SERVICE_NAME
    sleep 2
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo -e "${GREEN}✅ Бот успешно перезапущен!${NC}"
    else
        echo -e "${RED}❌ Ошибка перезапуска бота${NC}"
    fi
}

# Функция показа логов
show_logs() {
    echo -e "${YELLOW}Выберите логи для просмотра:${NC}"
    echo "1) Bot logs (последние 100 строк)"
    echo "2) Bot logs (в реальном времени)"
    echo "3) PostgreSQL logs"
    echo "4) Redis logs"
    echo "5) Django error logs"
    
    read -p "Выбор (1-5): " choice
    
    case $choice in
        1) sudo journalctl -u $SERVICE_NAME -n 100 ;;
        2) sudo journalctl -u $SERVICE_NAME -f ;;
        3) sudo journalctl -u postgresql -n 50 ;;
        4) sudo journalctl -u redis-server -n 50 ;;
        5) tail -n 100 $PROJECT_DIR/logs/django_errors.log 2>/dev/null || echo "Файл логов не найден" ;;
        *) echo "Неверный выбор" ;;
    esac
}

# Функция обновления кода
update_code() {
    echo -e "${YELLOW}Обновление кода из git...${NC}"
    
    cd "$PROJECT_DIR" || exit
    
    # Запускаем скрипт деплоя
    if [ -f "./scripts/deploy.sh" ]; then
        chmod +x ./scripts/deploy.sh
        ./scripts/deploy.sh
    else
        echo -e "${RED}Скрипт деплоя не найден!${NC}"
        exit 1
    fi
}

# Функция проверки здоровья бота
health_check() {
    echo -e "${YELLOW}Проверка здоровья системы...${NC}"
    echo ""
    
    # Проверка памяти
    echo -e "${BLUE}Использование памяти:${NC}"
    free -h | grep -E "^Mem|^Swap"
    echo ""
    
    # Проверка диска
    echo -e "${BLUE}Использование диска:${NC}"
    df -h | grep -E "^/dev|^Filesystem"
    echo ""
    
    # Проверка процессов Python
    echo -e "${BLUE}Процессы Python:${NC}"
    ps aux | grep python | grep -v grep | head -5
    echo ""
    
    # Проверка подключений к БД
    echo -e "${BLUE}Подключения к PostgreSQL:${NC}"
    sudo -u postgres psql -c "SELECT count(*) as connections FROM pg_stat_activity WHERE datname = 'expense_bot';" 2>/dev/null || echo "Не удалось получить информацию"
}

# Функция создания бэкапа
create_backup() {
    echo -e "${YELLOW}Создание резервной копии БД...${NC}"
    
    if [ -f "$PROJECT_DIR/scripts/backup_db.sh" ]; then
        cd "$PROJECT_DIR"
        ./scripts/backup_db.sh
    else
        echo -e "${RED}Скрипт бэкапа не найден!${NC}"
    fi
}

# Главное меню
clear
echo -e "${GREEN}======================================"
echo "    Expense Bot Management"
echo -e "======================================${NC}"
echo ""

PS3='Выберите действие: '
options=(
    "📊 Показать статус"
    "▶️  Запустить бота"
    "⏹️  Остановить бота"
    "🔄 Перезапустить бота"
    "📜 Показать логи"
    "🔧 Обновить код (деплой)"
    "💾 Создать бэкап БД"
    "🏥 Проверка здоровья"
    "❌ Выход"
)

while true; do
    select opt in "${options[@]}"
    do
        case $opt in
            "📊 Показать статус")
                show_status
                break
                ;;
            "▶️  Запустить бота")
                start_bot
                show_status
                break
                ;;
            "⏹️  Остановить бота")
                stop_bot
                show_status
                break
                ;;
            "🔄 Перезапустить бота")
                restart_bot
                show_status
                break
                ;;
            "📜 Показать логи")
                show_logs
                break
                ;;
            "🔧 Обновить код (деплой)")
                update_code
                break
                ;;
            "💾 Создать бэкап БД")
                create_backup
                break
                ;;
            "🏥 Проверка здоровья")
                health_check
                break
                ;;
            "❌ Выход")
                echo "До свидания!"
                exit 0
                ;;
            *) echo "Неверный выбор";;
        esac
    done
    
    echo ""
    echo "Нажмите Enter для продолжения..."
    read
    clear
    echo -e "${GREEN}======================================"
    echo "    Expense Bot Management"
    echo -e "======================================${NC}"
    echo ""
done