import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.utils.multiple_expense_parser import split_multiple_expense_texts


@pytest.mark.asyncio
async def test_text_explicit_separator_creates_multiple_expenses():
    result = split_multiple_expense_texts(
        "мороженое 120, помидоры 232, хлеб 20",
        input_source="text",
    )

    assert result == [
        "мороженое 120",
        "помидоры 232",
        "хлеб 20",
    ]


@pytest.mark.asyncio
async def test_voice_without_separator_creates_multiple_expenses():
    result = split_multiple_expense_texts(
        "мороженое 120 помидоры 232 хлеб 20",
        input_source="voice",
    )

    assert result == [
        "мороженое 120",
        "помидоры 232",
        "хлеб 20",
    ]


@pytest.mark.asyncio
async def test_text_without_separator_does_not_create_batch():
    result = split_multiple_expense_texts(
        "мороженое 120 помидоры 232 хлеб 20",
        input_source="text",
    )

    assert result is None


@pytest.mark.asyncio
async def test_voice_single_address_like_expense_falls_back_to_single_parser():
    result = split_multiple_expense_texts(
        "Ленина 5 255 руб",
        input_source="voice",
    )

    assert result is None


@pytest.mark.asyncio
async def test_voice_address_like_expense_before_next_item_creates_two_items():
    result = split_multiple_expense_texts(
        "Ленина 5 255 руб хлеб 20",
        input_source="voice",
    )

    assert result == [
        "Ленина 5 255 руб",
        "хлеб 20",
    ]


def test_text_comma_between_digits_still_splits_batch():
    result = split_multiple_expense_texts(
        "кофе 120,50",
        input_source="text",
    )

    assert result == ["кофе 120", "50"]


@pytest.mark.asyncio
async def test_voice_model_number_stays_in_description():
    result = split_multiple_expense_texts(
        "айфон 15 80000 чехол 1000",
        input_source="voice",
    )

    assert result == [
        "айфон 15 80000",
        "чехол 1000",
    ]


@pytest.mark.asyncio
async def test_text_amount_with_space_does_not_create_batch():
    result = split_multiple_expense_texts(
        "48 000 аренда",
        input_source="text",
    )

    assert result is None
