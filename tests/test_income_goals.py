"""Тесты целей по доходам."""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from asgiref.sync import sync_to_async

from bot.services.expense import get_expenses_summary
from bot.services.income_goal import (
    get_active_goals_map,
    get_goal,
    get_goal_status,
    get_income_goal_statuses,
    remove_goal,
    set_goal,
)
from bot.utils.income_goal_display import format_category_goal_bar_line
from bot.utils.income_goal_notifications import (
    get_income_goal_alert_messages,
    send_income_goal_alerts,
)
from expenses.models import (
    Income,
    IncomeBudget,
    IncomeCategory,
    Profile,
)


async def _create_income(
    profile,
    category,
    amount,
    when=None,
    currency="RUB",
):
    return await sync_to_async(Income.objects.create)(
        profile=profile,
        category=category,
        amount=Decimal(str(amount)),
        currency=currency,
        description="test",
        income_date=when or date.today(),
    )


def _previous_month_day() -> date:
    return date.today().replace(day=1) - timedelta(days=1)


def _patch_subscription(active=True):
    return patch(
        "bot.services.income_goal.check_subscription",
        new=sync_to_async(lambda *args, **kwargs: active),
    )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_set_goal_creates_category_goal(test_income_category):
    profile = test_income_category.profile
    with _patch_subscription():
        goal = await set_goal(
            profile.telegram_id,
            test_income_category.id,
            Decimal("100000"),
        )

    assert goal.category_id == test_income_category.id
    assert goal.amount == Decimal("100000")
    assert goal.currency == "RUB"
    assert goal.period_type == "monthly"
    assert goal.is_active is True
    assert (await get_goal(profile.telegram_id, test_income_category.id)).id == goal.id


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_set_goal_deactivates_previous_and_stale_period(test_income_category):
    profile = test_income_category.profile
    stale = await sync_to_async(IncomeBudget.objects.create)(
        profile=profile,
        category=test_income_category,
        amount=Decimal("500"),
        currency="RUB",
        period_type="weekly",
        start_date=date.today(),
    )

    with _patch_subscription():
        goal = await set_goal(
            profile.telegram_id,
            test_income_category.id,
            Decimal("80000"),
        )

    stale = await sync_to_async(IncomeBudget.objects.get)(id=stale.id)
    assert stale.is_active is False
    active = await sync_to_async(list)(
        IncomeBudget.objects.filter(
            profile=profile,
            category=test_income_category,
            is_active=True,
        )
    )
    assert [item.id for item in active] == [goal.id]


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_category_and_total_goals_are_independent(test_income_category):
    profile = test_income_category.profile
    with _patch_subscription():
        category_goal = await set_goal(
            profile.telegram_id,
            test_income_category.id,
            Decimal("100000"),
        )
        total_goal = await set_goal(
            profile.telegram_id,
            None,
            Decimal("150000"),
        )

    goals = await get_active_goals_map(profile.telegram_id)
    assert goals[test_income_category.id].id == category_goal.id
    assert goals[None].id == total_goal.id


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_remove_goal(test_income_category):
    profile = test_income_category.profile
    with _patch_subscription():
        await set_goal(
            profile.telegram_id,
            test_income_category.id,
            Decimal("100000"),
        )

    assert await remove_goal(profile.telegram_id, test_income_category.id) is True
    assert await remove_goal(profile.telegram_id, test_income_category.id) is False
    assert await get_goal(profile.telegram_id, test_income_category.id) is None


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_set_goal_validates_amount_and_subscription(test_income_category):
    profile = test_income_category.profile
    with _patch_subscription():
        with pytest.raises(ValueError):
            await set_goal(profile.telegram_id, test_income_category.id, Decimal("0"))
        with pytest.raises(ValueError):
            await set_goal(
                profile.telegram_id,
                test_income_category.id,
                Decimal("10000000000"),
            )
        with pytest.raises(ValueError):
            await set_goal(
                profile.telegram_id,
                test_income_category.id,
                Decimal("1.001"),
            )

    with _patch_subscription(active=False):
        with pytest.raises(ValueError):
            await set_goal(
                profile.telegram_id,
                test_income_category.id,
                Decimal("1000"),
            )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_set_goal_rejects_foreign_category(test_income_category):
    owner = test_income_category.profile
    other = await sync_to_async(Profile.objects.create)(
        telegram_id=999000222,
        currency="RUB",
    )
    foreign_category = await sync_to_async(IncomeCategory.objects.create)(
        profile=other,
        name="💼 Foreign",
        name_en="Foreign",
        icon="💼",
        original_language="en",
    )

    with _patch_subscription():
        with pytest.raises(ValueError):
            await set_goal(
                owner.telegram_id,
                foreign_category.id,
                Decimal("1000"),
            )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_goal_status_uses_floor_and_clamps_remaining(test_income_category):
    profile = test_income_category.profile
    with _patch_subscription():
        await set_goal(
            profile.telegram_id,
            test_income_category.id,
            Decimal("1000"),
        )

    await _create_income(profile, test_income_category, "725")
    status = await get_goal_status(profile.telegram_id, test_income_category.id)
    assert status.percent == 72
    assert status.achieved is False
    assert status.remaining == Decimal("275")

    await _create_income(profile, test_income_category, "400")
    status = await get_goal_status(profile.telegram_id, test_income_category.id)
    assert status.percent == 112
    assert status.achieved is True
    assert status.remaining == Decimal("0")


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_category_and_total_cross_only_100_percent(test_income_category):
    profile = test_income_category.profile
    with _patch_subscription():
        await set_goal(
            profile.telegram_id,
            test_income_category.id,
            Decimal("1000"),
        )
        await set_goal(profile.telegram_id, None, Decimal("1000"))

    first = await _create_income(profile, test_income_category, "850")
    statuses = await get_income_goal_statuses(profile.telegram_id, first)
    assert statuses[test_income_category.id].crossed_thresholds == []
    assert statuses[None].crossed_thresholds == []

    crossing = await _create_income(profile, test_income_category, "250")
    statuses = await get_income_goal_statuses(profile.telegram_id, crossing)
    assert statuses[test_income_category.id].crossed_thresholds == [100]
    assert statuses[None].crossed_thresholds == [100]


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_backdated_and_other_currency_income_do_not_trigger(test_income_category):
    profile = test_income_category.profile
    with _patch_subscription():
        await set_goal(
            profile.telegram_id,
            test_income_category.id,
            Decimal("1000"),
        )

    await _create_income(profile, test_income_category, "900")
    backdated = await _create_income(
        profile,
        test_income_category,
        "5000",
        when=_previous_month_day(),
    )
    status = await get_goal_status(
        profile.telegram_id,
        test_income_category.id,
        income=backdated,
    )
    assert status.received == Decimal("900")
    assert status.crossed_thresholds == []

    usd_income = await _create_income(
        profile,
        test_income_category,
        "5000",
        currency="USD",
    )
    status = await get_goal_status(
        profile.telegram_id,
        test_income_category.id,
        income=usd_income,
    )
    assert status.received == Decimal("900")
    assert status.crossed_thresholds == []


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_income_message_shows_goal_percent_and_achievement(test_income_category):
    from bot.utils.expense_messages import format_income_added_message

    profile = test_income_category.profile
    with _patch_subscription():
        await set_goal(
            profile.telegram_id,
            test_income_category.id,
            Decimal("1000"),
        )

    income = await _create_income(profile, test_income_category, "725")
    income = await sync_to_async(
        Income.objects.select_related('profile', 'category').get
    )(id=income.id)
    message = await format_income_added_message(
        income=income,
        category=test_income_category,
        lang="ru",
    )
    assert "(72%)" in message

    await _create_income(profile, test_income_category, "300")
    message = await format_income_added_message(
        income=income,
        category=test_income_category,
        lang="ru",
    )
    assert "(102% 🎉)" in message


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_income_summary_exposes_currency_totals_for_goal_bars(
    test_income_category,
):
    profile = test_income_category.profile
    await _create_income(profile, test_income_category, "1000", currency="RUB")
    await _create_income(profile, test_income_category, "50", currency="USD")

    summary = await get_expenses_summary(
        profile.telegram_id,
        date.today().replace(day=1),
        date.today(),
    )

    assert summary['income_currency_totals'] == {
        "RUB": Decimal("1000"),
        "USD": Decimal("50"),
    }
    category = summary['by_income_category'][0]
    assert category['amounts'] == {
        "RUB": Decimal("1000"),
        "USD": Decimal("50"),
    }


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_alert_messages_include_category_and_total_goal(test_income_category):
    profile = test_income_category.profile
    with _patch_subscription():
        await set_goal(
            profile.telegram_id,
            test_income_category.id,
            Decimal("1000"),
        )
        await set_goal(profile.telegram_id, None, Decimal("1000"))

    crossing = await _create_income(profile, test_income_category, "1100")
    messages = await get_income_goal_alert_messages(
        profile.telegram_id,
        crossing,
        category=test_income_category,
        lang="ru",
    )

    assert len(messages) == 2
    assert "Цель достигнута!" in messages[0]
    assert "Цель по доходу достигнута!" in messages[1]


@pytest.mark.asyncio
async def test_send_income_goal_alerts_does_not_break_on_telegram_error():
    bot = AsyncMock()
    bot.send_message.side_effect = RuntimeError("telegram unavailable")
    income = type(
        "IncomeStub",
        (),
        {"profile": type("ProfileStub", (), {"telegram_id": 123456789})()},
    )()

    with patch(
        "bot.utils.income_goal_notifications.get_income_goal_alert_messages",
        AsyncMock(return_value=["alert"]),
    ):
        sent = await send_income_goal_alerts(
            bot,
            123456789,
            income,
            category=None,
            lang="ru",
        )

    assert sent == 0
    bot.send_message.assert_awaited_once_with(
        chat_id=123456789,
        text="alert",
        parse_mode="HTML",
    )


def test_achieved_category_bar_uses_celebration_marker():
    assert format_category_goal_bar_line(100).endswith("100% 🎉")


def test_tools_keyboard_contains_income_goal_entry():
    # Лимит трат и цель дохода вынесены в меню «Инструменты» (/tools);
    # цель идёт сразу после лимита.
    from bot.keyboards import tools_keyboard

    keyboard = tools_keyboard(lang="ru")
    callbacks = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
    ]
    assert callbacks.index("total_goal") == callbacks.index("total_limit") + 1


def test_income_budget_is_registered_in_admin():
    from django.contrib import admin

    assert IncomeBudget in admin.site._registry
