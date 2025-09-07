"""
Тест отображения имени категории
"""
import os
import sys
import django

# Устанавливаем UTF-8 кодировку для Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import ExpenseCategory, Profile

# Тестируем отображение категорий
user_id = 881292737  # Ваш telegram_id

try:
    profile = Profile.objects.get(telegram_id=user_id)
    categories = ExpenseCategory.objects.filter(profile=profile)
    
    print("=" * 60)
    print(f"Категории пользователя {user_id}:")
    print("=" * 60)
    
    for cat in categories:
        print(f"\nКатегория ID: {cat.id}")
        print(f"  name (старое поле): {cat.name}")
        print(f"  name_ru: {cat.name_ru}")
        print(f"  name_en: {cat.name_en}")
        print(f"  icon: '{cat.icon}'")
        print(f"  is_translatable: {cat.is_translatable}")
        print(f"  original_language: {cat.original_language}")
        print(f"  get_display_name('ru'): {cat.get_display_name('ru')}")
        print(f"  get_display_name('en'): {cat.get_display_name('en')}")
        
        # Проверяем helper функцию
        from bot.utils.category_helpers import get_category_display_name
        print(f"  get_category_display_name(cat, 'ru'): {get_category_display_name(cat, 'ru')}")
        
except Profile.DoesNotExist:
    print(f"Профиль для пользователя {user_id} не найден")
except Exception as e:
    print(f"Ошибка: {e}")
    import traceback
    traceback.print_exc()