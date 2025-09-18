"""
Тестовый скрипт для проверки обработки доходов
"""
import asyncio
import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from decimal import Decimal
from datetime import date
from expenses.models import Profile, IncomeCategory
from bot.utils.expense_parser import detect_income_intent, parse_income_message
from bot.services.income import create_income


async def test_income_processing():
    """Тест обработки дохода "+5000" """
    
    print("=== Тестирование обработки доходов ===\n")
    
    # Получаем профиль
    try:
        profile = Profile.objects.first()
        if not profile:
            print("[ERROR] Нет профилей в базе данных")
            return
        
        print(f"[OK] Используем профиль: {profile.telegram_id}")
        print(f"[INFO] Валюта профиля: {profile.currency}")
        
        # Тестовые сообщения для проверки
        test_messages = [
            "+5000",
            "+1000 зарплата",
            "+500 кешбек",
            "+10000 премия за проект"
        ]
        
        for msg in test_messages:
            print(f"\n--- Тестируем: '{msg}' ---")
            
            # Проверяем детекцию дохода
            is_income = detect_income_intent(msg)
            print(f"[DETECT] Определено как доход: {is_income}")
            
            if is_income:
                # Парсим доход
                try:
                    parsed = await parse_income_message(
                        msg, 
                        user_id=profile.telegram_id,
                        profile=profile,
                        use_ai=False  # Без AI для тестирования
                    )
                    
                    if parsed:
                        print(f"[PARSED] Результат парсинга:")
                        print(f"  - Сумма: {parsed['amount']}")
                        print(f"  - Описание: {parsed.get('description', 'Нет')}")
                        print(f"  - Категория: {parsed.get('category', 'Не определена')}")
                        print(f"  - Валюта: {parsed.get('currency', 'RUB')}")
                        
                        # Пытаемся создать доход
                        income = await create_income(
                            user_id=profile.telegram_id,
                            amount=Decimal(str(parsed['amount'])),
                            description=parsed.get('description', 'Доход'),
                            income_date=date.today(),
                            currency=parsed.get('currency', 'RUB')
                        )
                        
                        if income:
                            print(f"[SUCCESS] Доход создан с ID: {income.id}")
                            # Удаляем тестовый доход
                            income.delete()
                            print(f"[CLEANUP] Тестовый доход удален")
                        else:
                            print(f"[ERROR] Не удалось создать доход")
                    else:
                        print(f"[ERROR] Не удалось распарсить сообщение")
                        
                except Exception as e:
                    print(f"[ERROR] Ошибка при обработке: {e}")
                    import traceback
                    traceback.print_exc()
                    
        print("\n=== Тест завершен ===")
        
    except Exception as e:
        print(f"[ERROR] Общая ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_income_processing())