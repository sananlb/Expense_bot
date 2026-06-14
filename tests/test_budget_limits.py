"""Тесты сервисного слоя лимитов трат (bot/services/budget.py)."""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from asgiref.sync import sync_to_async

from bot.services.budget import (
    get_active_limits_map,
    get_expense_limit_statuses,
    get_limit,
    get_limit_status,
    remove_limit,
    set_limit,
)
from bot.utils.budget_notifications import (
    get_expense_limit_alert_messages,
    send_expense_limit_alerts,
)
from expenses.models import Budget, Expense, ExpenseCategory, Profile

# --- helpers ----------------------------------------------------------------

async def _create_expense(profile, category, amount, when=None, currency="RUB"):
    return await sync_to_async(Expense.objects.create)(
        profile=profile,
        category=category,
        amount=Decimal(str(amount)),
        currency=currency,
        description="test",
        expense_date=when or date.today(),
    )


def _month_start() -> date:
    return date.today().replace(day=1)


def _prev_month_day() -> date:
    return _month_start() - timedelta(days=1)


# Патчим check_subscription, чтобы тесты не зависели от наличия подписки.
def _patch_sub(active=True):
    return patch("bot.services.budget.check_subscription",
                 new=sync_to_async(lambda *a, **k: active))


# --- set / get / remove -----------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_set_limit_creates_category_budget(test_expense_category):
    profile = test_expense_category.profile
    with _patch_sub():
        budget = await set_limit(profile.telegram_id, test_expense_category.id, Decimal("10000"))

    assert budget.amount == Decimal("10000")
    assert budget.category_id == test_expense_category.id
    assert budget.currency == "RUB"
    assert budget.period_type == "monthly"
    assert budget.is_active is True

    found = await get_limit(profile.telegram_id, test_expense_category.id)
    assert found is not None and found.id == budget.id


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_set_limit_deactivates_previous(test_expense_category):
    profile = test_expense_category.profile
    with _patch_sub():
        first = await set_limit(profile.telegram_id, test_expense_category.id, Decimal("5000"))
        second = await set_limit(profile.telegram_id, test_expense_category.id, Decimal("8000"))

    # Должен остаться только один активный лимит — последний.
    active = await sync_to_async(list)(
        Budget.objects.filter(profile=profile, category=test_expense_category, is_active=True)
    )
    assert len(active) == 1
    assert active[0].id == second.id
    assert active[0].amount == Decimal("8000")

    first_refreshed = await sync_to_async(Budget.objects.get)(id=first.id)
    assert first_refreshed.is_active is False


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_set_total_limit_independent_of_category(test_expense_category):
    profile = test_expense_category.profile
    with _patch_sub():
        cat_budget = await set_limit(profile.telegram_id, test_expense_category.id, Decimal("3000"))
        total_budget = await set_limit(profile.telegram_id, None, Decimal("50000"))

    assert cat_budget.category_id == test_expense_category.id
    assert total_budget.category_id is None

    # Оба активны одновременно.
    total = await get_limit(profile.telegram_id, None)
    cat = await get_limit(profile.telegram_id, test_expense_category.id)
    assert total.id == total_budget.id
    assert cat.id == cat_budget.id


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_remove_limit(test_expense_category):
    profile = test_expense_category.profile
    with _patch_sub():
        await set_limit(profile.telegram_id, test_expense_category.id, Decimal("10000"))

    removed = await remove_limit(profile.telegram_id, test_expense_category.id)
    assert removed is True
    assert await get_limit(profile.telegram_id, test_expense_category.id) is None

    # Повторное удаление — уже нечего деактивировать.
    removed_again = await remove_limit(profile.telegram_id, test_expense_category.id)
    assert removed_again is False


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_set_limit_rejects_nonpositive(test_expense_category):
    profile = test_expense_category.profile
    with _patch_sub():
        with pytest.raises(ValueError):
            await set_limit(profile.telegram_id, test_expense_category.id, Decimal("0"))


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_set_limit_rejects_amount_outside_decimal_field(test_expense_category):
    profile = test_expense_category.profile
    with _patch_sub():
        with pytest.raises(ValueError):
            await set_limit(
                profile.telegram_id,
                test_expense_category.id,
                Decimal("10000000000"),
            )
        with pytest.raises(ValueError):
            await set_limit(
                profile.telegram_id,
                test_expense_category.id,
                Decimal("1.001"),
            )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_set_limit_requires_subscription(test_expense_category):
    profile = test_expense_category.profile
    with _patch_sub(active=False):
        with pytest.raises(ValueError):
            await set_limit(profile.telegram_id, test_expense_category.id, Decimal("10000"))


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_set_limit_deactivates_stale_nonmonthly(test_expense_category):
    """Legacy активный лимит другого периода (weekly) не должен блокировать
    создание monthly через unique-constraint — set_limit деактивирует его."""
    profile = test_expense_category.profile
    # Имитируем legacy weekly-лимит на ту же категорию.
    await sync_to_async(Budget.objects.create)(
        profile=profile, category=test_expense_category,
        amount=Decimal("999"), currency="RUB",
        period_type="weekly", start_date=date.today(), is_active=True,
    )
    with _patch_sub():
        budget = await set_limit(profile.telegram_id, test_expense_category.id, Decimal("10000"))

    assert budget.period_type == "monthly"
    # Активным остался только новый monthly-лимит.
    active = await sync_to_async(list)(
        Budget.objects.filter(profile=profile, category=test_expense_category, is_active=True)
    )
    assert len(active) == 1
    assert active[0].id == budget.id


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_set_limit_rejects_foreign_category(test_expense_category):
    """Категория другого профиля → ValueError."""
    owner = test_expense_category.profile
    other = await sync_to_async(Profile.objects.create)(telegram_id=999000111, currency="RUB")
    foreign_cat = await sync_to_async(ExpenseCategory.objects.create)(
        profile=other, name="🍕 Чужое", name_ru="Чужое", icon="🍕", original_language="ru",
    )
    with _patch_sub():
        with pytest.raises(ValueError):
            await set_limit(owner.telegram_id, foreign_cat.id, Decimal("1000"))


# --- get_limit_status: spent / percent --------------------------------------

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_status_spent_and_percent_floor(test_expense_category):
    profile = test_expense_category.profile
    with _patch_sub():
        await set_limit(profile.telegram_id, test_expense_category.id, Decimal("10000"))
    # 7250 / 10000 = 72.5% → floor 72
    await _create_expense(profile, test_expense_category, "7250", when=date.today())

    status = await get_limit_status(profile.telegram_id, test_expense_category.id)
    assert status is not None
    assert status.spent == Decimal("7250")
    assert status.percent == 72
    assert status.exceeded is False


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_status_none_when_no_limit(test_expense_category):
    profile = test_expense_category.profile
    status = await get_limit_status(profile.telegram_id, test_expense_category.id)
    assert status is None


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_status_exceeded(test_expense_category):
    profile = test_expense_category.profile
    with _patch_sub():
        await set_limit(profile.telegram_id, test_expense_category.id, Decimal("1000"))
    await _create_expense(profile, test_expense_category, "1200", when=date.today())

    status = await get_limit_status(profile.telegram_id, test_expense_category.id)
    assert status.exceeded is True
    assert status.percent == 120


# --- crossed_thresholds -----------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_crossed_100_category(test_expense_category):
    """Категорийный лимит: трата, пересекающая 100%, даёт crossed=[100]."""
    profile = test_expense_category.profile
    with _patch_sub():
        await set_limit(profile.telegram_id, test_expense_category.id, Decimal("1000"))
    await _create_expense(profile, test_expense_category, "600", when=date.today())  # 60%
    crossing = await _create_expense(profile, test_expense_category, "500", when=date.today())  # 110%

    status = await get_limit_status(profile.telegram_id, test_expense_category.id, expense=crossing)
    assert status.crossed_thresholds == [100]


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_category_no_80_threshold(test_expense_category):
    """Категорийный лимит НЕ имеет порога 80% — только 100%."""
    profile = test_expense_category.profile
    with _patch_sub():
        await set_limit(profile.telegram_id, test_expense_category.id, Decimal("1000"))
    crossing = await _create_expense(profile, test_expense_category, "850", when=date.today())  # 85%

    status = await get_limit_status(profile.telegram_id, test_expense_category.id, expense=crossing)
    assert status.crossed_thresholds == []


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_crossed_80_total(test_expense_category):
    """Общий лимит: трата, пересекающая 80%, даёт crossed=[80]."""
    profile = test_expense_category.profile
    with _patch_sub():
        await set_limit(profile.telegram_id, None, Decimal("10000"))
    await _create_expense(profile, test_expense_category, "5000", when=date.today())  # 50%
    crossing = await _create_expense(profile, test_expense_category, "3500", when=date.today())  # 85%

    status = await get_limit_status(profile.telegram_id, None, expense=crossing)
    assert status.crossed_thresholds == [80]


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_crossed_both_total_one_expense(test_expense_category):
    """Общий лимит: одна большая трата может пересечь сразу 80% и 100%."""
    profile = test_expense_category.profile
    with _patch_sub():
        await set_limit(profile.telegram_id, None, Decimal("10000"))
    crossing = await _create_expense(profile, test_expense_category, "11000", when=date.today())  # 110%

    status = await get_limit_status(profile.telegram_id, None, expense=crossing)
    assert status.crossed_thresholds == [80, 100]


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_backdated_expense_does_not_trigger(test_expense_category):
    """Трата задним числом за прошлый месяц не считается пересечением порога
    в текущем месяце (и не входит в spent текущего месяца)."""
    profile = test_expense_category.profile
    with _patch_sub():
        await set_limit(profile.telegram_id, test_expense_category.id, Decimal("1000"))
    # Текущий месяц: уже на 90%.
    await _create_expense(profile, test_expense_category, "900", when=date.today())
    # Трата задним числом за прошлый месяц.
    backdated = await _create_expense(profile, test_expense_category, "5000", when=_prev_month_day())

    status = await get_limit_status(profile.telegram_id, test_expense_category.id, expense=backdated)
    # spent текущего месяца не изменился (900), порог не пересечён этой тратой.
    assert status.spent == Decimal("900")
    assert status.crossed_thresholds == []


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_other_currency_excluded(test_expense_category):
    """Трата в другой валюте не влияет на лимит в валюте профиля."""
    profile = test_expense_category.profile
    with _patch_sub():
        await set_limit(profile.telegram_id, test_expense_category.id, Decimal("1000"))
    await _create_expense(profile, test_expense_category, "500", when=date.today())  # RUB, 50%
    usd_expense = await _create_expense(profile, test_expense_category, "900", when=date.today(), currency="USD")

    status = await get_limit_status(profile.telegram_id, test_expense_category.id, expense=usd_expense)
    # USD-трата не учитывается: spent остаётся 500 RUB.
    assert status.spent == Decimal("500")
    assert status.crossed_thresholds == []


# --- get_active_limits_map --------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_expense_message_shows_percent(test_expense_category):
    """В подтверждении траты после названия категории появляется процент лимита."""
    from bot.utils.expense_messages import format_expense_added_message
    profile = test_expense_category.profile
    with _patch_sub():
        await set_limit(profile.telegram_id, test_expense_category.id, Decimal("10000"))
    expense = await _create_expense(profile, test_expense_category, "7250", when=date.today())
    # profile должен быть подгружен (как в реальном роутере).
    expense = await sync_to_async(
        Expense.objects.select_related('profile', 'category').get
    )(id=expense.id)

    message = await format_expense_added_message(
        expense=expense, category=test_expense_category, lang='ru'
    )
    assert "(72%)" in message


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_expense_message_no_percent_without_limit(test_expense_category):
    """Без лимита процент не добавляется."""
    from bot.utils.expense_messages import format_expense_added_message
    profile = test_expense_category.profile
    expense = await _create_expense(profile, test_expense_category, "500", when=date.today())
    expense = await sync_to_async(
        Expense.objects.select_related('profile', 'category').get
    )(id=expense.id)

    message = await format_expense_added_message(
        expense=expense, category=test_expense_category, lang='ru'
    )
    assert "%)" not in message


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_expense_message_exceeded_marker(test_expense_category):
    """При превышении лимита процент дополняется маркером 🔴."""
    from bot.utils.expense_messages import format_expense_added_message
    profile = test_expense_category.profile
    with _patch_sub():
        await set_limit(profile.telegram_id, test_expense_category.id, Decimal("1000"))
    expense = await _create_expense(profile, test_expense_category, "1200", when=date.today())
    expense = await sync_to_async(
        Expense.objects.select_related('profile', 'category').get
    )(id=expense.id)

    message = await format_expense_added_message(
        expense=expense, category=test_expense_category, lang='ru'
    )
    assert "(120% 🔴)" in message


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_active_limits_map(test_expense_category):
    profile = test_expense_category.profile
    with _patch_sub():
        await set_limit(profile.telegram_id, test_expense_category.id, Decimal("3000"))
        await set_limit(profile.telegram_id, None, Decimal("50000"))

    limits = await get_active_limits_map(profile.telegram_id)
    assert set(limits.keys()) == {test_expense_category.id, None}
    assert limits[test_expense_category.id].amount == Decimal("3000")
    assert limits[None].amount == Decimal("50000")


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_expense_limit_statuses_calculates_category_and_total_together(
    test_expense_category,
):
    profile = test_expense_category.profile
    with _patch_sub():
        await set_limit(profile.telegram_id, test_expense_category.id, Decimal("1000"))
        await set_limit(profile.telegram_id, None, Decimal("1000"))

    crossing = await _create_expense(
        profile, test_expense_category, "1100", when=date.today()
    )
    statuses = await get_expense_limit_statuses(profile.telegram_id, crossing)

    assert set(statuses) == {test_expense_category.id, None}
    assert statuses[test_expense_category.id].crossed_thresholds == [100]
    assert statuses[None].crossed_thresholds == [80, 100]


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_alert_messages_send_category_and_highest_total_threshold(
    test_expense_category,
):
    profile = test_expense_category.profile
    with _patch_sub():
        await set_limit(profile.telegram_id, test_expense_category.id, Decimal("1000"))
        await set_limit(profile.telegram_id, None, Decimal("1000"))

    crossing = await _create_expense(
        profile, test_expense_category, "1100", when=date.today()
    )
    messages = await get_expense_limit_alert_messages(
        profile.telegram_id,
        crossing,
        category=test_expense_category,
        lang="ru",
    )

    assert len(messages) == 2
    assert "Превышен лимит!" in messages[0]
    assert "Превышен общий лимит трат!" in messages[1]
    assert "Достигнуто 80% лимита трат" not in "\n".join(messages)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_alert_messages_send_total_80_threshold(test_expense_category):
    profile = test_expense_category.profile
    with _patch_sub():
        await set_limit(profile.telegram_id, None, Decimal("1000"))

    crossing = await _create_expense(
        profile, test_expense_category, "850", when=date.today()
    )
    messages = await get_expense_limit_alert_messages(
        profile.telegram_id,
        crossing,
        category=test_expense_category,
        lang="ru",
    )

    assert len(messages) == 1
    assert "Достигнуто 80% лимита трат" in messages[0]
    assert "Осталось:" in messages[0]


@pytest.mark.asyncio
async def test_send_expense_limit_alerts_does_not_break_on_telegram_error():
    bot = AsyncMock()
    bot.send_message.side_effect = RuntimeError("telegram unavailable")
    expense = type(
        "ExpenseStub",
        (),
        {"profile": type("ProfileStub", (), {"telegram_id": 123456789})()},
    )()

    with patch(
        "bot.utils.budget_notifications.get_expense_limit_alert_messages",
        AsyncMock(return_value=["alert"]),
    ):
        sent = await send_expense_limit_alerts(
            bot, 123456789, expense, category=None, lang="ru"
        )

    assert sent == 0
    bot.send_message.assert_awaited_once_with(
        chat_id=123456789,
        text="alert",
        parse_mode="HTML",
    )


def test_budget_is_registered_in_admin():
    from django.contrib import admin

    assert Budget in admin.site._registry
