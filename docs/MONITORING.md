# 📊 Система мониторинга ExpenseBot

## 📋 Содержание
1. [Обзор системы](#обзор-системы)
2. [Компоненты мониторинга](#компоненты-мониторинга)
3. [Метрики и показатели](#метрики-и-показатели)
4. [Настройка и конфигурация](#настройка-и-конфигурация)
5. [Работа с логами](#работа-с-логами)
6. [Алерты и уведомления](#алерты-и-уведомления)
7. [Дашборды и отчеты](#дашборды-и-отчеты)
8. [Troubleshooting](#troubleshooting)

## 🎯 Обзор системы

Система мониторинга ExpenseBot обеспечивает полный контроль над состоянием приложения, производительностью и поведением пользователей. Мониторинг работает на нескольких уровнях:

- **Инфраструктурный уровень**: Docker контейнеры, БД, Redis
- **Приложение**: Django, Telegram Bot, Celery
- **Бизнес-метрики**: пользователи, подписки, транзакции
- **Внешние сервисы**: OpenAI, Google AI, Telegram API

## 🔧 Компоненты мониторинга

### 1. Middleware для логирования

#### LoggingMiddleware (`bot/middlewares/logging_middleware.py`)
- **Назначение**: Логирование всех запросов к боту
- **Метрики**:
  - Количество запросов (total, по типам)
  - Время обработки запросов
  - Медленные запросы (>2 сек)
  - Статистика каждые 1000 запросов

#### ActivityTrackerMiddleware (`bot/middleware/activity_tracker.py`)
- **Назначение**: Отслеживание активности пользователей
- **Функции**:
  - Подсчет уникальных пользователей
  - Детекция подозрительной активности (>100 запросов/час)
  - Сбор ошибок с контекстом
  - Автоматические алерты администратору

#### RateLimitMiddleware
- **Назначение**: Защита от спама
- **Лимиты**:
  - 30 сообщений в минуту
  - 500 сообщений в час
- **Действия**: Блокировка + уведомление админа

### 2. Система логирования

#### Конфигурация (settings.py)
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/expense_bot.log',
            'maxBytes': 15728640,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}
```

#### Основные логгеры
- `expense_bot` - основной логгер приложения
- `audit` - аудит важных действий (только в файл)
- `performance` - метрики производительности
- `security` - события безопасности

### 3. Sentry для отслеживания ошибок

#### Конфигурация
```python
# settings.py
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

sentry_logging = LoggingIntegration(
    level=logging.INFO,        # Capture info and above as breadcrumbs
    event_level=logging.ERROR   # Send errors as events
)

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[
        DjangoIntegration(),
        CeleryIntegration(),
        RedisIntegration(),
        sentry_logging,
    ],
    traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
    profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1")),
    environment=os.getenv("ENVIRONMENT", "production"),
    before_send=filter_sensitive_data,
)
```

### 4. Модели для аналитики

#### UserAnalytics (`expenses/models.py`)
Ежедневная статистика по каждому пользователю:
- Количество сообщений
- Использованные команды
- Добавленные расходы
- AI категоризации
- Ошибки
- Время активности

#### AIServiceMetrics (`expenses/models.py`)
Метрики работы AI сервисов:
- Время ответа
- Использованные токены
- Успешность запросов
- Типы ошибок

### 5. Health Check Endpoint

#### Endpoint: `/health/`
Проверяет состояние всех критических компонентов:
- PostgreSQL соединение
- Redis доступность
- Telegram API
- OpenAI API
- Google AI API
- Celery workers
- Свободное место на диске

#### Формат ответа:
```json
{
    "status": "healthy",
    "timestamp": "2024-01-15T10:30:00Z",
    "checks": {
        "database": {"status": "up", "response_time": 0.023},
        "redis": {"status": "up", "response_time": 0.001},
        "telegram_api": {"status": "up", "response_time": 0.145},
        "openai_api": {"status": "up", "response_time": 0.534},
        "google_ai_api": {"status": "up", "response_time": 0.423},
        "celery": {"status": "up", "workers": 4},
        "disk_space": {"status": "up", "free_gb": 25.4}
    }
}
```

## 📈 Метрики и показатели

### Системные метрики
- **CPU использование** по контейнерам
- **RAM использование** по контейнерам
- **Размер БД** и скорость роста
- **Redis память** и количество ключей
- **Очередь Celery** (размер, задержки)

### Метрики производительности
- **Response Time** (P50, P95, P99)
- **Throughput** (запросов в секунду)
- **Error Rate** (% ошибок)
- **Slow Queries** в PostgreSQL
- **Cache Hit Rate** в Redis

### Бизнес-метрики
- **DAU/WAU/MAU** (Daily/Weekly/Monthly Active Users)
- **Новые регистрации** за период
- **Retention Rate** (1d, 7d, 30d)
- **Конверсия** trial → paid
- **ARPU** (Average Revenue Per User)
- **Churn Rate** (отток пользователей)
- **Feature Adoption** (использование функций)

### AI сервисы метрики
- **Время ответа** по сервисам (OpenAI, Google)
- **Токены** использованные за период
- **Стоимость** запросов
- **Error Rate** по типам ошибок
- **Fallback Rate** (переключение между сервисами)

## ⚙️ Настройка и конфигурация

### Переменные окружения (.env)
```bash
# Мониторинг
MONITORING_BOT_TOKEN=your_monitoring_bot_token
ADMIN_TELEGRAM_ID=your_admin_id

# Sentry
SENTRY_DSN=https://xxx@sentry.io/yyy
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_PROFILES_SAMPLE_RATE=0.1

# Логирование
DJANGO_LOG_LEVEL=INFO
LOG_FILE_MAX_SIZE=15728640  # 15MB
LOG_FILE_BACKUP_COUNT=10

# Алерты
ALERT_SUSPICIOUS_ACTIVITY_THRESHOLD=100  # запросов в час
ALERT_ERROR_THRESHOLD=5  # ошибок подряд
ALERT_SLOW_REQUEST_THRESHOLD=2  # секунд
```

### Настройка уведомлений администратору
```python
# bot/services/admin_notifier.py
ADMIN_ALERTS = {
    'suspicious_activity': True,
    'multiple_errors': True,
    'rate_limit_hit': True,
    'subscription_expired': True,
    'low_disk_space': True,
    'high_memory_usage': True,
    'api_failures': True,
}
```

## 📁 Работа с логами

### Расположение логов
- **Основной лог**: `/logs/expense_bot.log`
- **Celery лог**: `/logs/celery.log`
- **Django лог**: `/logs/django.log`
- **Audit лог**: `/logs/audit.log`

### Ротация логов
Автоматическая ротация при достижении 15MB, хранение 10 последних файлов.

### Полезные команды
```bash
# Просмотр последних ошибок
tail -f logs/expense_bot.log | grep ERROR

# Поиск по user_id
grep "user_id=123456" logs/expense_bot.log

# Статистика ошибок за день
grep "$(date +%Y-%m-%d)" logs/expense_bot.log | grep ERROR | wc -l

# Медленные запросы
grep "Slow request" logs/expense_bot.log

# Подозрительная активность
grep "Suspicious activity" logs/expense_bot.log
```

## 🔔 Алерты и уведомления

### Автоматические алерты
1. **Подозрительная активность** - >100 запросов/час от пользователя
2. **Множественные ошибки** - >5 ошибок подряд
3. **Rate limit** - блокировка пользователя
4. **Медленные запросы** - >2 секунд обработки
5. **Сбой AI сервиса** - недоступность OpenAI/Google
6. **Низкое место на диске** - <1GB свободно
7. **Высокое использование памяти** - >90% RAM

### Формат уведомлений
```
🚨 ALERT: Suspicious Activity
User: @username (ID: 123456)
Activity: 150 requests in last hour
Time: 2024-01-15 10:30:00 UTC
Action: User temporarily blocked
```

## 📊 Дашборды и отчеты

### Ежедневный отчет администратору
Отправляется каждый день в 10:00 UTC:
- Общая статистика пользователей
- Активность за последние 24 часа
- Новые регистрации и подписки
- Финансовые показатели
- Топ-10 активных пользователей
- Ошибки и проблемы
- Производительность системы

### Еженедельный отчет
Отправляется по понедельникам:
- Сравнение с предыдущей неделей
- Тренды роста
- Анализ retention
- Популярные функции
- Рекомендации по оптимизации

### Месячный отчет
Отправляется 1 числа каждого месяца:
- Полная статистика за месяц
- Финансовые результаты
- Анализ оттока пользователей
- Прогноз на следующий месяц
- Технические метрики

## 🔍 Troubleshooting

### Частые проблемы и решения

#### 1. Логи не пишутся
```bash
# Проверить права доступа
ls -la logs/
# Должно быть: drwxrwxr-x

# Исправить права
chmod 775 logs/
chmod 664 logs/*.log
```

#### 2. Не приходят уведомления админу
```bash
# Проверить переменные окружения
echo $MONITORING_BOT_TOKEN
echo $ADMIN_TELEGRAM_ID

# Проверить работу monitoring bot
python manage.py test_monitoring
```

#### 3. Переполнение диска логами
```bash
# Очистить старые логи
find logs/ -name "*.log.*" -mtime +30 -delete

# Настроить logrotate
sudo nano /etc/logrotate.d/expense_bot
```

#### 4. Высокая нагрузка от мониторинга
```python
# Уменьшить частоту сбора метрик
# settings.py
METRICS_COLLECTION_INTERVAL = 60  # секунд
SENTRY_TRACES_SAMPLE_RATE = 0.05  # 5% вместо 10%
```

## 📚 Дополнительные ресурсы

- [Django Logging Documentation](https://docs.djangoproject.com/en/4.2/topics/logging/)
- [Sentry Python SDK](https://docs.sentry.io/platforms/python/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
- [Grafana Dashboard Examples](https://grafana.com/grafana/dashboards/)

## 🆘 Контакты для экстренных случаев

- **Системный администратор**: @admin_username
- **Разработчик**: @developer_username
- **Telegram для алертов**: @monitoring_bot

---
*Последнее обновление: 2024-01-15*