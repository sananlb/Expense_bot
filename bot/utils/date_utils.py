"""
Утилиты для работы с датами и временными периодами
"""
from datetime import date, datetime, timedelta
from typing import Tuple, Optional


def get_period_dates(period: str, base_date: Optional[date] = None) -> Tuple[date, date]:
    """
    Получить начальную и конечную дату для заданного периода

    Args:
        period: Название периода:
            - 'today': сегодня
            - 'yesterday': вчера
            - 'week', 'this_week': текущая неделя с понедельника
            - 'last_week': прошлая неделя (пн-вс)
            - 'month', 'this_month': текущий месяц
            - 'last_month': прошлый месяц
            - 'year', 'this_year': текущий год
            - 'last_year': последние 365 дней (скользящее окно)
            - Времена года: 'зима', 'весна', 'лето', 'осень' (или winter, spring, summer, autumn/fall)
            - Названия месяцев: 'январь', 'февраль', ... 'декабрь'
            - Month names: 'january', 'february', ... 'december'
            - Сокращения: 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'
        base_date: Базовая дата для расчетов (по умолчанию - сегодня)

    Returns:
        Кортеж (start_date, end_date) включительно

    Examples:
        >>> get_period_dates('today')
        (date(2025, 9, 24), date(2025, 9, 24))

        >>> get_period_dates('last_week')
        (date(2025, 9, 15), date(2025, 9, 21))  # Пн-Вс прошлой недели

        >>> get_period_dates('last_month')
        (date(2025, 8, 1), date(2025, 8, 31))

        >>> get_period_dates('август')  # В сентябре вернет август текущего года
        (date(2025, 8, 1), date(2025, 8, 31))

        >>> get_period_dates('лето')  # В сентябре вернет прошедшее лето
        (date(2025, 6, 1), date(2025, 8, 31))
    """
    if base_date is None:
        base_date = date.today()

    # Сегодня
    if period == 'today':
        return base_date, base_date

    # Вчера
    elif period == 'yesterday':
        yesterday = base_date - timedelta(days=1)
        return yesterday, yesterday

    # Текущая неделя (с понедельника)
    elif period in ('week', 'this_week'):
        # Начало недели - понедельник
        start = base_date - timedelta(days=base_date.weekday())
        end = base_date
        return start, end

    # Прошлая неделя (полная неделя пн-вс)
    elif period == 'last_week':
        # Начало текущей недели
        this_week_start = base_date - timedelta(days=base_date.weekday())
        # Конец прошлой недели (воскресенье)
        last_week_end = this_week_start - timedelta(days=1)
        # Начало прошлой недели (понедельник)
        last_week_start = last_week_end - timedelta(days=6)
        return last_week_start, last_week_end

    # Текущий месяц
    elif period in ('month', 'this_month'):
        start = base_date.replace(day=1)
        end = base_date
        return start, end

    # Прошлый месяц (полный месяц)
    elif period == 'last_month':
        # Первый день текущего месяца
        this_month_start = base_date.replace(day=1)
        # Последний день прошлого месяца
        last_month_end = this_month_start - timedelta(days=1)
        # Первый день прошлого месяца
        last_month_start = last_month_end.replace(day=1)
        return last_month_start, last_month_end

    # Текущий год
    elif period in ('year', 'this_year'):
        start = base_date.replace(month=1, day=1)
        end = base_date
        return start, end

    # Последний год (скользящее окно — 365 дней назад до сегодня)
    elif period == 'last_year':
        start = base_date - timedelta(days=365)
        end = base_date
        return start, end

    # Позавчера
    elif period in ('day_before_yesterday', 'позавчера'):
        day = base_date - timedelta(days=2)
        return day, day

    # Три дня назад
    elif period == 'three_days_ago':
        day = base_date - timedelta(days=3)
        return day, day

    # Позапрошлая неделя (неделя перед прошлой)
    elif period == 'week_before_last':
        # Начало текущей недели
        this_week_start = base_date - timedelta(days=base_date.weekday())
        # Начало прошлой недели
        last_week_start = this_week_start - timedelta(days=7)
        # Начало позапрошлой недели
        week_before_last_start = last_week_start - timedelta(days=7)
        week_before_last_end = week_before_last_start + timedelta(days=6)
        return week_before_last_start, week_before_last_end

    # Позапрошлый месяц
    elif period == 'month_before_last':
        # Первый день текущего месяца
        this_month_start = base_date.replace(day=1)
        # Последний день позапрошлого месяца
        month_before_last_end = this_month_start - timedelta(days=1)
        month_before_last_end = month_before_last_end.replace(day=1) - timedelta(days=1)
        # Первый день позапрошлого месяца
        month_before_last_start = month_before_last_end.replace(day=1)
        return month_before_last_start, month_before_last_end

    # Последние N дней (для обратной совместимости)
    elif period.isdigit():
        days = int(period)
        start = base_date - timedelta(days=days-1)
        end = base_date
        return start, end

    # Проверяем времена года
    elif period.lower() in ['зима', 'winter', 'зимой']:
        # Зима: декабрь, январь, февраль
        current_month = base_date.month
        current_year = base_date.year

        # Определяем какая зима нужна
        if current_month >= 3:  # Если сейчас март или позже
            # Прошедшая зима (декабрь прошлого года - февраль текущего)
            start = date(current_year - 1, 12, 1)
            end = date(current_year, 2, 28)
            # Проверяем на високосный год
            if current_year % 4 == 0 and (current_year % 100 != 0 or current_year % 400 == 0):
                end = date(current_year, 2, 29)
        else:  # Если сейчас январь или февраль
            # Текущая зима (декабрь прошлого года - февраль текущего)
            start = date(current_year - 1, 12, 1)
            end = base_date  # До текущей даты
        return start, end

    elif period.lower() in ['весна', 'spring', 'весной']:
        # Весна: март, апрель, май
        current_month = base_date.month
        current_year = base_date.year

        if current_month >= 6:  # Если сейчас июнь или позже
            # Прошедшая весна
            start = date(current_year, 3, 1)
            end = date(current_year, 5, 31)
        elif current_month >= 3:  # Если сейчас март-май
            # Текущая весна
            start = date(current_year, 3, 1)
            end = base_date
        else:  # Если сейчас январь-февраль
            # Прошлая весна
            start = date(current_year - 1, 3, 1)
            end = date(current_year - 1, 5, 31)
        return start, end

    elif period.lower() in ['лето', 'summer', 'летом']:
        # Лето: июнь, июль, август
        current_month = base_date.month
        current_year = base_date.year

        if current_month >= 9:  # Если сейчас сентябрь или позже
            # Прошедшее лето
            start = date(current_year, 6, 1)
            end = date(current_year, 8, 31)
        elif current_month >= 6:  # Если сейчас июнь-август
            # Текущее лето
            start = date(current_year, 6, 1)
            end = base_date
        else:  # Если сейчас январь-май
            # Прошлое лето
            start = date(current_year - 1, 6, 1)
            end = date(current_year - 1, 8, 31)
        return start, end

    elif period.lower() in ['осень', 'autumn', 'fall', 'осенью']:
        # Осень: сентябрь, октябрь, ноябрь
        current_month = base_date.month
        current_year = base_date.year

        if current_month >= 12:  # Если сейчас декабрь
            # Прошедшая осень
            start = date(current_year, 9, 1)
            end = date(current_year, 11, 30)
        elif current_month >= 9:  # Если сейчас сентябрь-ноябрь
            # Текущая осень
            start = date(current_year, 9, 1)
            end = base_date
        else:  # Если сейчас январь-август
            # Прошлая осень
            start = date(current_year - 1, 9, 1)
            end = date(current_year - 1, 11, 30)
        return start, end

    # Проверяем не является ли period названием месяца
    else:
        # Словарь названий месяцев на русском и английском
        month_names = {
            # Русские названия
            'январь': 1, 'января': 1,
            'февраль': 2, 'февраля': 2,
            'март': 3, 'марта': 3,
            'апрель': 4, 'апреля': 4,
            'май': 5, 'мая': 5,
            'июнь': 6, 'июня': 6,
            'июль': 7, 'июля': 7,
            'август': 8, 'августа': 8,
            'сентябрь': 9, 'сентября': 9,
            'октябрь': 10, 'октября': 10,
            'ноябрь': 11, 'ноября': 11,
            'декабрь': 12, 'декабря': 12,
            # Английские названия
            'january': 1, 'jan': 1,
            'february': 2, 'feb': 2,
            'march': 3, 'mar': 3,
            'april': 4, 'apr': 4,
            'may': 5,
            'june': 6, 'jun': 6,
            'july': 7, 'jul': 7,
            'august': 8, 'aug': 8,
            'september': 9, 'sep': 9, 'sept': 9,
            'october': 10, 'oct': 10,
            'november': 11, 'nov': 11,
            'december': 12, 'dec': 12,
        }

        # Проверяем, не название ли месяца
        period_lower = period.lower()
        if period_lower in month_names:
            month_num = month_names[period_lower]
            year = base_date.year

            # Если запрашиваемый месяц больше текущего, значит это прошлый год
            if month_num > base_date.month:
                year -= 1

            # Первый день месяца
            start = date(year, month_num, 1)

            # Последний день месяца
            if month_num == 12:
                end = date(year, 12, 31)
            else:
                # Последний день месяца = день перед первым днём следующего месяца
                end = date(year, month_num + 1, 1) - timedelta(days=1)

            return start, end

        # По умолчанию - текущий месяц
        start = base_date.replace(day=1)
        end = base_date
        return start, end


def period_to_days(period: str, base_date: Optional[date] = None) -> int:
    """
    Преобразовать период в количество дней

    Args:
        period: Название периода
        base_date: Базовая дата для расчетов

    Returns:
        Количество дней в периоде
    """
    start_date, end_date = get_period_dates(period, base_date)
    return (end_date - start_date).days + 1


def get_month_name(month_num: int, language: str = 'ru') -> str:
    """
    Получить название месяца

    Args:
        month_num: Номер месяца (1-12)
        language: Язык ('ru' или 'en')

    Returns:
        Название месяца
    """
    if language == 'ru':
        months = [
            'январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
            'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь'
        ]
    else:
        months = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]

    if 1 <= month_num <= 12:
        return months[month_num - 1]
    return str(month_num)


def get_weekday_name(weekday_num: int, language: str = 'ru') -> str:
    """
    Получить название дня недели

    Args:
        weekday_num: Номер дня недели (0=пн, 6=вс)
        language: Язык ('ru' или 'en')

    Returns:
        Название дня недели
    """
    if language == 'ru':
        weekdays = [
            'Понедельник', 'Вторник', 'Среда', 'Четверг',
            'Пятница', 'Суббота', 'Воскресенье'
        ]
    else:
        weekdays = [
            'Monday', 'Tuesday', 'Wednesday', 'Thursday',
            'Friday', 'Saturday', 'Sunday'
        ]

    if 0 <= weekday_num <= 6:
        return weekdays[weekday_num]
    return str(weekday_num)