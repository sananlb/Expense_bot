#!/usr/bin/env python
"""
Тестовый скрипт для проверки создания пробной подписки
"""
import os
import sys
import django
import asyncio
from datetime import timedelta

# Добавляем путь к проекту
sys.path.insert(0, '/Users/aleksejnalbantov/Desktop/expense_bot')

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from django.utils import timezone
from expenses.models import Profile, Subscription, Expense, Income


async def test_trial_subscription_logic():
    """
    Тестирует логику создания пробной подписки
    """
    print("\n" + "="*60)
    print("ТЕСТ ЛОГИКИ ПРОБНОЙ ПОДПИСКИ")
    print("="*60)
    
    # Тестовый ID пользователя (используйте реальный ID для проверки)
    test_user_id = 12345678  # Замените на реальный telegram_id
    
    try:
        # Получаем профиль пользователя
        try:
            profile = await Profile.objects.aget(telegram_id=test_user_id)
            print(f"\n✅ Профиль найден: telegram_id={test_user_id}")
            print(f"   - is_beta_tester: {profile.is_beta_tester}")
            print(f"   - accepted_privacy: {profile.accepted_privacy}")
        except Profile.DoesNotExist:
            print(f"\n❌ Профиль не найден для telegram_id={test_user_id}")
            print("   Создайте профиль через бота сначала")
            return
        
        # Проверяем историю трат
        has_expenses = await Expense.objects.filter(profile=profile).aexists()
        print(f"\n📊 Проверка истории:")
        print(f"   - Есть траты: {has_expenses}")
        
        # Проверяем историю доходов
        has_incomes = await Income.objects.filter(profile=profile).aexists()
        print(f"   - Есть доходы: {has_incomes}")
        
        # Проверяем историю подписок
        has_subscription_history = await Subscription.objects.filter(profile=profile).aexists()
        print(f"   - Есть история подписок: {has_subscription_history}")
        
        # Определяем, новый ли пользователь
        is_new_user = not has_expenses and not has_incomes and not has_subscription_history
        print(f"\n🆕 Пользователь новый: {is_new_user}")
        
        # Проверяем существующий пробный период
        existing_trial = await profile.subscriptions.filter(
            type='trial'
        ).aexists()
        print(f"\n🎁 Пробный период:")
        print(f"   - Был ранее пробный период: {existing_trial}")
        
        # Проверяем активную подписку
        has_active_subscription = await profile.subscriptions.filter(
            is_active=True,
            end_date__gt=timezone.now()
        ).aexists()
        print(f"   - Есть активная подписка: {has_active_subscription}")
        
        # Получаем все подписки для детального анализа
        all_subscriptions = await profile.subscriptions.all().acount()
        print(f"   - Всего подписок в истории: {all_subscriptions}")
        
        if all_subscriptions > 0:
            async for sub in profile.subscriptions.all():
                status = "✅ Активна" if sub.is_active and sub.end_date > timezone.now() else "❌ Неактивна"
                print(f"\n     Подписка #{sub.id}:")
                print(f"       - Тип: {sub.get_type_display()}")
                print(f"       - Статус: {status}")
                print(f"       - Начало: {sub.start_date.strftime('%Y-%m-%d %H:%M')}")
                print(f"       - Конец: {sub.end_date.strftime('%Y-%m-%d %H:%M')}")
                print(f"       - is_active: {sub.is_active}")
        
        # Логика создания пробной подписки
        print("\n" + "="*60)
        print("АНАЛИЗ ВОЗМОЖНОСТИ СОЗДАНИЯ ПРОБНОЙ ПОДПИСКИ:")
        print("="*60)
        
        if profile.is_beta_tester:
            print("\n❌ НЕ БУДЕТ СОЗДАНА: Пользователь - бета-тестер")
        elif not is_new_user:
            print("\n❌ НЕ БУДЕТ СОЗДАНА: Пользователь не новый (есть история операций)")
        elif existing_trial:
            print("\n❌ НЕ БУДЕТ СОЗДАНА: Уже был пробный период")
        elif has_active_subscription:
            print("\n❌ НЕ БУДЕТ СОЗДАНА: Уже есть активная подписка")
        else:
            print("\n✅ ДОЛЖНА БЫТЬ СОЗДАНА: Все условия выполнены!")
            print("\nУсловия для создания:")
            print("  1. ✅ Новый пользователь (нет истории операций)")
            print("  2. ✅ Нет активной подписки")
            print("  3. ✅ Никогда не было пробного периода")
            print("  4. ✅ Не бета-тестер")
            
            # Симулируем создание пробной подписки
            print("\n🔧 Симуляция создания пробной подписки...")
            trial_end = timezone.now() + timedelta(days=7)
            print(f"   - Дата окончания: {trial_end.strftime('%Y-%m-%d %H:%M')}")
            print("   - Тип: trial")
            print("   - Сумма: 0")
            print("   - is_active: True")
            
    except Exception as e:
        import traceback
        print(f"\n❌ ОШИБКА: {e}")
        print(traceback.format_exc())


if __name__ == "__main__":
    print("\nЗапуск тестирования логики пробной подписки...")
    print("Замените test_user_id на реальный telegram_id для проверки")
    asyncio.run(test_trial_subscription_logic())