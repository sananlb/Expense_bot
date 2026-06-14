"""Формирование и отправка уведомлений о достижении целей по доходам."""
import logging
from html import escape

from bot.services.income_goal import get_income_goal_statuses
from bot.utils import get_text
from bot.utils.category_helpers import get_category_display_name
from bot.utils.formatters import format_currency
from bot.utils.logging_safe import log_safe_id

logger = logging.getLogger(__name__)


async def get_income_goal_alert_messages(
    profile_id: int,
    income,
    category=None,
    lang: str = 'ru',
) -> list[str]:
    """Строит уведомления для целей, достигнутых конкретным доходом."""
    statuses = await get_income_goal_statuses(profile_id, income)
    if not statuses:
        return []

    messages: list[str] = []
    category_id = getattr(income, 'category_id', None)
    category_status = statuses.get(category_id) if category_id is not None else None
    if category_status is not None and 100 in category_status.crossed_thresholds:
        goal = category_status.goal
        category_display = escape(
            get_category_display_name(category or goal.category, lang),
            quote=False,
        )
        messages.append(
            get_text('goal_alert_category_achieved', lang).format(
                category=category_display,
                amount=format_currency(goal.amount, goal.currency),
                received=format_currency(category_status.received, goal.currency),
                percent=category_status.percent,
            )
        )

    total_status = statuses.get(None)
    if total_status is not None and 100 in total_status.crossed_thresholds:
        goal = total_status.goal
        messages.append(
            get_text('goal_alert_total_achieved', lang).format(
                amount=format_currency(goal.amount, goal.currency),
                received=format_currency(total_status.received, goal.currency),
                percent=total_status.percent,
            )
        )
    return messages


async def send_income_goal_alerts(
    bot,
    chat_id: int,
    income,
    category=None,
    lang: str = 'ru',
) -> int:
    """Отправляет уведомления о целях, не ломая создание дохода."""
    try:
        messages = await get_income_goal_alert_messages(
            income.profile.telegram_id,
            income,
            category=category,
            lang=lang,
        )
    except Exception:
        logger.exception(
            "Failed to calculate income goal alerts for %s",
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
                "Failed to send income goal alert to %s",
                log_safe_id(chat_id, "user"),
            )
    return sent
