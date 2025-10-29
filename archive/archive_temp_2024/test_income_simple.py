#!/usr/bin/env python
"""
Простой тест создания и удаления категорий доходов
"""
import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, IncomeCategory, IncomeCategoryKeyword


def test_income_categories():
    """Тест работы с категориями доходов"""
    
    print("=" * 60)
    print("ТЕСТ КАТЕГОРИЙ ДОХОДОВ")
    print("=" * 60)
    
    # 1. Создаем тестового пользователя
    test_user_id = 999999999
    profile, created = Profile.objects.get_or_create(
        telegram_id=test_user_id,
        defaults={'language_code': 'ru', 'timezone': 'UTC'}
    )
    print(f"\n1. Профиль: {'создан' if created else 'найден'}")
    
    # 2. Создаем категорию доходов
    category, created = IncomeCategory.objects.get_or_create(
        profile=profile,
        name='💼 Тестовая категория',
        defaults={'is_active': True}
    )
    print(f"2. Категория доходов: {'создана' if created else 'найдена'}")
    
    # 3. Добавляем ключевые слова
    keywords = ['тест', 'проверка', 'доход']
    for kw in keywords:
        keyword, created = IncomeCategoryKeyword.objects.get_or_create(
            category=category,
            keyword=kw,
            defaults={'normalized_weight': 1.0}
        )
        print(f"   - Ключевое слово '{kw}': {'создано' if created else 'существует'}")
    
    # 4. Проверяем что ключевые слова связаны с категорией
    kw_count = IncomeCategoryKeyword.objects.filter(category=category).count()
    print(f"3. Всего ключевых слов для категории: {kw_count}")
    
    # 5. Удаляем категорию (должны удалиться и ключевые слова)
    category.delete()
    print("4. Категория удалена")
    
    # 6. Проверяем что ключевые слова тоже удалились
    remaining_keywords = IncomeCategoryKeyword.objects.filter(
        category__profile=profile
    ).count()
    print(f"5. Оставшихся ключевых слов: {remaining_keywords}")
    
    # 7. Очистка
    Profile.objects.filter(telegram_id=test_user_id).delete()
    print("6. Профиль удален")
    
    print("\n[OK] Тест завершен успешно!")


if __name__ == '__main__':
    test_income_categories()