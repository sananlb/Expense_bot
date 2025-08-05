import os
import sys
import django

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import ExpenseCategory, Profile

# ID пользователя для тестирования
user_id = 881292737

try:
    profile = Profile.objects.get(telegram_id=user_id)
    print(f"Profile found for user {user_id}")
    
    categories = ExpenseCategory.objects.filter(profile=profile)
    print(f"\nCategories ({categories.count()}):")
    for cat in categories:
        # Печатаем без эмодзи, чтобы избежать проблем с кодировкой
        name_clean = cat.name.encode('ascii', 'ignore').decode('ascii')
        print(f"  {cat.id}: {name_clean} (full: {repr(cat.name)})")
        
except Profile.DoesNotExist:
    print(f"Profile not found for user {user_id}")
    print("Creating profile with default categories...")
    from bot.services.category import create_default_categories_sync
    if create_default_categories_sync(user_id):
        print("Default categories created!")