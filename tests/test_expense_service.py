from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from asgiref.sync import sync_to_async
from django.utils import timezone

from bot.constants import MAX_DAILY_OPERATIONS, MAX_OPERATION_DESCRIPTION_LENGTH, MAX_TRANSACTION_AMOUNT, ONE_YEAR_DAYS
from bot.services.expense import create_expense, delete_expense, get_expense_by_id, get_expenses_by_period, update_expense
from expenses.models import Expense, ExpenseCategory, Profile, Subscription


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_get_expenses_by_period_returns_current_month_summary(test_expense_category):
    profile = test_expense_category.profile
    month_start = date.today().replace(day=1)

    await sync_to_async(Expense.objects.create)(
        profile=profile,
        category=test_expense_category,
        amount=Decimal("100.00"),
        currency="RUB",
        description="Current month one",
        expense_date=month_start,
    )
    await sync_to_async(Expense.objects.create)(
        profile=profile,
        category=test_expense_category,
        amount=Decimal("250.50"),
        currency="RUB",
        description="Current month two",
        expense_date=date.today(),
    )
    await sync_to_async(Expense.objects.create)(
        profile=profile,
        category=test_expense_category,
        amount=Decimal("999.00"),
        currency="RUB",
        description="Previous month",
        expense_date=month_start - timedelta(days=1),
    )

    summary = await get_expenses_by_period(profile.telegram_id, "month")

    assert isinstance(summary, dict)
    assert summary["count"] == 2
    assert summary["total"] == pytest.approx(350.5)
    assert summary["currency"] == "RUB"
    assert summary["income_total"] == 0


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_get_expenses_by_period_returns_empty_dict_for_user_without_expenses(test_profile):
    summary = await get_expenses_by_period(test_profile.telegram_id, "month")

    assert isinstance(summary, dict)
    assert summary["count"] == 0
    assert summary["total"] == 0
    assert summary["income_total"] == 0


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_update_expense_recalculates_cashback_and_triggers_keyword_update(test_expense, monkeypatch):
    profile = test_expense.profile
    new_category = await sync_to_async(ExpenseCategory.objects.create)(
        profile=profile,
        name="🚕 Такси",
        name_ru="Такси",
        name_en="Taxi",
        icon="🚕",
        original_language="ru",
        is_active=True,
        is_translatable=True,
    )
    await sync_to_async(Subscription.objects.create)(
        profile=profile,
        type="month",
        payment_method="stars",
        amount=100,
        start_date=timezone.now() - timedelta(days=1),
        end_date=timezone.now() + timedelta(days=30),
        is_active=True,
    )

    cashback_calls: list[tuple[int, int, Decimal, int]] = []
    task_calls: list[tuple[tuple[int, int, int], int]] = []

    def fake_cashback(*, user_id: int, category_id: int, amount: Decimal, month: int) -> Decimal:
        cashback_calls.append((user_id, category_id, amount, month))
        return Decimal("12.34")

    def fake_apply_async(*, args: tuple[int, int, int], countdown: int) -> None:
        task_calls.append((args, countdown))

    monkeypatch.setattr("bot.services.cashback.calculate_expense_cashback_sync", fake_cashback)
    monkeypatch.setattr(
        "bot.services.expense.update_keywords_weights",
        SimpleNamespace(apply_async=fake_apply_async),
    )

    success = await update_expense(
        profile.telegram_id,
        test_expense.id,
        category_id=new_category.id,
        description="Updated expense",
    )

    assert success is True

    refreshed = await sync_to_async(Expense.objects.get)(id=test_expense.id)
    assert refreshed.category_id == new_category.id
    assert refreshed.description == "Updated expense"
    assert refreshed.cashback_amount == Decimal("12.34")
    assert cashback_calls == [(profile.telegram_id, new_category.id, refreshed.amount, refreshed.created_at.month)]
    assert task_calls == [((test_expense.id, test_expense.category_id, new_category.id), 0)]


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_update_expense_rejects_foreign_expense(test_expense, profile_data):
    other_profile = await sync_to_async(Profile.objects.create)(
        telegram_id=profile_data["telegram_id"] + 200,
        language_code="ru",
        currency="RUB",
        is_active=True,
    )

    success = await update_expense(other_profile.telegram_id, test_expense.id, description="Should not update")

    assert success is False
    refreshed = await sync_to_async(Expense.objects.get)(id=test_expense.id)
    assert refreshed.description == test_expense.description


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_get_expense_by_id_returns_only_owned_expense(test_expense, profile_data):
    other_profile = await sync_to_async(Profile.objects.create)(
        telegram_id=profile_data["telegram_id"] + 1,
        language_code="ru",
        currency="RUB",
        is_active=True,
    )

    own_expense = await get_expense_by_id(test_expense.id, test_expense.profile.telegram_id)
    foreign_expense = await get_expense_by_id(test_expense.id, other_profile.telegram_id)
    missing_expense = await get_expense_by_id(test_expense.id + 9999, test_expense.profile.telegram_id)

    assert own_expense is not None
    assert own_expense.id == test_expense.id
    assert foreign_expense is None
    assert missing_expense is None


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_delete_expense_deletes_owned_record_and_rejects_missing(test_expense):
    deleted = await delete_expense(test_expense.profile.telegram_id, test_expense.id)
    missing_delete = await delete_expense(test_expense.profile.telegram_id, test_expense.id)

    assert deleted is True
    assert missing_delete is False
    assert not await sync_to_async(Expense.objects.filter(id=test_expense.id).exists)()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_delete_expense_rejects_foreign_expense(test_expense, profile_data):
    other_profile = await sync_to_async(Profile.objects.create)(
        telegram_id=profile_data["telegram_id"] + 300,
        language_code="ru",
        currency="RUB",
        is_active=True,
    )

    deleted = await delete_expense(other_profile.telegram_id, test_expense.id)

    assert deleted is False
    assert await sync_to_async(Expense.objects.filter(id=test_expense.id).exists)()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    ("expense_date", "expected_message"),
    [
        (date.today() + timedelta(days=1), "Нельзя вносить траты в будущем"),
        (date.today() - timedelta(days=ONE_YEAR_DAYS + 1), "Нельзя вносить траты старше 1 года"),
    ],
)
async def test_create_expense_rejects_invalid_dates(test_expense_category, expense_date, expected_message):
    with pytest.raises(ValueError, match=expected_message):
        await create_expense(
            user_id=test_expense_category.profile.telegram_id,
            amount=Decimal("10.00"),
            category_id=test_expense_category.id,
            description="Invalid date expense",
            expense_date=expense_date,
        )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_create_expense_rejects_date_before_profile_registration(test_expense_category):
    profile = test_expense_category.profile
    created_at = timezone.now()
    await sync_to_async(Profile.objects.filter(id=profile.id).update)(created_at=created_at)

    with pytest.raises(ValueError, match="Нельзя вносить траты до даты регистрации"):
        await create_expense(
            user_id=profile.telegram_id,
            amount=Decimal("10.00"),
            category_id=test_expense_category.id,
            description="Before registration expense",
            expense_date=date.today() - timedelta(days=1),
        )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_create_expense_rejects_daily_limit(test_expense_category):
    profile = test_expense_category.profile
    today = date.today()

    def create_many() -> None:
        Expense.objects.bulk_create(
            [
                Expense(
                    profile=profile,
                    category=test_expense_category,
                    amount=Decimal("1.00"),
                    currency="RUB",
                    description=f"Existing expense {idx}",
                    expense_date=today,
                )
                for idx in range(MAX_DAILY_OPERATIONS)
            ]
        )

    await sync_to_async(create_many)()

    with pytest.raises(ValueError, match="Достигнут лимит записей в день"):
        await create_expense(
            user_id=profile.telegram_id,
            amount=Decimal("5.00"),
            category_id=test_expense_category.id,
            description="Overflow expense",
            expense_date=today,
        )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_create_expense_rejects_too_long_description(test_expense_category):
    with pytest.raises(ValueError, match="Описание слишком длинное"):
        await create_expense(
            user_id=test_expense_category.profile.telegram_id,
            amount=Decimal("10.00"),
            category_id=test_expense_category.id,
            description="x" * (MAX_OPERATION_DESCRIPTION_LENGTH + 1),
            expense_date=date.today(),
        )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_create_expense_rejects_too_large_amount(test_expense_category):
    with pytest.raises(ValueError, match="Сумма слишком велика"):
        await create_expense(
            user_id=test_expense_category.profile.telegram_id,
            amount=MAX_TRANSACTION_AMOUNT + Decimal("0.01"),
            category_id=test_expense_category.id,
            description="Too large amount",
            expense_date=date.today(),
        )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_create_expense_rejects_foreign_category(test_expense_category, profile_data):
    other_profile = await sync_to_async(Profile.objects.create)(
        telegram_id=profile_data["telegram_id"] + 400,
        language_code="ru",
        currency="RUB",
        is_active=True,
    )
    foreign_category = await sync_to_async(ExpenseCategory.objects.create)(
        profile=other_profile,
        name="🎬 Кино",
        name_ru="Кино",
        name_en="Cinema",
        icon="🎬",
        original_language="ru",
        is_active=True,
        is_translatable=True,
    )

    with pytest.raises(ValueError, match="Нельзя использовать категорию другого пользователя"):
        await create_expense(
            user_id=test_expense_category.profile.telegram_id,
            amount=Decimal("10.00"),
            category_id=foreign_category.id,
            description="Foreign category expense",
            expense_date=date.today(),
        )
