import os
import sys
import django
import asyncio
from asgiref.sync import sync_to_async

# Принудительно устанавливаем UTF-8 кодировку для Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.utils.expense_parser import parse_expense_message
from expenses.models import Profile, ExpenseCategory
from bot.services.category import get_or_create_category

async def test_cappuccino():
    user_id = 881292737
    
    # Тестируем парсинг
    test_messages = [
        "капучино 200",
        "Капучино 200",
        "кофе капучино 200 руб",
        "купил капучино за 200"
    ]
    
    try:
        profile = await sync_to_async(Profile.objects.get)(telegram_id=user_id)
        print(f"Profile found for user {user_id}")
        
        # Показываем категории пользователя
        categories = await sync_to_async(list)(ExpenseCategory.objects.filter(profile=profile))
        print(f"\nUser categories ({len(categories)}):")
        for cat in categories:
            print(f"  - {cat.name}")
            # Проверяем, содержит ли категория слова "кафе" или "ресторан"
            if any(word in cat.name.lower() for word in ['кафе', 'ресторан', 'кофе']):
                print(f"    ^ This category matches cafe/restaurant keywords!")
        
        print("\n" + "="*50 + "\n")
        
        # Тестируем парсинг каждого сообщения
        for msg in test_messages:
            print(f"\nTesting: '{msg}'")
            
            # Парсим без AI
            result = await parse_expense_message(msg, user_id, profile, use_ai=False)
            if result:
                print(f"  Parser result: category='{result['category']}', amount={result['amount']}")
                
                # Пробуем найти категорию
                category = await get_or_create_category(user_id, result['category'])
                print(f"  Final category: '{category.name}'")
            else:
                print("  Failed to parse")
                
        print("\n" + "="*50 + "\n")
        
        # Теперь с AI
        print("\nTesting with AI categorization:")
        msg = "капучино 200"
        result = await parse_expense_message(msg, user_id, profile, use_ai=True)
        if result:
            print(f"  Parser result: category='{result['category']}', amount={result['amount']}")
            print(f"  AI enhanced: {result.get('ai_enhanced', False)}")
            print(f"  AI provider: {result.get('ai_provider', 'N/A')}")
            print(f"  Confidence: {result.get('confidence', 0)}")
            
            category = await get_or_create_category(user_id, result['category'])
            print(f"  Final category: '{category.name}'")
            
    except Profile.DoesNotExist:
        print(f"Profile not found for user {user_id}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

# Запускаем тест
if __name__ == "__main__":
    asyncio.run(test_cappuccino())