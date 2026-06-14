"""
Утилиты отображения лимитов трат: шкалы прогресса, дни до конца месяца,
сборка тела экрана лимита. Переиспользуются в роутерах категорий, настроек,
отчётов и в уведомлениях о порогах.
"""
from datetime import date

from bot.services.conversion_helper import get_user_local_date

from . import get_text
from .formatters import format_currency

# Глифы шкал. Категорийная — тонкая (10 сегментов), общий лимит — плотная,
# визуально выделенная (12 сегментов).
CATEGORY_BAR_FILLED = '▰'
CATEGORY_BAR_EMPTY = '▱'
CATEGORY_BAR_SEGMENTS = 10

TOTAL_BAR_FILLED = '■'
TOTAL_BAR_EMPTY = '□'
TOTAL_BAR_SEGMENTS = 14


def days_left_in_month(today: date | None = None) -> int:
    """Количество оставшихся дней до конца текущего месяца включительно
    (сегодняшний день считается оставшимся)."""
    today = today or date.today()
    if today.month == 12:
        next_first = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_first = today.replace(month=today.month + 1, day=1)
    return (next_first - today).days


def format_days_left(n: int, lang: str = 'ru') -> str:
    """Склонение 'дней' для русского, простое число для английского."""
    if lang == 'ru':
        if 11 <= (n % 100) <= 14:
            key = 'limit_days_left_many'
        elif n % 10 == 1:
            key = 'limit_days_left_one'
        elif 2 <= (n % 10) <= 4:
            key = 'limit_days_left_few'
        else:
            key = 'limit_days_left_many'
    else:
        key = 'limit_days_left_one' if n == 1 else 'limit_days_left_many'
    return get_text(key, lang).format(n=n)


def _render_bar(percent: int, filled_glyph: str, empty_glyph: str, segments: int) -> str:
    """Рисует шкалу заполнения из segments глифов по проценту (floor)."""
    filled = min(segments, max(0, percent * segments // 100))
    return filled_glyph * filled + empty_glyph * (segments - filled)


def render_category_bar(percent: int) -> str:
    """Тонкая шкала категорийного лимита (10 сегментов)."""
    return _render_bar(percent, CATEGORY_BAR_FILLED, CATEGORY_BAR_EMPTY, CATEGORY_BAR_SEGMENTS)


def render_total_bar(percent: int) -> str:
    """Крупная шкала общего лимита квадратами (14 сегментов)."""
    return _render_bar(percent, TOTAL_BAR_FILLED, TOTAL_BAR_EMPTY, TOTAL_BAR_SEGMENTS)


def status_emoji(percent: int) -> str:
    """Статусный эмодзи по проценту: <80 🟢, 80–99 🟡, ≥100 🔴."""
    if percent >= 100:
        return '🔴'
    if percent >= 80:
        return '🟡'
    return '🟢'


def format_category_bar_line(percent: int) -> str:
    """Строка шкалы категории для обзора месяца: '▰▰▰▱▱ 72%' (+ 🔴 при >100%)."""
    bar = render_category_bar(percent)
    if percent >= 100:
        return f"{bar} {percent}% 🔴"
    return f"{bar} {percent}%"


def format_total_bar_line(percent: int) -> str:
    """Строка шкалы общего лимита для обзора месяца: '■■■■■□□ 80%' (без эмодзи-индикатора справа)."""
    bar = render_total_bar(percent)
    return f"{bar} {percent}%"


def format_limit_screen_body(status, lang: str = 'ru') -> str:
    """Тело экрана конкретного лимита (категорийного или общего): лимит,
    потрачено, остаток, дни до конца месяца. Принимает LimitStatus."""
    currency = status.budget.currency
    amount = format_currency(status.budget.amount, currency)
    spent = format_currency(status.spent, currency)
    remaining = format_currency(status.remaining, currency)
    days = format_days_left(
        days_left_in_month(get_user_local_date(status.budget.profile)),
        lang,
    )
    return get_text('limit_screen_body', lang).format(
        amount=amount,
        spent=spent,
        percent=status.percent,
        remaining=remaining,
        days_left=days,
    )
