#!/bin/bash

# Скрипт диагностики Celery для ExpenseBot
# Запускать на сервере: bash check_celery.sh

echo "================================================"
echo "🔍 ДИАГНОСТИКА CELERY - ExpenseBot"
echo "================================================"
echo "Время: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "1️⃣ ПРОВЕРКА КОНТЕЙНЕРОВ"
echo "------------------------"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "(celery|redis)" || echo -e "${RED}Контейнеры не найдены${NC}"
echo ""

echo "2️⃣ СТАТУС CELERY BEAT"
echo "----------------------"
BEAT_STATUS=$(docker ps | grep expense_bot_celery_beat | grep -c "Up")
if [ "$BEAT_STATUS" -eq 1 ]; then
    echo -e "${GREEN}✅ Celery Beat работает${NC}"
    echo "Последние логи:"
    docker logs expense_bot_celery_beat --tail 5 | grep -E "(Scheduler|beat|task)"
else
    echo -e "${RED}❌ Celery Beat НЕ работает!${NC}"
fi
echo ""

echo "3️⃣ СТАТУС CELERY WORKER"
echo "------------------------"
WORKER_STATUS=$(docker ps | grep "expense_bot_celery" | grep -v "beat" | grep -c "Up")
if [ "$WORKER_STATUS" -eq 1 ]; then
    echo -e "${GREEN}✅ Celery Worker работает${NC}"
    # Проверяем зарегистрированные задачи
    echo "Проверка задач:"
    docker exec expense_bot_celery celery -A expense_bot inspect registered | grep -A2 "send_daily_admin_report" || echo "Задача send_daily_admin_report не найдена!"
else
    echo -e "${RED}❌ Celery Worker НЕ работает!${NC}"
fi
echo ""

echo "4️⃣ ПРОВЕРКА REDIS"
echo "-----------------"
REDIS_PING=$(docker exec expense_bot_redis redis-cli ping 2>/dev/null)
if [ "$REDIS_PING" = "PONG" ]; then
    echo -e "${GREEN}✅ Redis работает${NC}"
    # Проверяем очереди
    echo "Задачи в очередях:"
    docker exec expense_bot_redis redis-cli --raw LLEN celery | xargs -I {} echo "  celery (default): {} задач"
    docker exec expense_bot_redis redis-cli --raw LLEN reports | xargs -I {} echo "  reports: {} задач"
    docker exec expense_bot_redis redis-cli --raw LLEN notifications | xargs -I {} echo "  notifications: {} задач"
else
    echo -e "${RED}❌ Redis НЕ отвечает!${NC}"
fi
echo ""

echo "5️⃣ ПЕРИОДИЧЕСКИЕ ЗАДАЧИ В БД"
echo "-----------------------------"
docker exec expense_bot_web python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()
from django_celery_beat.models import PeriodicTask
tasks = PeriodicTask.objects.filter(enabled=True)
print(f'Активных задач: {tasks.count()}')
for task in tasks:
    print(f'  - {task.name}: {task.task}')
    if 'admin_report' in task.task:
        if task.crontab:
            print(f'    ⏰ Время: {task.crontab.hour}:{task.crontab.minute:02d}')
        if task.last_run_at:
            print(f'    📅 Последний запуск: {task.last_run_at}')
" 2>/dev/null || echo -e "${RED}Ошибка доступа к БД${NC}"
echo ""

echo "6️⃣ ПОСЛЕДНИЕ ОШИБКИ CELERY"
echo "---------------------------"
echo "Beat ошибки:"
docker logs expense_bot_celery_beat 2>&1 | grep -i error | tail -3 || echo "Ошибок не найдено"
echo ""
echo "Worker ошибки:"
docker logs expense_bot_celery 2>&1 | grep -i error | tail -3 || echo "Ошибок не найдено"
echo ""

echo "7️⃣ ПРОВЕРКА ЗАДАЧИ 10:00"
echo "------------------------"
CURRENT_HOUR=$(date +%H)
echo "Текущий час: $CURRENT_HOUR"

docker exec expense_bot_web python -c "
import os, django, pytz
from datetime import datetime
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()
from django_celery_beat.models import PeriodicTask

task = PeriodicTask.objects.filter(task='expense_bot.celery_tasks.send_daily_admin_report').first()
if task:
    print(f'✅ Задача найдена: {task.name}')
    print(f'   Включена: {\"Да\" if task.enabled else \"НЕТ!\"}')
    if task.crontab:
        print(f'   Время: {task.crontab.hour}:{task.crontab.minute:02d}')
    if task.last_run_at:
        moscow_tz = pytz.timezone('Europe/Moscow')
        last_run = task.last_run_at.astimezone(moscow_tz)
        print(f'   Последний запуск: {last_run.strftime(\"%Y-%m-%d %H:%M:%S\")} MSK')
        today = datetime.now(moscow_tz).date()
        if last_run.date() == today:
            print('   ✅ Запускалась сегодня')
        else:
            print('   ⚠️ Сегодня НЕ запускалась!')
else:
    print('❌ Задача НЕ НАЙДЕНА в БД!')
    print('Нужно создать задачу - см. инструкцию ниже')
" 2>/dev/null || echo -e "${RED}Ошибка проверки задачи${NC}"
echo ""

echo "================================================"
echo "📋 РЕКОМЕНДАЦИИ"
echo "================================================"

echo -e "${YELLOW}Если задача не выполняется:${NC}"
echo "1. Проверить, что все контейнеры работают (Up)"
echo "2. Проверить, что задача создана в БД и enabled=True"
echo "3. Проверить timezone (должен быть Europe/Moscow)"
echo "4. Перезапустить Celery Beat:"
echo "   docker-compose restart expense_bot_celery_beat"
echo ""

echo -e "${YELLOW}Для создания задачи в БД:${NC}"
cat << 'EOF'
docker exec -it expense_bot_web python manage.py shell
>>> from django_celery_beat.models import PeriodicTask, CrontabSchedule
>>> from django.utils import timezone
>>> 
>>> schedule, _ = CrontabSchedule.objects.get_or_create(
...     minute=0,
...     hour=10,
...     day_of_week='*',
...     day_of_month='*',
...     month_of_year='*',
...     timezone=timezone.get_current_timezone()
... )
>>> 
>>> PeriodicTask.objects.update_or_create(
...     task='expense_bot.celery_tasks.send_daily_admin_report',
...     defaults={
...         'crontab': schedule,
...         'name': 'Daily Admin Report at 10:00',
...         'queue': 'reports',
...         'enabled': True
...     }
... )
>>> exit()
EOF
echo ""

echo -e "${YELLOW}Для теста задачи вручную:${NC}"
cat << 'EOF'
docker exec -it expense_bot_web python manage.py shell
>>> from expense_bot.celery_tasks import send_daily_admin_report
>>> result = send_daily_admin_report.delay()
>>> print(f"Task ID: {result.id}")
>>> # Проверить результат через несколько секунд
>>> result.get(timeout=30)
>>> exit()
EOF