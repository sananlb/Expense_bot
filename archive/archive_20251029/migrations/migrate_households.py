import sqlite3
from datetime import datetime
from expenses.models import Profile, Household, UserSettings

print("=" * 50)
print("МИГРАЦИЯ ДОМОХОЗЯЙСТВ И НАСТРОЕК")
print("=" * 50)

# Подключаемся к SQLite
conn = sqlite3.connect('/tmp/expense_bot.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 1. МИГРАЦИЯ ДОМОХОЗЯЙСТВ
print("\n1. Мигрируем домохозяйства...")
cursor.execute("SELECT * FROM households")
households = cursor.fetchall()
household_map = {}

for row in households:
    try:
        household, created = Household.objects.update_or_create(
            id=row['id'],
            defaults={
                'name': row['name'] or f"Household {row['id']}",
                'is_active': bool(row['is_active']) if row['is_active'] is not None else True,
                'max_members': row['max_members'] or 5,
            }
        )
        household_map[row['id']] = household
        print(f"  {'Создано' if created else 'Обновлено'} домохозяйство: {household.name} (ID={household.id})")
    except Exception as e:
        print(f"  ❌ Ошибка с домохозяйством {row['id']}: {e}")

print(f"Итого домохозяйств: {len(household_map)}")

# 2. ОБНОВЛЯЕМ ПРОФИЛИ - привязываем к домохозяйствам
print("\n2. Обновляем профили с домохозяйствами...")
cursor.execute("SELECT id, telegram_id, household_id FROM users_profile WHERE household_id IS NOT NULL")
profiles_with_households = cursor.fetchall()

for row in profiles_with_households:
    try:
        profile = Profile.objects.get(telegram_id=row['telegram_id'])
        household = household_map.get(row['household_id'])

        if household:
            profile.household = household
            profile.save()
            print(f"  ✓ Профиль {row['telegram_id']} привязан к домохозяйству {household.name}")
        else:
            print(f"  ⚠ Домохозяйство {row['household_id']} не найдено для профиля {row['telegram_id']}")

    except Profile.DoesNotExist:
        print(f"  ❌ Профиль {row['telegram_id']} не найден в PostgreSQL")
    except Exception as e:
        print(f"  ❌ Ошибка с профилем {row['telegram_id']}: {e}")

# 3. МИГРАЦИЯ НАСТРОЕК ПОЛЬЗОВАТЕЛЕЙ
print("\n3. Мигрируем настройки пользователей...")
cursor.execute("SELECT * FROM users_settings")
settings = cursor.fetchall()

# Проверяем, какие поля есть в таблице
if settings:
    columns = list(settings[0].keys())
    print(f"  Найдены поля: {columns}")

for row in settings:
    try:
        profile = Profile.objects.get(telegram_id=row['profile_id'])

        settings_data = {
            'profile': profile,
        }

        # Добавляем поля, если они есть
        if 'view_scope' in row.keys():
            settings_data['view_scope'] = row['view_scope'] or 'personal'
        if 'notifications_enabled' in row.keys():
            settings_data['notifications_enabled'] = bool(row['notifications_enabled'])
        if 'language' in row.keys():
            settings_data['language'] = row['language'] or 'ru'

        user_settings, created = UserSettings.objects.update_or_create(
            profile=profile,
            defaults=settings_data
        )

        print(f"  {'Создан' if created else 'Обновлен'} UserSettings для {profile.telegram_id}")
        if 'view_scope' in row.keys():
            print(f"    view_scope: {row['view_scope']}")

    except Profile.DoesNotExist:
        print(f"  ❌ Профиль {row['profile_id']} не найден")
    except Exception as e:
        print(f"  ❌ Ошибка с настройками: {e}")

# 4. ПРОВЕРЯЕМ РЕЗУЛЬТАТ
print("\n" + "=" * 50)
print("ПРОВЕРКА РЕЗУЛЬТАТОВ")
print("=" * 50)

# Проверяем пользователя 881292737
try:
    profile = Profile.objects.get(telegram_id=881292737)
    print(f"\nПользователь 881292737:")
    print(f"  Profile ID: {profile.id}")
    print(f"  Household: {profile.household}")
    print(f"  Household ID: {profile.household_id}")

    try:
        settings = UserSettings.objects.get(profile=profile)
        print(f"  UserSettings найдены")
        # Проверяем атрибуты
        for attr in ['view_scope', 'notifications_enabled', 'language']:
            if hasattr(settings, attr):
                print(f"    {attr}: {getattr(settings, attr)}")
    except UserSettings.DoesNotExist:
        print(f"  UserSettings НЕ найдены")

    # Проверяем расходы
    from expenses.models import Expense
    expenses = Expense.objects.filter(profile=profile).count()
    print(f"  Расходов: {expenses}")

    # Если есть домохозяйство, проверяем других участников
    if profile.household:
        members = Profile.objects.filter(household=profile.household)
        print(f"\nУчастники домохозяйства '{profile.household.name}':")
        for member in members:
            exp_count = Expense.objects.filter(profile=member).count()
            print(f"  - {member.telegram_id}: {exp_count} расходов")

except Profile.DoesNotExist:
    print("❌ Профиль 881292737 не найден!")

conn.close()

print("\n✅ Миграция завершена!")
print("Перезапустите бота: docker-compose restart bot")