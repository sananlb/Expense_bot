import pytest

from bot.utils.expense_parser import parse_expense_message, parse_income_message


@pytest.mark.asyncio
async def test_fractional_expense_amount_not_treated_as_date():
    result = await parse_expense_message("Gum 4.5", use_ai=False)
    assert result is not None
    assert result["amount"] == pytest.approx(4.5)
    assert result["description"] == "Gum"
    assert result["expense_date"] is None


@pytest.mark.asyncio
async def test_fractional_income_amount_not_treated_as_date():
    result = await parse_income_message("+4.5", use_ai=False)
    assert result is not None
    assert result["amount"] == pytest.approx(4.5)
    assert result["income_date"] is None


@pytest.mark.asyncio
async def test_short_date_without_year_ignored():
    result = await parse_expense_message("Coffee 120 05.04", use_ai=False)
    assert result is not None
    assert result["amount"] == pytest.approx(120)
    assert result["expense_date"] is None
