import pytest

from bot.services.income import create_income_category, update_income_category


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_create_income_category_rejects_sanitized_duplicate(test_profile):
    await create_income_category(test_profile.telegram_id, "Test")

    with pytest.raises(ValueError, match="Категория с таким названием уже существует"):
        await create_income_category(test_profile.telegram_id, "Test`")


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_create_income_category_rejects_empty_after_sanitization(test_profile):
    with pytest.raises(ValueError, match="Название категории не может быть пустым"):
        await create_income_category(test_profile.telegram_id, "`")


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_update_income_category_rejects_empty_after_sanitization(test_income_category):
    with pytest.raises(ValueError, match="Название категории не может быть пустым"):
        await update_income_category(test_income_category.profile.telegram_id, test_income_category.id, new_name="`")
