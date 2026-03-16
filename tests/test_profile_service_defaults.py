import pytest

from bot.constants import (
    DEFAULT_CURRENCY_CODE,
    DEFAULT_LANGUAGE_CODE,
    DEFAULT_TIMEZONE,
)
from bot.services.profile import get_or_create_profile, get_user_settings, toggle_cashback
from expenses.models import Profile


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_get_user_settings_creates_profile_with_shared_defaults():
    settings = await get_user_settings(telegram_id=900001)

    profile = settings.profile
    assert profile.language_code == DEFAULT_LANGUAGE_CODE
    assert profile.timezone == DEFAULT_TIMEZONE
    assert profile.currency == DEFAULT_CURRENCY_CODE
    assert settings.cashback_enabled is True


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_toggle_cashback_creates_profile_with_shared_defaults():
    cashback_enabled = await toggle_cashback(telegram_id=900002)
    profile = await Profile.objects.aget(telegram_id=900002)

    assert cashback_enabled is False
    assert profile.language_code == DEFAULT_LANGUAGE_CODE
    assert profile.timezone == DEFAULT_TIMEZONE
    assert profile.currency == DEFAULT_CURRENCY_CODE


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_get_or_create_profile_uses_language_specific_default_currency():
    profile = await get_or_create_profile(telegram_id=900003, language_code="en-US")

    assert profile.language_code == "en"
    assert profile.timezone == DEFAULT_TIMEZONE
    assert profile.currency == "USD"
