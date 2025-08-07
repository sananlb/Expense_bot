"""
Тест AI категоризации для отладки
"""
import asyncio
import os
import sys
import django
import codecs

# Настройка вывода UTF-8
sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

import logging
logging.basicConfig(level=logging.INFO)

async def test_ai_categorization():
    """Тестируем AI категоризацию напрямую"""
    
    from bot.services.ai_selector import get_service
    from expenses.models import Profile, ExpenseCategory
    
    # Находим пользователя
    user_id = 881292737
    profile = await Profile.objects.aget(telegram_id=user_id)
    
    # Получаем категории пользователя
    from asgiref.sync import sync_to_async
    category_names = await sync_to_async(list)(
        ExpenseCategory.objects.filter(profile=profile).values_list('name', flat=True)
    )
    
    # Убираем эмоджи для вывода
    clean_names = []
    for name in category_names:
        clean_name = ''.join(c for c in name if ord(c) < 128)
        clean_names.append(clean_name.strip() if clean_name.strip() else name[:10])
    print(f"User categories ({len(category_names)} total): {clean_names[:5]}...")
    
    # Получаем AI сервис
    ai_service = get_service('categorization')
    print(f"Используем AI сервис: {ai_service.__class__.__name__}")
    
    # Тестируем категоризацию для "Макароны"
    test_cases = [
        ("Макароны", 200),
        ("Кофе", 150),
        ("Бензин", 3000),
        ("Такси", 500)
    ]
    
    for text, amount in test_cases:
        print(f"\nTest: '{text}' ({amount} rub)")
        
        result = await ai_service.categorize_expense(
            text=text,
            amount=amount,
            currency='RUB',
            categories=category_names,
            user_context={'recent_categories': category_names[:3]}
        )
        
        if result:
            # Убираем эмоджи из названия категории для вывода
            cat_clean = ''.join(c for c in result['category'] if ord(c) < 128).strip()
            print(f"  Category: {cat_clean if cat_clean else result['category'][:10]}")
            print(f"  Confidence: {result['confidence']}")
            reasoning = result.get('reasoning', 'not specified')
            if reasoning:
                # Убираем не-ASCII символы из обоснования
                reasoning_clean = ''.join(c for c in reasoning if ord(c) < 128)
                print(f"  Reasoning: {reasoning_clean[:100]}...")
        else:
            print(f"  Error: AI failed to categorize")

if __name__ == "__main__":
    asyncio.run(test_ai_categorization())