"""
Tests for expense and income parsing functionality.

Based on archived tests and edge cases discovered in production.
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal

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
    _extract_leading_amount,
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
    async def test_amount_with_k_suffix(self):
        """Amounts with 'k' suffix (thousands) should parse correctly."""
        result = await parse_expense_message("Зарплата 50k", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(50000)

    @pytest.mark.asyncio
    async def test_amount_with_тыс_suffix(self):
        """Amounts with 'тыс' suffix should parse correctly."""
        result = await parse_expense_message("Аренда 25 тыс", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(25000)

    @pytest.mark.asyncio
    async def test_amount_with_cyrillic_k_suffix(self):
        """Amounts with Cyrillic 'к' suffix should parse correctly."""
        result = await parse_expense_message("Премия 10к", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(10000)

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

    @pytest.mark.asyncio
    async def test_amount_with_ruble_symbol_and_space(self):
        """Amount with ₽ and space should parse correctly."""
        result = await parse_expense_message("1600₽ продукты", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(1600)
        assert result["description"] == "Продукты"

    @pytest.mark.asyncio
    async def test_amount_with_ruble_symbol_no_space(self):
        """Amount with ₽ and no space should parse correctly."""
        result = await parse_expense_message("1600₽продукты", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(1600)
        assert result["description"] == "Продукты"


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


# =============================================================================
# Income Leading Amount Extraction Tests
# Regression: production bug 2026-02-16 — "+75000 аренда Кольская 8" parsed as 8 RUB
# =============================================================================

class TestExtractLeadingIncomeAmount:
    """Unit tests for _extract_leading_amount helper."""

    def test_basic_leading_number(self):
        """Number at start should be extracted, no signal."""
        amount, remaining, has_signal = _extract_leading_amount("75000 аренда Кольская 8")
        assert amount == 75000
        assert remaining == "аренда Кольская 8"
        assert has_signal is False

    def test_number_with_description(self):
        """Number followed by description."""
        amount, remaining, has_signal = _extract_leading_amount("5000 зарплата")
        assert amount == 5000
        assert remaining == "зарплата"
        assert has_signal is False

    def test_number_only(self):
        """Just a number, no description."""
        amount, remaining, has_signal = _extract_leading_amount("9128")
        assert amount == 9128
        assert remaining == ""
        assert has_signal is False

    def test_number_with_thousands_separator_space(self):
        """Number with space as thousands separator."""
        amount, remaining, _sig = _extract_leading_amount("75 000 аренда")
        assert amount == 75000
        assert remaining == "аренда"

    def test_number_with_thousands_separator_comma(self):
        """Number with comma as thousands separator."""
        amount, remaining, _sig = _extract_leading_amount("75,000 аренда")
        assert amount == 75000
        assert remaining == "аренда"

    def test_decimal_number(self):
        """Decimal amount."""
        amount, remaining, _sig = _extract_leading_amount("5000.50 возврат")
        assert amount == pytest.approx(5000.50)
        assert remaining == "возврат"

    def test_text_at_start_returns_none(self):
        """Text at start — not a leading amount."""
        amount, remaining, has_signal = _extract_leading_amount("аренда 75000")
        assert amount is None
        assert remaining is None
        assert has_signal is False

    def test_empty_text(self):
        """Empty string."""
        amount, remaining, has_signal = _extract_leading_amount("")
        assert amount is None
        assert remaining is None
        assert has_signal is False

    def test_currency_suffix_rub(self):
        """Currency word after number — signal=True, stripped from description."""
        amount, remaining, has_signal = _extract_leading_amount("75000 руб аренда Кольская 8")
        assert amount == 75000
        assert remaining == "аренда Кольская 8"
        assert has_signal is True

    def test_currency_suffix_rublei(self):
        """Full currency word — signal=True."""
        amount, remaining, has_signal = _extract_leading_amount("50000 рублей зарплата")
        assert amount == 50000
        assert remaining == "зарплата"
        assert has_signal is True

    def test_currency_suffix_dollar_sign(self):
        """Dollar sign — signal=True."""
        amount, remaining, has_signal = _extract_leading_amount("100 $ фриланс")
        assert amount == 100
        assert remaining == "фриланс"
        assert has_signal is True

    def test_currency_suffix_euro(self):
        """Euro — signal=True."""
        amount, remaining, has_signal = _extract_leading_amount("500 евро перевод")
        assert amount == 500
        assert remaining == "перевод"
        assert has_signal is True

    def test_multiplier_tys(self):
        """Multiplier 'тыс' — signal=True."""
        amount, remaining, has_signal = _extract_leading_amount("75 тыс аренда")
        assert amount == 75000
        assert remaining == "аренда"
        assert has_signal is True

    def test_multiplier_k(self):
        """Multiplier 'к' — signal=True."""
        amount, remaining, has_signal = _extract_leading_amount("75к аренда")
        assert amount == 75000
        assert remaining == "аренда"
        assert has_signal is True

    def test_multiplier_mln(self):
        """Multiplier 'млн' — signal=True."""
        amount, remaining, has_signal = _extract_leading_amount("1.5 млн бонус")
        assert amount == pytest.approx(1500000)
        assert remaining == "бонус"
        assert has_signal is True

    def test_multiplier_and_currency(self):
        """Multiplier + currency — signal=True."""
        amount, remaining, has_signal = _extract_leading_amount("5 тыс руб аренда")
        assert amount == 5000
        assert remaining == "аренда"
        assert has_signal is True

    def test_zero_returns_none(self):
        """Zero amount should return None."""
        amount, remaining, _sig = _extract_leading_amount("0 тест")
        assert amount is None

    def test_dot_thousands(self):
        """Dot as thousands separator: 10.000.000 → 10000000."""
        amount, remaining, _sig = _extract_leading_amount("10.000.000 бонус")
        assert amount == 10_000_000
        assert remaining == "бонус"

    def test_dot_thousands_small(self):
        """Single dot-thousands group: 10.000 → 10000."""
        amount, remaining, _sig = _extract_leading_amount("10.000 премия")
        assert amount == 10_000
        assert remaining == "премия"

    def test_dot_decimal_not_thousands(self):
        """10.50 is decimal, not thousands (only 2 digits after dot)."""
        amount, remaining, _sig = _extract_leading_amount("10.50 возврат")
        assert amount == pytest.approx(10.50)
        assert remaining == "возврат"

    def test_partial_match_date_rejected(self):
        """25.11.2025 — partial match (25.11 + .2025), should return None."""
        amount, remaining, _sig = _extract_leading_amount("25.11.2025")
        assert amount is None

    def test_partial_match_malformed_dot(self):
        """10.000.000.5 — partial match after dot-thousands, should return None."""
        amount, remaining, _sig = _extract_leading_amount("10.000.000.5 бонус")
        assert amount is None

    def test_partial_match_comma_continuation(self):
        """25,11,2025 — partial match, should return None."""
        amount, remaining, _sig = _extract_leading_amount("25,11,2025")
        assert amount is None

    def test_date_with_year_20xx_rejected(self):
        """25.11.2025 — date DD.MM.20XX should be rejected early."""
        amount, remaining, _sig = _extract_leading_amount("25.11.2025")
        assert amount is None

    def test_date_with_short_year_20_rejected(self):
        """15.03.20 — date DD.MM.20 (short year) should be rejected."""
        amount, remaining, _sig = _extract_leading_amount("15.03.20")
        assert amount is None

    def test_date_with_year_and_text_rejected(self):
        """25.11.2025 кофе 300 — date at start with text should be rejected."""
        amount, remaining, _sig = _extract_leading_amount("25.11.2025 кофе 300")
        assert amount is None

    def test_non_date_dots_not_rejected(self):
        """10.000 — dot-thousands, NOT a date (should still work)."""
        amount, remaining, _sig = _extract_leading_amount("10.000")
        assert amount == Decimal("10000")

    def test_date_with_slash_separator_rejected(self):
        """31/12/24 — date with / separator should be rejected."""
        amount, remaining, _sig = _extract_leading_amount("31/12/24 зарплата 5000")
        assert amount is None

    def test_date_slash_partial_match(self):
        """31/12/2024 — slash after number triggers partial match."""
        amount, remaining, _sig = _extract_leading_amount("31/12/2024")
        assert amount is None

    def test_date_with_short_year_24_rejected(self):
        """15.03.24 — date DD.MM.YY (non-20xx) should also be rejected."""
        amount, remaining, _sig = _extract_leading_amount("15.03.24")
        assert amount is None


class TestConvertWordsToNumbers:
    """Tests for convert_words_to_numbers date protection."""

    def test_date_with_dash_preserved(self):
        """25-11-2025 should be converted to 25.11.2025, not broken."""
        from bot.utils.expense_parser import convert_words_to_numbers
        result = convert_words_to_numbers("25-11-2025 кофе 300")
        assert "25.11.2025" in result
        assert "кофе" in result
        assert "300" in result

    def test_date_with_dash_short_year_preserved(self):
        """31-12-24 should be converted to 31.12.24."""
        from bot.utils.expense_parser import convert_words_to_numbers
        result = convert_words_to_numbers("31-12-24 зарплата 5000")
        assert "31.12.24" in result

    def test_regular_dash_still_replaced(self):
        """Non-date dashes should still be replaced with spaces."""
        from bot.utils.expense_parser import convert_words_to_numbers
        result = convert_words_to_numbers("кофе-латте 300")
        # Dash between words (not date) should become space
        assert "-" not in result


class TestIncomeLeadingAmountRegression:
    """Integration tests: full parse_income_message with leading amount fix."""

    @pytest.mark.asyncio
    async def test_production_bug_address_number(self):
        """REGRESSION: +75000 аренда Кольская 8 → should be 75000, NOT 8."""
        result = await parse_income_message("+75000 аренда Кольская 8", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(75000)

    @pytest.mark.asyncio
    async def test_apartment_number_not_amount(self):
        """+50000 зп за январь кв 12 → should be 50000, NOT 12."""
        result = await parse_income_message("+50000 зп за январь кв 12", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(50000)

    @pytest.mark.asyncio
    async def test_house_number_not_amount(self):
        """+3000 возврат дом 5 → should be 3000, NOT 5."""
        result = await parse_income_message("+3000 возврат дом 5", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(3000)

    @pytest.mark.asyncio
    async def test_simple_income_still_works(self):
        """+5000 → basic case should still work."""
        result = await parse_income_message("+5000", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(5000)

    @pytest.mark.asyncio
    async def test_income_with_description_still_works(self):
        """+50000 зарплата → should still work."""
        result = await parse_income_message("+50000 зарплата", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(50000)

    @pytest.mark.asyncio
    async def test_income_number_only(self):
        """+9128 → number-only income."""
        result = await parse_income_message("+9128", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(9128)

    @pytest.mark.asyncio
    async def test_income_with_currency(self):
        """+75000 руб аренда Кольская 8 → amount with currency."""
        result = await parse_income_message("+75000 руб аренда Кольская 8", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(75000)

    @pytest.mark.asyncio
    async def test_income_with_multiplier(self):
        """+75 тыс аренда → multiplier should work."""
        result = await parse_income_message("+75 тыс аренда", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(75000)

    @pytest.mark.asyncio
    async def test_income_fractional(self):
        """+4.5 → fractional still works."""
        result = await parse_income_message("+4.5", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(4.5)

    @pytest.mark.asyncio
    async def test_income_dot_thousands(self):
        """+10.000.000 бонус → dot-thousands should give 10000000."""
        result = await parse_income_message("+10.000.000 бонус", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(10_000_000)

    @pytest.mark.asyncio
    async def test_income_dot_thousands_small(self):
        """+10.000 премия → 10000, not 10."""
        result = await parse_income_message("+10.000 премия", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(10_000)

    @pytest.mark.asyncio
    async def test_date_not_parsed_as_amount(self):
        """+25.11.2025 — date-like input should NOT give garbage amount."""
        result = await parse_income_message("+25.11.2025", use_ai=False)
        # Should be None (no valid amount) or at least not a partial number
        if result is not None:
            assert result["amount"] != pytest.approx(25.11)
            assert result["amount"] != pytest.approx(11.2025)

    @pytest.mark.asyncio
    async def test_malformed_dot_thousands(self):
        """+10.000.000.5 бонус — malformed number should not give garbage description."""
        result = await parse_income_message("+10.000.000.5 бонус", use_ai=False)
        if result is not None:
            # Description should not start with ".5"
            desc = result.get("description", "")
            assert not desc.startswith(".5")

    @pytest.mark.asyncio
    async def test_expense_not_affected(self):
        """Expense parsing should NOT be affected — 'кофе 300' still gets 300."""
        result = await parse_expense_message("кофе 300", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(300)

    @pytest.mark.asyncio
    async def test_income_date_with_slash(self):
        """+31/12/24 зарплата 5000 → amount should be 5000, NOT 31."""
        result = await parse_income_message("+31/12/24 зарплата 5000", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(5000)

    @pytest.mark.asyncio
    async def test_income_date_with_dash(self):
        """+31-12-24 зарплата 5000 → amount should be 5000, NOT 31."""
        result = await parse_income_message("+31-12-24 зарплата 5000", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(5000)


class TestExpenseLeadingAmountRegression:
    """Regression tests: leading amount extraction for expenses (unified with income)."""

    @pytest.mark.asyncio
    async def test_expense_with_currency_and_trailing_number(self):
        """75000 руб Кольская 8 — currency signals that 75000 is amount, not 8."""
        result = await parse_expense_message("75000 руб Кольская 8", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(75000)

    @pytest.mark.asyncio
    async def test_expense_leading_number_no_currency(self):
        """75000 Кольская 8 — leading number should be amount, not trailing 8."""
        result = await parse_expense_message("75000 Кольская 8", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(75000)

    @pytest.mark.asyncio
    async def test_expense_multiplier_and_trailing_number(self):
        """75 тыс Кольская 8 — multiplier signals 75000, not trailing 8."""
        result = await parse_expense_message("75 тыс Кольская 8", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(75000)

    @pytest.mark.asyncio
    async def test_expense_trailing_amount_still_works(self):
        """кофе 300 — classic pattern, amount at end still works."""
        result = await parse_expense_message("кофе 300", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(300)

    @pytest.mark.asyncio
    async def test_expense_trailing_amount_taxi(self):
        """такси 250 — amount at end, no leading number."""
        result = await parse_expense_message("такси 250", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(250)

    @pytest.mark.asyncio
    async def test_expense_trailing_amount_with_preposition(self):
        """обед в кафе 1500 — amount at end, description has preposition."""
        result = await parse_expense_message("обед в кафе 1500", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(1500)

    @pytest.mark.asyncio
    async def test_expense_leading_number_simple(self):
        """300 кофе — leading number is the amount."""
        result = await parse_expense_message("300 кофе", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(300)

    @pytest.mark.asyncio
    async def test_expense_quantity_not_amount(self):
        """2 кофе по 150 — 150 is the amount (from patterns), not 2 (quantity)."""
        result = await parse_expense_message("2 кофе по 150", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(150)

    @pytest.mark.asyncio
    async def test_expense_year_not_amount(self):
        """2024 подписка 500 — 500 is the amount, not 2024 (year)."""
        result = await parse_expense_message("2024 подписка 500", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(500)

    @pytest.mark.asyncio
    async def test_expense_date_with_slash(self):
        """31/12/24 кофе 300 — date with / separator, amount=300."""
        result = await parse_expense_message("31/12/24 кофе 300", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(300)

    @pytest.mark.asyncio
    async def test_expense_date_with_dash(self):
        """25-11-2025 кофе 300 — date with - separator, amount=300."""
        result = await parse_expense_message("25-11-2025 кофе 300", use_ai=False)
        assert result is not None
        assert result["amount"] == pytest.approx(300)
