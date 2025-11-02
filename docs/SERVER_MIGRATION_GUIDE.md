# Инструкция по миграции ExpenseBot на новый сервер

## Общая информация

**Дата миграции:** 31 октября 2025
**Старый сервер:** 80.66.87.178 (Ubuntu 22.04.5 LTS)
**Новый сервер:** 94.198.220.155 (Ubuntu 24.04.3 LTS)
**Домен:** expensebot.duckdns.org
**Downtime:** ~20-30 минут (из-за DNS propagation)

## Архитектура проекта

Все компоненты развернуты на **одном сервере** через Docker Compose:
- **PostgreSQL 15** (база данных)
- **Redis 7** (кеш и брокер Celery)
- **Bot** (Telegram бот на aiogram 3)
- **Web** (Django admin панель)
- **Celery Worker** (фоновые задачи)
- **Celery Beat** (планировщик задач)

## Подготовительный этап

### Проверка старого сервера
```bash
# Информация о системе
uname -a
lsb_release -a

# Версии установленного ПО
docker --version
docker-compose --version
nginx -v

# Проверка контейнеров
docker-compose ps

# Размер базы данных
docker exec expense_bot_db psql -U expense_user -d expense_bot -c "SELECT pg_size_pretty(pg_database_size('expense_bot'));"
```

**Результаты старого сервера:**
- OS: Ubuntu 22.04.5 LTS
- Docker: 27.5.1
- docker-compose: 1.29.2
- Nginx: 1.18.0
- База данных: ~1.2 MB (406 трат, 104 пользователя)

## ЭТАП 1: Создание резервных копий на старом сервере

### 1.1 Создание дампа PostgreSQL

```bash
# Создать директорию для бэкапов
mkdir -p ~/backups

# Создать дамп БД (ВАЖНО: используем expense_user, НЕ batman!)
docker exec expense_bot_db pg_dump -U expense_user -Fc expense_bot > ~/backups/expense_bot_db_$(date +%Y%m%d).dump

# Проверить размер дампа
ls -lh ~/backups/expense_bot_db_*.dump
```

**Результат:** `expense_bot_db_20251031.dump` (264 KB)

### 1.2 Архивирование проекта

```bash
cd ~
tar -czf backups/expense_bot_project_$(date +%Y%m%d).tar.gz \
  --exclude='expense_bot/__pycache__' \
  --exclude='expense_bot/.git' \
  --exclude='expense_bot/logs' \
  --exclude='expense_bot/staticfiles' \
  --exclude='expense_bot/*.db' \
  --exclude='expense_bot/*.sqlite3' \
  expense_bot/

# Проверить размер архива
ls -lh ~/backups/expense_bot_project_*.tar.gz
```

**Результат:** `expense_bot_project_20251031.tar.gz` (242 MB)

### 1.3 Копирование конфигурации Nginx

```bash
sudo cp /etc/nginx/sites-available/expensebot ~/backups/nginx_expensebot.conf
```

### 1.4 Копирование SSL сертификатов

```bash
sudo tar -czf ~/backups/ssl_certificates_$(date +%Y%m%d).tar.gz \
  -C /etc/letsencrypt/archive/expensebot.duckdns.org .

# Проверка
ls -lh ~/backups/ssl_certificates_*.tar.gz
```

**Результат:** `ssl_certificates_20251031.tar.gz` (27 KB)

### 1.5 Проверка целостности бэкапов

```bash
# Проверка что все файлы созданы
ls -lh ~/backups/

# Проверка PostgreSQL дампа
file ~/backups/expense_bot_db_*.dump

# Проверка tar архивов
tar -tzf ~/backups/expense_bot_project_*.tar.gz | head -10
tar -tzf ~/backups/ssl_certificates_*.tar.gz
```

## ЭТАП 2: Подготовка нового сервера

### 2.1 Обновление системы

```bash
sudo apt update
sudo apt upgrade -y
```

### 2.2 Установка Docker

```bash
# Удаление старых версий
sudo apt remove docker docker-engine docker.io containerd runc

# Установка зависимостей
sudo apt install -y ca-certificates curl gnupg lsb-release

# Добавление официального GPG ключа Docker
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Добавление репозитория Docker
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Установка Docker Engine
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Проверка установки
docker --version
docker compose version
```

**Результат:** Docker 28.5.1, docker-compose 1.29.2

### 2.3 Установка Docker Compose (если не установлен)

```bash
sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
docker-compose --version
```

### 2.4 Установка Nginx

```bash
sudo apt install -y nginx
nginx -v
```

**Результат:** Nginx 1.24.0

### 2.5 Установка Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
certbot --version
```

### 2.6 Настройка UFW Firewall

```bash
# Установка UFW (если не установлен)
sudo apt install -y ufw

# Разрешаем SSH (КРИТИЧЕСКИ ВАЖНО!)
sudo ufw allow 22/tcp

# Разрешаем HTTP и HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Проверка правил БЕЗ активации
sudo ufw show added

# Активация firewall
sudo ufw --force enable

# Проверка статуса
sudo ufw status verbose
```

### 2.7 Добавление пользователя в группу Docker

```bash
sudo usermod -aG docker $USER
newgrp docker

# Проверка
docker ps
```

## ЭТАП 3: Копирование файлов на новый сервер

### 3.1 Копирование с старого на локальную машину

**НА ЛОКАЛЬНОЙ МАШИНЕ:**

```bash
# Создать временную директорию
mkdir -p ~/temp_migration

# Скопировать файлы со старого сервера
scp batman@80.66.87.178:~/backups/expense_bot_db_20251031.dump ~/temp_migration/
scp batman@80.66.87.178:~/backups/expense_bot_project_20251031.tar.gz ~/temp_migration/
scp batman@80.66.87.178:~/backups/nginx_expensebot.conf ~/temp_migration/
scp batman@80.66.87.178:~/backups/ssl_certificates_20251031.tar.gz ~/temp_migration/
```

### 3.2 Копирование на новый сервер

**НА ЛОКАЛЬНОЙ МАШИНЕ:**

```bash
# Копирование на новый сервер
scp ~/temp_migration/expense_bot_db_20251031.dump batman@94.198.220.155:~/
scp ~/temp_migration/expense_bot_project_20251031.tar.gz batman@94.198.220.155:~/
scp ~/temp_migration/nginx_expensebot.conf batman@94.198.220.155:~/
scp ~/temp_migration/ssl_certificates_20251031.tar.gz batman@94.198.220.155:~/
```

### 3.3 Проверка на новом сервере

**НА НОВОМ СЕРВЕРЕ:**

```bash
ls -lh ~/*.dump ~/*.tar.gz ~/*.conf
```

## ЭТАП 4: Восстановление на новом сервере

### 4.1 Распаковка проекта

```bash
cd ~
tar -xzf expense_bot_project_20251031.tar.gz
cd expense_bot
```

### 4.2 Настройка Nginx

```bash
# Копирование конфигурации
sudo cp ~/nginx_expensebot.conf /etc/nginx/sites-available/expensebot

# Создание симлинка
sudo ln -sf /etc/nginx/sites-available/expensebot /etc/nginx/sites-enabled/

# Удаление дефолтной конфигурации
sudo rm -f /etc/nginx/sites-enabled/default

# Проверка конфигурации
sudo nginx -t
```

### 4.3 Восстановление SSL сертификатов

```bash
# Создать директории
sudo mkdir -p /etc/letsencrypt/archive/expensebot.duckdns.org
sudo mkdir -p /etc/letsencrypt/live/expensebot.duckdns.org

# Распаковать сертификаты
sudo tar -xzf ~/ssl_certificates_20251031.tar.gz -C /etc/letsencrypt/archive/expensebot.duckdns.org/

# ВАЖНО: Правильный порядок установки прав!
# СНАЧАЛА публичные сертификаты (644)
sudo chmod 644 /etc/letsencrypt/archive/expensebot.duckdns.org/cert*.pem
sudo chmod 644 /etc/letsencrypt/archive/expensebot.duckdns.org/chain*.pem
sudo chmod 644 /etc/letsencrypt/archive/expensebot.duckdns.org/fullchain*.pem

# ПОТОМ приватный ключ (600) - ПОСЛЕДНИМ!
sudo chmod 600 /etc/letsencrypt/archive/expensebot.duckdns.org/privkey*.pem

# Создать симлинки (найдите последние версии файлов)
sudo ln -sf /etc/letsencrypt/archive/expensebot.duckdns.org/cert1.pem /etc/letsencrypt/live/expensebot.duckdns.org/cert.pem
sudo ln -sf /etc/letsencrypt/archive/expensebot.duckdns.org/chain1.pem /etc/letsencrypt/live/expensebot.duckdns.org/chain.pem
sudo ln -sf /etc/letsencrypt/archive/expensebot.duckdns.org/fullchain1.pem /etc/letsencrypt/live/expensebot.duckdns.org/fullchain.pem
sudo ln -sf /etc/letsencrypt/archive/expensebot.duckdns.org/privkey1.pem /etc/letsencrypt/live/expensebot.duckdns.org/privkey.pem

# Проверка прав
ls -l /etc/letsencrypt/archive/expensebot.duckdns.org/
```

### 4.4 Запуск Nginx

```bash
sudo systemctl restart nginx
sudo systemctl status nginx
```

### 4.5 Сборка Docker образов

```bash
cd ~/expense_bot
docker-compose build --no-cache
```

### 4.6 Запуск контейнеров

```bash
docker-compose up -d
```

### 4.7 Проверка контейнеров

```bash
docker-compose ps

# Все контейнеры должны быть в статусе "Up"
```

### 4.8 Восстановление базы данных

```bash
# Дождаться полного запуска PostgreSQL (30-60 секунд)
sleep 60

# Копирование дампа в контейнер
docker cp ~/expense_bot_db_20251031.dump expense_bot_db:/tmp/

# Восстановление базы данных
docker exec expense_bot_db pg_restore -U expense_user -d expense_bot -c -v /tmp/expense_bot_db_20251031.dump

# Проверка восстановления
docker exec expense_bot_db psql -U expense_user -d expense_bot -c "SELECT COUNT(*) FROM expenses_expense;"
docker exec expense_bot_db psql -U expense_user -d expense_bot -c "SELECT COUNT(*) FROM users_profile;"
```

**Результат:** 406 трат, 104 пользователя восстановлены ✅

### 4.9 Очистка Redis (опционально)

```bash
# Получить пароль Redis из .env
grep REDIS_PASSWORD ~/expense_bot/.env

# Очистить старые данные (если нужно)
docker exec expense_bot_redis redis-cli -a ВАШ_ПАРОЛЬ FLUSHDB
```

## ЭТАП 5: Тестирование перед переключением DNS

### 5.1 Проверка локального доступа к контейнерам

```bash
# Проверка Django admin (должен быть HTTP 302 redirect)
curl -I http://localhost:8000/admin/

# Проверка webhook endpoint (должен быть HTTP 405 - метод не разрешен для GET)
curl -I http://localhost:8001/webhook/
```

**Ожидаемые результаты:**
- Admin: `HTTP/1.1 302 Found` ✅
- Webhook: `HTTP/1.1 405 Method Not Allowed` ✅

### 5.2 Проверка через внешний IP (с --resolve)

```bash
# Тест SSL и webhook endpoint
curl --resolve expensebot.duckdns.org:443:127.0.0.1 https://expensebot.duckdns.org/webhook/

# Тест admin панели
curl --resolve expensebot.duckdns.org:443:127.0.0.1 -I https://expensebot.duckdns.org/admin/
```

**Ожидаемые результаты:**
- Webhook: `HTTP/2 405` ✅
- Admin: `HTTP/2 302` ✅

### 5.3 Проверка логов на ошибки

```bash
# Логи бота
docker-compose logs --tail=50 bot | grep -i error

# Логи веб-сервера
docker-compose logs --tail=50 web | grep -i error

# Логи Nginx
sudo tail -50 /var/log/nginx/error.log
```

## ЭТАП 6: Переключение DNS

### 6.1 Остановка старого сервера (предотвращение конфликтов)

**НА СТАРОМ СЕРВЕРЕ (80.66.87.178):**

```bash
cd ~/expense_bot
docker-compose stop
docker-compose ps
```

**Результат:** Все контейнеры в статусе "Exit" ✅

### 6.2 Изменение DNS на DuckDNS

1. Зайти на https://www.duckdns.org/
2. Войти в аккаунт
3. Найти домен **expensebot.duckdns.org**
4. Изменить IP с **80.66.87.178** на **94.198.220.155**
5. Нажать **"update ip"**

### 6.3 Проверка DNS propagation

```bash
# Проверка через разные DNS серверы
nslookup expensebot.duckdns.org 1.1.1.1
nslookup expensebot.duckdns.org 8.8.8.8
nslookup expensebot.duckdns.org 8.8.4.4

# Проверка через dig
dig expensebot.duckdns.org +short
```

**Примечание:** DNS может обновляться 5-30 минут. Разные DNS серверы обновляются с разной скоростью.

## ПРОБЛЕМЫ И ИХ РЕШЕНИЯ

### Проблема 1: HTTP 502 Bad Gateway при доступе к admin

**Симптомы:**
```bash
curl -I https://expensebot.duckdns.org/admin/
HTTP/2 502
server: nginx/1.24.0
```

**Причина:** Django блокирует запросы из-за отсутствия нового IP в ALLOWED_HOSTS

**Логи Django:**
```
ERROR Invalid HTTP_HOST header: '94.198.220.155:8000'. You may need to add '94.198.220.155' to ALLOWED_HOSTS.
```

**Решение:**

```bash
# Редактировать .env
nano ~/expense_bot/.env

# Найти и изменить строку ALLOWED_HOSTS:
ALLOWED_HOSTS=localhost,127.0.0.1,expensebot.duckdns.org,94.198.220.155

# Сохранить (Ctrl+O, Enter, Ctrl+X)

# Перезапустить контейнеры
docker-compose restart web bot

# Проверить что ошибка исчезла
docker-compose logs --tail=20 web
curl -I https://expensebot.duckdns.org/admin/
```

**Результат:** HTTP 302 (успешный редирект на страницу логина) ✅

---

### Проблема 2: Бот падает при старте с ошибкой DNS

**Симптомы:**
```bash
docker-compose logs bot
ERROR run_bot Критическая ошибка: Telegram server says - Bad Request: bad webhook: Failed to resolve host: Temporary failure in name resolution
INFO run_bot Бот остановлен
```

**Причина:** Бот при старте пытается автоматически установить webhook через API Telegram, но DNS еще не распространился, и Telegram не может резолвить домен.

**Диагностика:**

```bash
# Проверка статуса контейнера
docker-compose ps
# Результат: expense_bot_app - Up (контейнер работает, но бот упал)

# Проверка логов
docker-compose logs --tail 50 bot | grep -i "webhook\|error"

# Проверка что webhook сервер НЕ запустился
docker-compose logs bot | grep "Webhook сервер запущен"
# Результат: пусто (сервер не запущен)

# Проверка попыток от Telegram
sudo tail -50 /var/log/nginx/access.log | grep -i telegram
# Результат: 91.108.5.20 POST /webhook/ HTTP/1.1 502
```

**Временное решение 1: Перезапуск после DNS propagation**

```bash
# Подождать 5-10 минут для распространения DNS
sleep 300

# Перезапустить контейнер bot
docker-compose restart bot

# Проверить что бот запустился
docker-compose logs --tail 30 bot | grep -i "запущен\|webhook"
```

**Временное решение 2: Polling режим (если нужно срочно)**

```bash
# Редактировать .env
nano ~/expense_bot/.env

# Изменить BOT_MODE
BOT_MODE=polling

# Сохранить и перезапустить
docker-compose restart bot

# Бот запустится в polling режиме без webhook

# После распространения DNS вернуть обратно:
# BOT_MODE=webhook
```

**Финальное решение:** После полного распространения DNS (20-30 минут) бот запускается нормально в webhook режиме.

---

### Проблема 3: Telegram не может достучаться до webhook

**Симптомы:**

```bash
# Логи Nginx показывают попытки от Telegram
sudo tail -50 /var/log/nginx/access.log | grep 91.108
91.108.5.20 - - [31/Oct/2025:19:38:58 +0000] "POST /webhook/ HTTP/1.1" 502 166 "-" "-"
91.108.5.20 - - [31/Oct/2025:19:39:00 +0000] "POST /webhook/ HTTP/1.1" 502 166 "-" "-"

# getWebhookInfo показывает пустой URL
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
{"ok":true,"result":{"url":"","has_custom_certificate":false,"pending_update_count":4}}
```

**Причина:** Комбинация проблем:
1. DNS еще не полностью распространился
2. Бот упал при старте и не запустил webhook сервер
3. Nginx пытается проксировать на порт 8001, но там никто не слушает

**Решение:**

```bash
# 1. Проверить что бот запущен
docker-compose ps

# 2. Перезапустить бот (после распространения DNS)
docker-compose restart bot

# 3. Проверить что webhook сервер запустился
docker-compose logs --tail 50 bot | grep "Webhook сервер запущен"

# 4. Вручную установить webhook с указанием IP
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://expensebot.duckdns.org/webhook/" \
  -d "ip_address=94.198.220.155"

# 5. Проверить установку
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

**Результат после решения:**
```json
{
  "ok": true,
  "result": {
    "url": "https://expensebot.duckdns.org/webhook/",
    "has_custom_certificate": false,
    "pending_update_count": 0,
    "max_connections": 40,
    "ip_address": "94.198.220.155"
  }
}
```

---

### Проблема 4: DNS показывает старый IP

**Симптомы:**
```bash
dig expensebot.duckdns.org +short
80.66.87.178  # Старый IP!

host expensebot.duckdns.org 8.8.8.8
expensebot.duckdns.org has address 80.66.87.178
```

**Причина:** DNS кеширование на разных уровнях:
- Локальный DNS resolver
- ISP DNS cache
- Публичные DNS серверы (Google, Cloudflare)
- Telegram DNS cache

**Диагностика:**

```bash
# Проверка через разные DNS серверы
nslookup expensebot.duckdns.org 1.1.1.1    # Cloudflare
nslookup expensebot.duckdns.org 8.8.8.8    # Google Primary
nslookup expensebot.duckdns.org 8.8.4.4    # Google Secondary

# Проверка через онлайн инструменты
# https://dnschecker.org/#A/expensebot.duckdns.org
```

**Результаты проверки (через 20 минут после смены DNS):**
- Cloudflare (1.1.1.1): ✅ 94.198.220.155 (обновлен)
- Google Secondary (8.8.4.4): ✅ 94.198.220.155 (обновлен)
- Google Primary (8.8.8.8): ❌ 80.66.87.178 (старый кеш)

**Решение:** Ждать. DNS propagation занимает от 5 до 30 минут. Ускорить этот процесс невозможно.

**Workaround для проверки:**
```bash
# Использовать параметр ip_address при установке webhook
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://expensebot.duckdns.org/webhook/" \
  -d "ip_address=94.198.220.155"
```

Это подсказывает Telegram использовать указанный IP напрямую, не дожидаясь DNS.

## ЭТАП 7: Финальная проверка

### 7.1 Проверка webhook

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
```

**Ожидаемый результат:**
```json
{
  "ok": true,
  "result": {
    "url": "https://expensebot.duckdns.org/webhook/",
    "has_custom_certificate": false,
    "pending_update_count": 0,
    "max_connections": 40,
    "ip_address": "94.198.220.155"
  }
}
```

### 7.2 Проверка работы бота через Telegram

Отправить команды в Telegram:
- `/start` - должно показаться главное меню
- `/expenses` - должна показаться сводка трат
- Отправить трату "кофе 200" - должна добавиться в базу

### 7.3 Проверка логов на активность

```bash
# Логи бота (должны показывать обработку команд)
docker-compose logs --tail 30 bot

# Ищем строки типа:
# INFO dispatcher Update id=... is handled
# INFO web_log POST /webhook/ HTTP/1.1 200
```

**Пример успешных логов:**
```
INFO web_log 172.18.0.1 [31/Oct/2025:22:47:08 +0300] "POST /webhook/ HTTP/1.1" 200 179
INFO logging_middleware Request: {"user_id": 881292737, "command": "/start"}
INFO dispatcher Update id=310876682 is handled. Duration 449 ms
```

### 7.4 Проверка доступа к admin панели

```bash
# Через браузер открыть
https://expensebot.duckdns.org/admin/

# Должна открыться страница логина Django admin
```

### 7.5 Проверка всех контейнеров

```bash
docker-compose ps
```

**Ожидаемый результат:** Все контейнеры в статусе "Up" ✅

### 7.6 Проверка Celery задач

```bash
# Проверка Celery worker
docker exec expense_bot_celery celery -A expense_bot inspect active

# Проверка Celery beat
docker-compose logs --tail 20 celery-beat
```

## Важные замечания и best practices

### 1. Порядок установки прав на SSL сертификаты

**❌ НЕПРАВИЛЬНО:**
```bash
sudo chmod 600 /etc/letsencrypt/archive/expensebot.duckdns.org/privkey*.pem
sudo chmod 644 /etc/letsencrypt/archive/expensebot.duckdns.org/*.pem  # Перезатирает 600!
```

**✅ ПРАВИЛЬНО:**
```bash
# СНАЧАЛА публичные сертификаты
sudo chmod 644 /etc/letsencrypt/archive/expensebot.duckdns.org/cert*.pem
sudo chmod 644 /etc/letsencrypt/archive/expensebot.duckdns.org/chain*.pem
sudo chmod 644 /etc/letsencrypt/archive/expensebot.duckdns.org/fullchain*.pem
# ПОТОМ приватный ключ
sudo chmod 600 /etc/letsencrypt/archive/expensebot.duckdns.org/privkey*.pem
```

### 2. Пользователь базы данных

**ВАЖНО:** Используй `expense_user`, а НЕ `batman` для всех операций с PostgreSQL!

```bash
# ✅ ПРАВИЛЬНО
docker exec expense_bot_db pg_dump -U expense_user expense_bot

# ❌ НЕПРАВИЛЬНО
docker exec expense_bot_db pg_dump -U batman expense_bot
# Ошибка: role "batman" is not permitted to log in
```

### 3. ALLOWED_HOSTS в Django

При миграции на новый сервер **обязательно** добавь новый IP в ALLOWED_HOSTS:

```bash
ALLOWED_HOSTS=localhost,127.0.0.1,expensebot.duckdns.org,НОВЫЙ_IP
```

### 4. DNS Propagation

- DNS обновление занимает **5-30 минут**
- Разные DNS серверы обновляются с разной скоростью
- Telegram имеет свой DNS cache
- Ускорить процесс **невозможно** - только ждать
- Workaround: использовать параметр `ip_address` при установке webhook

### 5. Тестирование перед переключением DNS

**Используй curl с --resolve для тестирования нового сервера:**

```bash
curl --resolve expensebot.duckdns.org:443:127.0.0.1 https://expensebot.duckdns.org/webhook/
```

Это позволяет протестировать локально без изменения DNS.

### 6. Firewall

**КРИТИЧЕСКИ ВАЖНО:** Настрой UFW **ДО** отключения от сервера, иначе можешь потерять SSH доступ!

```bash
# Обязательно сначала разреши SSH
sudo ufw allow 22/tcp
# Потом остальные порты
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
# И только потом активируй
sudo ufw --force enable
```

### 7. Остановка старого сервера

Останови старый сервер **перед** переключением DNS чтобы избежать:
- Конфликтов при одновременной работе двух серверов
- Расхождений в данных
- Проблем с Telegram API (webhook может переключаться между серверами)

## Контрольный чеклист миграции

### Подготовка
- [ ] Проверка версий ПО на старом сервере
- [ ] Создание дампа PostgreSQL
- [ ] Архивирование проекта
- [ ] Копирование конфигурации Nginx
- [ ] Копирование SSL сертификатов
- [ ] Проверка целостности всех бэкапов

### Новый сервер
- [ ] Обновление системы
- [ ] Установка Docker
- [ ] Установка Nginx
- [ ] Установка Certbot
- [ ] Настройка UFW firewall
- [ ] Добавление пользователя в группу docker

### Копирование данных
- [ ] Копирование файлов со старого сервера на локальную машину
- [ ] Копирование файлов с локальной машины на новый сервер
- [ ] Проверка всех файлов на новом сервере

### Восстановление
- [ ] Распаковка проекта
- [ ] Настройка Nginx
- [ ] Восстановление SSL сертификатов (правильный порядок прав!)
- [ ] Проверка конфигурации Nginx
- [ ] Сборка Docker образов
- [ ] Запуск контейнеров
- [ ] Восстановление базы данных
- [ ] Проверка количества записей в БД

### Тестирование
- [ ] Проверка локального доступа к контейнерам
- [ ] Проверка через curl с --resolve
- [ ] Проверка логов на ошибки
- [ ] Добавление нового IP в ALLOWED_HOSTS

### Переключение
- [ ] Остановка контейнеров на старом сервере
- [ ] Изменение DNS на DuckDNS
- [ ] Ожидание DNS propagation (5-30 минут)
- [ ] Проверка DNS через разные серверы

### Финальная проверка
- [ ] Установка Telegram webhook
- [ ] Проверка webhook info
- [ ] Тест команд бота в Telegram
- [ ] Проверка логов на активность
- [ ] Проверка admin панели
- [ ] Проверка всех контейнеров
- [ ] Проверка Celery задач

## Время выполнения

| Этап | Время |
|------|-------|
| Подготовка и бэкапы | 10-15 минут |
| Подготовка нового сервера | 15-20 минут |
| Копирование файлов | 10-15 минут |
| Восстановление и настройка | 20-30 минут |
| Тестирование | 10-15 минут |
| DNS propagation | 20-30 минут |
| Финальная проверка | 5-10 минут |
| **ИТОГО** | **90-135 минут** |

**Реальное downtime:** 20-30 минут (время DNS propagation)

## Rollback план

Если что-то пошло не так, можно быстро вернуться на старый сервер:

### 1. Вернуть DNS обратно
- Зайти на https://www.duckdns.org/
- Изменить IP обратно на **80.66.87.178**
- Нажать "update ip"

### 2. Запустить контейнеры на старом сервере
```bash
# На старом сервере
cd ~/expense_bot
docker-compose up -d
```

### 3. Проверить работу
```bash
docker-compose ps
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

**Время rollback:** 5-10 минут + DNS propagation

## Дополнительные команды для диагностики

### Проверка портов
```bash
sudo netstat -tlnp | grep -E '80|443|8000|8001'
```

### Проверка процессов Docker
```bash
docker ps -a
docker-compose logs --tail 100
```

### Проверка дискового пространства
```bash
df -h
docker system df
```

### Очистка Docker (если нужно место)
```bash
docker system prune -a --volumes
```

### Проверка памяти
```bash
free -h
docker stats --no-stream
```

## Заключение

Миграция выполнена успешно! Основные проблемы были связаны с:
1. **ALLOWED_HOSTS** - быстро решается добавлением нового IP
2. **DNS propagation** - требует времени, ускорить невозможно
3. **Порядок установки прав SSL** - важно делать публичные сначала, приватные потом

Новый сервер работает стабильно, все данные восстановлены, бот отвечает на команды.

**Версия документа:** 1.0
**Дата создания:** 31 октября 2025
**Автор:** Claude Code Assistant
