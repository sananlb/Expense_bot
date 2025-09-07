#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Диагностический скрипт для проверки данных PDF отчета
"""

import os
import sys
import django
import asyncio
from datetime import date

# Добавляем путь к проекту
sys.path.insert(0, '/mnt/c/Users/_batman_/Desktop/expense_bot')

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, Expense, Income
from bot.services.pdf_report import PDFReportService


async def debug_pdf_data():
    """Диагностика данных для PDF отчета"""
    try:
        # Получаем всех пользователей с расходами
        profiles_with_expenses = []
        async for profile in Profile.objects.all():
            expense_count = await Expense.objects.filter(profile=profile).acount()
            if expense_count > 0:
                profiles_with_expenses.append({
                    'profile': profile,
                    'telegram_id': profile.telegram_id,
                    'expense_count': expense_count
                })
        
        print(f"Найдено профилей с расходами: {len(profiles_with_expenses)}")
        
        if not profiles_with_expenses:
            print("НЕТ ПОЛЬЗОВАТЕЛЕЙ С РАСХОДАМИ!")
            return
        
        # Берем первого пользователя с расходами
        test_profile = profiles_with_expenses[0]['profile']
        test_user_id = test_profile.telegram_id
        
        print(f"\nТестовый пользователь:")
        print(f"  ID: {test_user_id}")
        print(f"  Количество трат: {profiles_with_expenses[0]['expense_count']}")
        
        # Проверяем данные за текущий месяц
        today = date.today()
        year = today.year
        month = today.month
        
        print(f"\nПроверка данных за {month}/{year}:")
        
        # Получаем расходы за текущий месяц
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        
        expenses = await Expense.objects.filter(
            profile=test_profile,
            expense_date__gte=start_date,
            expense_date__lt=end_date
        ).acount()
        
        incomes = await Income.objects.filter(
            profile=test_profile,
            income_date__gte=start_date,
            income_date__lt=end_date
        ).acount()
        
        print(f"  Расходов за месяц: {expenses}")
        print(f"  Доходов за месяц: {incomes}")
        
        # Проверяем за предыдущий месяц
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        
        print(f"\nПроверка данных за {prev_month}/{prev_year}:")
        
        prev_start = date(prev_year, prev_month, 1)
        if prev_month == 12:
            prev_end = date(prev_year + 1, 1, 1)
        else:
            prev_end = date(prev_year, prev_month + 1, 1)
        
        prev_expenses = await Expense.objects.filter(
            profile=test_profile,
            expense_date__gte=prev_start,
            expense_date__lt=prev_end
        ).acount()
        
        print(f"  Расходов за предыдущий месяц: {prev_expenses}")
        
        # Пробуем сгенерировать отчет
        print(f"\nПробуем сгенерировать отчет для пользователя {test_user_id}...")
        
        service = PDFReportService()
        
        # Ищем месяц с данными
        test_month = month
        test_year = year
        pdf_bytes = None
        
        for i in range(12):  # Проверяем последние 12 месяцев
            month_expenses = await Expense.objects.filter(
                profile=test_profile,
                expense_date__year=test_year,
                expense_date__month=test_month
            ).acount()
            
            print(f"\nПроверка {test_month}/{test_year}: {month_expenses} расходов")
            
            if month_expenses > 0:
                print(f"Генерируем отчет за {test_month}/{test_year}...")
                pdf_bytes = await service.generate_monthly_report(test_user_id, test_year, test_month)
                if pdf_bytes:
                    print(f"УСПЕХ! Отчет сгенерирован, размер: {len(pdf_bytes)} байт")
                    break
                else:
                    print(f"ОШИБКА: Не удалось сгенерировать отчет")
            
            # Переходим к предыдущему месяцу
            test_month -= 1
            if test_month < 1:
                test_month = 12
                test_year -= 1
        
        if not pdf_bytes:
            print("\n[ОШИБКА] Не удалось найти месяц с данными для генерации отчета")
        else:
            # Сохраняем отчет
            output_path = f"debug_report_{test_year}_{test_month}.pdf"
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
            print(f"\n[OK] Отчет сохранен: {output_path}")
        
        # Проверяем все расходы пользователя
        all_expenses = []
        async for exp in Expense.objects.filter(profile=test_profile).order_by('-expense_date')[:10]:
            all_expenses.append({
                'date': exp.expense_date,
                'amount': exp.amount,
                'category': exp.category.name if exp.category else 'Без категории'
            })
        
        print(f"\nПоследние 10 расходов пользователя:")
        for exp in all_expenses:
            print(f"  {exp['date']}: {exp['amount']} руб. ({exp['category']})")
            
    except Exception as e:
        print(f"\n[КРИТИЧЕСКАЯ ОШИБКА]: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_pdf_data())