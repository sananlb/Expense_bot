# 🚀 Инструкция по развёртыванию партнёрской программы на сервере

## 1. Подключение к серверу
```bash
ssh batman@80.66.87.178
```

## 2. Обновление кода из репозитория
```bash
cd /home/batman/expense_bot

# Сохраняем локальные изменения (если есть)
git stash

# Получаем последние изменения
git pull origin master
```

## 3. Применение миграций базы данных
```bash
# Входим в контейнер web для миграций
docker-compose exec expense_bot_web python manage.py migrate expenses
```

## 4. Перезапуск контейнеров
```bash
# Останавливаем контейнеры
docker-compose down

# Пересобираем с новым кодом
docker-compose build --no-cache expense_bot_app expense_bot_web

# Запускаем контейнеры
docker-compose up -d

# Проверяем статус
docker-compose ps
```

## 5. Проверка логов
```bash
# Логи бота
docker-compose logs --tail=50 expense_bot_app

# Логи веб-сервера
docker-compose logs --tail=50 expense_bot_web
```

## 6. Тестирование функционала

### В Telegram боте:
1. Отправить команду `/affiliate`
2. Должна появиться реферальная ссылка
3. Проверить кнопки статистики

### Проверка базы данных:
```bash
# Входим в контейнер БД
docker-compose exec expense_bot_db psql -U batman -d expense_bot

# Проверяем новые таблицы
\dt expenses_affiliate*

# Выход
\q
```

## 7. Откат (если что-то пошло не так)
```bash
# Откатываем код к предыдущей версии
git reset --hard HEAD~1

# Перезапускаем контейнеры
docker-compose down
docker-compose build --no-cache expense_bot_app expense_bot_web
docker-compose up -d
```

## Важные заметки

⚠️ **ВАЖНО**: Миграция 0027_add_affiliate_program_models должна быть применена автоматически.

✅ **Проверка**: После развёртывания убедитесь, что:
- Команда `/affiliate` работает
- Реферальные ссылки генерируются
- При переходе по ссылке создаётся связь реферер-реферал
- При оплате подписки начисляется комиссия 10%

📝 **Логи**: Если возникли проблемы, проверьте:
- `/home/batman/expense_bot/logs/django.log`
- Docker логи контейнеров

## Команды для мониторинга

```bash
# Статус всех контейнеров
docker-compose ps

# Логи в реальном времени
docker-compose logs -f expense_bot_app

# Проверка использования ресурсов
docker stats

# Проверка миграций
docker-compose exec expense_bot_web python manage.py showmigrations expenses
```