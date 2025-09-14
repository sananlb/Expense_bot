#!/usr/bin/env python
"""
Smoke tests for popular user queries against existing data.
Reads an existing user profile (TEST_USER_ID env or first Profile) and
executes a set of representative queries via existing functions and the
analytics_query fallback.

Usage:
  TEST_USER_ID=123 python -u scripts/test_popular_queries.py
"""
import os
import sys
import json
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')

from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
(ROOT / 'logs').mkdir(parents=True, exist_ok=True)

import asyncio
import django
django.setup()

from expenses.models import Profile
from bot.services.expense_functions import ExpenseFunctions


def pick_user_id() -> int:
    uid_env = os.getenv('TEST_USER_ID')
    if uid_env and uid_env.isdigit():
        return int(uid_env)
    prof = Profile.objects.order_by('id').first()
    if not prof:
        raise SystemExit("No profiles found. Please run the bot or set TEST_USER_ID.")
    return prof.telegram_id


def month_bounds(year: int, month: int):
    from calendar import monthrange
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return start, end


async def run():
    user_id = pick_user_id()
    f = ExpenseFunctions()

    print(f"Using user_id={user_id}\n")

    # 1) Самая маленькая покупка (fallback analytics_query)
    spec_min = {
        "entity": "expenses",
        "filters": {"date": {"period": "month"}},
        "sort": [{"by": "amount", "dir": "asc"}],
        "limit": 1,
        "projection": ["date", "amount", "category", "description", "currency"],
    }
    res_min = await f.analytics_query(user_id, json.dumps(spec_min, ensure_ascii=False))
    print("[min expense this month]", "OK" if res_min.get('success') else "FAIL", res_min.get('results', [])[:1])

    # 2) Сколько в прошлом месяце на продукты (через get_category_statistics с датами)
    today = date.today()
    prev_year = today.year if today.month > 1 else today.year - 1
    prev_month = today.month - 1 if today.month > 1 else 12
    m_start, m_end = month_bounds(prev_year, prev_month)
    res_cat = await f.get_category_statistics(user_id, start_date=m_start.isoformat(), end_date=m_end.isoformat())
    print("[category stats prev month]", "OK" if res_cat.get('success') else "FAIL", f"period={m_start}..{m_end}")

    # 3) Доходы по дням за неделю (analytics_query)
    spec_inc_week = {
        "entity": "incomes",
        "filters": {"date": {"period": "week"}},
        "group_by": "date",
        "aggregate": ["sum", "count"],
        "sort": [{"by": "date", "dir": "asc"}],
        "limit": 100,
    }
    res_inc = await f.analytics_query(user_id, json.dumps(spec_inc_week, ensure_ascii=False))
    print("[income by day week]", "OK" if res_inc.get('success') else "FAIL", res_inc.get('count'))

    # 4) Топ категорий расходов за текущий месяц (get_category_statistics)
    res_top = await f.get_category_statistics(user_id, period_days=31)
    print("[top categories month]", "OK" if res_top.get('success') else "FAIL", len(res_top.get('categories', [])))

    # 5) Все операции за 10 дней (get_all_operations)
    start_10 = (today - timedelta(days=10)).isoformat()
    end_today = today.isoformat()
    res_ops = await f.get_all_operations(user_id, start_date=start_10, end_date=end_today, limit=50)
    print("[operations 10 days]", "OK" if res_ops.get('success') else "FAIL", res_ops.get('count'))

    # 6) Самые дешевые 5 трат (analytics_query)
    spec_cheapest5 = {
        "entity": "expenses",
        "filters": {"date": {"period": "month"}},
        "sort": [{"by": "amount", "dir": "asc"}],
        "limit": 5,
        "projection": ["date", "amount", "category", "description"],
    }
    res_cheapest5 = await f.analytics_query(user_id, json.dumps(spec_cheapest5, ensure_ascii=False))
    print("[cheapest 5 expenses]", "OK" if res_cheapest5.get('success') else "FAIL", len(res_cheapest5.get('results', [])))

    # 7) Самая большая трата за 60 дней (готовая функция)
    res_max = await f.get_max_single_expense(user_id, 60)
    print("[max single expense 60d]", "OK" if res_max.get('success') else "FAIL", res_max.get('amount'))

    # 8) Траты на 'продукты' в текущем месяце (готовая функция)
    res_cat_total = await f.get_category_total(user_id, category='продукты', period='month')
    print("[category total month 'продукты']", "OK" if res_cat_total.get('success') else "FAIL", res_cat_total.get('total'))

    # 9) Траты по диапазону суммы (> 1000)
    res_amt_range = await f.get_expenses_by_amount_range(user_id, min_amount=1000, max_amount=None, limit=20)
    print("[expenses amount >=1000]", "OK" if res_amt_range.get('success') else "FAIL", res_amt_range.get('count'))

    # 10) Поиск трат по тексту 'кофе'
    res_search = await f.search_expenses(user_id, query='кофе', limit=10)
    print("[search 'кофе']", "OK" if res_search.get('success') else "FAIL", res_search.get('count'))

    # 11) День с максимальными тратами за 60 дней
    res_max_day = await f.get_max_expense_day(user_id, period_days=60)
    print("[max expense day 60d]", "OK" if res_max_day.get('success') else "FAIL", res_max_day.get('date'))

    # 12) Траты за сегодняшнюю дату списком (get_expenses_list)
    res_list_today = await f.get_expenses_list(user_id, start_date=end_today, end_date=end_today, limit=50)
    print("[expenses list today]", "OK" if res_list_today.get('success') else "FAIL", res_list_today.get('count'))

    # 13) analytics_query: фильтр по тексту + проекция
    spec_text = {
        "entity": "expenses",
        "filters": {"text": {"contains": "кофе"}},
        "sort": [{"by": "amount", "dir": "desc"}],
        "limit": 5,
        "projection": ["date", "amount", "category", "description"],
    }
    res_text = await f.analytics_query(user_id, json.dumps(spec_text, ensure_ascii=False))
    print("[analytics text contains 'кофе']", "OK" if res_text.get('success') else "FAIL", res_text.get('count'))

    # 14) analytics_query: по категориям с фильтром суммы
    spec_cat_agg = {
        "entity": "expenses",
        "filters": {"amount": {"gte": 1000}},
        "group_by": "category",
        "aggregate": ["sum", "count"],
        "sort": [{"by": "sum", "dir": "desc"}],
        "limit": 10,
    }
    res_cat_agg = await f.analytics_query(user_id, json.dumps(spec_cat_agg, ensure_ascii=False))
    print("[analytics by category sum>=1000]", "OK" if res_cat_agg.get('success') else "FAIL", res_cat_agg.get('count'))

    # 15) Доходы: самая большая запись
    res_max_income = await f.get_max_single_income(user_id)
    print("[max single income]", "OK" if res_max_income.get('success') else "FAIL")

    # 16) Доходы: последние 5
    res_recent_inc = await f.get_recent_incomes(user_id, limit=5)
    print("[recent incomes 5]", "OK" if res_recent_inc.get('success') else "FAIL", res_recent_inc.get('count'))

    # 17) analytics_query: топ-3 доходов
    spec_top_inc = {
        "entity": "incomes",
        "sort": [{"by": "amount", "dir": "desc"}],
        "limit": 3,
        "projection": ["date", "amount", "category", "description"],
    }
    res_top_inc = await f.analytics_query(user_id, json.dumps(spec_top_inc, ensure_ascii=False))
    print("[top 3 incomes]", "OK" if res_top_inc.get('success') else "FAIL", res_top_inc.get('count'))

    # 18) Сравнение периодов расходов (этот/прошлый месяц)
    res_cmp = await f.compare_periods(user_id, period1='this_month', period2='last_month')
    print("[compare periods expenses]", "OK" if res_cmp.get('success') else "FAIL")

    # 19) Статистика по дням недели (расходы)
    res_weekday = await f.get_weekday_statistics(user_id, period_days=30)
    print("[weekday stats expenses]", "OK" if res_weekday.get('success') else "FAIL")

    # 20) Доходы по дням недели
    res_i_weekday = await f.get_income_weekday_statistics(user_id)
    print("[weekday stats incomes]", "OK" if res_i_weekday.get('success') else "FAIL")


if __name__ == '__main__':
    asyncio.run(run())
