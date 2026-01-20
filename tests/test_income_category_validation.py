import pytest

from bot.services.income import create_income_category, update_income_category


@pytest.mark.django_db
def test_create_income_category_rejects_sanitized_duplicate(test_profile):
    create_income_category(test_profile.telegram_id, "Test")

    with pytest.raises(ValueError, match="Категория с таким названием уже существует"):
        create_income_category(test_profile.telegram_id, "Test`")


@pytest.mark.django_db
def test_create_income_category_rejects_empty_after_sanitization(test_profile):
    with pytest.raises(ValueError, match="Название категории не может быть пустым"):
        create_income_category(test_profile.telegram_id, "`")


@pytest.mark.django_db
def test_update_income_category_rejects_empty_after_sanitization(test_income_category):
    with pytest.raises(ValueError, match="Название категории не может быть пустым"):
        update_income_category(test_income_category.profile.telegram_id, test_income_category.id, new_name="`")
