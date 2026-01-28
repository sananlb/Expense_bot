import os
import sys

import pytest

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.utils.validators import parse_description_amount


@pytest.mark.parametrize(
    "text, allow_only_amount, expected",
    [
        ("Аренда 48 000", False, {"description": "Аренда", "amount": 48000.0, "is_income": False}),
        ("Недвижимость 1 000 000", False, {"description": "Недвижимость", "amount": 1000000.0, "is_income": False}),
        ("Интернет 1 500.50", False, {"description": "Интернет", "amount": 1500.5, "is_income": False}),
        ("Кофе 150,5", False, {"description": "Кофе", "amount": 150.5, "is_income": False}),
        ("48 000", True, {"description": None, "amount": 48000.0, "is_income": False}),
        ("Зарплата плюс 150 000", False, {"description": "Зарплата", "amount": 150000.0, "is_income": True}),
        ("Покупка 50 000 руб", False, {"description": "Покупка", "amount": 50000.0, "is_income": False}),
        ("Такси 500", False, {"description": "Такси", "amount": 500.0, "is_income": False}),
        ("Продукты 48000", False, {"description": "Продукты", "amount": 48000.0, "is_income": False}),
        ("Plus Market 1000", False, {"description": "Plus Market", "amount": 1000.0, "is_income": False}),
        ("C++ книга 500", False, {"description": "C++ книга", "amount": 500.0, "is_income": False}),
        ("Прораб 5000", False, {"description": "Прораб", "amount": 5000.0, "is_income": False}),
        ("+ 5000", True, {"description": None, "amount": 5000.0, "is_income": True}),
        ("Зарплата + 5000", False, {"description": "Зарплата", "amount": 5000.0, "is_income": True}),
        ("Зарплата +5000", False, {"description": "Зарплата", "amount": 5000.0, "is_income": True}),
        ("Обед 200 тенге", False, {"description": "Обед", "amount": 200.0, "is_income": False}),
        ("Обед 200 теньге", False, {"description": "Обед", "amount": 200.0, "is_income": False}),
        ("Такси 500р", False, {"description": "Такси", "amount": 500.0, "is_income": False}),
        ("Подарок 750 рублей", False, {"description": "Подарок", "amount": 750.0, "is_income": False}),
        ("Кофе 300 лир", False, {"description": "Кофе", "amount": 300.0, "is_income": False}),
    ],
)
def test_parse_description_amount_success(text, allow_only_amount, expected):
    result = parse_description_amount(text, allow_only_amount=allow_only_amount)

    assert result["description"] == expected["description"]
    assert result["is_income"] == expected["is_income"]
    assert result["amount"] == pytest.approx(expected["amount"])


@pytest.mark.parametrize(
    "text, allow_only_amount, match",
    [
        ("", False, "Пустой ввод"),
        ("Только текст без числа", False, "Неверный формат"),
        ("Тест 0", False, "Сумма должна быть больше 0"),
        ("Описание непарсящеесячисло", True, "Неверный формат. Отправьте сумму или название и сумму."),
    ],
)
def test_parse_description_amount_errors(text, allow_only_amount, match):
    with pytest.raises(ValueError, match=match):
        parse_description_amount(text, allow_only_amount=allow_only_amount)
