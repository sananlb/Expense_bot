
#!/usr/bin/env python
"""
Quick smoke check for all AI function-calling endpoints in ExpenseFunctions.
Creates minimal test data and invokes each function to ensure no exceptions
and a sane response schema.
"""
import os
import sys
import asyncio
from pathlib import Path
from datetime import date, timedelta, datetime, time

# Ensure project root on sys.path and logs dir exists before Django configures logging
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
(ROOT / 'logs').mkdir(parents=True, exist_ok=True)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')

import django
django.setup()

from expenses.models import Profile, Expense, Income, ExpenseCategory, IncomeCategory
from bot.services.expense_functions import ExpenseFunctions


TEST_USER = 555001


def seed_data():
    profile, _ = Profile.objects.get_or_create(telegram_id=TEST_USER, defaults={'language_code': 'ru'})

    # Categories (optional)
    cat_food, _ = ExpenseCategory.objects.get_or_create(profile=profile, name='Продукты', defaults={'icon': '🛒'})
    cat_travel, _ = ExpenseCategory.objects.get_or_create(profile=profile, name='Транспорт', defaults={'icon': '🚌'})

    inc_salary_cat, _ = IncomeCategory.objects.get_or_create(profile=profile, name='Зарплата')
    inc_other_cat, _ = IncomeCategory.objects.get_or_create(profile=profile, name='Прочее')

    # Clear any existing test window data to keep small
    start = date.today() - timedelta(days=14)
    Expense.objects.filter(profile=profile, expense_date__gte=start).delete()
    Income.objects.filter(profile=profile, income_date__gte=start).delete()

    # Expenses: last 10 days
    for i in range(10):
        d = date.today() - timedelta(days=i)
        Expense.objects.create(
            profile=profile,
            amount=100 + i * 10,
            currency='RUB',
            description=f'Трата {i}',
            expense_date=d,
            expense_time=time(12, (i * 7) % 60),
            category=cat_food if i % 2 == 0 else cat_travel,
        )

    # Incomes: last 6 days
    for i in range(6):
        d = date.today() - timedelta(days=i * 2)
        Income.objects.create(
            profile=profile,
            amount=1000 + i * 250,
            currency='RUB',
            description=f'Доход {i}',
            income_date=d,
            income_time=time(10, (i * 11) % 60),
            category=inc_salary_cat if i % 2 == 0 else inc_other_cat,
        )


async def run_checks():
    # Run synchronous seeding in a thread to avoid async DB restriction
    await asyncio.to_thread(seed_data)
    f = ExpenseFunctions()

    # Helper to run and print short outcome
    async def call(name, coro):
        try:
            res = await coro
            ok = bool(res and isinstance(res, dict))
            print(f"{name:35} -> {'OK' if ok else 'FAIL'} | keys={list(res.keys())[:5] if isinstance(res, dict) else type(res)}")
        except Exception as e:
            print(f"{name:35} -> EXC  | {e}")

    today_iso = date.today().isoformat()

    await call('get_max_expense_day', f.get_max_expense_day(TEST_USER, 30))
    await call('get_period_total(tday)', f.get_period_total(TEST_USER, 'today'))
    await call('get_category_statistics', f.get_category_statistics(TEST_USER, 30))
    await call('get_daily_totals', f.get_daily_totals(TEST_USER, 15))
    await call('search_expenses', f.search_expenses(TEST_USER, 'Трата', 5))
    await call('get_average_expenses', f.get_average_expenses(TEST_USER, 30))
    await call('get_expenses_list', f.get_expenses_list(TEST_USER, today_iso, today_iso, 20))
    await call('get_max_single_expense', f.get_max_single_expense(TEST_USER, 60))
    await call('get_category_total', f.get_category_total(TEST_USER, 'Продукты', 'month'))
    await call('compare_periods', f.compare_periods(TEST_USER, 'this_month', 'last_month'))
    await call('get_expenses_by_amount_range', f.get_expenses_by_amount_range(TEST_USER, 120, None, 50))
    await call('get_expense_trend', f.get_expense_trend(TEST_USER, 'month', 6))
    await call('get_weekday_statistics', f.get_weekday_statistics(TEST_USER, 30))
    await call('predict_month_expense', f.predict_month_expense(TEST_USER))
    await call('check_budget_status', f.check_budget_status(TEST_USER, 5000))
    await call('get_recent_expenses', f.get_recent_expenses(TEST_USER, 5))

    # Incomes
    await call('get_recent_incomes', f.get_recent_incomes(TEST_USER, 5))
    await call('get_max_income_day', f.get_max_income_day(TEST_USER))
    await call('get_income_period_total', f.get_income_period_total(TEST_USER, 'month'))
    await call('get_max_single_income', f.get_max_single_income(TEST_USER))
    await call('get_income_category_statistics', f.get_income_category_statistics(TEST_USER))
    await call('get_average_incomes', f.get_average_incomes(TEST_USER))
    await call('search_incomes', f.search_incomes(TEST_USER, 'Доход'))
    await call('get_income_weekday_statistics', f.get_income_weekday_statistics(TEST_USER))
    await call('predict_month_income', f.predict_month_income(TEST_USER))
    await call('check_income_target', f.check_income_target(TEST_USER, 10000))
    await call('compare_income_periods', f.compare_income_periods(TEST_USER))
    await call('get_income_trend', f.get_income_trend(TEST_USER, 30))
    await call('get_incomes_by_amount_range', f.get_incomes_by_amount_range(TEST_USER, 1000, None))
    await call('get_income_category_total', f.get_income_category_total(TEST_USER, 'Зарплата', 'month'))
    await call('get_incomes_list', f.get_incomes_list(TEST_USER, today_iso, today_iso, 50))
    await call('get_daily_income_totals', f.get_daily_income_totals(TEST_USER, 14))

    # Unified
    start = (date.today() - timedelta(days=10)).isoformat()
    await call('get_all_operations', f.get_all_operations(TEST_USER, start, today_iso, 100))
    await call('get_financial_summary', f.get_financial_summary(TEST_USER, 'month'))


if __name__ == '__main__':
    asyncio.run(run_checks())
