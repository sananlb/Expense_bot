# 🔗 Руководство по настройке Telegram Webhook

## 📋 Содержание
1. [Проблема](#проблема)
2. [Причина](#причина)
3. [Решение](#решение)
4. [Автоматическая установка](#автоматическая-установка)
5. [Ручная установка](#ручная-установка)
6. [Проверка статуса](#проверка-статуса)
7. [Troubleshooting](#troubleshooting)

---

## ❌ Проблема

### Симптомы:
- После обновления кода и перезапуска контейнеров бот не отвечает на сообщения
- В логах ошибка: `Failed to resolve host: Temporary failure in name resolution`
- Webhook URL пустой при проверке через `getWebhookInfo`

### Почему это происходит:
1. При обновлении выполняется `docker-compose down && docker-compose up -d`
2. Контейнер бота запускается заново
3. В `bot/main.py` при старте пытается установить webhook:
   ```python
   await bot.set_webhook(f"{webhook_url}{webhook_path}")
   ```
4. **НО** DNS еще не успел обновиться / резолвиться
5. Установка webhook **ПАДАЕТ** с ошибкой DNS
6. Webhook остается **ПУСТЫМ**
7. Бот не получает обновления от Telegram

---

## 🔍 Причина

### Корень проблемы - DNS Timing Issue:

```
┌─────────────────────────────────────────────────────────┐
│ Процесс обновления:                                     │
├─────────────────────────────────────────────────────────┤
│ 1. docker-compose down      → контейнеры остановлены    │
│ 2. docker-compose build     → пересборка образов        │
│ 3. docker-compose up -d     → запуск контейнеров        │
│ 4. Контейнер app стартует (0-2 сек)                    │
│ 5. bot/main.py запускается (2-3 сек)                   │
│ 6. Попытка bot.set_webhook()                           │
│    ├─ DNS запрос: expensebot.duckdns.org               │
│    ├─ ❌ DNS НЕ РЕЗОЛВИТСЯ                             │
│    └─ ❌ Webhook НЕ установлен                         │
│ 7. Бот запущен, но НЕ получает сообщения              │
└─────────────────────────────────────────────────────────┘
```

### Факторы влияющие на проблему:
1. **DNS кеш:** системный DNS resolver кеширует запросы
2. **DuckDNS обновление:** может быть задержка в обновлении записей
3. **Docker сеть:** внутри контейнера DNS может быть медленнее
4. **Timing:** контейнер стартует быстрее чем успевает обновиться DNS

---

## ✅ Решение

### Автоматическая установка webhook встроена в процесс обновления

Мы добавили **автоматическую установку webhook** с retry механизмом в скрипт `scripts/full_update.sh`:

```bash
# Процесс обновления теперь включает:
1. Остановка контейнеров
2. Обновление кода
3. Пересборка образов
4. Запуск контейнеров
5. ⏳ ОЖИДАНИЕ 10 секунд (контейнеры инициализируются)
6. 🔗 АВТОМАТИЧЕСКАЯ установка webhook с retry
7. ✅ Проверка статуса
```

---

## 🚀 Автоматическая установка

### Обновление сервера (рекомендуемый способ):

```bash
cd /home/batman/expense_bot && bash update.sh
```

Этот скрипт **АВТОМАТИЧЕСКИ**:
- ✅ Обновит код из Git
- ✅ Пересоберет Docker контейнеры
- ✅ Подождет готовности контейнеров (10 сек)
- ✅ **Установит webhook с retry механизмом**
- ✅ Проверит что всё работает

### Что делает скрипт установки webhook (`scripts/set_webhook.sh`):

1. **Проверка DNS** (5 попыток с интервалом 2 сек)
   - Если DNS резолвится → использует домен
   - Если DNS не резолвится → fallback на IP адрес

2. **Удаление старого webhook**
   - Очищает предыдущую конфигурацию

3. **Установка нового webhook** (3 попытки с интервалом 3 сек)
   - URL: `https://expensebot.duckdns.org/webhook/`
   - Allowed updates: message, callback_query, pre_checkout_query

4. **Проверка статуса**
   - Показывает текущий webhook URL
   - Показывает количество pending updates

---

## 🔧 Ручная установка

### Если автоматическая установка не сработала:

```bash
# Способ 1: Использовать готовый скрипт
cd /home/batman/expense_bot && bash scripts/set_webhook.sh

# Способ 2: Использовать старый скрипт (в home директории)
bash ~/fix_webhook_force.sh
```

### Ручная установка через curl:

```bash
# 1. Получить BOT_TOKEN из .env
BOT_TOKEN=$(grep '^BOT_TOKEN=' /home/batman/expense_bot/.env | cut -d '=' -f2 | tr -d ' "' | tr -d "'")

# 2. Удалить webhook
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/deleteWebhook"

# 3. Подождать 2 секунды
sleep 2

# 4. Установить webhook
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=https://expensebot.duckdns.org/webhook/&allowed_updates=[\"message\",\"callback_query\",\"pre_checkout_query\"]"

# 5. Проверить результат
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | jq .
```

---

## 🔍 Проверка статуса

### Проверка webhook через скрипт диагностики:

```bash
cd /home/batman/expense_bot && bash check_deployment.sh
```

Этот скрипт проверяет:
- ✅ Docker контейнеры запущены
- ✅ PostgreSQL доступна
- ✅ Redis работает
- ✅ Telegram Bot API доступен
- ✅ **Webhook URL установлен (КРИТИЧЕСКАЯ проверка!)**
- ✅ Нет накопления pending updates
- ✅ Celery workers активны

### Проверка webhook вручную:

```bash
# Получить статус webhook
BOT_TOKEN=$(grep '^BOT_TOKEN=' /home/batman/expense_bot/.env | cut -d '=' -f2 | tr -d ' "' | tr -d "'")
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | jq .
```

**Ожидаемый результат:**
```json
{
  "ok": true,
  "result": {
    "url": "https://expensebot.duckdns.org/webhook/",
    "has_custom_certificate": false,
    "pending_update_count": 0,
    "allowed_updates": ["message", "callback_query", "pre_checkout_query"]
  }
}
```

**❌ Проблема** если:
- `"url": ""` → webhook не установлен
- `"pending_update_count": > 100` → накопились необработанные обновления

---

## 🛠️ Troubleshooting

### 1. Webhook не устанавливается - DNS проблема

**Симптом:**
```
Failed to resolve host: Temporary failure in name resolution
```

**Решение:**
```bash
# Проверить DNS резолюцию
nslookup expensebot.duckdns.org

# Если не резолвится - проверить DuckDNS
curl "https://www.duckdns.org/update?domains=expensebot&token=YOUR_TOKEN&verbose=true"

# Использовать IP вместо домена (временно)
BOT_TOKEN=$(grep '^BOT_TOKEN=' /home/batman/expense_bot/.env | cut -d '=' -f2)
SERVER_IP=$(hostname -I | awk '{print $1}')
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=https://${SERVER_IP}/webhook/"
```

### 2. Webhook установлен но бот не отвечает

**Проверка 1: Nginx работает**
```bash
sudo systemctl status nginx
curl -I https://expensebot.duckdns.org/webhook/
```

**Проверка 2: Контейнер app запущен**
```bash
docker ps | grep expense_bot_app
docker logs expense_bot_app --tail 50
```

**Проверка 3: SSL сертификат валиден**
```bash
echo | openssl s_client -connect expensebot.duckdns.org:443 -servername expensebot.duckdns.org 2>/dev/null | openssl x509 -noout -dates
```

### 3. Накопились pending updates

**Симптом:**
```json
"pending_update_count": 500
```

**Решение:**
```bash
# Удалить webhook с drop_pending_updates=true
BOT_TOKEN=$(grep '^BOT_TOKEN=' /home/batman/expense_bot/.env | cut -d '=' -f2)
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/deleteWebhook?drop_pending_updates=true"

# Переустановить webhook
bash /home/batman/expense_bot/scripts/set_webhook.sh
```

### 4. "Bad webhook: failed to resolve host" после обновления

**Причина:** Контейнер запустился быстрее чем обновился DNS

**Решение:**
```bash
# Подождать 10-15 секунд и переустановить webhook
sleep 15
bash /home/batman/expense_bot/scripts/set_webhook.sh
```

---

## 📚 Дополнительные ресурсы

- [Telegram Bot API - setWebhook](https://core.telegram.org/bots/api#setwebhook)
- [Telegram Bot API - getWebhookInfo](https://core.telegram.org/bots/api#getwebhookinfo)
- [DuckDNS Documentation](https://www.duckdns.org/spec.jsp)

---

## ✅ Чеклист после обновления

- [ ] Код обновлен из Git
- [ ] Docker контейнеры пересобраны
- [ ] Контейнеры запущены
- [ ] **Webhook установлен** (`check_deployment.sh` показывает URL)
- [ ] Бот отвечает в Telegram
- [ ] Админка доступна
- [ ] Лендинг доступен
- [ ] Нет ошибок в логах

---

**Последнее обновление:** 09.10.2025
**Версия:** 1.0
