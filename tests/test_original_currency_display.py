"""
Тесты отображения суммы в валюте ввода для ответов бота по прошлым операциям.
"""
from decimal import Decimal
from types import SimpleNamespace

from bot.utils.currency_display import (
    format_original_amount_suffix,
    operation_currency_fields,
)
from bot.utils.expense_formatter import format_expenses_from_dict_list
from bot.utils.income_formatter import format_incomes_from_dict_list
from bot.services.response_formatter import _format_operations_list


def _converted_expense():
    return SimpleNamespace(
        currency='RUB',
        original_amount=Decimal('10.00'),
        original_currency='USD',
    )


def _plain_expense():
    return SimpleNamespace(
        currency='RUB',
        original_amount=None,
        original_currency=None,
    )


def test_operation_currency_fields_includes_original_for_converted():
    fields = operation_currency_fields(_converted_expense())

    assert fields == {
        'currency': 'RUB',
        'original_amount': 10.0,
        'original_currency': 'USD',
    }


def test_operation_currency_fields_without_conversion():
    assert operation_currency_fields(_plain_expense()) == {'currency': 'RUB'}


def test_operation_currency_fields_ignores_same_currency():
    same_currency = SimpleNamespace(
        currency='RUB',
        original_amount=Decimal('100.00'),
        original_currency='RUB',
    )

    assert operation_currency_fields(same_currency) == {'currency': 'RUB'}


def test_format_original_amount_suffix():
    suffix = format_original_amount_suffix({'original_amount': 10.0, 'original_currency': 'USD'})

    assert suffix == ' <i>($10)</i>'


def test_format_original_amount_suffix_empty_without_original():
    assert format_original_amount_suffix({'amount': 900.0, 'currency': 'RUB'}) == ''


def test_expenses_list_shows_input_currency():
    text = format_expenses_from_dict_list(
        [
            {
                'date': '2026-08-10',
                'time': '12:30',
                'description': 'Кофе',
                'amount': 900.0,
                'currency': 'RUB',
                'original_amount': 10.0,
                'original_currency': 'USD',
            },
            {
                'date': '2026-08-10',
                'time': '13:00',
                'description': 'Обед',
                'amount': 500.0,
                'currency': 'RUB',
            },
        ],
        title='Траты',
    )

    assert 'Кофе 900 ₽ <i>($10)</i>' in text
    assert 'Обед 500 ₽' in text
    assert 'Обед 500 ₽ <i>' not in text


def test_incomes_list_shows_input_currency():
    text = format_incomes_from_dict_list(
        [
            {
                'date': '2026-08-10',
                'time': '09:00',
                'description': 'Фриланс',
                'amount': 9000.0,
                'currency': 'RUB',
                'original_amount': 100.0,
                'original_currency': 'USD',
            }
        ],
        title='Доходы',
    )

    assert '<i>($100)</i>' in text


def test_operations_list_shows_input_currency():
    text = _format_operations_list(
        {
            'operations': [
                {
                    'type': 'expense',
                    'date': '2026-08-10',
                    'time': '12:30',
                    'description': 'Кофе',
                    'amount': -900.0,
                    'currency': 'RUB',
                    'original_amount': 10.0,
                    'original_currency': 'USD',
                },
                {
                    'type': 'income',
                    'date': '2026-08-10',
                    'time': '09:00',
                    'description': 'Фриланс',
                    'amount': 9000.0,
                    'currency': 'RUB',
                    'original_amount': 100.0,
                    'original_currency': 'USD',
                },
            ],
            'currency': 'RUB',
        },
        title='Операции',
        subtitle='',
    )

    assert 'Кофе 900 ₽ <i>($10)</i>' in text
    assert '+9 000 ₽</b> <i>($100)</i>' in text
