"""
Unified formatter for function-call results used by AI services.
"""
from __future__ import annotations

from typing import Dict, List


def _format_expenses_list(result: Dict, title: str, subtitle: str) -> str:
    from bot.utils.expense_formatter import format_expenses_from_dict_list
    expenses = result.get('expenses', [])
    return format_expenses_from_dict_list(
        expenses,
        title=title,
        subtitle=subtitle,
        max_expenses=100,
    )


def _format_incomes_list(result: Dict, title: str, subtitle: str) -> str:
    from bot.utils.income_formatter import format_incomes_from_dict_list
    incomes = result.get('incomes', [])
    return format_incomes_from_dict_list(
        incomes,
        title=title,
        subtitle=subtitle,
        max_incomes=100,
    )


def _format_category_stats(result: Dict) -> str:
    cats = result.get('categories', []) or []
    total = result.get('total', 0)
    parts: List[str] = []
    parts.append(f"Статистика по категориям (всего: {total:,.0f} ₽)\n")
    for c in cats[:20]:
        name = c.get('name', '')
        cat_total = c.get('total', 0)
        count = c.get('count', 0)
        percent = c.get('percentage', 0)
        parts.append(f"• {name}: {cat_total:,.0f} ₽ ({count} шт., {percent:.1f}%)")
    if len(cats) > 20:
        parts.append(f"\n... ещё {len(cats)-20} категорий")
    return "\n".join(parts)


def _format_daily_totals(result: Dict) -> str:
    daily = result.get('daily_totals', {}) or {}
    stats = result.get('statistics', {}) if isinstance(result.get('statistics'), dict) else {}
    total = result.get('total', stats.get('total', 0))
    avg = result.get('average', stats.get('average', 0))
    lines = [f"Траты по дням (всего: {total:,.0f} ₽, среднее: {avg:,.0f} ₽/день)\n"]
    # latest 30 days by date desc
    for dk in sorted(daily.keys(), reverse=True)[:30]:
        entry = daily.get(dk)
        amount_val = entry.get('amount', 0) if isinstance(entry, dict) else (entry or 0)
        try:
            amount = float(amount_val)
        except Exception:
            amount = 0.0
        if amount > 0:
            lines.append(f"• {dk}: {amount:,.0f} ₽")
    if len(daily) > 30:
        lines.append(f"\n... данные за {len(daily)} дней")
    return "\n".join(lines)


def format_function_result(func_name: str, result: Dict) -> str:
    """
    Convert ExpenseFunctions/OpenAI/Gemini function-call results to user-facing text.
    """
    if not result.get('success'):
        return f"Ошибка: {result.get('message','Не удалось получить данные')}"

    if func_name == 'get_expenses_list':
        total = result.get('total', 0)
        count = result.get('count', len(result.get('expenses', [])))
        start = result.get('start_date', '')
        end = result.get('end_date', '')
        title = f"📋 Траты {start}{(' — ' + end) if end and end != start else ''}"
        subtitle = f"Найдено: {count} трат на сумму {total:,.0f} ₽"
        return _format_expenses_list(result, title, subtitle)

    if func_name == 'get_max_expense_day':
        date_str = result.get('date', '')
        total = result.get('total', 0)
        count = result.get('count', 0)
        details = result.get('details', []) or []
        for d in details:
            d.setdefault('date', date_str)
        title = "📊 День с максимальными тратами"
        subtitle = f"Дата: {date_str} | Всего: {count} трат на сумму {total:,.0f} ₽"
        from bot.utils.expense_formatter import format_expenses_from_dict_list
        return format_expenses_from_dict_list(details, title=title, subtitle=subtitle, max_expenses=100)

    if func_name == 'get_category_statistics':
        return _format_category_stats(result)

    if func_name == 'get_daily_totals':
        return _format_daily_totals(result)

    if func_name == 'search_expenses':
        results = result.get('results', [])
        total = result.get('total', 0)
        count = result.get('count', len(results))
        return _format_expenses_list(
            {'expenses': results},
            title="🔍 Результаты поиска",
            subtitle=f"Найдено: {count} трат на сумму {total:,.0f} ₽",
        )

    if func_name == 'get_expenses_by_amount_range':
        expenses = result.get('expenses', [])
        total = result.get('total', 0)
        count = result.get('count', len(expenses))
        min_amt = result.get('min_amount', 0)
        max_amt = result.get('max_amount', 0)
        title = f"💰 Траты от {min_amt:,.0f} до {max_amt:,.0f} ₽"
        subtitle = f"Найдено: {count} трат на сумму {total:,.0f} ₽"
        return _format_expenses_list({'expenses': expenses}, title, subtitle)

    if func_name == 'get_incomes_list':
        total = result.get('total', 0)
        count = result.get('count', len(result.get('incomes', [])))
        start = result.get('start_date', '')
        end = result.get('end_date', '')
        title = f"📋 Доходы {start}{(' — ' + end) if end and end != start else ''}"
        subtitle = f"Найдено: {count} доходов на сумму {total:,.0f} ₽"
        return _format_incomes_list(result, title, subtitle)

    if func_name == 'get_category_total':
        category = result.get('category', '')
        total = result.get('total', 0)
        count = result.get('count', 0)
        period = result.get('period', '')

        if count == 0:
            return f"За указанный период трат в категории \"{category}\" не найдено."

        period_text = {
            'week': 'за неделю',
            'month': 'за месяц',
            'year': 'за год',
            'all': 'за все время'
        }.get(period, f'за {period}')

        return (
            f"📦 Категория: {category}\n"
            f"Период: {period_text}\n"
            f"Трат: {count}\n"
            f"Сумма: {total:,.0f} ₽"
        )

    if func_name == 'get_category_total_by_dates':
        category = result.get('category', '')
        total = result.get('total', 0)
        count = result.get('count', 0)
        start_date = result.get('start_date', '')
        end_date = result.get('end_date', '')

        if count == 0:
            return f"За период с {start_date} по {end_date} трат в категории \"{category}\" не найдено."

        # Определяем описание периода
        try:
            from datetime import datetime
            s = datetime.fromisoformat(start_date)
            e = datetime.fromisoformat(end_date)
            if s.month == e.month and s.year == e.year:
                months_ru = {
                    1: 'январь', 2: 'февраль', 3: 'март', 4: 'апрель',
                    5: 'май', 6: 'июнь', 7: 'июль', 8: 'август',
                    9: 'сентябрь', 10: 'октябрь', 11: 'ноябрь', 12: 'декабрь'
                }
                period_desc = f"за {months_ru[s.month]} {s.year}"
            else:
                period_desc = f"с {start_date} по {end_date}"
        except Exception:
            period_desc = f"с {start_date} по {end_date}"

        return (
            f"📦 Категория: {category}\n"
            f"Период: {period_desc}\n"
            f"Трат: {count}\n"
            f"Сумма: {total:,.0f} ₽"
        )

    # Fallback: JSON preview (truncated)
    import json as _json
    try:
        return _json.dumps(result, ensure_ascii=False)[:1000]
    except Exception:
        return str(result)[:1000]
