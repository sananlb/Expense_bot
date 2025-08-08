#!/usr/bin/env python
"""
Отладочный скрипт для проверки проблем с генерацией отчетов
"""
import os
import sys
import asyncio
from datetime import date, timedelta
import django

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, Expense, ExpenseCategory
from bot.services.expense import get_expenses_summary
from bot.services.pdf_report import PDFReportService


async def debug_reports():
    """Отладка проблем с отчетами"""
    print("=== DEBUG REPORTS ===")
    
    # 1. Проверим все профили
    print("\n1. Проверка профилей в БД:")
    profiles = await Profile.objects.all()
    async for profile in profiles:
        print(f"Profile ID: {profile.pk}, Telegram ID: {profile.telegram_id}")
    
    # 2. Проверим расходы
    print("\n2. Проверка расходов в БД:")
    expenses = await Expense.objects.select_related('profile', 'category').all()
    async for expense in expenses:
        print(f"Expense ID: {expense.pk}, Profile ID: {expense.profile_id}, "
              f"Telegram ID: {expense.profile.telegram_id}, Amount: {expense.amount}, "
              f"Date: {expense.expense_date}")
    
    # 3. Тестируем get_expenses_summary для пользователя с расходами
    telegram_id = 881292737  # У этого пользователя есть расходы (Profile ID 8)
    print(f"\n3. Тестируем get_expenses_summary для Telegram ID {telegram_id}:")
    
    try:
        today = date.today()
        start_date = today.replace(day=1)  # Начало месяца
        end_date = today
        
        print(f"Период: {start_date} - {end_date}")
        
        summary = await get_expenses_summary(
            user_id=telegram_id,
            start_date=start_date,
            end_date=end_date
        )
        
        print(f"Результат summary:")
        print(f"  Total: {summary['total']}")
        print(f"  Count: {summary['count']}")
        print(f"  Currency: {summary['currency']}")
        print(f"  Categories count: {len(summary['by_category'])}")
        
        if summary['by_category']:
            print("  Categories:")
            for cat in summary['by_category'][:3]:  # Показать только первые 3
                print(f"    {cat['name']}: {cat['total']}")
                
    except Exception as e:
        print(f"Ошибка в get_expenses_summary: {e}")
        import traceback
        traceback.print_exc()
    
    # 4. Тестируем PDFReportService
    print(f"\n4. Тестируем PDFReportService для Telegram ID {telegram_id}:")
    
    try:
        pdf_service = PDFReportService()
        current_date = date.today()
        
        print(f"Генерация отчета за {current_date.month}/{current_date.year}")
        
        # Проверяем подготовку данных (без генерации PDF)
        report_data = await pdf_service._prepare_report_data(
            user_id=telegram_id,
            year=current_date.year,
            month=current_date.month
        )
        
        if report_data is None:
            print("  ❌ _prepare_report_data вернул None - НЕТ ДАННЫХ!")
            
            # Дополнительная проверка
            print("\n  Дополнительная отладка:")
            try:
                profile = await Profile.objects.aget(telegram_id=telegram_id)
                print(f"    Profile найден: ID={profile.pk}")
                
                # Проверяем расходы напрямую
                expenses_count = await Expense.objects.filter(
                    profile=profile,
                    expense_date__month=current_date.month,
                    expense_date__year=current_date.year
                ).acount()
                print(f"    Расходы за месяц: {expenses_count}")
                
                if expenses_count == 0:
                    print("    Проблема: нет расходов за текущий месяц!")
                    # Проверим все расходы пользователя
                    all_expenses = await Expense.objects.filter(profile=profile).acount()
                    print(f"    Всего расходов у пользователя: {all_expenses}")
                    
                    if all_expenses > 0:
                        # Покажем даты расходов
                        print("    Даты расходов:")
                        async for exp in Expense.objects.filter(profile=profile).order_by('-expense_date')[:5]:
                            print(f"      {exp.expense_date}: {exp.amount} - {exp.description}")
                
            except Exception as debug_e:
                print(f"    Ошибка в дополнительной отладке: {debug_e}")
        else:
            print("  ✅ _prepare_report_data успешно!")
            print(f"    Total amount: {report_data.get('total_amount', 'N/A')}")
            print(f"    Total count: {report_data.get('total_count', 'N/A')}")
            print(f"    Categories: {len(report_data.get('categories', []))}")
            
    except Exception as e:
        print(f"  ❌ Ошибка в PDFReportService: {e}")
        import traceback
        traceback.print_exc()

    # 5. Проверим расходы за разные периоды
    print(f"\n5. Проверка расходов за разные периоды для Telegram ID {telegram_id}:")
    
    try:
        profile = await Profile.objects.aget(telegram_id=telegram_id)
        
        # За текущий месяц
        current_month_expenses = await Expense.objects.filter(
            profile=profile,
            expense_date__month=date.today().month,
            expense_date__year=date.today().year
        ).acount()
        print(f"  Текущий месяц: {current_month_expenses} расходов")
        
        # За последние 30 дней
        thirty_days_ago = date.today() - timedelta(days=30)
        last_30_days_expenses = await Expense.objects.filter(
            profile=profile,
            expense_date__gte=thirty_days_ago
        ).acount()
        print(f"  Последние 30 дней: {last_30_days_expenses} расходов")
        
        # Все расходы
        all_expenses = await Expense.objects.filter(profile=profile).acount()
        print(f"  Всего: {all_expenses} расходов")
        
    except Exception as e:
        print(f"  Ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(debug_reports())