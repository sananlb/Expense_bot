# 📊 Система мониторинга ExpenseBot

## Оглавление
1. [Обзор системы мониторинга](#обзор-системы-мониторинга)
2. [Sentry - отслеживание ошибок](#sentry---отслеживание-ошибок)
3. [Система уведомлений администратора](#система-уведомлений-администратора)
4. [Health Checks контейнеров](#health-checks-контейнеров)
5. [Мониторинг через Celery](#мониторинг-через-celery)
6. [Логирование](#логирование)
7. [Метрики и аналитика](#метрики-и-аналитика)
8. [Настройка на сервере](#настройка-на-сервере)
9. [Troubleshooting](#troubleshooting)

---

## 🎯 Обзор системы мониторинга

ExpenseBot имеет многоуровневую систему мониторинга production-уровня, которая включает:

- **Sentry** - автоматическое отслеживание ошибок и производительности
- **Telegram Bot для админа** - мгновенные уведомления о критических событиях
- **Health Checks** - проверка состояния контейнеров Docker
- **Celery Tasks** - периодические проверки системы
- **Структурированное логирование** - детальная информация для отладки
- **Аналитика** - сбор метрик использования

### Архитектура мониторинга

```
┌─────────────────────────────────────────────────┐
│                   ExpenseBot                      │
├───────────────────┬────────────────┬─────────────┤
│   Django App      │  Celery Worker │  Celery Beat│
├───────────────────┴────────────────┴─────────────┤
│                 Monitoring Layer                   │
├──────────┬──────────┬──────────┬─────────────────┤
│  Sentry  │ Admin Bot│  Logging │  Health Checks  │
└──────────┴──────────┴──────────┴─────────────────┘
```

---

## 🐛 Sentry - отслеживание ошибок

### Возможности

Sentry предоставляет:
- **Автоматическое отслеживание ошибок** во всех компонентах системы
- **Performance Monitoring** - метрики производительности
- **Release Tracking** - привязка ошибок к версиям
- **User Context** - информация о пользователе при ошибке
- **Breadcrumbs** - последовательность действий до ошибки
- **Профилирование** - анализ узких мест производительности

### Настройка Sentry

#### 1. Регистрация и создание проекта

1. Зарегистрируйтесь на [sentry.io](https://sentry.io)
2. Создайте новый проект с типом "Django"
3. Скопируйте DSN из настроек проекта

#### 2. Конфигурация в проекте

**requirements.txt:**
```txt
sentry-sdk[django]==2.19.2
```

**Переменные окружения (.env):**
```bash
# Sentry Error Tracking
SENTRY_DSN=https://your_key@your_org.ingest.us.sentry.io/your_project_id
SENTRY_TRACES_SAMPLE_RATE=0.1  # 10% запросов для performance
SENTRY_PROFILES_SAMPLE_RATE=0.1  # 10% для профилирования
```

**settings.py (уже настроено):**
```python
# Автоматически активируется при DEBUG=False
if not DEBUG:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
            LoggingIntegration(),
        ],
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1")),
        environment=os.getenv("ENVIRONMENT", "production"),
        before_send=filter_sensitive_data,  # Фильтрация чувствительных данных
    )
```

#### 3. Интеграции Sentry

- **Django Integration**: Отслеживание ошибок в views, middleware, templates
- **Celery Integration**: Ошибки в фоновых задачах
- **Redis Integration**: Проблемы с кешем
- **Logging Integration**: Связь с системой логирования

### Фильтрация чувствительных данных

Система автоматически фильтрует:
- Пароли и токены
- API ключи
- Персональные данные пользователей
- Платежную информацию

### Dashboard Sentry

После настройки вы получите доступ к:
- **Issues** - список всех ошибок с группировкой
- **Performance** - метрики производительности endpoints
- **Releases** - отслеживание версий
- **Alerts** - настройка уведомлений
- **User Feedback** - обратная связь от пользователей

---

## 📱 Система уведомлений администратора

### Архитектура

```
bot/services/admin_notifier.py
├── TelegramNotifier         # Класс для отправки сообщений
├── send_admin_alert()       # Основная функция отправки
├── notify_critical_error()  # Критические ошибки
├── notify_new_user()        # Новые пользователи
├── notify_payment_received() # Платежи
├── notify_bot_started()     # Запуск бота
├── notify_bot_stopped()     # Остановка бота
└── send_daily_report()      # Ежедневный отчет
```

### Настройка бота для мониторинга

**Переменные окружения:**
```bash
# Отдельный бот для мониторинга (рекомендуется)
MONITORING_BOT_TOKEN=your_monitoring_bot_token
ADMIN_TELEGRAM_ID=your_telegram_id

# Или использовать основной бот (не рекомендуется)
# MONITORING_BOT_TOKEN не указывать, будет использован TELEGRAM_BOT_TOKEN
```

### Типы уведомлений

#### 1. Критические ошибки (🚨)
```python
await notify_critical_error(
    error_type="Database Connection Failed",
    details="PostgreSQL is not responding",
    user_id=123456
)
```
- Отправляются мгновенно
- Кешируются на 30 минут (защита от спама)
- Содержат контекст ошибки

#### 2. Системные события
- ✅ **Запуск бота** - при старте контейнера
- 🛑 **Остановка бота** - при остановке/крэше
- 🎉 **Новый пользователь** - регистрация
- 💳 **Платеж получен** - успешная оплата

#### 3. Ежедневный отчет (📊)

Отправляется каждый день в 10:00 MSK через Celery Beat:

```
📊 [Coins] Ежедневный отчет за 21.09.2024

👥 Пользователи:
  • Всего: 1,234
  • Активных вчера: 89
  • Новых вчера: 12
  • Retention 7d: 65%

💰 Финансы:
  • Расходы: 45,678 записей на 1,234,567₽
  • Доходы: 234 записей на 567,890₽
  • Подписки: 45 активных

🤖 AI сервисы:
  • Запросов: 1,234
  • Успешность: 98.5%
  • Токенов: 456,789
  • Стоимость: $12.34

📂 Топ категорий:
  • Продукты: 234,567₽ (123 записей)
  • Транспорт: 123,456₽ (89 записей)
  • Рестораны: 98,765₽ (45 записей)

⚠️ Ошибок за день: 5

🕐 Отчет сформирован: 10:00:15
```

### Защита от спама

- **Rate limiting** - не более 1 алерта того же типа за 30 минут
- **Группировка ошибок** - похожие ошибки объединяются
- **Приоритеты** - критические с звуком, информационные без

---

## 🏥 Health Checks контейнеров

### Конфигурация Docker

**docker-compose.yml:**
```yaml
# PostgreSQL
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-expense_user}"]
  interval: 120s      # Проверка каждые 2 минуты
  timeout: 5s         # Таймаут проверки
  retries: 3          # Количество попыток
  start_period: 30s   # Время на инициализацию

# Redis
healthcheck:
  test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
  interval: 120s      # Проверка каждые 2 минуты
  timeout: 3s         # Таймаут проверки
  retries: 3          # Количество попыток
  start_period: 20s   # Время на инициализацию
```

### Зависимости контейнеров

```yaml
depends_on:
  db:
    condition: service_healthy  # Ждем готовности БД
  redis:
    condition: service_healthy  # Ждем готовности Redis
```

### Политика перезапуска

```yaml
restart: unless-stopped  # Автоматический перезапуск при падении
```

### Проверка состояния

```bash
# Статус всех контейнеров
docker-compose ps

# Логи health checks
docker inspect expense_bot_db | grep -A 10 Health

# Мониторинг в реальном времени
docker stats
```

---

## ⏰ Мониторинг через Celery

### Периодические задачи

#### system_health_check (каждые 15 минут)

```python
@shared_task
def system_health_check():
    """Проверка всех компонентов системы"""
    checks = {
        'database': check_database_health(),
        'redis': check_redis_health(),
        'telegram_api': check_telegram_api(),
        'openai_api': check_openai_api(),
        'google_ai_api': check_google_ai_api(),
        'celery_workers': check_celery_workers(),
        'disk_space': check_disk_space(),
        'memory': check_memory_usage(),
    }

    # Отправка алерта при проблемах
    if any(not check['healthy'] for check in checks.values()):
        notify_system_issues(checks)
```

Проверяет:
- ✅ Доступность PostgreSQL
- ✅ Доступность Redis
- ✅ Telegram API
- ✅ AI сервисы (OpenAI/Google)
- ✅ Celery workers
- ✅ Дисковое пространство
- ✅ Использование памяти
- ✅ CPU загрузка

#### collect_daily_analytics (02:00 каждый день)

Собирает статистику для отчетов:
- Активность пользователей
- Финансовые метрики
- Использование AI
- Системные метрики

#### send_daily_admin_report (10:00 каждый день)

Отправляет комплексный отчет администратору

### Очереди Celery

```python
CELERY_TASK_ROUTES = {
    'monitoring.*': {'queue': 'monitoring'},
    'analytics.*': {'queue': 'analytics'},
    'notifications.*': {'queue': 'notifications'},
    # ...
}
```

### Мониторинг Celery

```bash
# Статус workers
celery -A expense_bot inspect active

# Очереди
celery -A expense_bot inspect reserved

# Статистика
celery -A expense_bot inspect stats

# Web интерфейс (Flower)
pip install flower
celery -A expense_bot flower
```

---

## 📝 Логирование

### Структура логгеров

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/django.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'audit': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/audit.log',
            'maxBytes': 10485760,
            'backupCount': 30,  # Храним дольше для аудита
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'expense_bot': {
            'handlers': ['file'],
            'level': 'INFO',
        },
        'audit': {
            'handlers': ['audit'],
            'level': 'INFO',
        },
        'performance': {
            'handlers': ['file'],
            'level': 'INFO',
        },
        'security': {
            'handlers': ['file', 'audit'],
            'level': 'WARNING',
        },
    },
}
```

### Типы логов

- **django.log** - основной лог приложения
- **audit.log** - важные действия пользователей
- **celery.log** - логи фоновых задач
- **nginx/access.log** - HTTP запросы

### Ротация логов

- Автоматическая ротация при достижении 10MB
- Хранение 10 backup файлов
- Аудит логи хранятся 30 дней

---

## 📈 Метрики и аналитика

### Модели для аналитики

```python
class UserAnalytics(models.Model):
    """Ежедневная статистика по пользователям"""
    date = models.DateField()
    total_users = models.IntegerField()
    active_users = models.IntegerField()
    new_users = models.IntegerField()
    retention_7d = models.FloatField()

class AIServiceMetrics(models.Model):
    """Метрики использования AI"""
    date = models.DateField()
    provider = models.CharField(max_length=50)
    requests_count = models.IntegerField()
    tokens_used = models.IntegerField()
    cost_usd = models.DecimalField(max_digits=10, decimal_places=4)
    success_rate = models.FloatField()

class SystemHealthCheck(models.Model):
    """История проверок системы"""
    timestamp = models.DateTimeField()
    component = models.CharField(max_length=50)
    status = models.CharField(max_length=20)
    response_time_ms = models.IntegerField()
    details = models.JSONField()
```

### API endpoint для метрик

```http
GET /health/
```

Возвращает:
```json
{
    "status": "healthy",
    "timestamp": "2024-09-22T10:00:00Z",
    "components": {
        "database": {
            "status": "healthy",
            "response_time_ms": 5
        },
        "redis": {
            "status": "healthy",
            "response_time_ms": 2
        },
        "telegram_api": {
            "status": "healthy",
            "response_time_ms": 150
        }
    },
    "metrics": {
        "active_users_24h": 234,
        "requests_per_minute": 45,
        "error_rate": 0.02
    }
}
```

---

## 🚀 Настройка на сервере

### 1. Обновление .env на сервере

```bash
# Подключение к серверу
ssh batman@80.66.87.178

# Backup текущего .env
cp /home/batman/expense_bot/.env /home/batman/expense_bot/.env.backup_$(date +%Y%m%d_%H%M%S)

# Редактирование .env
nano /home/batman/expense_bot/.env
```

Добавить:
```bash
# Monitoring Bot
MONITORING_BOT_TOKEN=your_monitoring_bot_token
ADMIN_TELEGRAM_ID=your_telegram_id

# Sentry
SENTRY_DSN=https://your_key@your_org.ingest.us.sentry.io/your_project_id
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_PROFILES_SAMPLE_RATE=0.1

# Environment
ENVIRONMENT=production
DEBUG=False
```

### 2. Обновление и перезапуск

```bash
cd /home/batman/expense_bot

# Обновление кода
git pull origin master

# Пересборка контейнеров
docker-compose build --no-cache

# Перезапуск с новыми настройками
docker-compose down && docker-compose up -d

# Проверка логов
docker-compose logs -f bot
```

### 3. Проверка работы мониторинга

```bash
# Проверка health checks
docker-compose ps

# Проверка отправки уведомлений
docker exec expense_bot_app python -c "
from bot.services.admin_notifier import notify_bot_started
import asyncio
asyncio.run(notify_bot_started())
"

# Проверка Sentry (создаст тестовую ошибку)
docker exec expense_bot_web python -c "
import sentry_sdk
sentry_sdk.capture_message('Test message from production')
"
```

### 4. Настройка алертов в Sentry

1. Зайдите в проект на sentry.io
2. Settings → Alerts → Create Alert Rule
3. Настройте правила:
   - При первой ошибке нового типа
   - При росте error rate > 5%
   - При проблемах с производительностью

---

## 🔧 Troubleshooting

### Проблема: Не приходят уведомления в Telegram

1. Проверьте переменные окружения:
```bash
docker exec expense_bot_app env | grep -E "MONITORING_BOT_TOKEN|ADMIN_TELEGRAM_ID"
```

2. Проверьте, что бот может отправлять сообщения:
```bash
curl -X POST "https://api.telegram.org/bot${MONITORING_BOT_TOKEN}/sendMessage" \
  -d "chat_id=${ADMIN_TELEGRAM_ID}" \
  -d "text=Test message"
```

3. Проверьте логи:
```bash
docker logs expense_bot_app | grep admin_notifier
```

### Проблема: Sentry не получает ошибки

1. Проверьте DSN:
```bash
docker exec expense_bot_app python -c "
import os
print('SENTRY_DSN:', os.getenv('SENTRY_DSN'))
print('DEBUG:', os.getenv('DEBUG'))
"
```

2. Проверьте инициализацию:
```bash
docker logs expense_bot_app | grep SENTRY
```

3. Создайте тестовую ошибку:
```python
docker exec expense_bot_app python -c "
1/0  # Должна появиться в Sentry
"
```

### Проблема: Health checks failing

1. Проверьте статус:
```bash
docker inspect expense_bot_db | jq '.[0].State.Health'
```

2. Проверьте логи контейнера:
```bash
docker logs expense_bot_db --tail 50
```

3. Проверьте подключение вручную:
```bash
docker exec expense_bot_db pg_isready -U expense_user
docker exec expense_bot_redis redis-cli ping
```

### Проблема: Celery задачи не выполняются

1. Проверьте workers:
```bash
docker exec expense_bot_celery celery -A expense_bot inspect active
```

2. Проверьте beat schedule:
```bash
docker logs expense_bot_celery_beat --tail 50
```

3. Проверьте очереди:
```bash
docker exec expense_bot_celery celery -A expense_bot inspect reserved
```

---

## 📊 Метрики для отслеживания

### Ключевые метрики (KPIs)

1. **Доступность (Uptime)**
   - Цель: > 99.9%
   - Алерт: при недоступности > 5 минут

2. **Время ответа (Response Time)**
   - P50: < 200ms
   - P95: < 500ms
   - P99: < 1000ms

3. **Error Rate**
   - Цель: < 1%
   - Алерт: при > 5%

4. **Активные пользователи (DAU)**
   - Отслеживание тренда
   - Алерт при падении > 20%

5. **Успешность AI запросов**
   - Цель: > 95%
   - Алерт: при < 90%

### Dashboard рекомендации

Для визуализации метрик можно использовать:
- **Grafana** + Prometheus
- **Datadog** (платный)
- **New Relic** (платный)
- **Встроенный /health endpoint**

---

## 🔒 Безопасность мониторинга

### Защита чувствительных данных

1. **Никогда не логируйте:**
   - Пароли и токены
   - Персональные данные
   - Платежную информацию
   - Содержание личных сообщений

2. **Используйте переменные окружения**
   - Все ключи в .env
   - .env никогда не в git
   - Ротация ключей каждые 3 месяца

3. **Ограничьте доступ**
   - Health endpoint только для внутренней сети
   - Admin bot только для администраторов
   - Sentry проект с 2FA

### Соответствие требованиям

- ✅ GDPR - анонимизация данных пользователей
- ✅ Логирование только необходимого минимума
- ✅ Шифрование чувствительных данных
- ✅ Право на удаление данных

---

## 📚 Дополнительные ресурсы

- [Sentry Django Documentation](https://docs.sentry.io/platforms/python/guides/django/)
- [Docker Health Check Documentation](https://docs.docker.com/engine/reference/builder/#healthcheck)
- [Celery Monitoring Guide](https://docs.celeryproject.org/en/stable/userguide/monitoring.html)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Python Logging Best Practices](https://docs.python.org/3/howto/logging.html)

---

## 📞 Контакты для экстренных случаев

При критических проблемах в production:
1. Проверьте Telegram бот для мониторинга
2. Проверьте Sentry dashboard
3. Проверьте серверные логи
4. Откатитесь на предыдущую версию если необходимо

---

*Последнее обновление: 22.09.2024*
*Версия документации: 1.0.0*