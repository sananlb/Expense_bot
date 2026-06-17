"""Утилиты отображения целей по доходам."""
from bot.services.conversion_helper import get_user_local_date

from . import get_text
from .budget_display import (
    days_left_in_month,
    format_days_left,
    render_category_bar,
)
from .formatters import format_currency


def format_category_goal_bar_line(percent: int) -> str:
    """Строка шкалы категорийной цели."""
    suffix = " 🎉" if percent >= 100 else ""
    return f"{render_category_bar(percent)} {percent}%{suffix}"


def format_total_goal_bar_line(percent: int) -> str:
    """Строка шкалы общей цели в формате категорийной шкалы: '▰▰▰▱▱ 80%'
    (+ 🎉 при достижении). Категорийные шкалы в обзоре месяца больше не рисуются —
    шкала остаётся только у общей цели, но в «тонком» категорийном формате."""
    suffix = " 🎉" if percent >= 100 else ""
    return f"{render_category_bar(percent)} {percent}%{suffix}"


def format_goal_screen_body(status, lang: str = 'ru') -> str:
    """Формирует тело экрана категорийной цели."""
    currency = status.goal.currency
    days = format_days_left(
        days_left_in_month(get_user_local_date(status.goal.profile)),
        lang,
    )
    return get_text('goal_screen_body', lang).format(
        amount=format_currency(status.goal.amount, currency),
        received=format_currency(status.received, currency),
        percent=status.percent,
        remaining=format_currency(status.remaining, currency),
        days_left=days,
    )
