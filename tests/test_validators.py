import pytest

from bot.utils.validators import (
    validate_amount,
    validate_date_format,
    validate_email,
    validate_phone_number,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("0.01", 0.01),
        ("1 500,50", 1500.5),
        ("999999999", 999999999.0),
        (" 42 ", 42.0),
    ],
)
async def test_validate_amount_accepts_supported_formats(raw_value, expected):
    assert await validate_amount(raw_value) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw_value", "message"),
    [
        ("0", "Сумма должна быть больше нуля"),
        ("-10", "Сумма должна быть больше нуля"),
        ("1000000000", "Сумма слишком большая"),
        ("abc", "could not convert string to float"),
    ],
)
async def test_validate_amount_rejects_invalid_values(raw_value, message):
    with pytest.raises(ValueError, match=message):
        await validate_amount(raw_value)


@pytest.mark.asyncio
async def test_validate_amount_returns_generic_error_for_unexpected_input_type():
    with pytest.raises(ValueError, match="Неверный формат суммы"):
        await validate_amount(None)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("16.03.2026", True),
        ("1.03.2026", False),
        ("16/03/2026", False),
        ("2026-03-16", False),
    ],
)
def test_validate_date_format_matches_dd_mm_yyyy_contract(raw_value, expected):
    assert validate_date_format(raw_value) is expected


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("8 (999) 123-45-67", "+79991234567"),
        ("+966 50 123 4567", "+966501234567"),
        ("12345", None),
        ("1234567890123456", None),
    ],
)
def test_validate_phone_number_normalizes_supported_values(raw_value, expected):
    assert validate_phone_number(raw_value) == expected


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("user@example.com", True),
        ("user.name+tag@domain.co", True),
        ("broken@", False),
        ("no-at-sign.example.com", False),
    ],
)
def test_validate_email_accepts_basic_valid_addresses(raw_value, expected):
    assert validate_email(raw_value) is expected
