from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from asgiref.sync import sync_to_async
from django.utils import timezone

from bot.services.subscription import (
    check_subscription,
    deactivate_expired_subscriptions,
    get_active_subscription,
    is_trial_active,
)
from expenses.models import Profile, Subscription, UserSettings


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_check_subscription_returns_true_for_beta_tester(test_profile):
    await sync_to_async(Profile.objects.filter(id=test_profile.id).update)(is_beta_tester=True)

    assert await check_subscription(test_profile.telegram_id) is True


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_check_subscription_respects_include_trial_flag(test_profile):
    await sync_to_async(Subscription.objects.create)(
        profile=test_profile,
        type="trial",
        payment_method="trial",
        amount=0,
        start_date=timezone.now() - timedelta(days=1),
        end_date=timezone.now() + timedelta(days=3),
        is_active=True,
    )

    assert await check_subscription(test_profile.telegram_id, include_trial=True) is True
    assert await check_subscription(test_profile.telegram_id, include_trial=False) is False


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_check_subscription_returns_false_for_expired_subscription(test_profile):
    await sync_to_async(Subscription.objects.create)(
        profile=test_profile,
        type="month",
        payment_method="stars",
        amount=299,
        start_date=timezone.now() - timedelta(days=10),
        end_date=timezone.now() - timedelta(minutes=1),
        is_active=True,
    )

    assert await check_subscription(test_profile.telegram_id) is False


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_check_subscription_returns_true_for_paid_active_subscription(test_profile):
    await sync_to_async(Subscription.objects.create)(
        profile=test_profile,
        type="month",
        payment_method="stars",
        amount=299,
        start_date=timezone.now() - timedelta(days=1),
        end_date=timezone.now() + timedelta(days=10),
        is_active=True,
    )

    assert await check_subscription(test_profile.telegram_id) is True
    assert await check_subscription(test_profile.telegram_id, include_trial=False) is True


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_is_trial_active_and_get_active_subscription_use_current_records(test_profile):
    trial = await sync_to_async(Subscription.objects.create)(
        profile=test_profile,
        type="trial",
        payment_method="trial",
        amount=0,
        start_date=timezone.now() - timedelta(days=2),
        end_date=timezone.now() + timedelta(days=2),
        is_active=True,
    )
    paid = await sync_to_async(Subscription.objects.create)(
        profile=test_profile,
        type="month",
        payment_method="stars",
        amount=299,
        start_date=timezone.now() - timedelta(days=1),
        end_date=timezone.now() + timedelta(days=10),
        is_active=True,
    )

    assert await is_trial_active(test_profile.telegram_id) is True
    active = await get_active_subscription(test_profile.telegram_id)
    assert active is not None
    assert active.id == paid.id
    assert active.end_date > trial.end_date


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_get_active_subscription_returns_none_when_profile_has_no_subscriptions(test_profile):
    assert await get_active_subscription(test_profile.telegram_id) is None


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_subscription_queries_return_safe_defaults_for_missing_profile():
    assert await check_subscription(999999001) is False
    assert await is_trial_active(999999001) is False
    assert await get_active_subscription(999999001) is None


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_deactivate_expired_subscriptions_disables_premium_settings_and_updates_commands(
    test_profile,
    monkeypatch,
):
    await sync_to_async(UserSettings.objects.create)(
        profile=test_profile,
        cashback_enabled=True,
        view_scope="household",
    )
    expired = await sync_to_async(Subscription.objects.create)(
        profile=test_profile,
        type="month",
        payment_method="stars",
        amount=299,
        start_date=timezone.now() - timedelta(days=30),
        end_date=timezone.now() - timedelta(minutes=1),
        is_active=True,
    )

    update_commands = AsyncMock()
    monkeypatch.setattr("bot.services.subscription._update_commands_for_users", update_commands)

    expired_count = await deactivate_expired_subscriptions()

    refreshed_subscription = await sync_to_async(Subscription.objects.get)(id=expired.id)
    settings = await sync_to_async(UserSettings.objects.get)(profile=test_profile)

    assert expired_count == 1
    assert refreshed_subscription.is_active is False
    assert settings.view_scope == "personal"
    assert settings.cashback_enabled is False
    update_commands.assert_awaited_once_with([test_profile.telegram_id])


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_deactivate_expired_subscriptions_keeps_premium_settings_if_other_active_subscription_exists(
    test_profile,
    monkeypatch,
):
    await sync_to_async(UserSettings.objects.create)(
        profile=test_profile,
        cashback_enabled=True,
        view_scope="household",
    )
    expired = await sync_to_async(Subscription.objects.create)(
        profile=test_profile,
        type="month",
        payment_method="stars",
        amount=299,
        start_date=timezone.now() - timedelta(days=30),
        end_date=timezone.now() - timedelta(minutes=1),
        is_active=True,
    )
    active = await sync_to_async(Subscription.objects.create)(
        profile=test_profile,
        type="six_months",
        payment_method="stars",
        amount=999,
        start_date=timezone.now() - timedelta(days=1),
        end_date=timezone.now() + timedelta(days=30),
        is_active=True,
    )

    update_commands = AsyncMock()
    monkeypatch.setattr("bot.services.subscription._update_commands_for_users", update_commands)

    expired_count = await deactivate_expired_subscriptions()

    expired_refreshed = await sync_to_async(Subscription.objects.get)(id=expired.id)
    active_refreshed = await sync_to_async(Subscription.objects.get)(id=active.id)
    settings = await sync_to_async(UserSettings.objects.get)(profile=test_profile)

    assert expired_count == 1
    assert expired_refreshed.is_active is False
    assert active_refreshed.is_active is True
    assert settings.view_scope == "household"
    assert settings.cashback_enabled is True
    update_commands.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_deactivate_expired_subscriptions_returns_zero_for_empty_table(monkeypatch):
    update_commands = AsyncMock()
    monkeypatch.setattr("bot.services.subscription._update_commands_for_users", update_commands)

    expired_count = await deactivate_expired_subscriptions()

    assert expired_count == 0
    update_commands.assert_not_awaited()
