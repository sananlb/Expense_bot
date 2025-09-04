#!/usr/bin/env python
"""
Тестирование AI системы для доходов
"""
import os
import sys
import django
import asyncio
from decimal import Decimal

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, IncomeCategory, Income, IncomeCategoryKeyword
from bot.services.income import create_income_category
from bot.services.income_categorization import (
    categorize_income,
    generate_keywords_for_income_category,
    learn_from_income_category_change,
    find_category_by_keywords
)
from bot.utils.expense_parser import parse_income_message


async def test_income_ai_system():
    """Тест полной системы AI для доходов"""
    
    print("=" * 60)
    print("ТЕСТ AI СИСТЕМЫ ДЛЯ ДОХОДОВ")
    print("=" * 60)
    
    # 1. Создаем тестового пользователя
    test_user_id = 999999999  # Тестовый ID
    profile, created = Profile.objects.get_or_create(
        telegram_id=test_user_id,
        defaults={'username': 'test_income_ai'}
    )
    print(f"\n1. Профиль пользователя: {'создан' if created else 'найден'}")
    
    # 2. Создаем категории доходов с генерацией ключевых слов
    print("\n2. Создание категорий доходов с ключевыми словами:")
    
    test_categories = [
        ('💼 Зарплата', 'зарплата'),
        ('💻 Фриланс', 'фриланс'),
        ('📈 Инвестиции', 'инвестиции'),
    ]
    
    for full_name, name in test_categories:
        category, created = IncomeCategory.objects.get_or_create(
            profile=profile,
            name=full_name,
            defaults={'is_active': True}
        )
        
        if created:
            # Генерируем ключевые слова
            keywords = await generate_keywords_for_income_category(category, name)
            print(f"   - {full_name}: создано {len(keywords)} ключевых слов")
            if keywords:
                print(f"     Примеры: {', '.join(keywords[:5])}")
        else:
            # Показываем существующие ключевые слова
            existing_keywords = IncomeCategoryKeyword.objects.filter(
                category=category
            ).values_list('keyword', flat=True)[:5]
            print(f"   - {full_name}: уже существует ({len(existing_keywords)} ключевых слов)")
    
    # 3. Тестируем парсинг доходов с AI категоризацией
    print("\n3. Тестирование парсинга доходов с AI:")
    
    test_incomes = [
        "+50000 зарплата за октябрь",
        "получил 10000 за проект",
        "дивиденды 5000",
        "+3000 подработка",
        "премия 25к",
        "возврат налога 13000",
        "+1500 кешбэк",
    ]
    
    for income_text in test_incomes:
        print(f"\n   Текст: '{income_text}'")
        
        # Парсим с использованием AI
        result = await parse_income_message(
            income_text,
            user_id=test_user_id,
            profile=profile,
            use_ai=True
        )
        
        if result:
            print(f"   ✅ Распознано:")
            print(f"      - Сумма: {result['amount']} {result.get('currency', 'RUB')}")
            print(f"      - Описание: {result['description']}")
            print(f"      - Категория: {result.get('category', 'не определена')}")
            print(f"      - AI категоризация: {'Да' if result.get('ai_categorized') else 'Нет'}")
            if result.get('ai_confidence'):
                print(f"      - Уверенность AI: {result['ai_confidence']:.1%}")
        else:
            print(f"   ❌ Не удалось распознать")
    
    # 4. Тестируем прямую AI категоризацию
    print("\n4. Прямая AI категоризация:")
    
    ai_result = await categorize_income(
        "получил гонорар за статью 15000",
        test_user_id,
        profile
    )
    
    if ai_result:
        print(f"   Текст: 'получил гонорар за статью 15000'")
        print(f"   AI результат:")
        print(f"   - Категория: {ai_result.get('category')}")
        print(f"   - Сумма: {ai_result.get('amount')}")
        print(f"   - Описание: {ai_result.get('description')}")
        print(f"   - Уверенность: {ai_result.get('confidence', 0):.1%}")
    
    # 5. Тестируем обучение системы
    print("\n5. Тестирование обучения системы:")
    
    # Создаем тестовый доход
    test_income = Income.objects.create(
        profile=profile,
        amount=Decimal('20000'),
        description="Консультация по проекту",
        category=IncomeCategory.objects.filter(
            profile=profile,
            name__contains='Зарплата'
        ).first()
    )
    
    # Меняем категорию на правильную
    old_category = test_income.category
    new_category = IncomeCategory.objects.filter(
        profile=profile,
        name__contains='Фриланс'
    ).first()
    
    if old_category and new_category:
        await learn_from_income_category_change(
            test_income,
            old_category,
            new_category
        )
        print(f"   ✅ Система обучена: '{test_income.description}'")
        print(f"      {old_category.name} -> {new_category.name}")
        
        # Проверяем что ключевые слова созданы
        new_keywords = IncomeCategoryKeyword.objects.filter(
            category=new_category,
            keyword__icontains='консультация'
        ).exists()
        
        if new_keywords:
            print(f"      Новые ключевые слова добавлены")
    
    # 6. Проверяем поиск по ключевым словам
    print("\n6. Поиск категории по ключевым словам:")
    
    test_texts = [
        "консультация по разработке",
        "зарплата основная",
        "дивиденды от акций"
    ]
    
    for text in test_texts:
        category = await find_category_by_keywords(text, profile)
        if category:
            print(f"   '{text}' -> {category.name}")
        else:
            print(f"   '{text}' -> категория не найдена")
    
    # Очистка тестовых данных
    print("\n7. Очистка тестовых данных...")
    Income.objects.filter(profile=profile).delete()
    IncomeCategoryKeyword.objects.filter(category__profile=profile).delete()
    IncomeCategory.objects.filter(profile=profile).delete()
    
    print("\n✅ Все тесты завершены успешно!")


if __name__ == '__main__':
    # Запускаем асинхронные тесты
    asyncio.run(test_income_ai_system())