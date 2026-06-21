#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Скрипт для получения данных о тратах на автомобиль"""
import os
import sys
import django

# Установка кодировки для Windows консоли
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Expense, ExpenseCategory, Profile
from django.db.models import Sum, Count
from decimal import Decimal
from datetime import datetime, timedelta

def main():
    # Telegram ID владельца
    telegram_id = 881292737

    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        print(f'[OK] Профиль найден: ID {profile.id}')
        print(f'     Валюта: {profile.currency}')
        print()

        # Получаем все категории
        categories = ExpenseCategory.objects.filter(profile=profile, is_active=True)

        # Ищем автомобильные категории
        auto_keywords = ['авто', 'машин', 'транспорт', 'бензин', 'азс', 'топлив', 'заправ', 'car', 'fuel', 'gas', 'petrol', 'auto']

        print('КАТЕГОРИИ ПОЛЬЗОВАТЕЛЯ:')
        print('=' * 100)
        auto_cat_ids = []
        for cat in categories:
            name = (cat.name_ru or cat.name_en or cat.name or '').lower()
            is_auto = any(keyword in name for keyword in auto_keywords)
            marker = '[AUTO]' if is_auto else '      '
            display_name = cat.name_ru or cat.name_en or cat.name
            print(f'{marker} ID:{cat.id:3d} | {display_name}')
            if is_auto:
                auto_cat_ids.append(cat.id)

        print()
        print(f'[OK] Найдено автомобильных категорий: {len(auto_cat_ids)}')
        print()

        if auto_cat_ids:
            # Получаем все траты
            auto_expenses = Expense.objects.filter(
                profile=profile,
                category_id__in=auto_cat_ids
            ).select_related('category').order_by('-expense_date')

            total_count = auto_expenses.count()
            total_sum = auto_expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

            print('ОБЩАЯ СТАТИСТИКА:')
            print('=' * 100)
            print(f'   Всего трат: {total_count}')
            print(f'   Общая сумма: {total_sum:,.0f} {profile.currency}')
            print()

            # По категориям
            print('РАЗБИВКА ПО КАТЕГОРИЯМ:')
            print('=' * 100)
            for cat_id in auto_cat_ids:
                cat = ExpenseCategory.objects.get(id=cat_id)
                cat_expenses = auto_expenses.filter(category_id=cat_id)
                cat_count = cat_expenses.count()
                cat_sum = cat_expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
                cat_name = cat.name_ru or cat.name_en or cat.name
                print(f'   {cat_name:35s}: {cat_count:4d} трат | {cat_sum:12,.0f} руб')

            print()

            # За последний год
            one_year_ago = datetime.now().date() - timedelta(days=365)
            year_expenses = auto_expenses.filter(expense_date__gte=one_year_ago)
            year_count = year_expenses.count()
            year_sum = year_expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

            print(f'ЗА ПОСЛЕДНИЙ ГОД ({one_year_ago.strftime("%Y-%m-%d")} - {datetime.now().date()}):')
            print('=' * 100)
            print(f'   Трат: {year_count}')
            print(f'   Сумма: {year_sum:,.0f} руб')
            print(f'   Средний чек: {year_sum / year_count if year_count > 0 else 0:,.0f} руб')
            print(f'   В месяц: {year_sum / 12:,.0f} руб')
            print()

            # За последние 6 месяцев
            six_months_ago = datetime.now().date() - timedelta(days=180)
            six_month_expenses = auto_expenses.filter(expense_date__gte=six_months_ago)
            six_month_count = six_month_expenses.count()
            six_month_sum = six_month_expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

            print(f'ЗА ПОСЛЕДНИЕ 6 МЕСЯЦЕВ ({six_months_ago.strftime("%Y-%m-%d")} - {datetime.now().date()}):')
            print('=' * 100)
            print(f'   Трат: {six_month_count}')
            print(f'   Сумма: {six_month_sum:,.0f} руб')
            print(f'   В месяц: {six_month_sum / 6:,.0f} руб')
            print()

            # Последние 50 трат
            print('ПОСЛЕДНИЕ 50 ТРАТ НА АВТО:')
            print('=' * 100)
            print(f'{"Дата":<12} | {"Сумма":>12} | {"Категория":<30} | {"Описание":<40}')
            print('-' * 100)
            for exp in auto_expenses[:50]:
                cat_name = (exp.category.name_ru or exp.category.name_en or exp.category.name)[:28]
                desc = (exp.description or '')[:38]
                print(f'{exp.expense_date} | {exp.amount:>10,.0f} руб | {cat_name:<30} | {desc:<40}')

        else:
            print('[!] Категории с автомобилем не найдены')
            print()
            print('Показываю все категории для проверки:')
            for cat in categories:
                print(f'   ID:{cat.id} | {cat.name_ru or cat.name_en or cat.name}')

    except Profile.DoesNotExist:
        print(f'[ERROR] Профиль с telegram_id {telegram_id} не найден')
    except Exception as e:
        print(f'[ERROR] Ошибка: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
