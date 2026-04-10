# План переноса проекта на нидерландский сервер

**Дата составления:** 2026-04-10  
**Текущий сервер:** 176.124.218.53 (Россия, Ubuntu 24.04.3)  
**Новый сервер:** `144.31.97.139` (Нидерланды)  
**Домен бота:** expensebot.duckdns.org  

---

## Что меняется после переноса

| Параметр | Сейчас | После переноса |
|---|---|---|
| `BOT_MODE` | `polling` (костыль) | `webhook` (нормально) |
| `TELEGRAM_FORCE_IPV4` | `true` | убрать |

---

## Шаг 1. Первичная настройка нового сервера

### 1.1. Подключение под root и создание пользователя

Выполнять как root на новом сервере:

```bash
# Создать пользователя batman
adduser batman
# Ввести пароль: Aa07900790
# Остальные поля — Enter

# Дать sudo права
usermod -aG sudo batman

# Разрешить sudo без пароля (как на текущем сервере)
echo "batman ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/batman
chmod 440 /etc/sudoers.d/batman
```

### 1.2. Добавить SSH ключи для batman

```bash
# Создать .ssh директорию для batman
mkdir -p /home/batman/.ssh
chmod 700 /home/batman/.ssh

# Добавить SSH ключи (те же что на текущем сервере)
cat >> /home/batman/.ssh/authorized_keys << 'EOF'
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDJwpltn+tZdYWWIimHkTEVtVFxQ61x0cFNZ+BPMrN3B1zlfqooxE63X1Y+xRKfpgugAqA3/GPSx+3Ami/UzKbxkPLDW5SSWH4j11fMAoRxxkFvUmDCYXoynxIQ6Nx4bj1ZJ87wNLcbBgMglPQ3QDk9r6az12NU+oo9vRy7asLBTI+IG+/gFtftf5Mkv1DJtO7H+e3A66QkLx3kurqJ8CGpsudXF4FDpQ4BicLcpRoujlIai9iGl9A6hhrG9xEdvnLGAFnG6kODH746iKc6/PgFsEdpOCKEfRqsWkej2rnEl/hMMG9hHsj5H3ZgH1vapHmC5XilQYQ+dY9R6XODks4K5CD9IjiZWprtwqTiXrF01LN5R4PvuiUtjdfwPGdymgIuUmMFhZpnHGKkaMONleUmZkG2U7bR0YLH4vRl0jVt9drcoEVgb/FzuHYyGR6Y4AEIHm86xnE7yXiUU5ilmC3amKJbASvbRmi65Ghf3yXFNh6fLIyho8REhmHde/l/OxrxbrWuDGco5O+4E4dacb97JYzDnpLRUGgN0RR/UVpWuR/0ThFrENaPGzJwkU9eU8oJUXkIc+SSPUQxwnnFN9SCOduQlU2HLFaLd2t1wX5QIVRLmu1rLPWZA4QOuHTvbNqbDdR66xjm0W6e0n5NkHep5ffSUevJiECJZMw6H/LRdw== _batman_@LGgram
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKSiXSm6OjMH6A47Nz25zcU1kJRSspFKy1UzMn5hCX75 nalbantovfml@gmail.com
EOF

chmod 600 /home/batman/.ssh/authorized_keys
chown -R batman:batman /home/batman/.ssh
```

### 1.3. Отключить root по SSH

```bash
# Отредактировать sshd_config
sed -i 's/^PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config

# Убедиться что PasswordAuthentication для batman работает (пока)
grep -E "PermitRootLogin|PasswordAuthentication" /etc/ssh/sshd_config

# Перезапустить SSH
systemctl restart sshd
```

⚠️ **ВАЖНО:** До перезапуска SSH проверить что batman логинится по ключу в отдельном терминале!

```bash
# В ДРУГОМ терминале проверить:
ssh batman@144.31.97.139
# Должно войти без пароля
```

---

## Шаг 2. Установка зависимостей на новом сервере

Выполнять как batman:

```bash
# Обновить систему
sudo apt update && sudo apt upgrade -y

# Установить необходимые пакеты
sudo apt install -y curl git nginx certbot python3-certbot-nginx ufw

# Установить Docker
curl -fsSL https://get.docker.com | sudo bash

# Добавить batman в группу docker
sudo usermod -aG docker batman

# Установить docker-compose plugin (новый синтаксис)
sudo apt install -y docker-compose-plugin

# Проверить установку
docker --version
docker compose version
```

⚠️ После `usermod -aG docker batman` нужно перелогиниться чтобы группа применилась.

---

## Шаг 3. Перенос кода проекта

### 3.1. Склонировать репозиторий

```bash
cd /home/batman
git clone git@github.com:REPO_URL/expense_bot.git
# ИЛИ если по HTTPS:
git clone https://github.com/REPO_URL/expense_bot.git
cd expense_bot
```

### 3.2. Создать .env из текущего сервера

На **текущем сервере** (176.124.218.53) скопировать .env:

```bash
# Выполнить на ТЕКУЩЕМ сервере и скопировать вывод
cat /home/batman/expense_bot/.env
```

На **новом сервере** создать `.env` и вставить содержимое, затем внести следующие изменения:

```bash
cd /home/batman/expense_bot
nano .env
```

**Что изменить в .env на новом сервере:**

```env
# УБРАТЬ или закомментировать (больше не нужны):
# TELEGRAM_FORCE_IPV4=true

# ИЗМЕНИТЬ:
BOT_MODE=webhook

# ALLOWED_HOSTS и CSRF_TRUSTED_ORIGINS — добавить новый IP сервера:
ALLOWED_HOSTS=localhost,127.0.0.1,144.31.97.139,expensebot.duckdns.org
CSRF_TRUSTED_ORIGINS=https://expensebot.duckdns.org,http://144.31.97.139:8000
```

---

## Шаг 4. Перенос базы данных

### 4.1. Создать дамп на текущем сервере

```bash
# На ТЕКУЩЕМ сервере — сначала остановить бота (минимальный downtime)
ssh batman@176.124.218.53
cd /home/batman/expense_bot

# Создать дамп БД
docker exec expense_bot_db pg_dump -U expense_user expense_bot > /home/batman/expense_bot_dump_$(date +%Y%m%d_%H%M%S).sql

# Проверить размер дампа
ls -lh /home/batman/expense_bot_dump_*.sql
```

### 4.2. Передать дамп на новый сервер

```bash
# С локального компьютера (или с текущего сервера):
scp batman@176.124.218.53:/home/batman/expense_bot_dump_*.sql batman@144.31.97.139:/home/batman/
```

### 4.3. Запустить только PostgreSQL на новом сервере и залить дамп

```bash
# На НОВОМ сервере
cd /home/batman/expense_bot

# Поднять только БД
docker compose up -d db

# Подождать запуска
sleep 15

# Залить дамп
docker exec -i expense_bot_db psql -U expense_user expense_bot < /home/batman/expense_bot_dump_*.sql

# Проверить данные
docker exec expense_bot_db psql -U expense_user expense_bot -c "\dt"
docker exec expense_bot_db psql -U expense_user expense_bot -c "SELECT COUNT(*) FROM expenses_expense;"
```

---

## Шаг 5. Настройка Nginx

### 5.1. Создать конфиг Nginx

```bash
sudo cp /home/batman/expense_bot/nginx/expensebot-ssl.conf /etc/nginx/sites-available/expensebot
sudo ln -s /etc/nginx/sites-available/expensebot /etc/nginx/sites-enabled/expensebot
sudo rm -f /etc/nginx/sites-enabled/default

# Создать директорию для ACME challenge
sudo mkdir -p /var/www/html

# Временно изменить конфиг — только HTTP (нужен для получения SSL сертификата)
sudo nano /etc/nginx/sites-available/expensebot
```

**Временный конфиг (только для получения SSL):**

```nginx
server {
    listen 80;
    server_name expensebot.duckdns.org;

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/html;
        default_type "text/plain";
        try_files $uri =404;
    }

    location / {
        return 200 "OK";
    }
}
```

```bash
sudo nginx -t && sudo systemctl start nginx
```

---

## Шаг 6. Обновление DNS (DuckDNS)

⚠️ **КРИТИЧЕСКИЙ ШАГ** — с этого момента начинается переключение трафика.

1. Зайти на [duckdns.org](https://www.duckdns.org)
2. Найти домен `expensebot`
3. Изменить IP с `176.124.218.53` на `144.31.97.139`
4. Нажать "update ip"

Проверить распространение DNS (может занять 1-5 минут):

```bash
# На новом сервере или с компьютера:
nslookup expensebot.duckdns.org
# Должен вернуть 144.31.97.139
```

---

## Шаг 7. Получение SSL сертификата

```bash
# На новом сервере
sudo certbot --nginx -d expensebot.duckdns.org --non-interactive --agree-tos -m your@email.com

# Проверить что сертификат получен
sudo certbot certificates
```

После успешного получения сертификата — восстановить полный конфиг Nginx:

```bash
# Скопировать рабочий конфиг из репозитория
sudo cp /home/batman/expense_bot/nginx/expensebot-ssl.conf /etc/nginx/sites-available/expensebot
sudo nginx -t && sudo nginx -s reload
```

---

## Шаг 8. Запуск проекта

### 8.1. Собрать и запустить все контейнеры

```bash
cd /home/batman/expense_bot
docker compose build --no-cache
docker compose up -d
docker compose ps
```

Все контейнеры должны быть в статусе `running`:
- `expense_bot_db` ✅
- `expense_bot_redis` ✅
- `expense_bot_app` ✅
- `expense_bot_celery` ✅
- `expense_bot_celery_beat` ✅
- `expense_bot_web` ✅

### 8.2. Проверить логи бота

```bash
docker compose logs --tail=100 bot
```

Ожидаемые строки в логах:
```
Бот запущен и готов к работе
Run polling for bot @showmecoinbot  ← временно, пока webhook не настроен
```

**Нет** строк вида:
- `TelegramNetworkError`
- `Connection refused`
- `Applying Telegram API host override` ← уже не должно быть

---

## Шаг 9. Переключение в режим webhook

После того как убедились что бот запускается и работает:

```bash
# На новом сервере
cd /home/batman/expense_bot
nano .env
# Убедиться что: BOT_MODE=webhook

# Перезапустить бот-контейнер
docker compose restart bot

# Проверить логи — должна появиться строка с webhook
docker compose logs --tail=50 bot
```

Проверить что webhook зарегистрировался у Telegram:

```bash
# Заменить BOT_TOKEN на реальный токен
curl "https://api.telegram.org/botBOT_TOKEN/getWebhookInfo" | python3 -m json.tool
```

Ожидаемый ответ:
```json
{
  "url": "https://expensebot.duckdns.org/webhook/",
  "pending_update_count": 0,
  "last_error_message": ""
}
```

---

## Шаг 10. Финальная проверка

### 10.1. Функциональный тест

- Отправить боту `/start` → должен ответить
- Отправить трату "кофе 200" → должна создаться с AI категоризацией
- Открыть `/admin` → должна открыться Django админка

### 10.2. Проверка что прокси убран

```bash
# Убедиться что в логах нет упоминания прокси
docker compose logs bot | grep -i proxy
# Должно быть пусто

# Убедиться что OpenRouter работает напрямую
docker compose logs bot | grep -i openrouter
```

### 10.3. Настроить автообновление SSL

```bash
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

# Проверить
sudo certbot renew --dry-run
```

### 10.4. Настроить Firewall

```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (для ACME)
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
sudo ufw status
```

---

## Шаг 11. Остановка старого сервера

После успешной проверки что новый сервер работает:

```bash
# На СТАРОМ сервере — остановить контейнеры
ssh batman@176.124.218.53
cd /home/batman/expense_bot
docker-compose stop bot celery celery-beat
```

⚠️ **НЕ удалять сервер** сразу. Подождать 1-2 дня, убедиться что всё стабильно, только потом отключать.

---

## Сводка изменений в .env

| Переменная | Старый сервер | Новый сервер |
|---|---|---|
| `BOT_MODE` | `polling` | `webhook` |
| `TELEGRAM_FORCE_IPV4` | `true` | **удалить** |
| `ALLOWED_HOSTS` | содержит старый IP | заменить на новый IP |
| `CSRF_TRUSTED_ORIGINS` | содержит старый IP | заменить на новый IP |

---

## Чеклист

- [ ] Создан пользователь batman с паролем Aa07900790
- [ ] SSH ключи добавлены в authorized_keys
- [ ] Root доступ по SSH отключён
- [ ] Docker и docker-compose установлены
- [ ] Репозиторий склонирован
- [ ] .env создан с обновлёнными значениями (без прокси)
- [ ] Дамп БД перенесён и залит
- [ ] DNS обновлён на DuckDNS (expensebot → 144.31.97.139)
- [ ] SSL сертификат получен через certbot
- [ ] Nginx настроен с SSL
- [ ] Все Docker контейнеры запущены
- [ ] BOT_MODE=webhook работает
- [ ] Webhook зарегистрирован у Telegram
- [ ] Функциональный тест пройден (бот отвечает, трата создаётся)
- [ ] Firewall настроен (ufw)
- [ ] Автообновление SSL настроено
- [ ] Старый сервер остановлен (через 1-2 дня)

---

## Медиафайлы и статика

```bash
# Если есть загруженные пользователями файлы в /media —
# скопировать с текущего сервера:
rsync -avz batman@176.124.218.53:/home/batman/expense_bot/media/ \
  /home/batman/expense_bot/media/

# Статика пересобирается автоматически при запуске контейнеров
# (collectstatic в docker-entrypoint.sh)
```
