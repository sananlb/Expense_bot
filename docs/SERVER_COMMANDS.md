# Команды для сервера ExpenseBot

## Основная информация
- **IP сервера:** 80.66.87.178
- **Пользователь:** batman
- **Путь проекта:** `/home/batman/expense_bot`
- **ВАЖНО:** Все docker команды выполнять из `/home/batman/expense_bot`

## Базовые команды

### Переход в папку проекта (ВСЕГДА ПЕРВЫМ ДЕЛОМ!)
```bash
cd /home/batman/expense_bot
```

### Проверка статуса контейнеров
```bash
cd /home/batman/expense_bot && docker ps | grep expense_bot
```

### Перезапуск контейнеров
```bash
cd /home/batman/expense_bot && docker-compose restart celery celery-beat
```

## Обновление кода на сервере

### 🚀 НОВЫЙ СПОСОБ - Полное обновление одной командой (РЕКОМЕНДУЕТСЯ)
```bash
cd /home/batman/expense_bot && bash scripts/full_update.sh
```
Или еще короче:
```bash
cd /home/batman/expense_bot && bash update.sh
```

Этот скрипт автоматически:
- Остановит контейнеры
- Обновит код из Git
- Обновит лендинг страницу
- Пересоберет Docker образы
- Запустит контейнеры
- Проверит что всё работает

### Старый способ - Полное обновление вручную
```bash
cd /home/batman/expense_bot && \
git fetch origin && \
git reset --hard origin/master && \
docker-compose down && \
docker-compose build --no-cache && \
docker-compose up -d && \
chmod +x scripts/update_landing.sh && \
bash scripts/update_landing.sh
```

### Быстрое обновление (только pull и restart)
```bash
cd /home/batman/expense_bot && \
git pull origin master && \
docker-compose restart app celery web && \
bash scripts/update_landing.sh
```

## Работа с Celery

### Проверка периодических задач в БД
```bash
cd /home/batman/expense_bot && docker exec expense_bot_web python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()
from django_celery_beat.models import PeriodicTask
tasks = PeriodicTask.objects.all()
print(f'Всего задач: {tasks.count()}')
for task in tasks:
    print(f'  {task.name}: {task.enabled}')"
```

### Проверка задачи 10:00 (send_daily_admin_report)
```bash
cd /home/batman/expense_bot && docker exec expense_bot_web python -c "
import os, django, pytz
from datetime import datetime
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()
from django_celery_beat.models import PeriodicTask
task = PeriodicTask.objects.filter(task='expense_bot.celery_tasks.send_daily_admin_report').first()
if task:
    print(f'Задача: {task.name}')
    print(f'Включена: {task.enabled}')
    if task.crontab:
        print(f'Время: {task.crontab.hour}:{task.crontab.minute}')
    if task.last_run_at:
        moscow_tz = pytz.timezone('Europe/Moscow')
        last_run = task.last_run_at.astimezone(moscow_tz)
        print(f'Последний запуск: {last_run.strftime(\"%Y-%m-%d %H:%M:%S\")} MSK')
else:
    print('Задача НЕ найдена!')"
```

### Создание всех периодических задач
```bash
cd /home/batman/expense_bot && docker exec expense_bot_web python manage.py setup_periodic_tasks
```

### Тест задачи send_daily_admin_report вручную
```bash
cd /home/batman/expense_bot && docker exec expense_bot_web python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()
from expense_bot.celery_tasks import send_daily_admin_report
result = send_daily_admin_report.delay()
print(f'Задача запущена: {result.id}')"
```

## Мониторинг логов

### Мониторинг Celery в реальном времени
```bash
cd /home/batman/expense_bot && docker-compose logs -f celery-beat celery
```

### Мониторинг только задачи send_daily_admin_report
```bash
cd /home/batman/expense_bot && docker-compose logs -f celery-beat celery | grep --line-buffered "send_daily"
```

### Мониторинг ошибок Celery
```bash
cd /home/batman/expense_bot && docker-compose logs -f celery celery-beat | grep --line-buffered -E "(ERROR|CRITICAL|Exception)"
```

### Последние 100 строк логов Celery
```bash
cd /home/batman/expense_bot && docker logs expense_bot_celery --tail 100
```

### Последние 100 строк логов Celery Beat
```bash
cd /home/batman/expense_bot && docker logs expense_bot_celery_beat --tail 100
```

## Работа с Django

### Django shell
```bash
cd /home/batman/expense_bot && docker exec -it expense_bot_web python manage.py shell
```

### Создание суперпользователя
```bash
cd /home/batman/expense_bot && docker exec -it expense_bot_web python manage.py createsuperuser
```

### Миграции
```bash
cd /home/batman/expense_bot && docker exec expense_bot_web python manage.py migrate
```

### Проверка настроек
```bash
cd /home/batman/expense_bot && docker exec expense_bot_web python -c "
from django.conf import settings
print(f'DEBUG: {settings.DEBUG}')
print(f'ADMIN_TELEGRAM_ID: {settings.ADMIN_TELEGRAM_ID}')
print(f'TIME_ZONE: {settings.TIME_ZONE}')
print(f'USE_TZ: {settings.USE_TZ}')
print(f'CELERY_TIMEZONE: {settings.CELERY_TIMEZONE}')"
```

## Работа с базой данных

### Подключение к PostgreSQL
```bash
cd /home/batman/expense_bot && docker exec -it expense_bot_db psql -U batman -d expense_bot
```

### Проверка таблиц Celery Beat
```bash
cd /home/batman/expense_bot && docker exec expense_bot_db psql -U batman -d expense_bot -c "SELECT name, enabled, last_run_at FROM django_celery_beat_periodictask;"
```

## Redis

### Проверка Redis
```bash
cd /home/batman/expense_bot && docker exec expense_bot_redis redis-cli ping
```

### Проверка очередей
```bash
cd /home/batman/expense_bot && docker exec expense_bot_redis redis-cli LLEN celery
```

### Очистка очередей (ОСТОРОЖНО!)
```bash
cd /home/batman/expense_bot && docker exec expense_bot_redis redis-cli FLUSHALL
```

## Диагностика проблем

### Полная диагностика Celery
```bash
cd /home/batman/expense_bot && bash scripts/check_celery.sh
```

### Проверка всех контейнеров
```bash
cd /home/batman/expense_bot && docker-compose ps
```

### Перезапуск всей системы
```bash
cd /home/batman/expense_bot && docker-compose down && docker-compose up -d
```

### Пересборка контейнеров
```bash
cd /home/batman/expense_bot && docker-compose down && docker-compose build --no-cache && docker-compose up -d
```

## Мониторинг задачи 10:00 утра

### Создать скрипт мониторинга для задачи 10:00
```bash
cd /home/batman/expense_bot && cat > monitor_10am.sh << 'EOF'
#!/bin/bash
echo "====================================="
echo "Мониторинг задачи send_daily_admin_report"
echo "Время сервера: $(date)"
echo "====================================="
docker-compose logs -f celery-beat celery 2>&1 | grep --line-buffered -E "(send_daily_admin_report|ERROR|succeeded|failed|received)" | while read line; do
    echo "[$(date '+%H:%M:%S')] $line"
done
EOF
chmod +x monitor_10am.sh
./monitor_10am.sh
```

### Простой мониторинг в одну строку
```bash
cd /home/batman/expense_bot && docker-compose logs -f celery-beat celery 2>&1 | grep --line-buffered "send_daily"
```

## Быстрые проверки

### Проверить что Celery работает
```bash
cd /home/batman/expense_bot && docker exec expense_bot_celery celery -A expense_bot inspect active
```

### Проверить зарегистрированные задачи
```bash
cd /home/batman/expense_bot && docker exec expense_bot_celery celery -A expense_bot inspect registered | grep send_daily
```

### Проверить запланированные задачи
```bash
cd /home/batman/expense_bot && docker exec expense_bot_celery celery -A expense_bot inspect scheduled
```

## ВАЖНЫЕ ЗАМЕЧАНИЯ

1. **ВСЕГДА** начинайте с `cd /home/batman/expense_bot`
2. **НЕ** выполняйте docker команды из домашней директории
3. **НЕ** редактируйте файлы на сервере напрямую
4. Все изменения делайте локально и пушьте через Git
5. После `git pull` всегда делайте `docker-compose restart` соответствующих контейнеров

## Типичные проблемы и решения

### "Can't find docker-compose.yml"
```bash
cd /home/batman/expense_bot
```

### Контейнер не запускается
```bash
cd /home/batman/expense_bot && docker logs expense_bot_[имя_контейнера] --tail 50
```

### Задачи Celery не выполняются
```bash
cd /home/batman/expense_bot && docker-compose restart celery celery-beat
```