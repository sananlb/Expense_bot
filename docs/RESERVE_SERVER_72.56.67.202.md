# Резервный сервер 72.56.67.202 - Архитектура и развертывание

**Создано:** 2025-09-29
**Источник:** Документация Nutrition_bot проекта
**IP адрес:** 72.56.67.202
**Назначение:** Резервный сервер для обоих проектов (Expense Bot и Nutrition Bot)

## 1. Общая информация о резервном сервере

### 1.1 Технические характеристики
- **IP адрес:** 72.56.67.202
- **Операционная система:** Ubuntu 24.04.1 LTS
- **SSH доступ:** `ssh batman@72.56.67.202`
- **Статус:** НОВЫЙ резервный сервер (замена 45.95.2.84)
- **Причина замены:** Сетевые проблемы на старом сервере
- **Пользователь:** batman (с sudo правами)

### 1.2 WireGuard VPN конфигурация
- **WireGuard IP:** 100.64.0.3/24
- **Private Key:** `4NQB4c95rbA1KVIwZOdNPdhOeQ9h5VpYtPRjrrZuNHc=`
- **Public Key:** `lt2Ih3Nx0mlHRp85VtJ1mqMeK1HkZk1YZZwYYqJMQGA=`
- **Конфигурация:** `/etc/wireguard/wg0.conf`
- **Endpoint DB сервера:** 193.108.113.78:51820
- **Подключение к DB серверу:** 100.64.0.1
- **Статус подключения:** В процессе настройки для Nutrition Bot

### 1.3 Установленное ПО
- **Docker CE:** v28.4.0
- **Docker Compose:** v2.39.4
- **WireGuard:** Установлен и настроен
- **Git:** Готов к клонированию репозиториев
- **SSH:** Пользователь batman с sudo правами
- **Nginx:** v1.24.0

## 2. Обновленная инфраструктура

### 2.1 Многосерверная архитектура
```
┌─────────────────────────────────────┐         ┌─────────────────────────────────────┐
│   MAIN APP СЕРВЕР (АКТИВНЫЙ)        │         │   NEW BACKUP APP СЕРВЕР             │
│   Expense: 80.66.87.178             │         │   72.56.67.202                      │
│   Nutrition: 78.40.216.41           │         │   WireGuard IP: 100.64.0.3          │
│   WireGuard IP: 100.64.0.2          │         │   Status: PARTIALLY READY           │
└─────────────────┬───────────────────┘         └─────────────────┬───────────────────┘
                  │                                               │
                  │            WireGuard VPN                      │
                  │           100.64.0.0/24                       │
                  │                                               │
                  └─────────────────┬───────────────────────────────┘
                                    │
            ┌─────────────────────────▼─────────────────────────┐
            │         DB СЕРВЕР (АКТИВНЫЙ)                     │
            │         193.108.113.78                           │
            │         WireGuard IP: 100.64.0.1                 │
            │         PostgreSQL + Redis                       │
            └─────────────────────────────────────────────────┘

┌─────────────────────────────────────┐
│   OLD BACKUP СЕРВЕР (ДЕАКТИВИРОВАН) │
│   45.95.2.84                        │
│   Status: NETWORK ISSUES            │
│   Status: DECOMMISSIONED            │
└─────────────────────────────────────┘
```

### 2.2 Роль нового резервного сервера
- **Основной функционал:** Backup для обоих проектов
- **Expense Bot:** ✅ ПОЛНОСТЬЮ ГОТОВ
- **Nutrition Bot:** ⏳ ТРЕБУЕТ НАСТРОЙКИ

## 3. Развернутые проекты на резервном сервере

### 3.1 Expense Bot (✅ ПОЛНОСТЬЮ НАСТРОЕН)

#### 3.1.1 Технические детали
- **Статус:** Полностью развернут и протестирован
- **Путь:** `/home/batman/expense_bot_deploy/expense_bot/`
- **Домен:** https://expensebot.duckdns.org
- **SSL:** Let's Encrypt до 27.12.2025
- **База данных:** Локальная PostgreSQL в Docker
- **Redis:** Локальный в Docker
- **Webhook URL:** `https://expensebot.duckdns.org/webhook/` (унифицирован с основным сервером)

#### 3.1.2 Docker контейнеры
- `expense_bot_app` - Telegram бот (порт 8001)
- `expense_bot_web` - Django админка (порт 8000)
- `expense_bot_db` - PostgreSQL
- `expense_bot_redis` - Redis
- `expense_bot_celery` - Celery воркер
- `expense_bot_celery_beat` - Celery планировщик

#### 3.1.3 Nginx конфигурация
```nginx
# /etc/nginx/sites-available/expensebot.conf
server {
    listen 443 ssl;
    server_name expensebot.duckdns.org;

    ssl_certificate /etc/letsencrypt/live/expensebot.duckdns.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/expensebot.duckdns.org/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Webhook без токена (точное совпадение)
    location = /webhook/ {
        proxy_pass http://localhost:8001/webhook/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Webhook с токеном (для совместимости)
    location ~ ^/webhook/(.+)$ {
        proxy_pass http://localhost:8001/webhook/$1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /admin/ {
        proxy_pass http://localhost:8000/admin/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /static/ {
        alias /home/batman/expense_bot_deploy/expense_bot/staticfiles/;
    }

    location / {
        proxy_pass http://localhost:8000/;
    }
}
```

### 3.2 Nutrition Bot (⏳ ОЖИДАЕТ НАСТРОЙКИ)

#### 3.2.1 Планируемая конфигурация
- **Статус:** Планируется к развертыванию
- **Планируемый путь:** `/root/Nutrition_bot_v2/`
- **Git репозиторий:** https://github.com/sananlb/Nutrition_bot
- **Ветка:** master
- **Docker Compose:** `/root/Nutrition_bot_v2/deploy/app-server/docker-compose.yml`

#### 3.2.2 Планируемые контейнеры
| Контейнер | Описание | Порты | Network Mode | Статус |
|-----------|----------|-------|--------------|--------|
| `nutrition_bot` | Telegram бот | - | bridge | Не собран |
| `nutrition_admin` | Django админка | 8001 | host | Не собран |
| `nutrition_custom_admin` | Кастомная админка | 8001:8001 | bridge | Не собран |
| `nutrition_celery_worker` | Celery воркер | - | bridge | Не собран |
| `nutrition_celery_beat` | Celery планировщик | - | bridge | Не собран |
| `portainer` | Управление Docker | 9443:9443 | bridge | Не собран |

## 4. Архитектура развертывания из Nutrition Bot

### 4.1 WireGuard конфигурация для Nutrition Bot
```ini
# /etc/wireguard/wg0.conf
[Interface]
PrivateKey = 4NQB4c95rbA1KVIwZOdNPdhOeQ9h5VpYtPRjrrZuNHc=
Address = 100.64.0.3/24
DNS = 8.8.8.8

[Peer]
PublicKey = bTjCKhyAOiuojhg3oYQN8mI3TDxB7QiGGJYpfYWJ4R0=
Endpoint = 193.108.113.78:51820
AllowedIPs = 100.64.0.0/24
PersistentKeepalive = 25
```

### 4.2 Команды управления WireGuard
```bash
# Запуск VPN
sudo systemctl start wg-quick@wg0
sudo systemctl enable wg-quick@wg0

# Проверка статуса
sudo wg show
sudo systemctl status wg-quick@wg0

# Проверка подключения к DB серверу
ping -c 3 100.64.0.1
```

### 4.3 Переменные окружения для Nutrition Bot
```bash
# База данных - подключение через WireGuard VPN
DATABASE_URL=postgresql://batman:Aa07900790@100.64.0.1:5432/nutrition_bot_v2

# Redis кеш - подключение через WireGuard VPN
REDIS_URL=redis://:l8EyYiHNKp7XcIkwxngBRfq03LsvMCjo@100.64.0.1:6379/1

# Telegram боты (идентичные основному серверу)
TELEGRAM_BOT_TOKEN=8023416067:AAFf4CK7y4Ir163Ea2RCBWzOyevCCvRLdOw
MONITORING_BOT_TOKEN=1665719947:AAHXIl_IloP0HEUaUczNKKemjqNEy70PAF4

# Особенности для резервного сервера
USE_SIMPLE_DOCKER_MONITORING=false
DJANGO_SETTINGS_MODULE=nutrition_bot.settings
```

## 5. Команды для развертывания и управления

### 5.1 Команды для Expense Bot (готовые к использованию)

#### 5.1.1 Процедура активации при аварии
```bash
# 1. Изменить DNS на DuckDNS
# Зайти на https://www.duckdns.org/
# Изменить IP expensebot с 80.66.87.178 на 72.56.67.202

# 2. На резервном сервере (72.56.67.202) - запустить
ssh batman@72.56.67.202
cd /home/batman/expense_bot_deploy/expense_bot
docker compose start
docker compose ps

# 3. Проверить работу (webhook переустанавливать НЕ нужно!)
docker compose logs --tail=50 bot
```

#### 5.1.2 Возврат на основной сервер
```bash
# 1. На резервном - остановить
cd /home/batman/expense_bot_deploy/expense_bot
docker compose stop

# 2. Изменить DNS обратно на 80.66.87.178 на DuckDNS

# 3. На основном - запустить
ssh batman@80.66.87.178
cd /home/batman/expense_bot
docker-compose start

# 4. При необходимости переустановить webhook (только если были проблемы)
curl "https://api.telegram.org/bot8239680156:AAGe68TEXVcJzbcGaNA3YJGSb4lvpna349U/deleteWebhook"
curl "https://api.telegram.org/bot8239680156:AAGe68TEXVcJzbcGaNA3YJGSb4lvpna349U/setWebhook?url=https://expensebot.duckdns.org/webhook/"
```

### 5.2 Команды для Nutrition Bot (требуют завершения настройки)

#### 5.2.1 Полное обновление кода (из документации Nutrition Bot)
```bash
# Полное обновление проекта на резервном сервере
cd /root/Nutrition_bot_v2 && \
git fetch --all && \
git reset --hard origin/master && \
git pull origin master && \
cd /root/Nutrition_bot_v2/deploy/app-server/ && \
docker-compose down && \
docker-compose build --no-cache && \
docker-compose up -d --force-recreate && \
docker image prune -f && \
docker container prune -f
```

#### 5.2.2 Проверка здоровья системы
```bash
# Быстрая проверка (из корня проекта)
cd /root/Nutrition_bot_v2
./server_scripts/quick_check.sh

# Полная проверка (из корня проекта)
./server_scripts/health_check.sh

# Проверка статуса контейнеров
cd /root/Nutrition_bot_v2/deploy/app-server/
docker-compose ps
docker-compose logs --tail=50 bot
```

### 5.3 Скрипты резервного копирования

#### 5.3.1 Backup скрипт для Expense Bot
**Файл:** `/mnt/c/Users/_batman_/Desktop/Nutrition_bot/nutrition_bot/server_scripts/expense_bot/backup_to_reserve.sh`

**Использование:**
```bash
# На основном сервере
cd /home/batman/expense_bot
chmod +x scripts/backup_to_reserve.sh
bash scripts/backup_to_reserve.sh
# Скопировать выведенный Timestamp (например, 20240927_153012)
```

#### 5.3.2 Deploy скрипт для резервного сервера
**Файл:** `/mnt/c/Users/_batman_/Desktop/Nutrition_bot/nutrition_bot/server_scripts/expense_bot/deploy_on_reserve.sh`

**Использование:**
```bash
# На резервном сервере
chmod +x /root/expense_bot/nutrition_bot/scripts/deploy_on_reserve.sh
bash /root/expense_bot/nutrition_bot/scripts/deploy_on_reserve.sh YYYYMMDD_HHMMSS
```

## 6. Процедура завершения настройки Nutrition Bot

### 6.1 Шаг 1: Настройка WireGuard подключения
```bash
# На DB сервере добавить публичный ключ нового сервера
# Public Key: lt2Ih3Nx0mlHRp85VtJ1mqMeK1HkZk1YZZwYYqJMQGA=
# IP: 100.64.0.3/24

# На новом резервном сервере
sudo systemctl start wg-quick@wg0
sudo systemctl enable wg-quick@wg0
ping -c 3 100.64.0.1  # Проверка подключения к DB
```

### 6.2 Шаг 2: Клонирование репозиториев
```bash
# Nutrition Bot
cd /root
git clone https://github.com/sananlb/Nutrition_bot.git
cd Nutrition_bot_v2

# Expense Bot (если требуется)
cd /root
git clone https://github.com/batman-username/expense_bot.git
```

### 6.3 Шаг 3: Настройка .env файлов
```bash
# Копирование .env с основного сервера
cd /root/Nutrition_bot_v2
# Создание .env файла с идентичными настройками
```

### 6.4 Шаг 4: Тестирование подключений
```bash
# Проверка доступности БД
nc -zv 100.64.0.1 5432  # PostgreSQL
nc -zv 100.64.0.1 6379  # Redis

# Тестовая сборка контейнеров
cd deploy/app-server
docker-compose build --no-cache
```

## 7. Время активации и готовность

### 7.1 Время активации
- **Expense Bot:** ~1-2 минуты (только ожидание DNS)
- **Nutrition Bot:** ~5-10 минут (требует сборки)

### 7.2 Унифицированная конфигурация webhook
После обновления конфигурации Nginx на резервном сервере 29.09.2025:
- **Основной сервер:** webhook URL = `https://expensebot.duckdns.org/webhook/`
- **Резервный сервер:** webhook URL = `https://expensebot.duckdns.org/webhook/`
- **Результат:** При переключении между серверами webhook переустанавливать НЕ нужно!

## 8. Чек-лист завершения настройки

### 8.1 Критические задачи для Nutrition Bot
- [ ] **Добавить публичный ключ на DB сервер**
  - Ключ: `lt2Ih3Nx0mlHRp85VtJ1mqMeK1HkZk1YZZwYYqJMQGA=`
  - IP: `100.64.0.3/24`

- [ ] **Клонировать репозитории**
  - Nutrition_bot_v2
  - expense_bot (по необходимости)

- [ ] **Настроить .env файлы**
  - Скопировать с основного сервера
  - Проверить все переменные

- [ ] **Протестировать подключения**
  - WireGuard VPN
  - PostgreSQL
  - Redis

### 8.2 Тестирование
- [ ] Сборка Docker образов
- [ ] Запуск контейнеров в тестовом режиме
- [ ] Проверка всех сервисов
- [ ] Деактивация старого резервного сервера

## 9. Итоговый статус

### ✅ Expense Bot - ПОЛНОСТЬЮ ГОТОВ
- Развернут и протестирован на резервном сервере
- База данных восстановлена (222 траты, 17 пользователей)
- SSL сертификат активен до 27.12.2025
- Nginx конфигурация унифицирована с основным сервером
- Webhook URL идентичен основному серверу (переустановка не требуется)
- **Время активации при сбое: ~1-2 минуты (только смена DNS)**

### ⏳ Nutrition Bot - ТРЕБУЕТ НАСТРОЙКИ
- Nginx и SSL уже готовы (showmefood.duckdns.org)
- Требуется клонирование репозитория
- Требуется настройка WireGuard для подключения к DB серверу

### 🔐 Безопасность
- Root доступ по SSH отключен
- Доступ только через пользователя batman
- SSL сертификаты Let's Encrypt настроены

---

**Последнее обновление:** 2025-09-29
**Автор:** Claude Code на основе документации Nutrition_bot
**Ключевой статус:** Резервный сервер 72.56.67.202 готов для экстренного переключения expense_bot. Для полной готовности требуется завершить настройку Nutrition_bot.