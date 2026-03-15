import logging
from datetime import date, timedelta
from decimal import Decimal

import pytest
from asgiref.sync import sync_to_async

from bot.services.expense_functions import ExpenseFunctions
from bot.utils.logging_safe import log_safe_id, sanitize_callback_action, summarize_text


def test_log_safe_id_masks_raw_identifier():
    masked = log_safe_id(123456789, "user")

    assert masked.startswith("user:")
    assert "123456789" not in masked
    assert len(masked.split(":")[1]) == 8


def test_summarize_text_returns_only_metadata():
    summary = summarize_text("/start 500")

    assert summary == "len=10, flags=digits,command"


def test_sanitize_callback_action_strips_params_and_tokens():
    assert sanitize_callback_action("edit_expense_456") == ("edit_expense", True)
    assert sanitize_callback_action("confirm_join:secret-token") == ("confirm_join", True)
    assert sanitize_callback_action("expenses_today") == ("expenses_today", False)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_income_comparison_logs_keep_financial_totals_out_of_info(caplog, test_profile, test_income_category):
    from expenses.models import Income

    today = date.today()
    month_start = today.replace(day=1)
    previous_month_last_day = month_start - timedelta(days=1)
    previous_month_date = previous_month_last_day.replace(day=min(previous_month_last_day.day, 10))

    await sync_to_async(Income.objects.create)(
        profile=test_profile,
        category=test_income_category,
        amount=Decimal("50000.00"),
        currency="RUB",
        description="salary current month",
        income_date=today,
    )
    await sync_to_async(Income.objects.create)(
        profile=test_profile,
        category=test_income_category,
        amount=Decimal("40000.00"),
        currency="RUB",
        description="salary previous month",
        income_date=previous_month_date,
    )

    with caplog.at_level(logging.INFO, logger="bot.services.expense_functions"):
        search_result = await ExpenseFunctions.search_incomes(
            test_profile.telegram_id,
            query="salary",
            period="month",
        )

    assert search_result["success"] is True
    assert "previous_comparison" in search_result
    search_messages = [record.getMessage() for record in caplog.records if record.name == "bot.services.expense_functions"]
    assert not any("search_incomes: previous period - total=" in message for message in search_messages)
    assert not any("search_incomes: comparison - difference=" in message for message in search_messages)

    caplog.clear()

    with caplog.at_level(logging.INFO, logger="bot.services.expense_functions"):
        category_result = await ExpenseFunctions.get_income_category_total(
            test_profile.telegram_id,
            category="Зарплата",
            period="month",
        )

    assert category_result["success"] is True
    assert "previous_comparison" in category_result
    category_messages = [record.getMessage() for record in caplog.records if record.name == "bot.services.expense_functions"]
    assert not any("get_income_category_total: previous period - total=" in message for message in category_messages)
    assert not any("get_income_category_total: comparison - difference=" in message for message in category_messages)
