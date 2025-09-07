#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест подготовки данных для PDF отчета
"""

import os
import sys
import django
import asyncio

# Настройка Django
sys.path.insert(0, '/mnt/c/Users/_batman_/Desktop/expense_bot')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.services.pdf_report import PDFReportService
from datetime import date

async def test_report_data():
    """Тест подготовки данных для отчета"""
    try:
        service = PDFReportService()
        
        # Тестовый пользователь
        user_id = 881292737
        year = 2025
        month = 9
        
        print(f"Подготовка данных отчета для пользователя {user_id} за {month}/{year}...")
        
        # Получаем только данные, без генерации PDF
        report_data = await service._prepare_report_data(user_id, year, month)
        
        if report_data:
            print("[SUCCESS] Данные отчета подготовлены успешно")
            print(f"Период: {report_data['period']}")
            print(f"Общая сумма: {report_data['total_amount']}")
            print(f"Количество трат: {report_data['total_count']}")
            print(f"Категорий: {len(report_data['categories'])}")
            print(f"Статистика по месяцам: {len(report_data['prev_summaries'])} записей")
            
            print("\nСтатистика по месяцам:")
            for month_data in report_data['prev_summaries']:
                print(f"  {month_data['label']}: Расходы={month_data['expenses']}, Доходы={month_data['incomes']}, Баланс={month_data['balance']}")
                
            print("\nКатегории:")
            for cat in report_data['categories']:
                print(f"  {cat['icon']} {cat['name']}: {cat['amount_formatted']} ₽")
        else:
            print("[ERROR] Не удалось подготовить данные для отчета")
            
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_report_data())