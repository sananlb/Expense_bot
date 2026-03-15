import logging
from decimal import Decimal
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from bot.routers.chat import parse_dates_from_text
from bot.services.analytics_query import AnalyticsQueryExecutor, AnalyticsQuerySpec
from bot.services.expense_functions import ExpenseFunctions
from bot.services.pdf_report import PDFReportService as PlaywrightPDFReportService
from bot.services.response_formatter import format_function_result
from bot.utils.expense_formatter import format_expenses_from_dict_list
from bot.utils.income_formatter import format_incomes_from_dict_list
from expenses.models import ExpenseCategory, Profile


@pytest.mark.asyncio
async def test_parse_dates_from_text_invalid_range_returns_none(caplog):
    with caplog.at_level(logging.DEBUG, logger="bot.routers.chat"), patch(
        "bot.routers.chat.parser.parse", side_effect=ValueError("bad date")
    ):
        result = await parse_dates_from_text("покажи расходы с 32.13 по 40.13")

    assert result is None
    assert "Failed to parse date range from message" in caplog.text


def test_format_results_uses_raw_category_name_when_category_lookup_fails():
    executor = AnalyticsQueryExecutor(user_id=123)
    executor.profile = SimpleNamespace(language_code="ru")
    spec = AnalyticsQuerySpec(entity="expenses", group_by="category", aggregate=["sum", "count"], limit=10)

    grouped_rows = [
        {
            "category__id": 999,
            "category__name": "Старая категория",
            "total": Decimal("123.45"),
            "count": 2,
        }
    ]

    with patch.object(ExpenseCategory.objects, "get", side_effect=ExpenseCategory.DoesNotExist):
        result = executor._format_results(grouped_rows, spec)

    assert result == [
        {
            "category": "Старая категория",
            "category_id": 999,
            "total": 123.45,
            "count": 2,
        }
    ]


@pytest.mark.asyncio
async def test_get_max_expense_day_keeps_default_language_when_profile_lookup_fails():
    with patch.object(Profile.objects, "get_or_create", side_effect=RuntimeError("boom")), patch.object(
        Profile.objects, "get", side_effect=Profile.DoesNotExist
    ), patch("bot.utils.get_text", side_effect=lambda key, lang="ru", **kwargs: f"{lang}:{key}"):
        result = await ExpenseFunctions.get_max_expense_day(user_id=123)

    assert result == {
        "success": False,
        "message": "ru:error: boom",
    }


def test_format_expenses_from_dict_list_falls_back_to_today_for_invalid_iso_date():
    result = format_expenses_from_dict_list(
        expenses_data=[
            {
                "date": "not-a-date",
                "amount": Decimal("150"),
                "category": "Еда",
                "description": "Обед",
                "currency": "RUB",
            }
        ],
        lang="ru",
    )

    assert "Обед" in result
    assert "150" in result


def test_format_incomes_from_dict_list_uses_raw_date_when_parsing_fails():
    result = format_incomes_from_dict_list(
        incomes_data=[
            {
                "date": "2026-99-99",
                "amount": Decimal("5000"),
                "category": "Зарплата",
                "description": "Аванс",
                "currency": "RUB",
            }
        ],
        lang="ru",
    )

    assert "2026-99-99" in result
    assert "Аванс" in result


@pytest.mark.asyncio
async def test_pdf_report_logo_fallback_returns_empty_string_for_missing_file():
    service = PlaywrightPDFReportService.__new__(PlaywrightPDFReportService)
    service.LOGO_PATH = Path("missing-logo.png")

    result = await service._get_logo_base64()

    assert result == ""


@pytest.mark.asyncio
async def test_weasyprint_pdf_report_logo_fallback_returns_empty_string_for_missing_file():
    try:
        from bot.services.pdf_report_weasyprint import PDFReportService as WeasyPrintPDFReportService
    except OSError as import_error:
        pytest.skip(f"WeasyPrint native dependencies are unavailable in test environment: {import_error}")

    service = WeasyPrintPDFReportService.__new__(WeasyPrintPDFReportService)
    service.LOGO_PATH = Path("missing-logo.png")

    result = await service._get_logo_base64()

    assert result == ""


def test_format_function_result_keeps_default_period_text_for_invalid_category_dates():
    result = format_function_result(
        "get_category_total",
        {
            "success": True,
            "category": "Еда",
            "total": Decimal("1200"),
            "count": 3,
            "period": "month",
            "start_date": "bad-date",
            "previous_comparison": {
                "previous_total": Decimal("1000"),
                "percent_change": 20,
                "trend": "увеличение",
                "previous_period": {"start": "still-bad"},
            },
        },
    )

    assert "в этом месяце" in result
    assert "предыдущем периоде" in result


def test_format_function_result_keeps_default_period_text_for_invalid_income_dates():
    result = format_function_result(
        "get_income_category_total",
        {
            "success": True,
            "category": "Зарплата",
            "total": Decimal("5000"),
            "count": 2,
            "period": "month",
            "start_date": "not-an-iso-date",
            "previous_comparison": {
                "previous_total": Decimal("4500"),
                "percent_change": 11.1,
                "trend": "увеличение",
                "previous_period": {"start": "bad-prev-date"},
            },
        },
    )

    assert "в этом месяце" in result
    assert "предыдущем периоде" in result


def test_format_function_result_uses_raw_operation_date_when_date_is_invalid():
    result = format_function_result(
        "get_all_operations",
        {
            "success": True,
            "operations": [
                {
                    "date": "broken-date",
                    "time": "09:00",
                    "description": "Тестовая операция",
                    "amount": Decimal("99"),
                    "type": "expense",
                    "currency": "RUB",
                }
            ],
            "total_expense": Decimal("99"),
            "total_income": Decimal("0"),
            "count": 1,
            "user_id": None,
        },
    )

    assert "broken-date" in result
    assert "Тестовая операция" in result
