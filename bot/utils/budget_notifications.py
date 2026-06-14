"""Формирование и отправка уведомлений о пересечении лимитов трат."""
import logging
from html import escape

from bot.services.budget import get_expense_limit_statuses
from bot.services.conversion_helper import get_user_local_date
from bot.utils import get_text
from bot.utils.budget_display import days_left_in_month, format_days_left
from bot.utils.category_helpers import get_category_display_name
from bot.utils.formatters import format_currency
from bot.utils.logging_safe import log_safe_id

logger = logging.getLogger(__name__)


async def get_expense_limit_alert_messages(
    profile_id: int,
    expense,
    category=None,
    lang: str = 'ru',
) -> list[str]:
    """Строит сообщения для порогов, пересечённых конкретной новой тратой."""
    statuses = await get_expense_limit_statuses(profile_id, expense)
    if not statuses:
        return []

    today = get_user_local_date(expense.profile)
    days_left = format_days_left(days_left_in_month(today), lang)
    messages: list[str] = []

    category_id = getattr(expense, 'category_id', None)
    category_status = statuses.get(category_id) if category_id is not None else None
    if category_status is not None and 100 in category_status.crossed_thresholds:
        budget = category_status.budget
        category_display = escape(
            get_category_display_name(category or budget.category, lang),
            quote=False,
        )
        messages.append(
            get_text('limit_alert_category_exceeded', lang).format(
                category=category_display,
                amount=format_currency(budget.amount, budget.currency),
                spent=format_currency(category_status.spent, budget.currency),
                percent=category_status.percent,
                days_left=days_left,
            )
        )

    total_status = statuses.get(None)
    if total_status is not None and total_status.crossed_thresholds:
        budget = total_status.budget
        highest_threshold = max(total_status.crossed_thresholds)
        if highest_threshold >= 100:
            key = 'limit_alert_total_exceeded'
            messages.append(
                get_text(key, lang).format(
                    amount=format_currency(budget.amount, budget.currency),
                    spent=format_currency(total_status.spent, budget.currency),
                    percent=total_status.percent,
                    days_left=days_left,
                )
            )
        elif highest_threshold >= 80:
            key = 'limit_alert_total_80'
            messages.append(
                get_text(key, lang).format(
                    amount=format_currency(budget.amount, budget.currency),
                    spent=format_currency(total_status.spent, budget.currency),
                    remaining=format_currency(total_status.remaining, budget.currency),
                    days_left=days_left,
                )
            )

    return messages


async def send_expense_limit_alerts(
    bot,
    chat_id: int,
    expense,
    category=None,
    lang: str = 'ru',
) -> int:
    """Отправляет отдельные threshold-уведомления, не ломая создание траты."""
    try:
        profile_id = expense.profile.telegram_id
        messages = await get_expense_limit_alert_messages(
            profile_id,
            expense,
            category=category,
            lang=lang,
        )
    except Exception:
        logger.exception(
            "Failed to calculate expense limit alerts for %s",
            log_safe_id(chat_id, "user"),
        )
        return 0

    sent = 0
    for text in messages:
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML')
            sent += 1
        except Exception:
            logger.exception(
                "Failed to send expense limit alert to %s",
                log_safe_id(chat_id, "user"),
            )
    return sent
