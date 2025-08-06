#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест системы весов ключевых слов
"""

import os
import sys
import django

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import ExpenseCategory, CategoryKeyword, Expense, Profile
from expense_bot.celery_tasks import update_keywords_weights, extract_words_from_description
from bot.utils.expense_categorizer import categorize_expense_smart
from datetime import datetime


def test_keyword_extraction():
    """Тест извлечения слов из описания"""
    print("\n=== Тест извлечения слов ===")
    
    test_cases = [
        "кофе, вода и чебурек 450",
        "купил молоко за 85р в магните",
        "такси до дома 350 рублей",
    ]
    
    for text in test_cases:
        words = extract_words_from_description(text)
        print(f"'{text}' -> {words}")


def test_weight_update():
    """Тест обновления весов при изменении категории"""
    print("\n=== Тест обновления весов ===")
    
    # Получаем тестового пользователя
    try:
        profile = Profile.objects.get(telegram_id=123456789)  # Замените на реальный ID
    except Profile.DoesNotExist:
        print("Создаем тестового пользователя...")
        profile = Profile.objects.create(
            telegram_id=123456789,
            username="test_user"
        )
    
    # Создаем категории если их нет
    cafe_cat, _ = ExpenseCategory.objects.get_or_create(
        profile=profile,
        name="Кафе и рестораны",
        defaults={'icon': '☕'}
    )
    
    market_cat, _ = ExpenseCategory.objects.get_or_create(
        profile=profile,
        name="Супермаркеты",
        defaults={'icon': '🛒'}
    )
    
    # Создаем тестовый расход
    expense = Expense.objects.create(
        profile=profile,
        description="кофе и вода",
        amount=250,
        category=cafe_cat,
        expense_date=datetime.now().date()
    )
    
    print(f"Создан расход: {expense.description} в категории {expense.category.name}")
    
    # Симулируем изменение категории пользователем
    print("Пользователь меняет категорию на 'Супермаркеты'...")
    
    # Вызываем задачу обновления весов
    update_keywords_weights(
        expense_id=expense.id,
        old_category_id=cafe_cat.id,
        new_category_id=market_cat.id
    )
    
    # Проверяем ключевые слова
    print("\nКлючевые слова для 'Супермаркеты':")
    for kw in CategoryKeyword.objects.filter(category=market_cat):
        print(f"  {kw.keyword}: usage_count={kw.usage_count}, "
              f"weight={kw.normalized_weight:.2f}")
    
    print("\nКлючевые слова для 'Кафе и рестораны':")
    for kw in CategoryKeyword.objects.filter(category=cafe_cat):
        print(f"  {kw.keyword}: usage_count={kw.usage_count}, "
              f"weight={kw.normalized_weight:.2f}")
    
    # Тестируем категоризацию с новыми весами
    print("\n=== Тест категоризации с весами ===")
    test_texts = [
        "кофе",
        "вода",
        "кофе и вода",
    ]
    
    for text in test_texts:
        category, confidence, corrected = categorize_expense_smart(text, profile)
        print(f"'{text}' -> {category} (уверенность: {confidence:.2%})")


def test_50_word_limit():
    """Тест ограничения на 50 слов в категории"""
    print("\n=== Тест ограничения на 50 слов ===")
    
    # Получаем тестового пользователя
    try:
        profile = Profile.objects.get(telegram_id=123456789)
    except Profile.DoesNotExist:
        print("Профиль не найден. Запустите сначала test_weight_update()")
        return
    
    # Получаем категорию
    category = ExpenseCategory.objects.filter(profile=profile).first()
    if not category:
        print("Категории не найдены")
        return
    
    print(f"Добавляем 60 ключевых слов в категорию '{category.name}'...")
    
    # Создаем 60 ключевых слов
    for i in range(60):
        CategoryKeyword.objects.get_or_create(
            category=category,
            keyword=f"testword{i:03d}",
            defaults={
                'usage_count': i % 10,  # Разные веса
                'normalized_weight': 1.0
            }
        )
    
    print(f"Создано {CategoryKeyword.objects.filter(category=category).count()} слов")
    
    # Вызываем проверку лимита
    from expense_bot.celery_tasks import check_category_keywords_limit
    check_category_keywords_limit(category)
    
    # Проверяем результат
    remaining = CategoryKeyword.objects.filter(category=category).count()
    print(f"После проверки лимита осталось: {remaining} слов")
    
    if remaining > 50:
        print("❌ Ошибка: лимит не работает!")
    else:
        print("✅ Лимит работает правильно")


if __name__ == "__main__":
    print("="*50)
    print("ТЕСТИРОВАНИЕ СИСТЕМЫ ВЕСОВ КЛЮЧЕВЫХ СЛОВ")
    print("="*50)
    
    # Запускаем тесты
    test_keyword_extraction()
    test_weight_update()
    test_50_word_limit()
    
    print("\n" + "="*50)
    print("Тестирование завершено!")