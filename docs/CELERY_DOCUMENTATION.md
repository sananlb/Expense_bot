# Документация Celery для ExpenseBot

## Оглавление
1. [Архитектура](#архитектура)
2. [Конфигурация](#конфигурация)
3. [Периодические задачи](#периодические-задачи)
4. [Команды для диагностики](#команды-для-диагностики)
5. [Troubleshooting](#troubleshooting)

## Архитектура

### Компоненты системы
- **Celery Worker** - выполняет асинхронные задачи
- **Celery Beat** - планировщик периодических задач
- **Redis** - брокер сообщений и хранилище результатов
- **PostgreSQL** - хранение расписания задач (django-celery-beat)

### Docker контейнеры
```yaml
expense_bot_celery      # Worker для выполнения задач
expense_bot_celery_beat # Планировщик периодических задач
expense_bot_redis       # Брокер сообщений
```

## Конфигурация

### Основные файлы
- `expense_bot/celery.py` - главная конфигурация Celery
- `expense_bot/celery_tasks.py` - определение всех задач
- `expense_bot/settings.py` - настройки Django и расписание

### Очереди задач
| Очередь | Назначение | Приоритет |
|---------|------------|-----------|
| default | Общие задачи | 5 |
| reports | Отчеты | 5-6 |
| recurring | Регулярные платежи | 8 |
| maintenance | Очистка данных | 3 |
| notifications | Уведомления | 8 |

### Переменные окружения
```bash
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
USE_DB_BEAT=true  # Использовать БД для хранения расписания
```

## Периодические задачи

### Активные задачи

#### 1. Ежемесячные отчеты
- **Задача:** `send_monthly_reports`
- **Время:** Ежедневно в 20:00
- **Функция:** Отправка отчетов в последний день месяца
- **Очередь:** reports

#### 2. Проверка лимитов бюджета
- **Задача:** `check_budget_limits`
- **Время:** Каждые 30 минут
- **Функция:** Проверка превышения лимитов (80%, 90%, 100%)
- **Очередь:** notifications

#### 3. Регулярные платежи
- **Задача:** `process_recurring_payments`
- **Время:** Ежедневно в 12:00
- **Функция:** Обработка ежемесячных платежей
- **Очередь:** recurring

#### 4. Очистка старых данных
- **Задача:** `cleanup_old_expenses`
- **Время:** Воскресенье в 03:00
- **Функция:** Удаление расходов старше 730 дней
- **Очередь:** maintenance

#### 5. Отчет администратору
- **Задача:** `send_daily_admin_report`
- **Время:** Ежедневно в 10:00
- **Функция:** Статистика по системе
- **Очередь:** reports

## Команды для диагностики

### Проверка статуса на сервере

#### 1. Проверка состояния контейнеров
```bash
# Статус всех контейнеров
docker ps | grep celery

# Проверка логов worker
docker logs expense_bot_celery --tail 100

# Проверка логов beat
docker logs expense_bot_celery_beat --tail 100

# Проверка Redis
docker exec expense_bot_redis redis-cli ping
```

#### 2. Проверка выполнения задач
```bash
# Интерактивная консоль Celery
docker exec -it expense_bot_celery celery -A expense_bot inspect active

# Статистика по задачам
docker exec -it expense_bot_celery celery -A expense_bot inspect stats

# Зарегистрированные задачи
docker exec -it expense_bot_celery celery -A expense_bot inspect registered

# Запланированные задачи
docker exec -it expense_bot_celery celery -A expense_bot inspect scheduled

# Зарезервированные задачи
docker exec -it expense_bot_celery celery -A expense_bot inspect reserved
```

#### 3. Проверка расписания Beat
```bash
# Просмотр активного расписания
docker exec -it expense_bot_celery_beat celery -A expense_bot beat --loglevel=debug --max-interval=10

# Проверка БД с расписанием
docker exec -it expense_bot_web python manage.py shell
>>> from django_celery_beat.models import PeriodicTask
>>> PeriodicTask.objects.all().values('name', 'enabled', 'last_run_at')
```

#### 4. Тестирование задач вручную
```bash
# Запуск тестовой задачи
docker exec -it expense_bot_web python manage.py shell
>>> from expense_bot.celery import debug_task
>>> debug_task.delay()

# Запуск конкретной периодической задачи
>>> from expense_bot.celery_tasks import send_daily_admin_report
>>> send_daily_admin_report.delay()
```

#### 5. Проверка очередей Redis
```bash
# Подключение к Redis
docker exec -it expense_bot_redis redis-cli

# В консоли Redis:
> KEYS celery*
> LLEN celery  # Количество задач в очереди default
> LLEN reports  # Количество задач в очереди reports
> LLEN recurring  # И так далее для каждой очереди
```

## Troubleshooting

### Проблема: Задачи не выполняются

1. **Проверить worker жив ли:**
```bash
docker logs expense_bot_celery --tail 50 | grep -E "(ERROR|WARNING|started|ready)"
```

2. **Проверить подключение к Redis:**
```bash
docker exec expense_bot_celery redis-cli -h redis ping
```

3. **Проверить регистрацию задач:**
```bash
docker exec expense_bot_celery celery -A expense_bot inspect registered
```

### Проблема: Beat не отправляет задачи

1. **Проверить логи beat:**
```bash
docker logs expense_bot_celery_beat --tail 100 | grep -E "(Scheduler|beat|ERROR)"
```

2. **Проверить таблицы django-celery-beat:**
```bash
docker exec expense_bot_web python manage.py dbshell
# В PostgreSQL:
\dt django_celery_beat*
SELECT * FROM django_celery_beat_periodictask WHERE enabled = true;
```

3. **Пересоздать расписание:**
```bash
docker exec expense_bot_web python manage.py shell
>>> from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule
>>> # Проверить существующие задачи
>>> PeriodicTask.objects.all()
```

### Проблема: Задачи зависают

1. **Проверить активные задачи:**
```bash
docker exec expense_bot_celery celery -A expense_bot inspect active
```

2. **Проверить таймауты:**
```bash
# В settings.py должны быть:
# task_soft_time_limit = 300 (5 минут)
# task_time_limit = 600 (10 минут)
```

3. **Перезапустить worker с очисткой:**
```bash
docker-compose restart expense_bot_celery
docker exec expense_bot_celery celery -A expense_bot purge -f
```

### Проблема: Высокое потребление памяти

1. **Проверить настройки worker:**
```bash
# Текущие настройки для Linux:
# worker_pool = 'prefork'
# worker_prefetch_multiplier = 4
# worker_max_tasks_per_child = 1000
```

2. **Ограничить количество воркеров:**
```bash
# В docker-compose.yml изменить команду:
command: celery -A expense_bot worker --loglevel=info --concurrency=2
```

### Полный перезапуск Celery

```bash
# На сервере
cd /home/batman/expense_bot
docker-compose stop expense_bot_celery expense_bot_celery_beat
docker-compose rm -f expense_bot_celery expense_bot_celery_beat
docker-compose up -d expense_bot_celery expense_bot_celery_beat
docker logs -f expense_bot_celery  # Проверить запуск
```

## Мониторинг

### Flower (веб-интерфейс для мониторинга)
```bash
# Установка (если не установлен)
pip install flower

# Запуск локально для отладки
celery -A expense_bot flower --broker=redis://80.66.87.178:6379/0

# Или в контейнере
docker run -p 5555:5555 mher/flower celery flower --broker=redis://redis:6379/0
```

### Метрики для мониторинга
- Количество задач в очередях
- Время выполнения задач
- Количество неудачных задач
- Использование памяти worker'ами
- Доступность Redis

## Важные замечания

1. **USE_DB_BEAT** должен быть `true` в production для сохранения расписания в БД
2. **Таймзона** должна совпадать во всех компонентах (Django, Celery, PostgreSQL)
3. **worker_pool** различается для разных ОС (Windows: threads, Linux/macOS: prefork)
4. **Логи** хранятся в контейнерах, используйте `docker logs` для просмотра
5. **Результаты задач** хранятся в Redis 1 час (result_expires=3600)

## Частые ошибки и решения

| Ошибка | Причина | Решение |
|--------|---------|---------|
| "Cannot connect to redis://..." | Redis недоступен | Проверить контейнер redis |
| "Task not registered" | Задача не найдена | Проверить autodiscover_tasks() |
| "Database is locked" | SQLite блокировка | Переключиться на PostgreSQL |
| "Received unregistered task" | Несоответствие версий | Пересобрать контейнеры |
| "WorkerLostError" | Worker упал | Проверить логи, увеличить таймауты |

## Контакты для поддержки

При возникновении проблем проверьте:
1. Эту документацию
2. Логи контейнеров (`docker logs`)
3. Статус сервисов (`docker ps`)
4. Подключение к Redis и PostgreSQL