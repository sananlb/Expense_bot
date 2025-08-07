"""
Тест двухшагового парсинга расходов
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

async def test_two_step_parsing():
    """Тестируем двухшаговый парсинг как в реальном сценарии"""
    
    from bot.utils.expense_parser import parse_expense_message
    from expenses.models import Profile
    
    # Находим пользователя
    user_id = 881292737
    profile = await Profile.objects.aget(telegram_id=user_id)
    
    # Тестовые случаи двухшагового ввода
    test_cases = [
        ("Макароны", "200"),
        ("Кофе в кафе", "350"),
        ("Бензин", "3500"),
        ("Такси домой", "650")
    ]
    
    for description, amount_text in test_cases:
        print(f"\n=== Тест: '{description}' -> '{amount_text}' ===")
        
        # Имитируем двухшаговый ввод как в handle_amount_clarification
        
        # 1. Парсим сумму
        parsed_amount = await parse_expense_message(
            amount_text, 
            user_id=user_id, 
            profile=profile, 
            use_ai=False
        )
        
        if parsed_amount:
            print(f"  Распознана сумма: {parsed_amount['amount']} {parsed_amount.get('currency', 'RUB')}")
        else:
            print(f"  Ошибка: не удалось распознать сумму из '{amount_text}'")
            continue
        
        # 2. Объединяем описание и сумму для полного парсинга с AI
        full_text = f"{description} {amount_text}"
        print(f"  Полный текст для парсинга: '{full_text}'")
        
        parsed_full = await parse_expense_message(
            full_text, 
            user_id=user_id, 
            profile=profile, 
            use_ai=True
        )
        
        if parsed_full:
            print(f"  Результат парсинга:")
            print(f"    - Категория: {parsed_full.get('category', 'не определена')}")
            print(f"    - Описание: {parsed_full.get('description', 'не определено')}")
            print(f"    - Сумма: {parsed_full['amount']} {parsed_full.get('currency', 'RUB')}")
            print(f"    - Уверенность: {parsed_full.get('confidence', 0)}")
            if parsed_full.get('ai_enhanced'):
                print(f"    - AI улучшено: Да (провайдер: {parsed_full.get('ai_provider', 'unknown')})")
        else:
            print(f"  Ошибка: парсинг не удался")

if __name__ == "__main__":
    asyncio.run(test_two_step_parsing())