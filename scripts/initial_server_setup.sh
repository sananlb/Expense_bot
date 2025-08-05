#!/bin/bash
# Начальная настройка сервера для Expense Bot

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================"
echo "  Expense Bot Server Initial Setup"
echo -e "======================================${NC}"
echo ""

# Проверка root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Запустите скрипт от root!${NC}"
    exit 1
fi

# 1. Обновление системы
echo -e "${YELLOW}[1/9] Обновление системы...${NC}"
apt update && apt upgrade -y

# 2. Установка базовых пакетов
echo -e "${YELLOW}[2/9] Установка базовых пакетов...${NC}"
apt install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    postgresql \
    postgresql-contrib \
    redis-server \
    nginx \
    git \
    curl \
    wget \
    htop \
    ncdu \
    supervisor \
    build-essential \
    libpq-dev \
    ufw

# 3. Настройка файрвола
echo -e "${YELLOW}[3/9] Настройка файрвола...${NC}"
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# 4. Создание пользователя для деплоя
echo -e "${YELLOW}[4/9] Создание пользователя deploy...${NC}"
if ! id "deploy" &>/dev/null; then
    adduser --system --group --home /home/deploy --shell /bin/bash deploy
    echo -e "${GREEN}Пользователь deploy создан${NC}"
else
    echo -e "${YELLOW}Пользователь deploy уже существует${NC}"
fi

# 5. Настройка PostgreSQL
echo -e "${YELLOW}[5/9] Настройка PostgreSQL...${NC}"

# Создание пользователя и БД
sudo -u postgres psql << EOF
-- Создаем пользователя если не существует
DO
\$\$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = 'expense_user') THEN
      CREATE USER expense_user WITH PASSWORD 'secure_password_here';
   END IF;
END
\$\$;

-- Создаем БД если не существует
SELECT 'CREATE DATABASE expense_bot OWNER expense_user'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'expense_bot')\\gexec

-- Даем права
GRANT ALL PRIVILEGES ON DATABASE expense_bot TO expense_user;
EOF

echo -e "${GREEN}PostgreSQL настроен${NC}"

# 6. Настройка Redis
echo -e "${YELLOW}[6/9] Настройка Redis...${NC}"
sed -i 's/^# maxmemory <bytes>/maxmemory 256mb/' /etc/redis/redis.conf
sed -i 's/^# maxmemory-policy noeviction/maxmemory-policy allkeys-lru/' /etc/redis/redis.conf
systemctl restart redis-server
echo -e "${GREEN}Redis настроен${NC}"

# 7. Создание структуры директорий
echo -e "${YELLOW}[7/9] Создание структуры директорий...${NC}"
mkdir -p /home/deploy/expense_bot
mkdir -p /home/deploy/expense_bot/logs
mkdir -p /home/deploy/expense_bot/backups
mkdir -p /home/deploy/expense_bot/media
mkdir -p /home/deploy/expense_bot/static
chown -R deploy:deploy /home/deploy

# 8. Создание systemd сервиса для бота
echo -e "${YELLOW}[8/9] Создание systemd сервиса...${NC}"

cat > /etc/systemd/system/expense-bot.service << 'EOF'
[Unit]
Description=Expense Bot Telegram Service
After=network.target postgresql.service redis-server.service
Requires=postgresql.service redis-server.service

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=/home/deploy/expense_bot
Environment="PATH=/home/deploy/expense_bot/venv/bin"
ExecStart=/home/deploy/expense_bot/venv/bin/python run_bot.py
Restart=always
RestartSec=10

# Логирование
StandardOutput=journal
StandardError=journal
SyslogIdentifier=expense-bot

# Безопасность
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/home/deploy/expense_bot

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
echo -e "${GREEN}Systemd сервис создан${NC}"

# 9. Настройка Nginx (базовая)
echo -e "${YELLOW}[9/9] Настройка Nginx...${NC}"

cat > /etc/nginx/sites-available/expense-bot << 'EOF'
server {
    listen 80;
    server_name _;  # Замените на ваш домен

    # Статические файлы (если будут)
    location /static/ {
        alias /home/deploy/expense_bot/static/;
    }

    location /media/ {
        alias /home/deploy/expense_bot/media/;
    }

    # Health check endpoint
    location /health {
        access_log off;
        return 200 "OK\n";
        add_header Content-Type text/plain;
    }

    # Блокировка доступа к служебным файлам
    location ~ /\. {
        deny all;
    }
}
EOF

ln -sf /etc/nginx/sites-available/expense-bot /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo -e "${GREEN}Nginx настроен${NC}"

# Создание скрипта с инструкциями
cat > /root/expense_bot_setup_complete.txt << 'EOF'
Expense Bot Server Setup Complete!
==================================

Что было сделано:
1. ✓ Обновлена система
2. ✓ Установлены необходимые пакеты
3. ✓ Настроен файрвол (ufw)
4. ✓ Создан пользователь deploy
5. ✓ Настроен PostgreSQL (БД: expense_bot, пользователь: expense_user)
6. ✓ Настроен Redis
7. ✓ Созданы директории проекта
8. ✓ Создан systemd сервис (expense-bot.service)
9. ✓ Настроен Nginx

Что нужно сделать дальше:
1. Измените пароль PostgreSQL:
   sudo -u postgres psql -c "ALTER USER expense_user PASSWORD 'your_secure_password';"

2. Клонируйте репозиторий:
   su - deploy
   cd /home/deploy
   git clone https://github.com/your-username/expense_bot.git expense_bot

3. Настройте виртуальное окружение:
   cd expense_bot
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

4. Создайте и настройте .env файл:
   cp .env.example .env
   nano .env

5. Примените миграции:
   python manage.py migrate

6. Запустите бота:
   sudo systemctl start expense-bot
   sudo systemctl enable expense-bot

7. Проверьте статус:
   sudo systemctl status expense-bot

Полезные команды:
- Логи бота: sudo journalctl -u expense-bot -f
- Перезапуск: sudo systemctl restart expense-bot
- Статус сервисов: sudo systemctl status postgresql redis-server nginx expense-bot

Безопасность:
1. Настройте SSH ключи и отключите вход по паролю
2. Запустите скрипт: ./scripts/setup_ssh_user.sh
3. Регулярно обновляйте систему: apt update && apt upgrade
4. Настройте автоматические бэкапы БД

EOF

echo ""
echo -e "${GREEN}======================================"
echo "  Настройка сервера завершена!"
echo -e "======================================${NC}"
echo ""
echo "Инструкции сохранены в: /root/expense_bot_setup_complete.txt"
echo ""
echo -e "${YELLOW}ВАЖНО:${NC}"
echo "1. Измените пароль PostgreSQL для expense_user"
echo "2. Настройте SSH для пользователя deploy"
echo "3. Клонируйте репозиторий и настройте .env"
echo ""