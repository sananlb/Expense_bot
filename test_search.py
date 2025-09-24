#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import django

# Установка Django настроек
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Expense, Profile
from django.db.models import Q

# Тестируем поиск
profile = Profile.objects.filter(telegram_id=881292737).first()
if profile:
    print(f"Profile found: {profile.id}")

    # Все траты пользователя
    all_expenses = Expense.objects.filter(profile=profile).order_by('-expense_date')[:10]
    print(f"\nAll expenses ({all_expenses.count()}):")
    for exp in all_expenses:
        print(f"  - {exp.description}: {exp.amount}")

    # Поиск с icontains
    query = "сникерс"
    expenses_icontains = Expense.objects.filter(
        profile=profile,
        description__icontains=query
    )
    print(f"\nicontains '{query}': found {expenses_icontains.count()}")

    # Поиск с iexact
    expenses_iexact = Expense.objects.filter(
        profile=profile,
        description__iexact=query
    )
    print(f"iexact '{query}': found {expenses_iexact.count()}")

    # Поиск с точным совпадением
    expenses_exact = Expense.objects.filter(
        profile=profile,
        description="Сникерс"
    )
    print(f"exact 'Сникерс': found {expenses_exact.count()}")

    # Проверка регистра в описании
    for exp in all_expenses:
        if "никерс" in exp.description.lower():
            print(f"\nFound by Python check: {exp.description}")

    # Проверка с Q объектами как в функции
    expenses_q = Expense.objects.filter(profile=profile).filter(
        Q(description__icontains=query) |
        Q(category__name__icontains=query)
    )
    print(f"\nWith Q objects (like in function): found {expenses_q.count()}")

else:
    print("Profile not found")