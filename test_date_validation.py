#!/usr/bin/env python
"""
Тест валидации дат при внесении операций
"""

import os
import sys
import django
from datetime import date, timedelta
import asyncio

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.services.expense import create_expense
from bot.services.income import create_income
from expenses.models import Profile
from decimal import Decimal


def test_date_validation():
    """Тест проверок на даты"""
    print("=" * 60)
    print("ТЕСТ ВАЛИДАЦИИ ДАТ")
    print("=" * 60)
    
    # Создаем тестовый профиль или используем существующий
    test_user_id = 999999999  # Тестовый ID
    
    # Получаем или создаем профиль
    from bot.utils.db_utils import get_or_create_user_profile_sync
    profile = get_or_create_user_profile_sync(test_user_id)
    
    # Устанавливаем дату создания профиля на 30 дней назад
    from django.utils import timezone
    thirty_days_ago = timezone.now() - timedelta(days=30)
    profile.created_at = thirty_days_ago
    profile.save()
    
    print(f"Профиль создан: {profile.created_at.date()}")
    print(f"Сегодня: {date.today()}")
    print()
    
    # Тест 1: Попытка создать трату в будущем
    print("Тест 1: Трата в будущем")
    tomorrow = date.today() + timedelta(days=1)
    try:
        expense = create_expense(
            user_id=test_user_id,
            amount=Decimal('100'),
            description="Тест будущая трата",
            expense_date=tomorrow
        )
        print(f"  ERROR ОШИБКА: Трата в будущем создана!")
    except ValueError as e:
        print(f"  OK Ожидаемая ошибка: {e}")
    
    # Тест 2: Попытка создать трату старше 1 года
    print("\nТест 2: Трата старше 1 года")
    old_date = date.today() - timedelta(days=400)
    try:
        expense = create_expense(
            user_id=test_user_id,
            amount=Decimal('100'),
            description="Тест старая трата",
            expense_date=old_date
        )
        print(f"  ERROR ОШИБКА: Старая трата создана!")
    except ValueError as e:
        print(f"  OK Ожидаемая ошибка: {e}")
    
    # Тест 3: Попытка создать трату до регистрации
    print("\nТест 3: Трата до регистрации")
    before_registration = (thirty_days_ago - timedelta(days=5)).date()
    try:
        expense = create_expense(
            user_id=test_user_id,
            amount=Decimal('100'),
            description="Тест до регистрации",
            expense_date=before_registration
        )
        print(f"  ERROR ОШИБКА: Трата до регистрации создана!")
    except ValueError as e:
        print(f"  OK Ожидаемая ошибка: {e}")
    
    # Тест 4: Корректная трата (вчера)
    print("\nТест 4: Корректная трата (вчера)")
    yesterday = date.today() - timedelta(days=1)
    try:
        expense = create_expense(
            user_id=test_user_id,
            amount=Decimal('100'),
            description="Тест вчерашняя трата",
            expense_date=yesterday
        )
        if expense:
            print(f"  OK Трата создана: {expense.description} на {expense.expense_date}")
            # Удаляем тестовую трату
            expense.delete()
    except ValueError as e:
        print(f"  ERROR Неожиданная ошибка: {e}")
    
    # Тест 5: Попытка создать доход в будущем
    print("\nТест 5: Доход в будущем")
    try:
        income = create_income(
            user_id=test_user_id,
            amount=Decimal('1000'),
            description="Тест будущий доход",
            income_date=tomorrow
        )
        print(f"  ERROR ОШИБКА: Доход в будущем создан!")
    except ValueError as e:
        print(f"  OK Ожидаемая ошибка: {e}")
    
    # Тест 6: Попытка создать доход старше 1 года
    print("\nТест 6: Доход старше 1 года")
    try:
        income = create_income(
            user_id=test_user_id,
            amount=Decimal('1000'),
            description="Тест старый доход",
            income_date=old_date
        )
        print(f"  ERROR ОШИБКА: Старый доход создан!")
    except ValueError as e:
        print(f"  OK Ожидаемая ошибка: {e}")
    
    # Тест 7: Корректный доход (неделю назад)
    print("\nТест 7: Корректный доход (неделю назад)")
    week_ago = date.today() - timedelta(days=7)
    try:
        income = create_income(
            user_id=test_user_id,
            amount=Decimal('1000'),
            description="Тест доход неделю назад",
            income_date=week_ago
        )
        if income:
            print(f"  OK Доход создан: {income.description} на {income.income_date}")
            # Удаляем тестовый доход
            income.delete()
    except ValueError as e:
        print(f"  ERROR Неожиданная ошибка: {e}")
    
    # Удаляем тестовый профиль
    profile.delete()
    print("\nOK Тестовый профиль удален")


if __name__ == "__main__":
    print("\nТЕСТИРОВАНИЕ ВАЛИДАЦИИ ДАТ ПРИ ВНЕСЕНИИ ОПЕРАЦИЙ\n")
    test_date_validation()
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 60)