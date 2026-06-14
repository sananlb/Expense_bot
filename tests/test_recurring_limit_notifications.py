from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from expense_bot.celery_tasks import _send_recurring_operation_notification


@pytest.mark.asyncio
async def test_recurring_expense_sends_confirmation_then_limit_alert():
    bot = AsyncMock()
    category = SimpleNamespace(id=7)
    operation = SimpleNamespace(
        id=42,
        category=category,
        profile=SimpleNamespace(language_code="en"),
    )
    payment_info = {
        "user_id": 123456789,
        "operation": operation,
        "operation_type": "expense",
        "payment": SimpleNamespace(id=3),
    }

    with patch(
        "bot.utils.expense_messages.format_expense_added_message",
        AsyncMock(return_value="recurring expense"),
    ) as format_message, patch(
        "bot.utils.budget_notifications.send_expense_limit_alerts",
        AsyncMock(),
    ) as send_alerts, patch(
        "bot.utils.get_text",
        side_effect=lambda key, lang="ru", **kwargs: key,
    ):
        await _send_recurring_operation_notification(bot, payment_info)

    format_message.assert_awaited_once_with(
        expense=operation,
        category=category,
        cashback_text="",
        is_recurring=True,
        lang="en",
    )
    bot.send_message.assert_awaited_once()
    send_alerts.assert_awaited_once_with(
        bot,
        123456789,
        operation,
        category=category,
        lang="en",
    )


@pytest.mark.asyncio
async def test_recurring_income_sends_confirmation_then_goal_alert():
    bot = AsyncMock()
    category = SimpleNamespace(id=8)
    operation = SimpleNamespace(
        id=43,
        category=category,
        profile=SimpleNamespace(language_code="ru"),
    )
    payment_info = {
        "user_id": 123456789,
        "operation": operation,
        "operation_type": "income",
        "payment": SimpleNamespace(id=4),
    }

    with patch(
        "bot.utils.expense_messages.format_income_added_message",
        AsyncMock(return_value="recurring income"),
    ) as format_message, patch(
        "bot.utils.income_goal_notifications.send_income_goal_alerts",
        AsyncMock(),
    ) as send_alerts, patch(
        "bot.utils.get_text",
        side_effect=lambda key, lang="ru", **kwargs: key,
    ):
        await _send_recurring_operation_notification(bot, payment_info)

    format_message.assert_awaited_once_with(
        income=operation,
        category=category,
        is_recurring=True,
        lang="ru",
    )
    bot.send_message.assert_awaited_once()
    send_alerts.assert_awaited_once_with(
        bot,
        123456789,
        operation,
        category=category,
        lang="ru",
    )
