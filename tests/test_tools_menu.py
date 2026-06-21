"""Тесты меню «Инструменты» (/tools), разгрузки настроек и бесплатного кешбэка.

Покрывают изменения из TOOLS_MENU_IMPLEMENTATION_PLAN.md:
- новое меню tools_keyboard;
- очищенное settings_keyboard;
- команды бота (/tools вместо /cashback и /recurring);
- кешбэк рассчитывается независимо от UserSettings.cashback_enabled.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from asgiref.sync import sync_to_async

from bot.keyboards import settings_keyboard, tools_keyboard
from bot.utils.commands import set_bot_commands, update_user_commands


# --- helpers ----------------------------------------------------------------

def _callbacks(keyboard) -> list:
    """Собрать все callback_data кнопок клавиатуры в плоский список."""
    return [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
    ]


def _command_names(set_my_commands_mock) -> list:
    """Извлечь список command из вызова bot.set_my_commands(...).

    set_my_commands вызывается либо позиционно (commands первым аргументом),
    либо как kwarg commands=...  — поддерживаем оба варианта.
    """
    set_my_commands_mock.assert_awaited()
    call = set_my_commands_mock.await_args
    if "commands" in call.kwargs:
        commands = call.kwargs["commands"]
    else:
        commands = call.args[0]
    return [command.command for command in commands]


# --- 1. tools_keyboard ------------------------------------------------------

def test_tools_keyboard_has_all_entries():
    """Меню «Инструменты» содержит все запланированные пункты."""
    callbacks = _callbacks(tools_keyboard("ru", has_subscription=True))

    for expected in (
        "recurring_menu",
        "total_limit",
        "total_goal",
        "cashback_menu",
        "household_budget",
        "close",
    ):
        assert expected in callbacks, f"Нет кнопки {expected} в меню инструментов"


def test_tools_keyboard_hides_income_goal_without_subscription():
    """Без подписки цель дохода не показывается в меню инструментов."""
    callbacks = _callbacks(tools_keyboard("ru", has_subscription=False))

    assert "total_goal" not in callbacks
    assert "total_limit" in callbacks
    assert "cashback_menu" in callbacks


@pytest.mark.asyncio
async def test_tools_text_hides_active_income_goal_without_subscription(monkeypatch):
    """Без подписки цель дохода не показывается даже в блоке активных инструментов."""
    from bot.routers.tools import _tools_text

    monkeypatch.setattr(
        "bot.routers.tools._collect_active_tools",
        AsyncMock(return_value=["limit", "goal"]),
    )

    text = await _tools_text(123456789, "ru", has_subscription=False)

    assert "Лимит трат" in text
    assert "Цель дохода" not in text


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_cashback_is_active_only_when_configured_for_current_month(
    test_expense_category,
):
    """Кешбэк из прошлого месяца не должен отображаться как активный."""
    from bot.routers.tools import _collect_active_tools
    from expenses.models import Cashback

    profile = test_expense_category.profile
    current_month = date.today().month
    previous_month = 12 if current_month == 1 else current_month - 1

    await sync_to_async(Cashback.objects.create)(
        profile=profile,
        category=test_expense_category,
        bank_name="Прошлый банк",
        cashback_percent=Decimal("5"),
        month=previous_month,
    )

    assert "cashback" not in await _collect_active_tools(profile.telegram_id)

    await sync_to_async(Cashback.objects.create)(
        profile=profile,
        category=test_expense_category,
        bank_name="Текущий банк",
        cashback_percent=Decimal("5"),
        month=current_month,
    )

    assert "cashback" in await _collect_active_tools(profile.telegram_id)


# --- 2. settings_keyboard ---------------------------------------------------

def test_settings_keyboard_decluttered():
    """Из настроек убраны лимит/цель/семейный бюджет и кешбэк."""
    callbacks = _callbacks(settings_keyboard("ru"))

    for removed in (
        "total_limit",
        "total_goal",
        "household_budget",
        "toggle_cashback",
        "cashback_menu",
    ):
        assert removed not in callbacks, f"Кнопка {removed} не должна быть в настройках"


# --- 3. set_bot_commands ----------------------------------------------------

@pytest.mark.asyncio
async def test_bot_commands_have_tools_not_cashback_recurring():
    """Глобальные команды бота содержат /tools и не содержат /cashback, /recurring."""
    bot = AsyncMock()

    await set_bot_commands(bot)

    names = _command_names(bot.set_my_commands)
    assert "tools" in names
    assert "cashback" not in names
    assert "recurring" not in names


# --- 4. update_user_commands ------------------------------------------------

@pytest.mark.asyncio
async def test_update_user_commands_have_tools_not_cashback_recurring(monkeypatch):
    """Персональные команды пользователя содержат /tools и не содержат /cashback, /recurring.

    get_user_language импортируется внутри функции через `from bot.utils import ...`,
    поэтому патчим bot.utils.get_user_language. get_text не мокаем — он работает без БД.
    """
    monkeypatch.setattr(
        "bot.utils.get_user_language",
        AsyncMock(return_value="ru"),
    )
    bot = AsyncMock()

    await update_user_commands(bot, user_id=881292737)

    names = _command_names(bot.set_my_commands)
    assert "tools" in names
    assert "cashback" not in names
    assert "recurring" not in names


# --- 5. бесплатный кешбэк ---------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_free_cashback_ignores_cashback_enabled(test_expense_category):
    """cashback_enabled=False больше НЕ блокирует расчёт кешбэка.

    Раньше calculate_expense_cashback_sync возвращала 0 при выключенном кешбэке;
    теперь поле игнорируется и кешбэк считается всегда.
    """
    from bot.services.cashback import (
        calculate_expense_cashback,
        calculate_expense_cashback_sync,
    )
    from expenses.models import Cashback, UserSettings

    profile = test_expense_category.profile

    # Явно выключаем кешбэк в настройках — это не должно ни на что влиять.
    await sync_to_async(UserSettings.objects.create)(
        profile=profile,
        cashback_enabled=False,
    )

    month = date.today().month
    await sync_to_async(Cashback.objects.create)(
        profile=profile,
        category=test_expense_category,
        bank_name="Тест-банк",
        cashback_percent=Decimal("5"),
        month=month,
    )

    amount = Decimal("1000")
    expected = amount * Decimal("5") / Decimal("100")  # 50.00

    # Синхронная версия.
    result_sync = await sync_to_async(calculate_expense_cashback_sync)(
        profile.telegram_id,
        test_expense_category.id,
        amount,
        month,
    )
    assert result_sync > 0
    assert result_sync == expected

    # Асинхронная обёртка должна давать тот же результат.
    result_async = await calculate_expense_cashback(
        profile.telegram_id,
        test_expense_category.id,
        amount,
        month,
    )
    assert result_async == expected
