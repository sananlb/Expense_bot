#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Проверка категорий пользователя
"""

import os
import sys
import django

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, ExpenseCategory

# Ваш telegram ID
user_id = 881292737

try:
    profile = Profile.objects.get(telegram_id=user_id)
    print(f"Профиль найден: {profile.telegram_id}")
    
    categories = ExpenseCategory.objects.filter(profile=profile)
    print(f"\nВсего категорий: {categories.count()}")
    print("\nСписок категорий:")
    
    for cat in categories:
        print(f"  ID: {cat.id}, Название: '{cat.name}', Иконка: '{cat.icon}'")
        
except Profile.DoesNotExist:
    print(f"Профиль с ID {user_id} не найден")