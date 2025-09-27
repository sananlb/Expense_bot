# Webhook Deployment Guide for ExpenseBot

## Быстрый старт для резервного сервера

### 1. Подготовка сервера

```bash
# Подключение к серверу
ssh batman@YOUR_SERVER_IP

# Клонирование репозитория (если еще не сделано)
git clone https://github.com/YOUR_USERNAME/expense_bot.git
cd expense_bot

# Обновление кода
git pull origin master
```

### 2. Настройка .env файла

Скопируйте `.env.example` и настройте:

```bash
cp .env.example .env
nano .env
```

Обязательные переменные для webhook:
```env
# Bot
BOT_TOKEN=your_bot_token_here
BOT_MODE=webhook
WEBHOOK_URL=https://your-domain.com
ADMIN_ID=your_telegram_id

# Database
DB_NAME=expense_bot
DB_USER=expense_user
DB_PASSWORD=strong_password_here

# Redis
REDIS_PASSWORD=redis_password
REDIS_URL=redis://:redis_password@redis:6379/0
CELERY_BROKER_URL=redis://:redis_password@redis:6379/0
CELERY_RESULT_BACKEND=redis://:redis_password@redis:6379/0

# API Keys
OPENAI_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here

# Django
DJANGO_SECRET_KEY=generate-new-secret-key
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com
```

### 3. Автоматическая установка webhook

Используйте готовый скрипт:

```bash
# Дайте права на выполнение
chmod +x scripts/deploy_webhook.sh

# Запустите с вашим доменом
sudo ./scripts/deploy_webhook.sh your-domain.com
```

Скрипт автоматически:
- ✅ Настроит .env для webhook режима
- ✅ Установит и настроит Nginx
- ✅ Получит SSL сертификат от Let's Encrypt
- ✅ Запустит Docker контейнеры
- ✅ Зарегистрирует webhook в Telegram

### 4. Проверка работы

```bash
# Проверка статуса webhook
./scripts/check_webhook.sh

# Просмотр логов бота
docker-compose logs -f bot

# Проверка контейнеров
docker-compose ps
```

## Ручная настройка (если автоматическая не сработала)

### Шаг 1: Docker Compose

```bash
# Остановка контейнеров
docker-compose down

# Пересборка с новыми настройками
docker-compose build --no-cache

# Запуск
docker-compose up -d
```

### Шаг 2: Nginx

Создайте конфигурацию `/etc/nginx/sites-available/expensebot`:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location ~ ^/webhook/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /home/batman/expense_bot/staticfiles/;
    }
}
```

Активируйте конфигурацию:

```bash
# Создать символическую ссылку
sudo ln -s /etc/nginx/sites-available/expensebot /etc/nginx/sites-enabled/

# Проверить конфигурацию
sudo nginx -t

# Перезапустить Nginx
sudo systemctl reload nginx
```

### Шаг 3: SSL сертификат

```bash
# Установка Certbot
sudo apt install certbot python3-certbot-nginx

# Получение сертификата
sudo certbot --nginx -d your-domain.com
```

### Шаг 4: Проверка webhook

```bash
# Получить информацию о webhook
curl -s "https://api.telegram.org/bot$BOT_TOKEN/getWebhookInfo" | python3 -m json.tool

# Должен показать:
# "url": "https://your-domain.com/webhook/YOUR_BOT_TOKEN"
# "has_custom_certificate": false
# "pending_update_count": 0
```

## Troubleshooting

### Проблема: Webhook не регистрируется

```bash
# Проверьте что порт 8001 открыт
docker-compose ps

# Проверьте логи бота
docker-compose logs bot

# Убедитесь что BOT_MODE=webhook
grep BOT_MODE .env
```

### Проблема: Connection timeout

```bash
# Проверьте DNS из контейнера
docker exec expense_bot_app nslookup api.telegram.org

# Если не работает, добавьте DNS в Docker
sudo nano /etc/docker/daemon.json
```

Добавьте:
```json
{
  "dns": ["1.1.1.1", "8.8.8.8"]
}
```

Затем:
```bash
sudo systemctl restart docker
docker-compose up -d
```

### Проблема: Redis authentication failed

```bash
# Проверьте пароль Redis
grep REDIS_PASSWORD .env

# Убедитесь что URL содержит пароль
grep REDIS_URL .env
# Должно быть: redis://:password@redis:6379/0
```

### Проблема: 502 Bad Gateway

```bash
# Проверьте что контейнер бота запущен
docker-compose ps bot

# Проверьте порты
netstat -tulpn | grep 8001

# Перезапустите контейнеры
docker-compose restart
```

## Мониторинг

### Полезные команды

```bash
# Логи в реальном времени
docker-compose logs -f --tail=100

# Только ошибки
docker-compose logs bot | grep -E "ERROR|WARNING"

# Статус контейнеров
watch -n 2 docker-compose ps

# Использование ресурсов
docker stats
```

### Health Check

```bash
# Проверка webhook endpoint
curl -I https://your-domain.com/webhook/health

# Проверка Telegram API
curl https://api.telegram.org/bot$BOT_TOKEN/getMe

# Проверка Nginx
sudo nginx -t && echo "Nginx config OK"
```

## Откат при проблемах

Если что-то пошло не так:

```bash
# Вернуться к polling режиму
sed -i 's/BOT_MODE=webhook/BOT_MODE=polling/' .env

# Перезапустить
docker-compose restart bot

# Удалить webhook из Telegram
curl -s "https://api.telegram.org/bot$BOT_TOKEN/deleteWebhook"
```

## Безопасность

1. **Используйте сильные пароли** для БД и Redis
2. **Ограничьте доступ** к портам (только 80, 443, 22)
3. **Регулярно обновляйте** систему и Docker
4. **Мониторьте логи** на подозрительную активность
5. **Делайте бэкапы** БД и конфигурации

## Контакты для поддержки

При проблемах проверьте:
1. Логи: `docker-compose logs`
2. Статус: `./scripts/check_webhook.sh`
3. Документацию: `/docs` папка в проекте