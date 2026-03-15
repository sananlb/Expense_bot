from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from asgiref.sync import sync_to_async

from bot.services.expense import create_expense
from bot.services.income import create_income
from expenses.models import Expense, Income


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_create_expense_creates_record_and_uses_noon_for_past_date(test_expense_category, monkeypatch):
    reminder_calls: list[int] = []

    def fake_clear_expense_reminder(telegram_id: int) -> None:
        reminder_calls.append(telegram_id)

    monkeypatch.setattr("expenses.tasks.clear_expense_reminder", fake_clear_expense_reminder)

    profile = test_expense_category.profile
    created_at = profile.created_at - timedelta(days=7)
    await sync_to_async(type(profile).objects.filter(id=profile.id).update)(created_at=created_at)
    profile.created_at = created_at

    expense_date = date.today() - timedelta(days=1)
    expense = await create_expense(
        user_id=profile.telegram_id,
        amount=Decimal("123.45"),
        category_id=test_expense_category.id,
        description="Characterization expense",
        expense_date=expense_date,
    )

    assert expense is not None
    assert expense.id is not None
    assert expense.expense_date == expense_date
    assert expense.expense_time == time(12, 0)
    assert reminder_calls == [profile.telegram_id]
    assert await sync_to_async(
        Expense.objects.filter(id=expense.id, description="Characterization expense").exists
    )()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_create_expense_returns_created_record_when_reminder_side_effect_fails(test_expense_category, monkeypatch):
    def failing_clear_expense_reminder(_: int) -> None:
        raise RuntimeError("reminder cleanup failed")

    monkeypatch.setattr("expenses.tasks.clear_expense_reminder", failing_clear_expense_reminder)

    expense = await create_expense(
        user_id=test_expense_category.profile.telegram_id,
        amount=Decimal("55.00"),
        category_id=test_expense_category.id,
        description="Partial expense persistence",
        expense_date=date.today(),
    )

    assert expense is not None
    persisted = Expense.objects.filter(
        profile=test_expense_category.profile,
        description="Partial expense persistence",
    )
    assert await sync_to_async(persisted.count)() == 1


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_create_income_creates_record_and_uses_noon_for_past_date(test_income_category, monkeypatch):
    reminder_calls: list[int] = []

    def fake_clear_expense_reminder(telegram_id: int) -> None:
        reminder_calls.append(telegram_id)

    monkeypatch.setattr("expenses.tasks.clear_expense_reminder", fake_clear_expense_reminder)

    profile = test_income_category.profile
    created_at = profile.created_at - timedelta(days=7)
    await sync_to_async(type(profile).objects.filter(id=profile.id).update)(created_at=created_at)
    profile.created_at = created_at

    income_date = date.today() - timedelta(days=1)
    income = await create_income(
        user_id=profile.telegram_id,
        amount=Decimal("999.99"),
        category_id=test_income_category.id,
        description="Characterization income",
        income_date=income_date,
    )

    assert income is not None
    assert income.id is not None
    assert income.income_date == income_date
    assert income.income_time == time(12, 0)
    assert reminder_calls == [profile.telegram_id]
    assert await sync_to_async(
        Income.objects.filter(id=income.id, description="Characterization income").exists
    )()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_create_income_returns_created_record_when_reminder_side_effect_fails(test_income_category, monkeypatch):
    def failing_clear_expense_reminder(_: int) -> None:
        raise RuntimeError("reminder cleanup failed")

    monkeypatch.setattr("expenses.tasks.clear_expense_reminder", failing_clear_expense_reminder)

    income = await create_income(
        user_id=test_income_category.profile.telegram_id,
        amount=Decimal("77.00"),
        category_id=test_income_category.id,
        description="Partial income persistence",
        income_date=date.today(),
    )

    assert income is not None
    persisted = Income.objects.filter(
        profile=test_income_category.profile,
        description="Partial income persistence",
    )
    assert await sync_to_async(persisted.count)() == 1
