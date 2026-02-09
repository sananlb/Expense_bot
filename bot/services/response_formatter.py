"""
Unified formatter for function-call results used by AI services.
"""
from __future__ import annotations

from typing import Dict, List, Optional
from bot.utils.language import get_text
from bot.utils.formatters import format_currency
import logging

logger = logging.getLogger(__name__)


def _get_result_currency(result: Dict, fallback: str = 'RUB') -> str:
    currency = result.get('currency') or result.get('user_currency') or fallback
    return currency.upper() if isinstance(currency, str) else fallback


def _get_user_language(result: Dict) -> str:
    """Extract user language from result or default to 'ru'

    IMPORTANT: This function uses Django ORM synchronously.
    It's safe to call from sync context (like format_function_result called via asyncio.to_thread).
    """
    user_id = result.get('user_id')
    logger.info(f"[_get_user_language] Received result with user_id: {user_id}")

    if not user_id:
        logger.warning(f"[_get_user_language] No user_id in result, defaulting to 'ru'. Result keys: {list(result.keys())}")
        return 'ru'

    try:
        import os
        os.environ.setdefault('DJANGO_ALLOW_ASYNC_UNSAFE', 'true')

        from expenses.models import Profile
        profile = Profile.objects.get(telegram_id=user_id)
        language = getattr(profile, 'language_code', 'ru')
        logger.info(f"[_get_user_language] Found profile for user_id={user_id}, language_code='{language}'")
        return language
    except Profile.DoesNotExist:
        logger.error(f"[_get_user_language] Profile not found for user_id={user_id}, defaulting to 'ru'")
        return 'ru'
    except Exception as e:
        logger.error(f"[_get_user_language] Error getting language for user_id={user_id}: {type(e).__name__}: {e}")
        return 'ru'


def _localize_period(period: str, lang: str) -> str:
    """Localize period name (yesterday -> вчера, etc.)"""
    period_translations = {
        'ru': {
            'today': 'сегодня',
            'yesterday': 'вчера',
            'day_before_yesterday': 'позавчера',
            'week': 'неделя',
            'last_week': 'прошлая неделя',
            'month': 'месяц',
            'last_month': 'прошлый месяц',
            'year': 'год',
            'last_year': 'последний год',
            'winter': 'зима',
            'spring': 'весна',
            'summer': 'лето',
            'fall': 'осень',
            'autumn': 'осень',
        },
        'en': {
            'today': 'today',
            'yesterday': 'yesterday',
            'day_before_yesterday': 'day before yesterday',
            'week': 'week',
            'last_week': 'last week',
            'month': 'month',
            'last_month': 'last month',
            'year': 'year',
            'last_year': 'last year',
            'winter': 'winter',
            'spring': 'spring',
            'summer': 'summer',
            'fall': 'fall',
            'autumn': 'autumn',
        }
    }

    translations = period_translations.get(lang, period_translations['ru'])
    return translations.get(period.lower(), period)


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


def _format_operations_list(result: Dict, title: str, subtitle: str, lang: str = 'ru') -> str:
    """Форматирует список операций (расходы и доходы) в стиле дневника"""
    from datetime import datetime, date
    from collections import defaultdict

    operations = result.get('operations', [])
    if not operations:
        return f"<b>{title}</b>\n\n{get_text('no_operations', lang)}"
    default_currency = _get_result_currency(result)

    # Группируем по датам
    grouped_ops = defaultdict(list)
    for op in operations[:100]:  # Ограничиваем количество
        date_str = op.get('date', '2024-01-01')
        grouped_ops[date_str].append(op)

    # Сортируем даты в возрастающем порядке (старые даты вверху)
    sorted_dates = sorted(grouped_ops.keys())

    # Форматируем результат
    result_parts = []
    result_parts.append(f"<b>{title}</b>")
    if subtitle:
        result_parts.append(f"<i>{subtitle}</i>")

    today = date.today()

    # Маппинг месяцев на ключи
    month_keys = [
        'month_january', 'month_february', 'month_march', 'month_april',
        'month_may', 'month_june', 'month_july', 'month_august',
        'month_september', 'month_october', 'month_november', 'month_december'
    ]

    for date_str in sorted_dates:
        # Парсим дату для красивого вывода
        try:
            op_date = datetime.fromisoformat(date_str).date()
            if op_date == today:
                formatted_date = get_text('today', lang)
            else:
                day = op_date.day
                month_key = month_keys[op_date.month - 1]
                month_name = get_text(month_key, lang)
                # Для английского: "January 15", для русского: "15 января"
                if lang == 'en':
                    formatted_date = f"{month_name} {day}"
                else:
                    formatted_date = f"{day} {month_name}"
        except:
            formatted_date = date_str

        result_parts.append(f"\n<b>📅 {formatted_date}</b>")

        # Операции за день
        day_expenses: Dict[str, float] = {}
        day_incomes: Dict[str, float] = {}

        for op in grouped_ops[date_str]:
            time_str = op.get('time', '00:00')
            description = op.get('description', get_text('no_description', lang))
            amount = op.get('amount', 0)
            op_type = op.get('type', 'expense')
            currency = op.get('currency') or default_currency

            if op_type == 'income':
                amount_str = format_currency(abs(amount), currency)
                result_parts.append(f"  {time_str} — <b>{description}</b> <b>+{amount_str}</b>")
                day_incomes[currency] = day_incomes.get(currency, 0) + abs(amount)
            else:
                amount_str = format_currency(abs(amount), currency)
                result_parts.append(f"  {time_str} — {description} {amount_str}")
                day_expenses[currency] = day_expenses.get(currency, 0) + abs(amount)

        # Итоги за день
        if day_expenses:
            expenses_label = get_text('expenses_label', lang)
            totals_list = [format_currency(day_expenses[curr], curr) for curr in sorted(day_expenses.keys(), key=lambda c: (c != default_currency, c))]
            result_parts.append(f"  💸 <b>{expenses_label}:</b> " + ", ".join(totals_list))
        if day_incomes:
            income_label = get_text('income_label', lang)
            totals_list = [format_currency(day_incomes[curr], curr) for curr in sorted(day_incomes.keys(), key=lambda c: (c != default_currency, c))]
            result_parts.append(f"  💰 <b>{income_label}:</b> +" + ", +".join(totals_list))

    # Предупреждение о лимите
    if len(operations) > 100:
        result_parts.append(f"\n⚠️ <i>Показано первые 100 операций</i>")

    return "\n".join(result_parts)


def _format_category_stats(result: Dict) -> str:
    cats = result.get('categories', []) or []
    total = result.get('total', 0)
    start = result.get('start_date', '')
    end = result.get('end_date', '')
    currency = _get_result_currency(result)
    parts: List[str] = []

    # Добавляем даты если они есть
    if start and end:
        if start == end:
            parts.append(f"Статистика по категориям {start} (всего: {format_currency(total, currency)})\n")
        else:
            parts.append(f"Статистика по категориям {start} — {end} (всего: {format_currency(total, currency)})\n")
    else:
        parts.append(f"Статистика по категориям (всего: {format_currency(total, currency)})\n")

    for c in cats[:20]:
        name = c.get('name', '')
        cat_total = c.get('total', c.get('amount', 0))
        count = c.get('count', 0)
        percent = c.get('percentage', 0)
        parts.append(f"• {name}: {format_currency(cat_total, currency)} ({count} шт., {percent:.1f}%)")
    if len(cats) > 20:
        parts.append(f"\n... ещё {len(cats)-20} категорий")
    return "\n".join(parts)


def _format_daily_totals(result: Dict) -> str:
    daily = result.get('daily_totals', {}) or {}
    stats = result.get('statistics', {}) if isinstance(result.get('statistics'), dict) else {}
    total = result.get('total', stats.get('total', 0))
    avg = result.get('average', stats.get('average', 0))
    currency = _get_result_currency(result)
    lang = _get_user_language(result)
    lines = [f"Траты по дням (всего: {format_currency(total, currency)}, среднее: {format_currency(avg, currency)}/{get_text('day', lang)})\n"]
    # latest 30 days by date desc
    for dk in sorted(daily.keys(), reverse=True)[:30]:
        entry = daily.get(dk)
        amount_val = entry.get('amount', 0) if isinstance(entry, dict) else (entry or 0)
        try:
            amount = float(amount_val)
        except Exception:
            amount = 0.0
        if amount > 0:
            lines.append(f"• {dk}: {format_currency(amount, currency)}")
    if len(daily) > 30:
        lines.append(f"\n... данные за {len(daily)} дней")
    return "\n".join(lines)


def format_function_result(func_name: str, result: Dict) -> str:
    """
    Convert ExpenseFunctions/OpenAI/Gemini function-call results to user-facing text.
    """
    logger.info(f"[format_function_result] Called with func_name='{func_name}', user_id={result.get('user_id')}, result_keys={list(result.keys())}")

    if not result.get('success'):
        return f"Ошибка: {result.get('message','Не удалось получить данные')}"
    currency = _get_result_currency(result)

    if func_name == 'get_expenses_list':
        lang = _get_user_language(result)
        total = result.get('total', 0)
        count = result.get('count', len(result.get('expenses', [])))
        start = result.get('start_date', '')
        end = result.get('end_date', '')
        title = f"📋 {get_text('expenses_title', lang)} {start}{(' — ' + end) if end and end != start else ''}"
        subtitle = f"Найдено: {count} трат на сумму {format_currency(total, currency)}"
        return _format_expenses_list(result, title, subtitle)

    if func_name == 'get_max_expense_day':
        date_str = result.get('date', '')
        total = result.get('total', 0)
        count = result.get('count', 0)
        details = result.get('details', []) or []
        for d in details:
            d.setdefault('date', date_str)
        title = "📊 День с максимальными тратами"
        subtitle = f"Дата: {date_str} | Всего: {count} трат на сумму {format_currency(total, currency)}"
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
        query = result.get('query', '')
        period = result.get('period', '')
        start_date = result.get('start_date', '')
        previous_comparison = result.get('previous_comparison')

        # Форматируем числа правильно
        if count == 1:
            count_text = "1 трата"
        elif 2 <= count <= 4:
            count_text = f"{count} траты"
        else:
            count_text = f"{count} трат"

        # Формируем подзаголовок с указанием запроса
        if query:
            subtitle = f"Найдено: {count_text} на сумму {format_currency(total, currency)} по запросу \"{query}\""
        else:
            subtitle = f"Найдено: {count_text} на сумму {format_currency(total, currency)}"
        shown_count = len(results)
        if shown_count and count and shown_count < count:
            subtitle += f" (показано {shown_count})"

        # Форматируем основной список
        formatted_list = _format_expenses_list(
            {'expenses': results},
            title="🔍 Результаты поиска",
            subtitle=subtitle,
        )

        # Добавляем сравнение с предыдущим периодом если оно есть
        if previous_comparison:
            from datetime import datetime

            prev_total = previous_comparison.get('previous_total', 0)
            percent_change = previous_comparison.get('percent_change', 0)
            trend = previous_comparison.get('trend', '')
            prev_period = previous_comparison.get('previous_period', {})
            prev_start = prev_period.get('start', '')

            # Определяем эмодзи в зависимости от тренда
            if trend == 'увеличение':
                trend_emoji = '📈'
            elif trend == 'уменьшение':
                trend_emoji = '📉'
            else:
                trend_emoji = '➡️'

            # Форматируем процент изменения
            abs_percent = abs(percent_change)

            # Определяем название текущего и предыдущего периода
            month_names_ru = {
                1: 'январе', 2: 'феврале', 3: 'марте', 4: 'апреле', 5: 'мае', 6: 'июне',
                7: 'июле', 8: 'августе', 9: 'сентябре', 10: 'октябре', 11: 'ноябре', 12: 'декабре'
            }

            current_period_name = 'в этом периоде'
            prev_period_name = 'предыдущем периоде'

            if start_date:
                try:
                    date_obj = datetime.fromisoformat(start_date)
                    month_num = date_obj.month
                    # Всегда используем название месяца если есть дата
                    current_period_name = f'в {month_names_ru[month_num]}'
                except:
                    pass

            if prev_start:
                try:
                    prev_date_obj = datetime.fromisoformat(prev_start)
                    prev_month_num = prev_date_obj.month
                    prev_period_name = month_names_ru[prev_month_num]
                except:
                    pass

            # Формируем человечное сообщение о сравнении
            if trend == 'без изменений':
                comparison_text = f"\n\n{trend_emoji} {current_period_name.capitalize()} вы потратили столько же, сколько было в {prev_period_name}."
            elif trend == 'увеличение':
                comparison_text = f"\n\n{trend_emoji} {current_period_name.capitalize()} вы потратили на {abs_percent:.1f}% больше, чем в {prev_period_name} (было {format_currency(prev_total, currency)})."
            else:  # уменьшение
                comparison_text = f"\n\n{trend_emoji} {current_period_name.capitalize()} вы потратили на {abs_percent:.1f}% меньше, чем в {prev_period_name} (было {format_currency(prev_total, currency)})."

            formatted_list += comparison_text

        return formatted_list

    if func_name == 'get_expenses_by_amount_range':
        expenses = result.get('expenses', [])
        total = result.get('total', 0)
        count = result.get('count', len(expenses))
        min_amt = result.get('min_amount', 0)
        max_amt = result.get('max_amount', 0)
        title = f"💰 Траты от {format_currency(min_amt, currency)} до {format_currency(max_amt, currency)}"
        subtitle = f"Найдено: {count} трат на сумму {format_currency(total, currency)}"
        return _format_expenses_list({'expenses': expenses}, title, subtitle)

    if func_name == 'get_incomes_list':
        lang = _get_user_language(result)
        total = result.get('total', 0)
        count = result.get('count', len(result.get('incomes', [])))
        start = result.get('start_date', '')
        end = result.get('end_date', '')
        title = f"📋 {get_text('incomes_title', lang)} {start}{(' — ' + end) if end and end != start else ''}"
        subtitle = f"Найдено: {count} доходов на сумму {format_currency(total, currency)}"
        return _format_incomes_list(result, title, subtitle)

    if func_name == 'get_category_total':
        category = result.get('category', '')
        total = result.get('total', 0)
        count = result.get('count', 0)
        period = result.get('period', '')
        start_date = result.get('start_date', '')
        end_date = result.get('end_date', '')
        previous_comparison = result.get('previous_comparison')

        if count == 0:
            return f"За указанный период трат в категории \"{category}\" не найдено."

        # Формируем описание периода
        period_text = {
            'week': 'на этой неделе',
            'month': 'в этом месяце',
            'year': 'в этом году',
            'all': 'за все время'
        }.get(period, f'за период {period}')

        # Пытаемся определить название месяца из периода
        from datetime import datetime

        month_names_ru = {
            1: 'январе', 2: 'феврале', 3: 'марте', 4: 'апреле', 5: 'мае', 6: 'июне',
            7: 'июле', 8: 'августе', 9: 'сентябре', 10: 'октябре', 11: 'ноябре', 12: 'декабре'
        }

        # Если есть start_date, пытаемся определить месяц
        if start_date:
            try:
                date_obj = datetime.fromisoformat(start_date)
                month_num = date_obj.month
                if period.lower() in ('month', 'this_month', 'last_month') or any(m in period.lower() for m in ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь', 'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']):
                    period_text = f'в {month_names_ru[month_num]}'
            except:
                pass

        # Формируем основное сообщение
        if count == 1:
            message = f"В категории \"{category}\" {period_text} вы потратили {format_currency(total, currency)} (1 трата)."
        else:
            message = f"В категории \"{category}\" {period_text} вы потратили {format_currency(total, currency)} ({count} трат)."

        # Добавляем сравнение с предыдущим периодом если оно есть
        if previous_comparison:
            prev_total = previous_comparison.get('previous_total', 0)
            percent_change = previous_comparison.get('percent_change', 0)
            trend = previous_comparison.get('trend', '')
            prev_period = previous_comparison.get('previous_period', {})
            prev_start = prev_period.get('start', '')

            # Определяем эмодзи и текст в зависимости от тренда
            if trend == 'увеличение':
                trend_emoji = '📈'
            elif trend == 'уменьшение':
                trend_emoji = '📉'
            else:
                trend_emoji = '➡️'

            # Форматируем процент изменения
            abs_percent = abs(percent_change)

            # Определяем название предыдущего периода
            prev_period_name = 'предыдущем периоде'
            if prev_start:
                try:
                    prev_date_obj = datetime.fromisoformat(prev_start)
                    prev_month_num = prev_date_obj.month
                    prev_period_name = month_names_ru[prev_month_num]
                except:
                    pass

            if trend == 'без изменений':
                message += f" {trend_emoji} Это столько же, сколько было в {prev_period_name}."
            elif trend == 'увеличение':
                message += f" {trend_emoji} Это на {abs_percent:.1f}% больше, чем в {prev_period_name} (было {format_currency(prev_total, currency)})."
            else:  # уменьшение
                message += f" {trend_emoji} Это на {abs_percent:.1f}% меньше, чем в {prev_period_name} (было {format_currency(prev_total, currency)})."

        return message

    if func_name == 'get_category_total_by_dates':
        lang = _get_user_language(result)
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
                month_keys = [
                    'month_january', 'month_february', 'month_march', 'month_april',
                    'month_may', 'month_june', 'month_july', 'month_august',
                    'month_september', 'month_october', 'month_november', 'month_december'
                ]
                month_name = get_text(month_keys[s.month - 1], lang)
                period_desc = f"за {month_name} {s.year}"
            else:
                period_desc = f"с {start_date} по {end_date}"
        except Exception:
            period_desc = f"с {start_date} по {end_date}"

        return (
            f"📦 Категория: {category}\n"
            f"Период: {period_desc}\n"
            f"Трат: {count}\n"
            f"Сумма: {format_currency(total, currency)}"
        )

    if func_name == 'get_max_single_expense':
        lang = _get_user_language(result)
        date_str = result.get('date', '')
        time_str = result.get('time')
        amount = result.get('amount', 0)
        category = result.get('category', get_text('no_category', lang))
        description = result.get('description', '')
        lines = [f"💸 {get_text('biggest_expense', lang)}"]
        lines.append(f"{get_text('date', lang)}: {date_str}{(' ' + time_str) if time_str else ''}")
        lines.append(f"{get_text('amount', lang)}: {format_currency(amount, currency)}")
        lines.append(f"{get_text('category', lang)}: {category}")
        if description:
            lines.append(f"{get_text('description', lang)}: {description}")
        return "\n".join(lines)

    if func_name == 'get_max_single_income':
        lang = _get_user_language(result)
        inc = result.get('income') or {}
        date_str = inc.get('date', '')
        amount = inc.get('amount', 0)
        category = inc.get('category', get_text('no_category', lang))
        description = inc.get('description', '')
        lines = [f"💰 {get_text('biggest_income', lang)}"]
        lines.append(f"{get_text('date', lang)}: {date_str}")
        lines.append(f"{get_text('amount', lang)}: {format_currency(amount, currency)}")
        lines.append(f"{get_text('category', lang)}: {category}")
        if description:
            lines.append(f"{get_text('description', lang)}: {description}")
        return "\n".join(lines)

    if func_name == 'get_recent_expenses':
        lang = _get_user_language(result)
        count = result.get('count', len(result.get('expenses', [])))
        return _format_expenses_list(result, f"🧾 {get_text('recent_expenses', lang)}", f"{get_text('shown', lang)}: {count}")

    if func_name == 'get_recent_incomes':
        lang = _get_user_language(result)
        count = result.get('count', len(result.get('incomes', [])))
        return _format_incomes_list(result, f"💰 {get_text('recent_incomes', lang)}", f"{get_text('shown', lang)}: {count}")

    if func_name == 'get_period_total':
        lang = _get_user_language(result)
        logger.info(f"[get_period_total] Formatting with lang='{lang}', user_id={result.get('user_id')}")

        total = result.get('total', 0)
        period = result.get('period', '')
        start = result.get('start_date', '')
        end = result.get('end_date', '')
        cats = result.get('categories', []) or []

        # Логируем перед получением текстов
        logger.info(f"[get_period_total] Getting text 'expense_summary' for lang='{lang}'")
        expense_summary_text = get_text('expense_summary', lang)
        logger.info(f"[get_period_total] Got expense_summary='{expense_summary_text}'")

        logger.info(f"[get_period_total] Getting text 'total' for lang='{lang}'")
        total_text = get_text('total', lang)
        logger.info(f"[get_period_total] Got total='{total_text}'")

        localized_period = _localize_period(period, lang)
        lines = [f"{expense_summary_text} {start}{(' — ' + end) if end and end != start else ''} ({localized_period})"]
        lines.append(f"{total_text}: {format_currency(total, currency)}")
        if cats:
            lines.append("")
            top_categories_text = get_text('top_categories', lang)
            logger.info(f"[get_period_total] Got top_categories='{top_categories_text}'")
            lines.append(f"{top_categories_text}:")
            for c in cats:
                lines.append(f"• {c.get('name','')}: {format_currency(c.get('amount', 0), currency)}")

        result_text = "\n".join(lines)
        logger.info(f"[get_period_total] Final formatted text (first 200 chars): {result_text[:200]}")
        return result_text

    if func_name == 'get_income_period_total':
        lang = _get_user_language(result)
        total = result.get('total', 0)
        period = result.get('period', '')
        start = result.get('start_date', '')
        end = result.get('end_date', '')
        cats = result.get('categories', []) or []
        localized_period = _localize_period(period, lang)
        lines = [f"{get_text('income_summary', lang)} {start}{(' — ' + end) if end and end != start else ''} ({localized_period})"]
        lines.append(f"{get_text('total', lang)}: {format_currency(total, currency)}")
        if cats:
            lines.append("")
            lines.append(f"{get_text('top_sources', lang)}:")
            for c in cats:
                lines.append(f"• {c.get('name','')}: {format_currency(c.get('amount', 0), currency)}")
        return "\n".join(lines)

    if func_name == 'get_weekday_statistics':
        lang = _get_user_language(result)
        stats = result.get('statistics') or result.get('weekday_statistics') or {}
        lines = [f"📅 {get_text('expenses_weekday_stats', lang)}"]
        for day, data in stats.items():
            total = (data.get('total') if isinstance(data, dict) else data) or 0
            lines.append(f"• {day}: {format_currency(float(total), currency)}")
        return "\n".join(lines)

    if func_name == 'get_income_weekday_statistics':
        lang = _get_user_language(result)
        stats = result.get('weekday_statistics') or {}
        lines = [f"📅 {get_text('income_weekday_stats', lang)}"]
        for day, data in stats.items():
            total = (data.get('total') if isinstance(data, dict) else data) or 0
            lines.append(f"• {day}: {format_currency(float(total), currency)}")
        return "\n".join(lines)

    if func_name == 'get_average_expenses':
        lang = _get_user_language(result)
        avg = result.get('average', 0)
        days = result.get('period_days') or result.get('days', 30)
        count = result.get('count', 0)
        return f"{get_text('average_expenses', lang)}: {format_currency(avg, currency)}/{get_text('day', lang)} {get_text('for', lang)} {days} {get_text('days_short', lang)} ({get_text('counted', lang)} {count} {get_text('expenses_counted', lang)})"

    if func_name == 'get_average_incomes':
        lang = _get_user_language(result)
        daily = result.get('daily_average', 0)
        weekly = result.get('weekly_average', 0)
        monthly = result.get('monthly_average', 0)
        return (
            f"{get_text('average_incomes', lang)}:\n"
            f"• {get_text('day_capital', lang)}: {format_currency(daily, currency)}\n"
            f"• {get_text('week_capital', lang)}: {format_currency(weekly, currency)}\n"
            f"• {get_text('month_capital', lang)}: {format_currency(monthly, currency)}"
        )

    if func_name == 'get_expense_trend':
        lang = _get_user_language(result)
        trend = result.get('trends') or result.get('trend') or []
        lines = [f"📈 {get_text('expense_trend', lang)}"]
        for item in trend[:12]:
            lines.append(f"• {item.get('period','')}: {format_currency(item.get('total', 0), currency)}")
        return "\n".join(lines)

    if func_name == 'get_income_trend':
        lang = _get_user_language(result)
        trend = result.get('trend') or []
        lines = [f"📈 {get_text('income_trend', lang)}"]
        for item in trend[:12]:
            lines.append(f"• {item.get('period','')}: {format_currency(item.get('total', 0), currency)}")
        return "\n".join(lines)

    if func_name == 'predict_month_expense':
        lang = _get_user_language(result)
        total = result.get('current_total', 0)
        avg = result.get('average_per_day', 0)
        days_passed = result.get('days_passed', 0)
        days_in_month = result.get('days_in_month', 30)
        return (
            f"Прогноз расходов на месяц: {format_currency(total, currency)} уже потрачено, среднее {format_currency(avg, currency)}/{get_text('day', lang)},\n"
            f"прошло {days_passed} из {days_in_month} дней."
        )

    if func_name == 'predict_month_income':
        total = result.get('current_total', 0)
        daily = result.get('daily_rate', 0)
        predicted = result.get('predicted_total', 0)
        return (
            f"Прогноз доходов на месяц: текущая сумма {format_currency(total, currency)},\n"
            f"средний дневной доход {format_currency(daily, currency)}, прогноз {format_currency(predicted, currency)}."
        )

    if func_name == 'check_income_target':
        target = result.get('target', 0)
        current = result.get('current', 0)
        percent = result.get('percentage', 0)
        on_track = result.get('on_track', False)
        return (
            f"Цель по доходам: {format_currency(target, currency)}\n"
            f"Текущий доход: {format_currency(current, currency)}\n"
            f"Достигнуто: {percent:.1f}%\n"
            f"Статус: {'достигнута' if on_track else 'ещё не достигнута'}"
        )

    if func_name == 'compare_periods':
        diff = result.get('difference', 0)
        pct = result.get('percent_change', 0)
        trend = result.get('trend', '')

        # Периоды могут быть строками или словарями
        p1 = result.get('period1', {})
        p2 = result.get('period2', {})

        # Если период - словарь, извлекаем данные
        if isinstance(p1, dict):
            p1_name = p1.get('name', '')
            p1_start = p1.get('start', '')
            p1_end = p1.get('end', '')
            p1_total = p1.get('total', 0)
        else:
            p1_name = str(p1)
            p1_start = p1_end = p1_total = ''

        if isinstance(p2, dict):
            p2_name = p2.get('name', '')
            p2_start = p2.get('start', '')
            p2_end = p2.get('end', '')
            p2_total = p2.get('total', 0)
        else:
            p2_name = str(p2)
            p2_start = p2_end = p2_total = ''

        lines = ["📊 Сравнение периодов\n"]

        # Период 1
        if p1_name:
            if p1_start and p1_end:
                lines.append(f"<b>{p1_name.capitalize()}</b> ({p1_start} — {p1_end}): {format_currency(p1_total, currency)}")
            else:
                lines.append(f"<b>{p1_name}</b>: {format_currency(p1_total, currency)}")

        # Период 2
        if p2_name:
            if p2_start and p2_end:
                lines.append(f"<b>{p2_name.capitalize()}</b> ({p2_start} — {p2_end}): {format_currency(p2_total, currency)}")
            else:
                lines.append(f"<b>{p2_name}</b>: {format_currency(p2_total, currency)}")

        # Разница
        lines.append("")
        if diff > 0:
            lines.append(f"📈 <b>Изменение:</b> +{format_currency(diff, currency)} (+{pct:.1f}%)")
        elif diff < 0:
            lines.append(f"📉 <b>Изменение:</b> {format_currency(diff, currency)} ({pct:.1f}%)")
        else:
            lines.append(f"➡️ <b>Изменение:</b> без изменений")

        if trend:
            trend_emoji = "📈" if trend == "увеличение" else "📉" if trend == "уменьшение" else "➡️"
            lines.append(f"{trend_emoji} <b>Тренд:</b> {trend}")

        return "\n".join(lines)

    if func_name == 'compare_income_periods':
        change = result.get('change', 0)
        pct = result.get('change_percent', 0)
        trend = result.get('trend', '')

        # Периоды могут быть строками или словарями
        p1 = result.get('period1', {})
        p2 = result.get('period2', {})

        # Если период - словарь, извлекаем данные
        if isinstance(p1, dict):
            p1_name = p1.get('name', '')
            p1_start = p1.get('start', '')
            p1_end = p1.get('end', '')
            p1_total = p1.get('total', 0)
        else:
            p1_name = str(p1)
            p1_start = p1_end = p1_total = ''

        if isinstance(p2, dict):
            p2_name = p2.get('name', '')
            p2_start = p2.get('start', '')
            p2_end = p2.get('end', '')
            p2_total = p2.get('total', 0)
        else:
            p2_name = str(p2)
            p2_start = p2_end = p2_total = ''

        lines = ["📊 Сравнение доходов\n"]

        # Период 1
        if p1_name:
            if p1_start and p1_end:
                lines.append(f"<b>{p1_name.capitalize()}</b> ({p1_start} — {p1_end}): {format_currency(p1_total, currency)}")
            else:
                lines.append(f"<b>{p1_name}</b>: {format_currency(p1_total, currency)}")

        # Период 2
        if p2_name:
            if p2_start and p2_end:
                lines.append(f"<b>{p2_name.capitalize()}</b> ({p2_start} — {p2_end}): {format_currency(p2_total, currency)}")
            else:
                lines.append(f"<b>{p2_name}</b>: {format_currency(p2_total, currency)}")

        # Разница
        lines.append("")
        if change > 0:
            lines.append(f"📈 <b>Изменение:</b> +{format_currency(change, currency)} (+{pct:.1f}%)")
        elif change < 0:
            lines.append(f"📉 <b>Изменение:</b> {format_currency(change, currency)} ({pct:.1f}%)")
        else:
            lines.append(f"➡️ <b>Изменение:</b> без изменений")

        if trend:
            trend_emoji = "📈" if trend == "увеличение" else "📉" if trend == "уменьшение" else "➡️"
            lines.append(f"{trend_emoji} <b>Тренд:</b> {trend}")

        return "\n".join(lines)

    if func_name == 'search_incomes':
        results = result.get('incomes', [])
        total = result.get('total', 0)
        count = result.get('count', len(results))
        query = result.get('query', '')
        period = result.get('period', '')
        start_date = result.get('start_date', '')
        previous_comparison = result.get('previous_comparison')

        # Форматируем числа правильно
        if count == 1:
            count_text = "1 доход"
        elif 2 <= count <= 4:
            count_text = f"{count} дохода"
        else:
            count_text = f"{count} доходов"

        # Формируем подзаголовок с указанием запроса
        if query:
            subtitle = f"Найдено: {count_text} на сумму {format_currency(total, currency)} по запросу \"{query}\""
        else:
            subtitle = f"Найдено: {count_text} на сумму {format_currency(total, currency)}"
        shown_count = len(results)
        if shown_count and count and shown_count < count:
            subtitle += f" (показано {shown_count})"

        # Форматируем основной список
        formatted_list = _format_incomes_list(
            {'incomes': results},
            title="🔍 Результаты поиска по доходам",
            subtitle=subtitle,
        )

        # Добавляем сравнение с предыдущим периодом если оно есть
        if previous_comparison:
            from datetime import datetime

            prev_total = previous_comparison.get('previous_total', 0)
            percent_change = previous_comparison.get('percent_change', 0)
            trend = previous_comparison.get('trend', '')
            prev_period = previous_comparison.get('previous_period', {})
            prev_start = prev_period.get('start', '')

            # Определяем эмодзи в зависимости от тренда
            if trend == 'увеличение':
                trend_emoji = '📈'
            elif trend == 'уменьшение':
                trend_emoji = '📉'
            else:
                trend_emoji = '➡️'

            # Форматируем процент изменения
            abs_percent = abs(percent_change)

            # Определяем название текущего и предыдущего периода
            month_names_ru = {
                1: 'январе', 2: 'феврале', 3: 'марте', 4: 'апреле', 5: 'мае', 6: 'июне',
                7: 'июле', 8: 'августе', 9: 'сентябре', 10: 'октябре', 11: 'ноябре', 12: 'декабре'
            }

            current_period_name = 'в этом периоде'
            prev_period_name = 'предыдущем периоде'

            if start_date:
                try:
                    date_obj = datetime.fromisoformat(start_date)
                    month_num = date_obj.month
                    # Всегда используем название месяца если есть дата
                    current_period_name = f'в {month_names_ru[month_num]}'
                except:
                    pass

            if prev_start:
                try:
                    prev_date_obj = datetime.fromisoformat(prev_start)
                    prev_month_num = prev_date_obj.month
                    prev_period_name = month_names_ru[prev_month_num]
                except:
                    pass

            # Формируем человечное сообщение о сравнении
            if trend == 'без изменений':
                comparison_text = f"\n\n{trend_emoji} {current_period_name.capitalize()} вы получили столько же, сколько было в {prev_period_name}."
            elif trend == 'увеличение':
                comparison_text = f"\n\n{trend_emoji} {current_period_name.capitalize()} вы получили на {abs_percent:.1f}% больше, чем в {prev_period_name} (было {format_currency(prev_total, currency)})."
            else:  # уменьшение
                comparison_text = f"\n\n{trend_emoji} {current_period_name.capitalize()} вы получили на {abs_percent:.1f}% меньше, чем в {prev_period_name} (было {format_currency(prev_total, currency)})."

            formatted_list += comparison_text

        return formatted_list

    if func_name == 'get_incomes_by_amount_range':
        incomes = result.get('incomes', [])
        count = result.get('count', len(incomes))
        min_amt = result.get('min_amount', 0)
        max_amt = result.get('max_amount', 0)
        title = f"💰 Доходы от {format_currency(min_amt, currency)} до {format_currency(max_amt, currency)}"
        subtitle = f"Найдено: {count}"
        return _format_incomes_list({'incomes': incomes}, title, subtitle)

    if func_name == 'get_income_category_statistics':
        # Reuse category stats heading for incomes
        return _format_category_stats(result)

    if func_name == 'get_income_category_total':
        category = result.get('category', '')
        total = result.get('total', 0)
        count = result.get('count', 0)
        period = result.get('period', '')
        start_date = result.get('start_date', '')
        end_date = result.get('end_date', '')
        previous_comparison = result.get('previous_comparison')

        if count == 0:
            return f"За указанный период доходов в категории \"{category}\" не найдено."

        # Формируем описание периода
        period_text = {
            'week': 'на этой неделе',
            'month': 'в этом месяце',
            'year': 'в этом году',
            'all': 'за все время'
        }.get(period, f'за период {period}')

        # Пытаемся определить название месяца из периода
        from datetime import datetime

        month_names_ru = {
            1: 'январе', 2: 'феврале', 3: 'марте', 4: 'апреле', 5: 'мае', 6: 'июне',
            7: 'июле', 8: 'августе', 9: 'сентябре', 10: 'октябре', 11: 'ноябре', 12: 'декабре'
        }

        # Если есть start_date, пытаемся определить месяц
        if start_date:
            try:
                date_obj = datetime.fromisoformat(start_date)
                month_num = date_obj.month
                if period.lower() in ('month', 'this_month', 'last_month') or any(m in period.lower() for m in ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь', 'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']):
                    period_text = f'в {month_names_ru[month_num]}'
            except:
                pass

        # Формируем основное сообщение
        if count == 1:
            message = f"В категории \"{category}\" {period_text} вы получили {format_currency(total, currency)} (1 доход)."
        else:
            message = f"В категории \"{category}\" {period_text} вы получили {format_currency(total, currency)} ({count} доходов)."

        # Добавляем сравнение с предыдущим периодом если оно есть
        if previous_comparison:
            prev_total = previous_comparison.get('previous_total', 0)
            percent_change = previous_comparison.get('percent_change', 0)
            trend = previous_comparison.get('trend', '')
            prev_period = previous_comparison.get('previous_period', {})
            prev_start = prev_period.get('start', '')

            # Определяем эмодзи и текст в зависимости от тренда
            if trend == 'увеличение':
                trend_emoji = '📈'
            elif trend == 'уменьшение':
                trend_emoji = '📉'
            else:
                trend_emoji = '➡️'

            # Форматируем процент изменения
            abs_percent = abs(percent_change)

            # Определяем название предыдущего периода
            prev_period_name = 'предыдущем периоде'
            if prev_start:
                try:
                    prev_date_obj = datetime.fromisoformat(prev_start)
                    prev_month_num = prev_date_obj.month
                    prev_period_name = month_names_ru[prev_month_num]
                except:
                    pass

            if trend == 'без изменений':
                message += f" {trend_emoji} Это столько же, сколько было в {prev_period_name}."
            elif trend == 'увеличение':
                message += f" {trend_emoji} Это на {abs_percent:.1f}% больше, чем в {prev_period_name} (было {format_currency(prev_total, currency)})."
            else:  # уменьшение
                message += f" {trend_emoji} Это на {abs_percent:.1f}% меньше, чем в {prev_period_name} (было {format_currency(prev_total, currency)})."

        return message

    if func_name == 'get_daily_income_totals':
        lang = _get_user_language(result)
        daily = result.get('daily_totals', [])
        total = result.get('grand_total', 0)
        lines = [f"{get_text('incomes_title', lang)} по дням (всего: {format_currency(total, currency)})\n"]
        for d in daily[:30]:
            lines.append(f"• {d.get('date','')}: {format_currency(d.get('total', 0), currency)}")
        return "\n".join(lines)

    if func_name == 'get_all_operations':
        lang = _get_user_language(result)
        ops = result.get('operations', [])
        total_expense = result.get('total_expense', 0)
        total_income = result.get('total_income', 0)
        count = result.get('count', len(ops))
        start = result.get('start_date', '')
        end = result.get('end_date', '')
        title = f"📊 {get_text('operations', lang)} {start}{(' — ' + end) if end and end != start else ''}"
        subtitle = f"Найдено: {count} операций (расходы: {format_currency(total_expense, currency)}, доходы: {format_currency(total_income, currency)})"
        return _format_operations_list({'operations': ops}, title, subtitle, lang)

    if func_name == 'get_financial_summary':
        period = result.get('period', '')
        start = result.get('start_date', '')
        end = result.get('end_date', '')
        income = (result.get('income') or {}).get('total', 0)
        expense = (result.get('expense') or {}).get('total', 0)
        net = (result.get('balance') or {}).get('net', income - expense)
        return (
            f"Финансовая сводка ({period}) {start}{(' — ' + end) if end and end != start else ''}\n"
            f"Доходы: {format_currency(income, currency)}\n"
            f"Расходы: {format_currency(expense, currency)}\n"
            f"Баланс: {format_currency(net, currency)}"
        )

    # Analytics query fallback formatting
    if func_name == 'analytics_query':
        lang = _get_user_language(result)
        if not result.get('success'):
            return f"Ошибка выполнения аналитического запроса: {result.get('message','не удалось выполнить запрос')}"
        entity = result.get('entity', 'expenses')
        group_by = result.get('group_by', 'none')
        items = result.get('results', []) or []

        title_map = {
            'expenses': get_text('expenses_title', lang),
            'incomes': get_text('incomes_title', lang),
            'operations': get_text('operations', lang),
        }
        title = title_map.get(entity, 'Данные')

        lines = [f"{title} — найдено: {len(items)}"]

        if group_by == 'category':
            for it in items[:20]:
                name = it.get('category') or get_text('no_category', lang)
                total = it.get('total') or it.get('sum') or it.get('amount') or 0
                cnt = it.get('count', '')
                avg = it.get('average')
                item_currency = it.get('currency') or currency
                parts = [f"• {name}: {format_currency(float(total), item_currency)}"]
                if cnt:
                    parts.append(f"({cnt} шт.)")
                if avg:
                    parts.append(f", ср.: {format_currency(float(avg), item_currency)}")
                lines.append(' '.join(parts))
        elif group_by == 'date':
            for it in items[:30]:
                d = it.get('date')
                total = it.get('total') or it.get('sum') or it.get('amount') or 0
                cnt = it.get('count', '')
                suffix = f" ({cnt} шт.)" if cnt else ''
                item_currency = it.get('currency') or currency
                lines.append(f"• {d}: {format_currency(float(total), item_currency)}{suffix}")
        elif group_by == 'weekday':
            for it in items:
                wd = it.get('weekday') or ''
                total = it.get('total') or it.get('sum') or 0
                item_currency = it.get('currency') or currency
                lines.append(f"• {wd}: {format_currency(float(total), item_currency)}")
        else:
            # List mode
            for it in items[:20]:
                d = it.get('date', '')
                amount = it.get('amount', 0)
                cat = it.get('category') or get_text('no_category', lang)
                desc = (it.get('description') or '')[:60]
                item_currency = it.get('currency') or currency
                lines.append(f"• {d} — {format_currency(float(amount), item_currency)} — {cat} — {desc}")

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
    lang = _get_user_language(result)
    currency = _get_result_currency(result)

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
        item_currency = item.get('currency') or currency
        if entity == 'expenses':
            lines.append("💰 Результат поиска:")
            lines.append(f"Дата: {item.get('date', 'N/A')}")
            lines.append(f"Сумма: {format_currency(item.get('amount', 0), item_currency)}")
            if 'category' in item:
                lines.append(f"Категория: {item.get('category', get_text('no_category', lang))}")
            if 'description' in item:
                lines.append(f"Описание: {item.get('description', '')}")
        elif entity == 'incomes':
            lines.append("💵 Результат поиска:")
            lines.append(f"Дата: {item.get('date', 'N/A')}")
            lines.append(f"Сумма: {format_currency(item.get('amount', 0), item_currency)}")
            if 'category' in item:
                lines.append(f"Категория: {item.get('category', get_text('no_category', lang))}")
            if 'description' in item:
                lines.append(f"Описание: {item.get('description', '')}")
        return "\n".join(lines)

    # List of items
    if group_by == 'none':
        entity_emoji = '💸' if entity == 'expenses' else '💰' if entity == 'incomes' else '📊'
        if entity == 'expenses':
            entity_name = get_text('expenses_title', lang)
        elif entity == 'incomes':
            entity_name = get_text('incomes_title', lang)
        else:
            entity_name = get_text('operations', lang)
        lines.append(f"{entity_emoji} {entity_name} (найдено: {count})\n")

        for i, item in enumerate(results[:20], 1):
            date_str = item.get('date', '')
            amount = item.get('amount', 0)
            category = item.get('category', '')
            description = item.get('description', '')
            item_currency = item.get('currency') or currency

            line = f"{i}. {date_str}"
            if entity == 'operations':
                op_type = item.get('type', '')
                sign = '-' if op_type == 'expense' else '+'
                line += f" {sign}{format_currency(amount, item_currency)}"
            else:
                line += f" • {format_currency(amount, item_currency)}"

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
            item_currency = item.get('currency') or currency
            lines.append(f"• {date_str}: {format_currency(total, item_currency)} ({count} шт.)")

    elif group_by == 'category':
        lines.append("📦 Результаты по категориям:\n")
        for item in results[:20]:
            category = item.get('category', get_text('no_category', lang))
            total = item.get('total', 0)
            count = item.get('count', 0)
            item_currency = item.get('currency') or currency
            lines.append(f"• {category}: {format_currency(total, item_currency)} ({count} шт.)")

    elif group_by == 'weekday':
        lines.append("📅 Результаты по дням недели:\n")
        for item in results:
            weekday = item.get('weekday', 'N/A')
            total = item.get('total', 0)
            count = item.get('count', 0)
            avg = item.get('average', 0)
            item_currency = item.get('currency') or currency
            lines.append(f"• {weekday}: {format_currency(total, item_currency)} (среднее: {format_currency(avg, item_currency)})")

    return "\n".join(lines)
