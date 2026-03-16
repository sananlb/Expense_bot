from asgiref.sync import sync_to_async
import pytest

from bot.services.category import (
    create_category,
    create_default_categories_sync,
    delete_category,
    get_category_by_id,
    get_or_create_category_sync,
    get_user_categories,
    update_category_name,
)
from bot.utils.category_validators import MAX_CATEGORIES_PER_USER
from expenses.models import ExpenseCategory, Profile


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_create_category_creates_profile_and_multilingual_fields():
    user_id = 987654321

    category = await create_category(user_id, "Travel", "✈️")

    profile = await sync_to_async(Profile.objects.get)(telegram_id=user_id)
    assert category.profile_id == profile.id
    assert category.name_en == "Travel"
    assert category.name_ru in (None, "")
    assert category.original_language == "en"
    assert category.is_translatable is False
    assert category.name == "✈️ Travel"


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_create_category_rejects_duplicate_name_for_same_user(test_profile):
    await create_category(test_profile.telegram_id, "Еда", "🍔")

    with pytest.raises(ValueError, match="Категория с таким названием уже существует"):
        await create_category(test_profile.telegram_id, "Еда", "🍽️")


@pytest.mark.django_db
def test_get_or_create_category_sync_returns_exact_match_ignoring_emoji(test_expense_category):
    category = get_or_create_category_sync(test_expense_category.profile.telegram_id, "Еда")

    assert category.id == test_expense_category.id


@pytest.mark.django_db
def test_get_or_create_category_sync_falls_back_to_other_expenses(test_profile):
    category = get_or_create_category_sync(test_profile.telegram_id, "Несуществующая категория")

    assert category.profile_id == test_profile.id
    assert category.name_ru == "Прочие расходы"
    assert category.name_en == "Other Expenses"


@pytest.mark.django_db
def test_get_or_create_category_sync_is_idempotent_for_missing_category(test_profile):
    first = get_or_create_category_sync(test_profile.telegram_id, "Совсем новая категория")
    second = get_or_create_category_sync(test_profile.telegram_id, "Совсем новая категория")

    assert first.id == second.id
    assert ExpenseCategory.objects.filter(profile=test_profile, name_ru="Прочие расходы").count() == 1


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_get_user_categories_sorts_regular_categories_and_keeps_other_last(test_profile):
    categories = [
        ExpenseCategory(
            profile=test_profile,
            name="🍌 Бананы",
            name_ru="Бананы",
            name_en="Bananas",
            original_language="ru",
            is_translatable=False,
            icon="🍌",
        ),
        ExpenseCategory(
            profile=test_profile,
            name="🍎 Яблоки",
            name_ru="Яблоки",
            name_en="Apples",
            original_language="ru",
            is_translatable=False,
            icon="🍎",
        ),
        ExpenseCategory(
            profile=test_profile,
            name="💰 Прочие расходы",
            name_ru="Прочие расходы",
            name_en="Other Expenses",
            original_language="ru",
            is_translatable=True,
            icon="💰",
        ),
    ]
    await sync_to_async(ExpenseCategory.objects.bulk_create)(categories)

    result = await get_user_categories(test_profile.telegram_id)
    names = [cat.name_ru for cat in result]

    assert names[:-1] == ["Бананы", "Яблоки"]
    assert names[-1] == "Прочие расходы"


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_get_user_categories_does_not_leak_other_users_categories(test_profile, profile_data):
    other_profile = await sync_to_async(Profile.objects.create)(
        telegram_id=profile_data["telegram_id"] + 901,
        language_code="ru",
        currency="RUB",
        is_active=True,
    )
    await sync_to_async(ExpenseCategory.objects.create)(
        profile=test_profile,
        name="🍎 Яблоки",
        name_ru="Яблоки",
        name_en="Apples",
        original_language="ru",
        is_translatable=False,
        icon="🍎",
    )
    await sync_to_async(ExpenseCategory.objects.create)(
        profile=other_profile,
        name="🚗 Машина",
        name_ru="Машина",
        name_en="Car",
        original_language="ru",
        is_translatable=False,
        icon="🚗",
    )

    result = await get_user_categories(test_profile.telegram_id)

    names = {cat.name_ru for cat in result}
    assert "Яблоки" in names
    assert "Машина" not in names


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_update_category_name_updates_icon_and_language(test_expense_category):
    success = await update_category_name(
        test_expense_category.profile.telegram_id,
        test_expense_category.id,
        "✈️ Travel",
    )

    refreshed = await sync_to_async(ExpenseCategory.objects.get)(id=test_expense_category.id)

    assert success is True
    assert refreshed.icon == "✈️"
    assert refreshed.name_en == "Travel"
    assert refreshed.original_language == "en"
    assert refreshed.name == "✈️ Travel"


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_update_category_name_rejects_duplicate(test_profile):
    first = await create_category(test_profile.telegram_id, "Еда", "🍔")
    second = await create_category(test_profile.telegram_id, "Транспорт", "🚕")

    with pytest.raises(ValueError, match="Категория с таким названием уже существует"):
        await update_category_name(test_profile.telegram_id, second.id, "🍔 Еда")

    unchanged = await sync_to_async(ExpenseCategory.objects.get)(id=second.id)
    assert unchanged.id == second.id
    assert first.id != second.id


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_update_category_name_rejects_foreign_category(test_expense_category, profile_data):
    other_profile = await sync_to_async(Profile.objects.create)(
        telegram_id=profile_data["telegram_id"] + 902,
        language_code="ru",
        currency="RUB",
        is_active=True,
    )

    with pytest.raises(ValueError, match="Категория не найдена"):
        await update_category_name(other_profile.telegram_id, test_expense_category.id, "🍔 Новое имя")

    unchanged = await sync_to_async(ExpenseCategory.objects.get)(id=test_expense_category.id)
    assert unchanged.id == test_expense_category.id
    assert unchanged.name_ru == test_expense_category.name_ru


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_delete_category_and_get_category_by_id_respect_ownership(test_expense_category, profile_data):
    other_profile = await sync_to_async(Profile.objects.create)(
        telegram_id=profile_data["telegram_id"] + 900,
        language_code="ru",
        currency="RUB",
        is_active=True,
    )

    owned = await get_category_by_id(test_expense_category.profile.telegram_id, test_expense_category.id)
    foreign = await get_category_by_id(other_profile.telegram_id, test_expense_category.id)
    foreign_delete = await delete_category(other_profile.telegram_id, test_expense_category.id)
    owned_delete = await delete_category(test_expense_category.profile.telegram_id, test_expense_category.id)

    assert owned is not None
    assert foreign is None
    assert foreign_delete is False
    assert owned_delete is True
    assert not await sync_to_async(ExpenseCategory.objects.filter(id=test_expense_category.id).exists)()


@pytest.mark.django_db
def test_create_default_categories_sync_is_idempotent(test_profile):
    created = create_default_categories_sync(test_profile.telegram_id)
    first_count = ExpenseCategory.objects.filter(profile=test_profile).count()
    second_run = create_default_categories_sync(test_profile.telegram_id)
    second_count = ExpenseCategory.objects.filter(profile=test_profile).count()

    assert created is True
    assert first_count == 17
    assert second_run is False
    assert second_count == 17


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_create_category_rejects_limit_reached(test_profile):
    categories = [
        ExpenseCategory(
            profile=test_profile,
            name=f"💰 Категория {idx}",
            name_ru=f"Категория {idx}",
            name_en=f"Category {idx}",
            original_language="ru",
            is_translatable=False,
            icon="💰",
        )
        for idx in range(MAX_CATEGORIES_PER_USER)
    ]
    await sync_to_async(ExpenseCategory.objects.bulk_create)(categories)

    with pytest.raises(ValueError, match="Достигнут лимит категорий"):
        await create_category(test_profile.telegram_id, "Лишняя", "➕")
