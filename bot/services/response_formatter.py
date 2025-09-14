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

    if func_name == 'get_max_single_expense':
        date_str = result.get('date', '')
        time_str = result.get('time')
        amount = result.get('amount', 0)
        category = result.get('category', 'Без категории')
        description = result.get('description', '')
        lines = ["💸 Самая большая трата"]
        lines.append(f"Дата: {date_str}{(' ' + time_str) if time_str else ''}")
        lines.append(f"Сумма: {amount:,.0f} ₽")
        lines.append(f"Категория: {category}")
        if description:
            lines.append(f"Описание: {description}")
        return "\n".join(lines)

    if func_name == 'get_max_single_income':
        inc = result.get('income') or {}
        date_str = inc.get('date', '')
        amount = inc.get('amount', 0)
        category = inc.get('category', 'Без категории')
        description = inc.get('description', '')
        lines = ["💰 Самый большой доход"]
        lines.append(f"Дата: {date_str}")
        lines.append(f"Сумма: {amount:,.0f} ₽")
        lines.append(f"Категория: {category}")
        if description:
            lines.append(f"Описание: {description}")
        return "\n".join(lines)

    if func_name == 'get_recent_expenses':
        count = result.get('count', len(result.get('expenses', [])))
        return _format_expenses_list(result, "🧾 Последние траты", f"Показано: {count}")

    if func_name == 'get_recent_incomes':
        count = result.get('count', len(result.get('incomes', [])))
        return _format_incomes_list(result, "💰 Последние доходы", f"Показано: {count}")

    if func_name == 'get_period_total':
        total = result.get('total', 0)
        period = result.get('period', '')
        start = result.get('start_date', '')
        end = result.get('end_date', '')
        cats = result.get('categories', []) or []
        lines = [f"Итоги расходов {start}{(' — ' + end) if end and end != start else ''} ({period})"]
        lines.append(f"Всего: {total:,.0f} ₽")
        if cats:
            lines.append("")
            lines.append("Топ категорий:")
            for c in cats:
                lines.append(f"• {c.get('name','')}: {c.get('amount',0):,.0f} ₽")
        return "\n".join(lines)

    if func_name == 'get_income_period_total':
        total = result.get('total', 0)
        period = result.get('period', '')
        start = result.get('start_date', '')
        end = result.get('end_date', '')
        cats = result.get('categories', []) or []
        lines = [f"Итоги доходов {start}{(' — ' + end) if end and end != start else ''} ({period})"]
        lines.append(f"Всего: {total:,.0f} ₽")
        if cats:
            lines.append("")
            lines.append("Топ источников:")
            for c in cats:
                lines.append(f"• {c.get('name','')}: {c.get('amount',0):,.0f} ₽")
        return "\n".join(lines)

    if func_name == 'get_weekday_statistics':
        stats = result.get('statistics') or result.get('weekday_statistics') or {}
        lines = ["📅 Расходы по дням недели"]
        for day, data in stats.items():
            total = (data.get('total') if isinstance(data, dict) else data) or 0
            lines.append(f"• {day}: {float(total):,.0f} ₽")
        return "\n".join(lines)

    if func_name == 'get_income_weekday_statistics':
        stats = result.get('weekday_statistics') or {}
        lines = ["📅 Доходы по дням недели"]
        for day, data in stats.items():
            total = (data.get('total') if isinstance(data, dict) else data) or 0
            lines.append(f"• {day}: {float(total):,.0f} ₽")
        return "\n".join(lines)

    if func_name == 'get_average_expenses':
        avg = result.get('average', 0)
        days = result.get('period_days') or result.get('days', 30)
        count = result.get('count', 0)
        return f"Средние расходы: {avg:,.0f} ₽/день за {days} дн. (учтено {count} трат)"

    if func_name == 'get_average_incomes':
        daily = result.get('daily_average', 0)
        weekly = result.get('weekly_average', 0)
        monthly = result.get('monthly_average', 0)
        return (
            "Средние доходы:\n"
            f"• День: {daily:,.0f} ₽\n"
            f"• Неделя: {weekly:,.0f} ₽\n"
            f"• Месяц: {monthly:,.0f} ₽"
        )

    if func_name == 'get_expense_trend':
        trend = result.get('trends') or result.get('trend') or []
        lines = ["📈 Тренд расходов"]
        for item in trend[:12]:
            lines.append(f"• {item.get('period','')}: {item.get('total',0):,.0f} ₽")
        return "\n".join(lines)

    if func_name == 'get_income_trend':
        trend = result.get('trend') or []
        lines = ["📈 Тренд доходов"]
        for item in trend[:12]:
            lines.append(f"• {item.get('period','')}: {item.get('total',0):,.0f} ₽")
        return "\n".join(lines)

    if func_name == 'predict_month_expense':
        total = result.get('current_total', 0)
        avg = result.get('average_per_day', 0)
        days_passed = result.get('days_passed', 0)
        days_in_month = result.get('days_in_month', 30)
        return (
            f"Прогноз расходов на месяц: {total:,.0f} ₽ уже потрачено, среднее {avg:,.0f} ₽/день,\n"
            f"прошло {days_passed} из {days_in_month} дней."
        )

    if func_name == 'predict_month_income':
        total = result.get('current_total', 0)
        daily = result.get('daily_rate', 0)
        predicted = result.get('predicted_total', 0)
        return (
            f"Прогноз доходов на месяц: текущая сумма {total:,.0f} ₽,\n"
            f"средний дневной доход {daily:,.0f} ₽, прогноз {predicted:,.0f} ₽."
        )

    if func_name == 'check_budget_status':
        budget = result.get('budget', 0)
        spent = result.get('spent', 0)
        remaining = result.get('remaining', 0)
        percent = result.get('percent_used', 0)
        status = result.get('status', '')
        return (
            f"Бюджет: {budget:,.0f} ₽\n"
            f"Потрачено: {spent:,.0f} ₽ ({percent:.1f}%)\n"
            f"Осталось: {remaining:,.0f} ₽\n"
            f"Статус: {status}"
        )

    if func_name == 'check_income_target':
        target = result.get('target', 0)
        current = result.get('current', 0)
        percent = result.get('percentage', 0)
        on_track = result.get('on_track', False)
        return (
            f"Цель по доходам: {target:,.0f} ₽\n"
            f"Текущий доход: {current:,.0f} ₽\n"
            f"Достигнуто: {percent:.1f}%\n"
            f"Статус: {'достигнута' if on_track else 'ещё не достигнута'}"
        )

    if func_name == 'compare_periods':
        diff = result.get('difference', 0)
        pct = result.get('percent_change', 0)
        p1 = result.get('period1', '')
        p2 = result.get('period2', '')
        return (
            f"Сравнение периодов ({p1} vs {p2})\n"
            f"Изменение: {diff:,.0f} ₽ ({pct:.1f}%)"
        )

    if func_name == 'compare_income_periods':
        change = result.get('change', 0)
        pct = result.get('change_percent', 0)
        curr = result.get('current_month', 0)
        prev = result.get('previous_month', 0)
        return (
            f"Сравнение доходов (текущий/прошлый месяц)\n"
            f"Текущий: {curr:,.0f} ₽, прошлый: {prev:,.0f} ₽\n"
            f"Изменение: {change:,.0f} ₽ ({pct:.1f}%)"
        )

    if func_name == 'search_incomes':
        results = result.get('incomes', [])
        count = result.get('count', len(results))
        return _format_incomes_list({'incomes': results}, "🔍 Результаты поиска по доходам", f"Найдено: {count}")

    if func_name == 'get_incomes_by_amount_range':
        incomes = result.get('incomes', [])
        count = result.get('count', len(incomes))
        min_amt = result.get('min_amount', 0)
        max_amt = result.get('max_amount', 0)
        title = f"💰 Доходы от {min_amt:,.0f} до {max_amt:,.0f} ₽"
        subtitle = f"Найдено: {count}"
        return _format_incomes_list({'incomes': incomes}, title, subtitle)

    if func_name == 'get_income_category_statistics':
        # Reuse category stats heading for incomes
        return _format_category_stats(result)

    if func_name == 'get_daily_income_totals':
        daily = result.get('daily_totals', [])
        total = result.get('grand_total', 0)
        lines = [f"Доходы по дням (всего: {total:,.0f} ₽)\n"]
        for d in daily[:30]:
            lines.append(f"• {d.get('date','')}: {d.get('total',0):,.0f} ₽")
        return "\n".join(lines)

    if func_name == 'get_all_operations':
        ops = result.get('operations', [])
        count = result.get('count', len(ops))
        start = result.get('start_date', '')
        end = result.get('end_date', '')
        lines = [f"Все операции {start}{(' — ' + end) if end and end != start else ''} (показано: {count})"]
        for op in ops[:50]:
            sign = '+' if op.get('type') == 'income' else '-'
            lines.append(f"• {op.get('date','')} {sign}{abs(op.get('amount',0)):,.0f} ₽ — {op.get('description','')}")
        if len(ops) > 50:
            lines.append(f"... и ещё {len(ops)-50} операций")
        return "\n".join(lines)

    if func_name == 'get_financial_summary':
        period = result.get('period', '')
        start = result.get('start_date', '')
        end = result.get('end_date', '')
        income = (result.get('income') or {}).get('total', 0)
        expense = (result.get('expense') or {}).get('total', 0)
        net = (result.get('balance') or {}).get('net', income - expense)
        return (
            f"Финансовая сводка ({period}) {start}{(' — ' + end) if end and end != start else ''}\n"
            f"Доходы: {income:,.0f} ₽\n"
            f"Расходы: {expense:,.0f} ₽\n"
            f"Баланс: {net:,.0f} ₽"
        )

    # Analytics query fallback formatting
    if func_name == 'analytics_query':
        if not result.get('success'):
            return f"Ошибка выполнения аналитического запроса: {result.get('message','не удалось выполнить запрос')}"
        entity = result.get('entity', 'expenses')
        group_by = result.get('group_by', 'none')
        items = result.get('results', []) or []

        title_map = {
            'expenses': 'Траты',
            'incomes': 'Доходы',
            'operations': 'Операции',
        }
        title = title_map.get(entity, 'Данные')

        lines = [f"{title} — найдено: {len(items)}"]

        if group_by == 'category':
            for it in items[:20]:
                name = it.get('category') or 'Без категории'
                total = it.get('total') or it.get('sum') or it.get('amount') or 0
                cnt = it.get('count', '')
                avg = it.get('average')
                parts = [f"• {name}: {float(total):,.0f} ₽"]
                if cnt:
                    parts.append(f"({cnt} шт.)")
                if avg:
                    parts.append(f", ср.: {float(avg):,.0f} ₽")
                lines.append(' '.join(parts))
        elif group_by == 'date':
            for it in items[:30]:
                d = it.get('date')
                total = it.get('total') or it.get('sum') or it.get('amount') or 0
                cnt = it.get('count', '')
                suffix = f" ({cnt} шт.)" if cnt else ''
                lines.append(f"• {d}: {float(total):,.0f} ₽{suffix}")
        elif group_by == 'weekday':
            for it in items:
                wd = it.get('weekday') or ''
                total = it.get('total') or it.get('sum') or 0
                lines.append(f"• {wd}: {float(total):,.0f} ₽")
        else:
            # List mode
            for it in items[:20]:
                d = it.get('date', '')
                amount = it.get('amount', 0)
                cat = it.get('category') or 'Без категории'
                desc = (it.get('description') or '')[:60]
                lines.append(f"• {d} — {float(amount):,.0f} ₽ — {cat} — {desc}")

        if len(items) > 20:
            lines.append(f"... и ещё {len(items)-20} записей")
        return "\n".join(lines)

    if func_name == 'analytics_query':
        return _format_analytics_query_result(result)

    # Fallback: JSON preview (truncated)
    import json as _json
    try:
        return _json.dumps(result, ensure_ascii=False)[:1000]
    except Exception:
        return str(result)[:1000]


def _format_analytics_query_result(result: Dict) -> str:
    """Format analytics query results."""
    if not result.get('success'):
        return f"❌ {result.get('message', 'Не удалось выполнить запрос')}"

    entity = result.get('entity', 'unknown')
    group_by = result.get('group_by', 'none')
    results = result.get('results', [])
    count = result.get('count', 0)

    if count == 0:
        entity_name = {
            'expenses': 'трат',
            'incomes': 'доходов',
            'operations': 'операций'
        }.get(entity, 'записей')
        return f"По вашему запросу {entity_name} не найдено."

    lines = []

    # Single item result (like minimum expense)
    if count == 1 and group_by == 'none':
        item = results[0]
        if entity == 'expenses':
            lines.append("💰 Результат поиска:")
            lines.append(f"Дата: {item.get('date', 'N/A')}")
            lines.append(f"Сумма: {item.get('amount', 0):,.0f} ₽")
            if 'category' in item:
                lines.append(f"Категория: {item.get('category', 'Без категории')}")
            if 'description' in item:
                lines.append(f"Описание: {item.get('description', '')}")
        elif entity == 'incomes':
            lines.append("💵 Результат поиска:")
            lines.append(f"Дата: {item.get('date', 'N/A')}")
            lines.append(f"Сумма: {item.get('amount', 0):,.0f} ₽")
            if 'category' in item:
                lines.append(f"Категория: {item.get('category', 'Без категории')}")
            if 'description' in item:
                lines.append(f"Описание: {item.get('description', '')}")
        return "\n".join(lines)

    # List of items
    if group_by == 'none':
        entity_emoji = '💸' if entity == 'expenses' else '💰' if entity == 'incomes' else '📊'
        entity_name = 'Траты' if entity == 'expenses' else 'Доходы' if entity == 'incomes' else 'Операции'
        lines.append(f"{entity_emoji} {entity_name} (найдено: {count})\n")

        for i, item in enumerate(results[:20], 1):
            date_str = item.get('date', '')
            amount = item.get('amount', 0)
            category = item.get('category', '')
            description = item.get('description', '')

            line = f"{i}. {date_str}"
            if entity == 'operations':
                op_type = item.get('type', '')
                sign = '-' if op_type == 'expense' else '+'
                line += f" {sign}{amount:,.0f} ₽"
            else:
                line += f" • {amount:,.0f} ₽"

            if category:
                line += f" • {category}"
            if description:
                line += f" • {description[:30]}"

            lines.append(line)

        if count > 20:
            lines.append(f"\n... и ещё {count - 20} записей")

        return "\n".join(lines)

    # Grouped results
    if group_by == 'date':
        lines.append("📅 Результаты по датам:\n")
        for item in results[:30]:
            date_str = item.get('date', 'N/A')
            total = item.get('total', 0)
            count = item.get('count', 0)
            lines.append(f"• {date_str}: {total:,.0f} ₽ ({count} шт.)")

    elif group_by == 'category':
        lines.append("📦 Результаты по категориям:\n")
        for item in results[:20]:
            category = item.get('category', 'Без категории')
            total = item.get('total', 0)
            count = item.get('count', 0)
            lines.append(f"• {category}: {total:,.0f} ₽ ({count} шт.)")

    elif group_by == 'weekday':
        lines.append("📅 Результаты по дням недели:\n")
        for item in results:
            weekday = item.get('weekday', 'N/A')
            total = item.get('total', 0)
            count = item.get('count', 0)
            avg = item.get('average', 0)
            lines.append(f"• {weekday}: {total:,.0f} ₽ (среднее: {avg:,.0f} ₽)")

    return "\n".join(lines)
