from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from asgiref.sync import sync_to_async
from django.utils import timezone

from bot.constants import MAX_DAILY_OPERATIONS, MAX_OPERATION_DESCRIPTION_LENGTH, MAX_TRANSACTION_AMOUNT, ONE_YEAR_DAYS
from bot.services.income import create_income, delete_income, get_income_by_id, get_incomes_by_period, update_income
from expenses.models import Expense, Income, IncomeCategory, Profile


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_get_incomes_by_period_returns_current_month_summary(test_income_category):
    profile = test_income_category.profile
    month_start = date.today().replace(day=1)

    await sync_to_async(Income.objects.create)(
        profile=profile,
        category=test_income_category,
        amount=Decimal("1000.00"),
        currency="RUB",
        description="Current month one",
        income_date=month_start,
    )
    await sync_to_async(Income.objects.create)(
        profile=profile,
        category=test_income_category,
        amount=Decimal("2500.50"),
        currency="RUB",
        description="Current month two",
        income_date=date.today(),
    )
    await sync_to_async(Income.objects.create)(
        profile=profile,
        category=test_income_category,
        amount=Decimal("9999.00"),
        currency="RUB",
        description="Previous month",
        income_date=month_start - timedelta(days=1),
    )

    summary = await get_incomes_by_period(profile.telegram_id, "month")

    assert isinstance(summary, dict)
    assert summary["count"] == 2
    assert summary["total"] == pytest.approx(3500.5)
    assert summary["currency"] == "RUB"


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_get_incomes_by_period_returns_empty_dict_for_user_without_incomes(test_profile):
    summary = await get_incomes_by_period(test_profile.telegram_id, "month")

    assert isinstance(summary, dict)
    assert summary["count"] == 0
    assert summary["total"] == 0
    assert summary["by_category"] == []


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_update_income_updates_category_and_triggers_keyword_learning(test_income, monkeypatch):
    profile = test_income.profile
    new_category = await sync_to_async(IncomeCategory.objects.create)(
        profile=profile,
        name="💼 Фриланс",
        name_ru="Фриланс",
        name_en="Freelance",
        icon="💼",
        original_language="ru",
        is_active=True,
        is_translatable=True,
    )

    task_calls: list[tuple[dict[str, int | None], int]] = []

    def fake_apply_async(*, kwargs: dict[str, int | None], countdown: int) -> None:
        task_calls.append((kwargs, countdown))

    monkeypatch.setattr(
        "bot.services.income.update_income_keywords",
        SimpleNamespace(apply_async=fake_apply_async),
    )

    success = await update_income(
        profile.telegram_id,
        test_income.id,
        category_id=new_category.id,
        description="Updated income",
    )

    assert success is True

    refreshed = await sync_to_async(Income.objects.get)(id=test_income.id)
    assert refreshed.category_id == new_category.id
    assert refreshed.description == "Updated income"
    assert task_calls == [
        (
            {
                "income_id": test_income.id,
                "old_category_id": test_income.category_id,
                "new_category_id": new_category.id,
            },
            0,
        )
    ]


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_update_income_rejects_foreign_income(test_income, profile_data):
    other_profile = await sync_to_async(Profile.objects.create)(
        telegram_id=profile_data["telegram_id"] + 500,
        language_code="ru",
        currency="RUB",
        is_active=True,
    )

    success = await update_income(other_profile.telegram_id, test_income.id, description="Should not update")

    assert success is False
    refreshed = await sync_to_async(Income.objects.get)(id=test_income.id)
    assert refreshed.description == test_income.description


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_get_income_by_id_returns_only_owned_income(test_income, profile_data):
    other_profile = await sync_to_async(Profile.objects.create)(
        telegram_id=profile_data["telegram_id"] + 600,
        language_code="ru",
        currency="RUB",
        is_active=True,
    )

    own_income = await get_income_by_id(test_income.id, test_income.profile.telegram_id)
    foreign_income = await get_income_by_id(test_income.id, other_profile.telegram_id)
    missing_income = await get_income_by_id(test_income.id + 9999, test_income.profile.telegram_id)

    assert own_income is not None
    assert own_income.id == test_income.id
    assert foreign_income is None
    assert missing_income is None


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_delete_income_deletes_owned_record_and_rejects_missing(test_income):
    deleted = await delete_income(test_income.profile.telegram_id, test_income.id)
    missing_delete = await delete_income(test_income.profile.telegram_id, test_income.id)

    assert deleted is True
    assert missing_delete is False
    assert not await sync_to_async(Income.objects.filter(id=test_income.id).exists)()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_delete_income_rejects_foreign_income(test_income, profile_data):
    other_profile = await sync_to_async(Profile.objects.create)(
        telegram_id=profile_data["telegram_id"] + 700,
        language_code="ru",
        currency="RUB",
        is_active=True,
    )

    deleted = await delete_income(other_profile.telegram_id, test_income.id)

    assert deleted is False
    assert await sync_to_async(Income.objects.filter(id=test_income.id).exists)()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    ("income_date", "expected_message"),
    [
        (date.today() + timedelta(days=1), "Нельзя вносить доходы в будущем"),
        (date.today() - timedelta(days=ONE_YEAR_DAYS + 1), "Нельзя вносить доходы старше 1 года"),
    ],
)
async def test_create_income_rejects_invalid_dates(test_income_category, income_date, expected_message):
    with pytest.raises(ValueError, match=expected_message):
        await create_income(
            user_id=test_income_category.profile.telegram_id,
            amount=Decimal("10.00"),
            category_id=test_income_category.id,
            description="Invalid date income",
            income_date=income_date,
        )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_create_income_rejects_date_before_profile_registration(test_income_category):
    profile = test_income_category.profile
    created_at = timezone.now()
    await sync_to_async(Profile.objects.filter(id=profile.id).update)(created_at=created_at)

    with pytest.raises(ValueError, match="Нельзя вносить доходы до даты регистрации"):
        await create_income(
            user_id=profile.telegram_id,
            amount=Decimal("10.00"),
            category_id=test_income_category.id,
            description="Before registration income",
            income_date=date.today() - timedelta(days=1),
        )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_create_income_rejects_daily_limit_from_combined_operations(test_income_category):
    profile = test_income_category.profile
    today = date.today()

    def create_many() -> None:
        Expense.objects.bulk_create(
            [
                Expense(
                    profile=profile,
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
        await create_income(
            user_id=profile.telegram_id,
            amount=Decimal("5.00"),
            category_id=test_income_category.id,
            description="Overflow income",
            income_date=today,
        )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_create_income_truncates_too_long_description(test_income_category, monkeypatch):
    def fake_clear_expense_reminder(_: int) -> None:
        return None

    monkeypatch.setattr("expenses.tasks.clear_expense_reminder", fake_clear_expense_reminder)

    income = await create_income(
        user_id=test_income_category.profile.telegram_id,
        amount=Decimal("10.00"),
        category_id=test_income_category.id,
        description="x" * (MAX_OPERATION_DESCRIPTION_LENGTH + 25),
        income_date=date.today(),
    )

    assert income is not None
    assert len(income.description) == MAX_OPERATION_DESCRIPTION_LENGTH


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_create_income_rejects_too_large_amount(test_income_category):
    with pytest.raises(ValueError, match="Сумма слишком велика"):
        await create_income(
            user_id=test_income_category.profile.telegram_id,
            amount=MAX_TRANSACTION_AMOUNT + Decimal("0.01"),
            category_id=test_income_category.id,
            description="Too large amount",
            income_date=date.today(),
        )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_create_income_rejects_foreign_category(test_income_category, profile_data):
    other_profile = await sync_to_async(Profile.objects.create)(
        telegram_id=profile_data["telegram_id"] + 800,
        language_code="ru",
        currency="RUB",
        is_active=True,
    )
    foreign_category = await sync_to_async(IncomeCategory.objects.create)(
        profile=other_profile,
        name="🎁 Подарок",
        name_ru="Подарок",
        name_en="Gift",
        icon="🎁",
        original_language="ru",
        is_active=True,
        is_translatable=True,
    )

    with pytest.raises(ValueError, match="Нельзя использовать категорию другого пользователя"):
        await create_income(
            user_id=test_income_category.profile.telegram_id,
            amount=Decimal("10.00"),
            category_id=foreign_category.id,
            description="Foreign category income",
            income_date=date.today(),
        )
