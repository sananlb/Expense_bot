"""
Tests for Top-5 aggregation service (bot/services/top5.py).

Основной сценарий: операции, созданные из регулярных платежей
(is_recurring=True), не должны попадать в топ-5.
"""
from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from asgiref.sync import sync_to_async

from expenses.models import Expense, Income, Profile
from bot.services.top5 import calculate_top5_sync


def _make_profile(telegram_id: int = 987654321) -> Profile:
    return Profile.objects.create(
        telegram_id=telegram_id,
        language_code='ru',
        currency='RUB',
        is_active=True,
    )


def _make_expense(profile: Profile, description: str, amount: str,
                  days_ago: int = 1, is_recurring: bool = False) -> Expense:
    return Expense.objects.create(
        profile=profile,
        amount=Decimal(amount),
        currency='RUB',
        description=description,
        expense_date=date.today() - timedelta(days=days_ago),
        expense_time=time(12, 0),
        is_recurring=is_recurring,
    )


def _make_income(profile: Profile, description: str, amount: str,
                 days_ago: int = 1, is_recurring: bool = False) -> Income:
    return Income.objects.create(
        profile=profile,
        amount=Decimal(amount),
        currency='RUB',
        description=description,
        income_date=date.today() - timedelta(days=days_ago),
        income_time=time(12, 0),
        is_recurring=is_recurring,
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_top5_includes_repeated_manual_expenses():
    """Повторяющиеся ручные траты (count >= 2) попадают в топ-5."""
    profile = await sync_to_async(_make_profile)()
    await sync_to_async(_make_expense)(profile, 'Кофе', '200', days_ago=1)
    await sync_to_async(_make_expense)(profile, 'Кофе', '200', days_ago=2)

    window_end = date.today()
    window_start = window_end - timedelta(days=89)
    items, _ = await calculate_top5_sync(profile, window_start, window_end)

    assert len(items) == 1
    assert items[0]['title_norm'] == 'кофе'
    assert items[0]['count'] == 2


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_top5_excludes_recurring_expenses():
    """Траты из регулярных платежей (is_recurring=True) исключаются из топ-5."""
    profile = await sync_to_async(_make_profile)()
    # Регулярная трата повторяется 3 раза — раньше гарантированно попала бы в топ
    for days_ago in (1, 31, 61):
        await sync_to_async(_make_expense)(
            profile, '[Ежемесячный] Аренда', '30000',
            days_ago=days_ago, is_recurring=True,
        )
    # Обычная повторяющаяся трата — должна остаться
    await sync_to_async(_make_expense)(profile, 'Кофе', '200', days_ago=1)
    await sync_to_async(_make_expense)(profile, 'Кофе', '200', days_ago=2)

    window_end = date.today()
    window_start = window_end - timedelta(days=89)
    items, _ = await calculate_top5_sync(profile, window_start, window_end)

    titles = [it['title_norm'] for it in items]
    assert 'кофе' in titles
    assert all('аренда' not in t for t in titles)


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_top5_excludes_recurring_incomes():
    """Доходы из регулярных платежей (is_recurring=True) исключаются из топ-5."""
    profile = await sync_to_async(_make_profile)()
    for days_ago in (1, 31):
        await sync_to_async(_make_income)(
            profile, '[Ежемесячный] Зарплата', '100000',
            days_ago=days_ago, is_recurring=True,
        )
    await sync_to_async(_make_income)(profile, 'Фриланс', '5000', days_ago=1)
    await sync_to_async(_make_income)(profile, 'Фриланс', '5000', days_ago=3)

    window_end = date.today()
    window_start = window_end - timedelta(days=89)
    items, _ = await calculate_top5_sync(profile, window_start, window_end)

    titles = [it['title_norm'] for it in items]
    assert 'фриланс' in titles
    assert all('зарплата' not in t for t in titles)
