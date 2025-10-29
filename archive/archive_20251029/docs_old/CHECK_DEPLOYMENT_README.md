# Скрипт проверки состояния системы после деплоя

## 📋 Назначение

`check_deployment.sh` - комплексный скрипт для проверки состояния всех компонентов ExpenseBot после обновления на сервере.

## 🎯 Когда использовать

**ВСЕГДА запускайте этот скрипт после:**
- Обновления кода из Git
- Перезапуска Docker контейнеров
- Изменения конфигурации
- При подозрении на проблемы с ботом

## 🚀 Использование

### На сервере
```bash
ssh batman@80.66.87.178
cd /home/batman/expense_bot
bash check_deployment.sh
```

### Одной командой с локального компьютера
```bash
ssh batman@80.66.87.178 'cd /home/batman/expense_bot && bash check_deployment.sh'
```

## ✅ Что проверяет скрипт

### 1. Docker контейнеры
- Все контейнеры запущены и работают
- Статус каждого контейнера
- Открытые порты

### 2. База данных PostgreSQL
- Доступность БД
- Количество пользователей в системе

### 3. Redis
- Доступность Redis
- Использование памяти

### 4. Telegram Bot API
- Валидность токена
- Доступность API Telegram
- Username бота

### 5. Webhook (КРИТИЧЕСКИ ВАЖНО!)
- **Webhook URL установлен** (если пустой - бот НЕ работает!)
- Количество pending updates (если >10 - проблема)
- Last error message от Telegram

### 6. Celery Workers
- Активность Celery workers
- Статистика по воркерам

### 7. Webhook endpoint
- Доступность webhook URL снаружи
- HTTP статус (405 или 200 = OK)

### 8. Логи
- Количество ошибок за последний час
- Последние 5 ошибок (если есть)

### 9. Дисковое пространство
- Использование диска
- Доступное пространство
- Предупреждение при >80%, критическая проблема при >90%

## 📊 Пример вывода

### ✅ Успешная проверка
```
==================================
Проверка состояния системы
==================================

=== 1. Docker контейнеры ===
NAMES                        STATUS              PORTS
expense_bot_app             Up 2 hours          0.0.0.0:8001->8000/tcp
expense_bot_web             Up 2 hours          0.0.0.0:8000->8000/tcp
...

=== 5. Telegram Webhook ===
Webhook URL: https://expensebot.duckdns.org/webhook/
Pending updates: 0

==================================
✅ Все проверки пройдены успешно!
==================================
```

### ❌ Обнаружена критическая проблема
```
=== 5. Telegram Webhook ===
⚠️  КРИТИЧЕСКАЯ ПРОБЛЕМА: Webhook URL пустой!
Бот НЕ получает обновления от Telegram!

Запустите: bash ~/fix_webhook_force.sh

==================================
❌ Обнаружено проблем: 1
==================================

Рекомендации:
1. Проверьте логи: docker logs expense_bot_app --tail 100
2. Проверьте статус контейнеров: docker ps -a
3. Перезапустите проблемные контейнеры: docker restart <container_name>
```

## 🔴 Критические проблемы

Если скрипт обнаружит критические проблемы, он выведет их с emoji ⚠️ и даст рекомендации.

### Пустой Webhook URL
**Симптом:** `Webhook URL пустой!`

**Решение:**
```bash
bash ~/fix_webhook_force.sh
```

### Много pending updates
**Симптом:** `WARNING: 15 pending updates in webhook queue`

**Причина:** Бот не успевает обрабатывать обновления или был недоступен

**Решение:**
1. Проверить логи бота
2. Перезапустить бот: `docker restart expense_bot_app`
3. Если не помогло - `bash ~/fix_webhook_force.sh`

### Celery workers не работают
**Симптом:** `Celery workers: FAILED`

**Решение:**
```bash
docker restart expense_bot_celery expense_bot_celery_beat
docker logs expense_bot_celery --tail 50
```

### Мало дискового пространства
**Симптом:** `КРИТИЧЕСКОЕ: Использование диска 95%`

**Решение:**
```bash
# Очистить Docker
docker system prune -a -f

# Очистить старые логи
find /home/batman/expense_bot/logs -name "*.log.*" -mtime +30 -delete

# Удалить старые резервные копии
find /home/batman/backups -name "*.sql" -mtime +30 -delete
```

## 🔧 Интеграция в процесс деплоя

### Рекомендуемый процесс обновления сервера

1. **Обновление кода:**
   ```bash
   cd /home/batman/expense_bot && bash update.sh
   ```

2. **Проверка состояния:**
   ```bash
   bash check_deployment.sh
   ```

3. **Если есть проблемы:**
   - Следуйте рекомендациям скрипта
   - Запустите check_deployment.sh снова после исправления

## 📝 Цветной вывод

- 🟢 **Зеленый** - всё OK
- 🟡 **Желтый** - предупреждение (не критично)
- 🔴 **Красный** - критическая проблема (требует внимания)

## ⚙️ Настройка

### Первый запуск на сервере
```bash
# Конвертация line endings (если нужно)
dos2unix check_deployment.sh

# Права на выполнение
chmod +x check_deployment.sh

# Запуск
bash check_deployment.sh
```

## 🐛 Troubleshooting

### Скрипт не запускается
```bash
# Проверить права
ls -la check_deployment.sh

# Добавить права
chmod +x check_deployment.sh

# Запустить явно через bash
bash check_deployment.sh
```

### Ошибка "command not found"
Скрипт использует стандартные команды Linux. Если какая-то команда не найдена:
```bash
# Для dos2unix
sudo apt-get install dos2unix

# Для curl (обычно уже установлен)
sudo apt-get install curl
```

## 📚 См. также

- `docs/SERVER_COMMANDS.md` - полный список команд для сервера
- `docs/WEBHOOK_DEPLOYMENT.md` - настройка webhook
- `fix_webhook_force.sh` - скрипт восстановления webhook
- `update.sh` - скрипт полного обновления сервера
