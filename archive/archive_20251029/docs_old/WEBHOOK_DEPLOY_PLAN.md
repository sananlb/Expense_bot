# Expense Bot — Webhook Deployment Plan

Цель: унифицировать прод-развёртывание на обоих серверах через webhook за HTTPS‑прокси (Nginx), устранить расхождения окружений и ошибки polling/таймаутов.

## ✅ Реализованные изменения

### Созданные файлы:
1. **docker-compose.yml** - добавлен порт 8001:8000 для bot сервиса
2. **.env.example** - обновлен с унифицированными переменными
3. **.env.production** - готовый шаблон для продакшена
4. **nginx/webhook-config.conf** - конфигурация Nginx для webhook
5. **scripts/deploy_webhook.sh** - автоматический скрипт развертывания
6. **scripts/check_webhook.sh** - скрипт проверки webhook
7. **scripts/sync_servers.sh** - скрипт синхронизации серверов
8. **docs/WEBHOOK_DEPLOYMENT.md** - полная документация

## 1) Подготовка репозитория

- Добавить публикацию порта для сервиса `bot` в `docker-compose.yml`:
  - В сервисе `bot` добавить блок:
    ports:
      - "8001:8000"

- Проверить `run_bot.py`/`bot/main.py` — режим по умолчанию `BOT_MODE=polling`. Для prod будет задан `.env`.

- Свести переменные в `.env.example` (при необходимости):
  - BOT_MODE=webhook
  - WEBHOOK_URL=https://YOUR_DOMAIN
  - REDIS_PASSWORD=redis_password
  - REDIS_URL=redis://:redis_password@redis:6379/0
  - CELERY_BROKER_URL=redis://:redis_password@redis:6379/0
  - CELERY_RESULT_BACKEND=redis://:redis_password@redis:6379/0
  - SENTRY_DSN=… (одной строкой) или закомментировать

## 2) Обновление .env (боевые сервера)

- На обоих серверах привести `.env` к единому виду:
  - BOT_MODE=webhook
  - WEBHOOK_URL=https://YOUR_DOMAIN
  - REDIS_PASSWORD=redis_password
  - REDIS_URL=redis://:redis_password@redis:6379/0
  - CELERY_BROKER_URL=redis://:redis_password@redis:6379/0
  - CELERY_RESULT_BACKEND=redis://:redis_password@redis:6379/0
  - SENTRY_DSN — одной строкой или закомментировать проблемную строку
  - Проверить BOT_TOKEN, ADMIN_ID и прочие ключи.

Примечание: разрыв строки в SENTRY_DSN недопустим в Compose. Всё значение — на одной строке.

## 3) Рестарт Docker‑стека

- Команды на сервере:
  - docker-compose pull
  - docker-compose up -d --build
  - docker-compose ps
  - docker-compose logs -f --tail=100 bot

Ожидаем: сервисы Up, бот в режиме webhook без таймаутов.

## 4) Nginx (HTTPS проксирование вебхука)

- Настроить серверный блок с TLS (Let’s Encrypt/Certbot):

  server {
      listen 443 ssl;
      server_name YOUR_DOMAIN;

      ssl_certificate /etc/letsencrypt/live/YOUR_DOMAIN/fullchain.pem;
      ssl_certificate_key /etc/letsencrypt/live/YOUR_DOMAIN/privkey.pem;

      location /webhook/YOUR_BOT_TOKEN {
          proxy_pass http://127.0.0.1:8001;
          proxy_set_header Host $host;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      }
  }

- Проверка и перезагрузка:
  - nginx -t && systemctl reload nginx

Примечание: путь вебхука формируется ботом как `/webhook/<BOT_TOKEN>`, домен берётся из `WEBHOOK_URL`.

## 5) Проверка вебхука и работоспособности

- Проверить регистрацию вебхука:
  - curl -s "https://api.telegram.org/bot$BOT_TOKEN/getWebhookInfo"
  - Ожидаем `ok:true` и `url` = `WEBHOOK_URL` + `/webhook/<BOT_TOKEN>`

- Проверить логи приложения:
  - docker-compose logs -f --tail=100 bot

## 6) Приведение обоих серверов к одному состоянию

- На основном сервере убедиться, что bot/celery контейнеры Up (а не Exit 0). Если бот запускался вне Compose, перевести запуск в этот же стек.
- Синхронизировать `.env` на основе `.env.example` и текущих ключей.
- Убедиться, что `web` (Django admin) остаётся на порту 8000, а `bot` для вебхука слушает 8001.

## 7) Альтернатива (если нужен polling)

- Требуется исходящий доступ к `api.telegram.org:443` и рабочий DNS в Docker.
- На хосте Docker добавить резолверы (пример `/etc/docker/daemon.json`):
  {
    "dns": ["1.1.1.1", "8.8.8.8"]
  }
  затем `systemctl restart docker && docker-compose up -d`.
- Проверка из контейнера:
  - curl -sS -m 10 https://api.telegram.org/bot${BOT_TOKEN}/getMe
  Если таймаутов нет — polling возможен, но для прод предпочтителен webhook.

## 8) Чистота логов (необязательно)

- Redis auth warning при старте (`Authentication required`) уходит после указания `REDIS_PASSWORD` и URL с паролем.
- Sentry DSN оставить валидным или закомментировать, чтобы не было ошибок инициализации.

---

## 🚀 Команды для развертывания на резервном сервере

### Шаг 1: Подключение к резервному серверу
```bash
ssh batman@45.95.2.84
```

### Шаг 2: Клонирование или обновление репозитория
```bash
# Если репозиторий еще не клонирован
git clone https://github.com/YOUR_USERNAME/expense_bot.git
cd expense_bot

# Если уже клонирован
cd /home/batman/expense_bot
git pull origin master
```

### Шаг 3: Копирование production конфигурации
```bash
# Создать .env из production шаблона
cp .env.production .env

# Отредактировать WEBHOOK_URL для резервного сервера
nano .env
# Изменить WEBHOOK_URL=https://45.95.2.84 или ваш домен
```

### Шаг 4: Запуск автоматического развертывания
```bash
# Дать права на выполнение скриптам
chmod +x scripts/*.sh

# Запустить развертывание (замените на ваш домен или IP)
sudo ./scripts/deploy_webhook.sh 45.95.2.84
```

### Шаг 5: Проверка работы
```bash
# Проверить статус webhook
./scripts/check_webhook.sh

# Посмотреть логи
docker-compose logs -f --tail=100 bot
```

### Шаг 6: Настройка синхронизации с основным сервером
```bash
# На ОСНОВНОМ сервере (80.66.87.178)
./scripts/sync_servers.sh sync

# Проверить статус синхронизации
./scripts/sync_servers.sh status

# Настроить автоматическую синхронизацию (каждые 6 часов)
./scripts/sync_servers.sh auto
```

---

## 📋 Чек-лист для проверки

- [ ] Docker контейнеры запущены: `docker-compose ps`
- [ ] Bot слушает порт 8001: `netstat -tlpn | grep 8001`
- [ ] Nginx настроен и работает: `nginx -t && systemctl status nginx`
- [ ] SSL сертификат установлен: `ls /etc/letsencrypt/live/`
- [ ] Webhook зарегистрирован: `curl -s "https://api.telegram.org/bot$BOT_TOKEN/getWebhookInfo"`
- [ ] Бот отвечает на команды в Telegram
- [ ] База данных доступна: `docker exec expense_bot_db pg_isready`
- [ ] Redis работает: `docker exec expense_bot_redis redis-cli ping`

---

## 🔄 Восстановление с основного сервера

Если нужно восстановить данные с основного сервера:

```bash
# На резервном сервере
cd /home/batman/expense_bot

# Получить последний бэкап с основного сервера
scp batman@80.66.87.178:/home/batman/backups/latest_backup.sql.gz ./

# Восстановить базу данных
./scripts/sync_servers.sh restore
```

---

## ⚠️ Важные замечания

1. **Пароли**: Обязательно смените пароли в .env файле
2. **Домен**: Для production лучше использовать домен, а не IP
3. **Firewall**: Откройте только порты 22, 80, 443
4. **Backup**: Настройте регулярное резервное копирование
5. **Мониторинг**: Проверяйте логи на ошибки регулярно

---

Краткая шпаргалка команд (prod):

- docker-compose up -d --build && docker-compose ps
- docker-compose logs -f --tail=100 bot
- curl -s "https://api.telegram.org/bot$BOT_TOKEN/getWebhookInfo"
- ./scripts/check_webhook.sh
- ./scripts/sync_servers.sh status

