#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки изменений в PDF отчетах
"""

import os
import sys
import django
import asyncio
from datetime import date

# Установка UTF-8 кодировки для вывода
import locale
locale.setlocale(locale.LC_ALL, 'ru_RU.UTF-8')

# Добавляем путь к проекту
sys.path.insert(0, '/mnt/c/Users/_batman_/Desktop/expense_bot')

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.services.pdf_report import PDFReportService
from expenses.models import Profile


async def test_pdf_report():
    """Тест генерации PDF отчета"""
    try:
        # Создаем сервис
        service = PDFReportService()
        
        # Находим первого пользователя с расходами
        try:
            profile = await Profile.objects.filter(expenses__isnull=False).afirst()
            if not profile:
                print("Нет пользователей с расходами")
                return
            user_id = profile.telegram_id
        except Exception as e:
            print(f"Ошибка при поиске профиля: {e}")
            # Используем тестовый ID
            user_id = 1161133982  # batman
        
        # Текущий месяц
        today = date.today()
        year = today.year
        month = today.month
        
        print(f"Генерация отчета для пользователя {user_id}")
        print(f"Период: {month}/{year}")
        
        # Генерируем отчет
        pdf_bytes = await service.generate_monthly_report(user_id, year, month)
        
        if pdf_bytes:
            # Сохраняем результат
            output_path = f"test_report_{year}_{month}.pdf"
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
            print(f"[OK] Отчет успешно сохранен: {output_path}")
            print(f"Размер файла: {len(pdf_bytes):,} байт")
            
            # Проверяем основные изменения
            print("\nПроверьте следующие изменения в PDF:")
            print("1. Овалы категорий изменены на прямоугольники 10x24px с закругленными краями")
            print("2. Проценты в диаграммах теперь почти белые (#f3f4f6)")
            print("3. Проценты расположены дальше от края (85% радиуса)")
            print("4. Проценты показываются для секторов > 5% (вместо 15%)")
            print("5. Убраны проценты после суммы в списке категорий")
            
        else:
            print("[ERROR] Не удалось создать отчет")
            
    except Exception as e:
        print(f"[ERROR] Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_pdf_report())