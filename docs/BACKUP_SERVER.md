# Резервный сервер ExpenseBot

## Информация о сервере
- **IP адрес:** 72.56.67.202
- **Hostname:** 5727149-kz47794
- **ОС:** Ubuntu 24.04.3 LTS
- **Пользователь:** batman
- **Путь проекта:** `/home/batman/expense_bot_deploy/expense_bot`
- **Docker версия:** Используется docker compose (v2)

## Конфигурация
- **Порты:**
  - 8000: Django web (админ-панель)
  - 8001: Telegram bot (webhook)
- **База данных:** PostgreSQL 15 (контейнер)
- **Redis:** Для кеширования и FSM (контейнер)
- **Nginx:** Проксирует запросы на контейнеры

## Важные файлы
- `.env` - переменные окружения (содержит токены)
- `docker-compose.yml` - конфигурация контейнеров
- `~/fix_webhook.sh` - скрипт для переключения webhook

## Docker контейнеры
- `expense_bot_app` - основной бот (сервис: bot)
- `expense_bot_web` - админ-панель Django
- `expense_bot_celery` - воркер для фоновых задач
- `expense_bot_celery_beat` - планировщик задач
- `expense_bot_db` - PostgreSQL база данных
- `expense_bot_redis` - Redis кеш

## Процедура переключения на резервный сервер

### ⚠️ ВАЖНО: Проблема с кешированием DNS у Telegram
Telegram агрессивно кеширует DNS записи на 5-15 минут. После изменения IP в DuckDNS, Telegram продолжит отправлять запросы на старый IP пока кеш не истечет.

### Быстрое переключение (1-2 минуты + ожидание кеша)

1. **На основном сервере (80.66.87.178):**
   ```bash
   # Остановить контейнеры
   docker-compose stop
   ```

2. **Изменить DNS:**
   - Зайти на https://www.duckdns.org/
   - Изменить IP для `expensebot` на `72.56.67.202`
   - Нажать update

3. **На резервном сервере (72.56.67.202):**
   ```bash
   # Запустить контейнеры
   cd ~/expense_bot_deploy/expense_bot
   docker compose up -d

   # Переустановить webhook
   ~/fix_webhook.sh
   ```

4. **Проверить webhook:**
   ```bash
   curl -s "https://api.telegram.org/bot8239680156:AAGe68TEXVcJzbcGaNA3YJGSb4lvpna349U/getWebhookInfo" | grep ip_address
   ```

   Если IP всё еще старый - подождать 5-15 минут и повторить `~/fix_webhook.sh`

### Обратное переключение на основной сервер

1. **На резервном сервере:**
   ```bash
   docker compose stop
   ```

2. **Изменить DNS обратно на** `80.66.87.178`

3. **На основном сервере:**
   ```bash
   docker-compose start
   ~/fix_webhook.sh
   ```

## Команды для управления

### Проверка состояния
```bash
# Статус контейнеров
docker compose ps

# Логи бота
docker compose logs bot --tail=50

# Мониторинг логов в реальном времени
docker compose logs -f bot
```

### Обновление кода
```bash
cd ~/expense_bot_deploy/expense_bot
git pull origin master
docker compose down
docker compose build --no-cache bot
docker compose up -d
```

### Перезапуск контейнеров
```bash
docker compose restart bot
# или полный перезапуск
docker compose down && docker compose up -d
```

## Решение проблем

### Webhook не обновляется
Если после запуска `~/fix_webhook.sh` IP адрес webhook всё еще указывает на старый сервер:
1. Подождать 5-15 минут (кеш DNS у Telegram)
2. Запустить скрипт снова
3. Если не помогает, удалить webhook и подождать дольше:
   ```bash
   curl -X POST "https://api.telegram.org/bot8239680156:AAGe68TEXVcJzbcGaNA3YJGSb4lvpna349U/deleteWebhook"
   # Подождать 10 минут
   sleep 600
   ~/fix_webhook.sh
   ```

### Redis authentication required
В логах появляется предупреждение о Redis аутентификации - это нормально, бот работает через fallback на memory storage.

### PostgreSQL недоступен
Если БД контейнер не запускается:
```bash
docker compose logs db --tail=50
docker compose restart db
```

## Мониторинг
- Проверка работы бота: отправить `/start` в Telegram
- Проверка админ-панели: https://expensebot.duckdns.org/admin/
- Проверка webhook:
  ```bash
  curl -s "https://api.telegram.org/bot8239680156:AAGe68TEXVcJzbcGaNA3YJGSb4lvpna349U/getWebhookInfo" | python3 -m json.tool
  ```

## Автоматизация с fix_webhook.sh
Скрипт `~/fix_webhook.sh` автоматически:
1. Удаляет старый webhook
2. Ждет 3 секунды
3. Устанавливает новый webhook на https://expensebot.duckdns.org/webhook/
4. Показывает текущий URL и IP адрес

Использовать после каждого изменения IP в DuckDNS для обновления webhook.