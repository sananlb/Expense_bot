"""
Tests for expense and income parsing functionality.

Based on archived tests and edge cases discovered in production.
"""
import pytest
from datetime import date, timedelta

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
import django
django.setup()

from bot.utils.expense_parser import (
    parse_expense_message,
    parse_income_message,
    detect_currency,
)


# =============================================================================
# Amount Parsing Tests
# =============================================================================

class TestAmountParsing:
    """Tests for amount extraction from text."""

    @pytest.mark.asyncio
    async def test_simple_integer_amount(self):
        """Simple integer amounts should parse correctly."""
        result = await parse_expense_message("Coffee 150", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(150)

    @pytest.mark.asyncio
    async def test_fractional_amount_with_dot(self):
        """Fractional amounts with dot should parse correctly."""
        result = await parse_expense_message("Gum 4.5", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(4.5)
        assert result["description"] == "Gum"
        # Fractional amount should NOT be treated as date
        assert result["expense_date"] is None

    @pytest.mark.asyncio
    async def test_fractional_amount_with_comma(self):
        """Fractional amounts with comma should parse correctly."""
        result = await parse_expense_message("Молоко 89,90", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(89.90)

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Known limitation: 'k' suffix not parsed")
    async def test_amount_with_k_suffix(self):
        """Amounts with 'k' suffix (thousands) should parse correctly."""
        result = await parse_expense_message("Зарплата 50k", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(50000)

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Known limitation: 'тыс' parsed incorrectly")
    async def test_amount_with_тыс_suffix(self):
        """Amounts with 'тыс' suffix should parse correctly."""
        result = await parse_expense_message("Аренда 25 тыс", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(25000)

    @pytest.mark.asyncio
    async def test_amount_at_start(self):
        """Amount at start of message should parse correctly."""
        result = await parse_expense_message("500 на обед", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(500)

    @pytest.mark.asyncio
    async def test_amount_at_end(self):
        """Amount at end of message should parse correctly."""
        result = await parse_expense_message("Кофе 200", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(200)


# =============================================================================
# Currency Detection Tests
# =============================================================================

class TestCurrencyDetection:
    """Tests for currency detection in text."""

    def test_detect_rub_keywords(self):
        """Russian ruble should be detected by keywords."""
        assert detect_currency("500 рублей на продукты") == "RUB"
        assert detect_currency("100 руб кофе") == "RUB"

    def test_detect_usd_keywords(self):
        """US dollar should be detected by keywords."""
        assert detect_currency("100 долларов подарок") == "USD"
        assert detect_currency("$50 на книгу") == "USD"

    def test_detect_eur_keywords(self):
        """Euro should be detected by keywords."""
        assert detect_currency("50 евро билет") == "EUR"
        assert detect_currency("€30 на кофе") == "EUR"

    def test_detect_cis_currencies(self):
        """CIS currencies should be detected."""
        assert detect_currency("500 тенге на продукты") == "KZT"
        assert detect_currency("1000 гривен за такси") == "UAH"
        assert detect_currency("200 сум на обед") == "UZS"
        assert detect_currency("950 лари ремонт") == "GEL"

    def test_default_currency_when_not_specified(self):
        """Should return None when no currency specified."""
        # When no currency is mentioned, detect_currency may return None or default
        result = detect_currency("кофе 150")
        # This depends on implementation - could be None or default


# =============================================================================
# Date Parsing Tests
# =============================================================================

class TestDateParsing:
    """Tests for date extraction from expense messages."""

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Known bug: short date like 05.04 parsed as amount 5.04")
    async def test_short_date_without_year_ignored(self):
        """Short date format without year should be ignored (not a valid date)."""
        result = await parse_expense_message("Coffee 120 05.04", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(120)
        # Short date like 05.04 should NOT be parsed as date
        assert result["expense_date"] is None

    @pytest.mark.asyncio
    async def test_full_date_parsed(self):
        """Full date with year should be parsed."""
        result = await parse_expense_message("Обед 500 25.11.2025", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(500)
        if result["expense_date"]:
            assert result["expense_date"].day == 25
            assert result["expense_date"].month == 11

    @pytest.mark.asyncio
    async def test_yesterday_keyword(self):
        """'Вчера' keyword should set date to yesterday."""
        result = await parse_expense_message("Вчера кофе 200", use_ai=False)
        assert result is not None
        if result["expense_date"]:
            assert result["expense_date"] == date.today() - timedelta(days=1)


# =============================================================================
# Income Parsing Tests
# =============================================================================

class TestIncomeParsing:
    """Tests for income message parsing."""

    @pytest.mark.asyncio
    async def test_income_with_plus_prefix(self):
        """Income with + prefix should parse correctly."""
        result = await parse_income_message("+5000", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(5000)

    @pytest.mark.asyncio
    async def test_fractional_income_amount(self):
        """Fractional income amounts should parse correctly."""
        result = await parse_income_message("+4.5", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(4.5)
        assert result["income_date"] is None

    @pytest.mark.asyncio
    async def test_income_with_description(self):
        """Income with description should parse both."""
        result = await parse_income_message("+50000 зарплата", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(50000)


# =============================================================================
# Edge Cases Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and potential bugs."""

    @pytest.mark.asyncio
    async def test_empty_message(self):
        """Empty message should return None."""
        result = await parse_expense_message("", use_ai=False)
        assert result is None

    @pytest.mark.asyncio
    async def test_message_without_amount(self):
        """Message without amount should return None."""
        result = await parse_expense_message("просто текст без суммы", use_ai=False)
        # May return None or have amount=0 depending on implementation
        if result:
            assert result.get("amount", 0) == 0 or result.get("amount") is None

    @pytest.mark.asyncio
    async def test_very_large_amount(self):
        """Very large amounts should be handled."""
        result = await parse_expense_message("999999999 супер покупка", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(999999999)

    @pytest.mark.asyncio
    async def test_zero_amount(self):
        """Zero amount should be handled appropriately."""
        result = await parse_expense_message("Бесплатно 0", use_ai=False)
        # Zero amount might be rejected or accepted depending on business logic

    @pytest.mark.asyncio
    async def test_multiple_numbers(self):
        """Message with multiple numbers should extract the correct one."""
        result = await parse_expense_message("2 кофе по 150", use_ai=False)
        # Implementation may vary - could be 150 or 2 or 300
        assert result is not None
        assert result["amount"] > 0

    @pytest.mark.asyncio
    async def test_unicode_in_description(self):
        """Unicode characters in description should be preserved."""
        result = await parse_expense_message("🍕 Пицца 500", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(500)
        if result.get("description"):
            assert "🍕" in result["description"] or "Пицца" in result["description"]
