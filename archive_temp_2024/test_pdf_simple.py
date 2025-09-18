#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Простой тест генерации PDF
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

async def test_pdf():
    """Тест генерации PDF"""
    try:
        service = PDFReportService()
        
        # Тестовый пользователь
        user_id = 881292737
        year = 2025
        month = 9
        
        print(f"Генерация PDF отчета для пользователя {user_id} за {month}/{year}...")
        
        pdf_bytes = await service.generate_monthly_report(user_id, year, month)
        
        if pdf_bytes:
            output_path = f"test_report_{year}_{month}.pdf"
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
            print(f"[SUCCESS] PDF отчет сохранен: {output_path}")
            print(f"Размер: {len(pdf_bytes):,} байт")
        else:
            print("[ERROR] Не удалось создать PDF отчет")
            
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Запускаем в синхронном контексте
    asyncio.run(test_pdf())