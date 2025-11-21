"""
Скрипт для проверки языка пользователя в БД
"""
import os
import sys
import django

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from expenses.models import Profile


def check_user_language(telegram_id: int):
    """Проверить язык пользователя в БД"""
    print(f"\n=== Проверка языка пользователя telegram_id={telegram_id} ===\n")

    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        print(f"✅ Профиль найден:")
        print(f"   - ID в БД: {profile.id}")
        print(f"   - Telegram ID: {profile.telegram_id}")
        print(f"   - language_code: '{profile.language_code}'")
        print(f"   - currency: '{profile.currency}'")
        print(f"   - timezone: '{profile.timezone}'")
        print(f"   - is_active: {profile.is_active}")
        print(f"   - created_at: {profile.created_at}")
        print(f"   - updated_at: {profile.updated_at}")

        # Проверяем что язык действительно английский
        if profile.language_code == 'en':
            print(f"\n✅ ЯЗЫК УСТАНОВЛЕН ПРАВИЛЬНО: 'en'")
        elif profile.language_code == 'ru':
            print(f"\n⚠️ ПРОБЛЕМА: Язык в БД 'ru', но должен быть 'en'")
        else:
            print(f"\n❌ НЕОЖИДАННОЕ ЗНАЧЕНИЕ: language_code='{profile.language_code}'")

    except Profile.DoesNotExist:
        print(f"❌ Профиль с telegram_id={telegram_id} НЕ НАЙДЕН в БД")
        return

    print("\n" + "=" * 60)


if __name__ == "__main__":
    # Укажите telegram_id пользователя для проверки
    # Пример: python check_user_language.py 1190249363

    if len(sys.argv) > 1:
        telegram_id = int(sys.argv[1])
    else:
        print("⚠️ Не указан telegram_id пользователя")
        print("Использование: python check_user_language.py <telegram_id>")
        print("\nПримеры:")
        print("  python check_user_language.py 1190249363")
        print("  python check_user_language.py 987654321")
        sys.exit(1)

    check_user_language(telegram_id)
