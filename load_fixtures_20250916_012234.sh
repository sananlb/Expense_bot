#!/bin/bash
# Скрипт для загрузки fixtures в PostgreSQL через Django

echo "Загрузка полной миграции данных из SQLite..."

# Останавливаем контейнеры
echo "Остановка контейнеров..."
docker-compose down

# Очищаем PostgreSQL базу (ОСТОРОЖНО!)
echo "Очистка PostgreSQL базы..."
docker-compose run --rm web python manage.py flush --noinput

# Применяем миграции
echo "Применение миграций..."
docker-compose run --rm web python manage.py migrate

# Загружаем fixtures
echo "Загрузка данных..."
docker-compose run --rm web python manage.py loaddata complete_migration_fixtures_20250916_012234.json

# Проверяем результат
echo "Проверка миграции..."
docker-compose run --rm web python manage.py shell -c "
from expenses.models import Profile, Expense
profile = Profile.objects.filter(telegram_id=881292737).first()
if profile:
    print(f'Пользователь 881292737 найден: Profile ID {profile.id}')
    expenses = Expense.objects.filter(profile=profile).count()
    print(f'Количество трат: {expenses}')
    print(f'View scope: {profile.settings.view_scope if hasattr(profile, "settings") else "НЕТ НАСТРОЕК"}')
    if profile.household:
        print(f'Домохозяйство: {profile.household.name} (ID: {profile.household.id})')
        household_expenses = Expense.objects.filter(profile__household=profile.household).count()
        print(f'Всего трат в домохозяйстве: {household_expenses}')
else:
    print('ОШИБКА: Пользователь 881292737 не найден!')
"

# Запускаем контейнеры
echo "Запуск контейнеров..."
docker-compose up -d

echo "Миграция завершена!"
