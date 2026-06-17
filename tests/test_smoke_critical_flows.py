from calendar import monthrange
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.routers import recurring as recurring_router
from bot.routers import reports as reports_router
from bot.routers import start as start_router


def make_state(user_id: int = 123456789, chat_id: int = 123456789, bot_id: int = 42) -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=bot_id, chat_id=chat_id, user_id=user_id)
    return FSMContext(storage=storage, key=key)


def make_message(bot: AsyncMock | None = None):
    bot = bot or AsyncMock()
    message = AsyncMock()
    message.bot = bot
    message.from_user = SimpleNamespace(id=123456789, language_code="ru")
    message.chat = SimpleNamespace(id=123456789, type="private")
    message.text = "/start"
    message.message_id = 101
    message.answer = AsyncMock()
    return message


def make_callback(bot: AsyncMock | None = None):
    bot = bot or AsyncMock()
    callback = AsyncMock()
    callback.bot = bot
    callback.from_user = SimpleNamespace(id=123456789, language_code="ru")
    callback.answer = AsyncMock()
    callback.message = AsyncMock()
    callback.message.bot = bot
    callback.message.chat = SimpleNamespace(id=123456789)
    callback.message.message_id = 202
    callback.message.text = "privacy"
    callback.message.answer = AsyncMock()
    return callback


class DummyExistsQuery:
    def __init__(self, exists: bool):
        self.exists = exists

    async def aexists(self) -> bool:
        return self.exists


class DummySubscriptions:
    def __init__(self, existing_trial: bool = False, active_subscription: bool = False):
        self.existing_trial = existing_trial
        self.active_subscription = active_subscription

    def filter(self, **kwargs):
        if kwargs.get("type") == "trial":
            return DummyExistsQuery(self.existing_trial)
        if kwargs.get("is_active") is True:
            return DummyExistsQuery(self.active_subscription)
        return DummyExistsQuery(False)


class DummyProfile:
    def __init__(self, language_code: str = "ru", currency: str = "RUB"):
        self.language_code = language_code
        self.currency = currency
        self.accepted_privacy = False
        self.is_beta_tester = False
        self.subscriptions = DummySubscriptions()
        self.saved = False

    async def asave(self):
        self.saved = True


class DummyProfileFilter:
    def first(self):
        return None

    def exclude(self, **kwargs):
        return self

    def exists(self):
        return False


@pytest.mark.asyncio
async def test_cmd_start_for_new_user_requests_privacy_acceptance():
    message = make_message()
    state = make_state()

    with patch.object(start_router.Profile.objects, "aget", side_effect=start_router.Profile.DoesNotExist), patch(
        "bot.routers.start.get_privacy_url_for", return_value="https://example.com/privacy"
    ):
        await start_router.cmd_start(message, state)

    message.answer.assert_awaited_once()
    args, kwargs = message.answer.await_args
    keyboard = kwargs["reply_markup"]

    assert "privacy" in args[0].lower()
    assert kwargs["parse_mode"] == "HTML"
    assert keyboard.inline_keyboard[0][0].callback_data == "privacy_decline"
    assert keyboard.inline_keyboard[0][1].callback_data == "privacy_accept"

    state_data = await state.get_data()
    assert state_data["start_command_args"] is None
    assert state_data["pending_profile_data"]["telegram_id"] == 123456789
    assert state_data["pending_profile_data"]["language_code"] == "ru"


@pytest.mark.asyncio
async def test_privacy_accept_creates_profile_and_sends_welcome_message():
    callback = make_callback()
    state = make_state()
    profile = DummyProfile()

    await state.update_data(
        start_command_args=None,
        pending_profile_data={"telegram_id": 123456789, "language_code": "ru", "raw_language_code": "ru"},
    )

    with patch.object(start_router.Profile.objects, "aget", side_effect=start_router.Profile.DoesNotExist), patch(
        "bot.routers.start.get_or_create_profile", AsyncMock(return_value=profile)
    ), patch(
        "bot.routers.start.create_default_categories", AsyncMock()
    ) as create_categories, patch(
        "bot.routers.start.create_default_income_categories", AsyncMock()
    ) as create_income_categories, patch.object(
        start_router.Subscription.objects, "filter", return_value=DummyExistsQuery(False)
    ), patch.object(
        start_router.Subscription.objects, "acreate", AsyncMock()
    ) as create_trial, patch(
        "bot.routers.start.safe_delete_message", AsyncMock(return_value=True)
    ), patch(
        "bot.routers.start.update_user_commands", AsyncMock()
    ) as update_commands, patch(
        "bot.routers.start.get_welcome_message", return_value="WELCOME"
    ):
        await start_router.privacy_accept(callback, state)

    callback.answer.assert_any_await("Согласие принято")
    callback.message.answer.assert_awaited_once_with("WELCOME", parse_mode="HTML")
    create_categories.assert_awaited_once_with(123456789)
    create_income_categories.assert_awaited_once_with(123456789)
    create_trial.assert_awaited_once()
    update_commands.assert_awaited_once_with(callback.bot, 123456789)
    assert profile.accepted_privacy is True
    assert profile.saved is True

    state_data = await state.get_data()
    assert state_data["start_command_args"] is None
    assert state_data["pending_profile_data"] is None


@pytest.mark.asyncio
async def test_show_recurring_menu_renders_empty_state_menu():
    message = make_message()
    state = make_state()

    with patch("bot.routers.recurring.get_user_default_currency", AsyncMock(return_value="RUB")), patch(
        "bot.routers.recurring.get_user_recurring_payments", AsyncMock(return_value=[])
    ), patch(
        "bot.routers.recurring.send_message_with_cleanup", AsyncMock()
    ) as send_message, patch(
        "bot.routers.recurring.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ):
        await recurring_router.show_recurring_menu(message, state, lang="ru")

    send_message.assert_awaited_once()
    _, _, text = send_message.await_args.args[:3]
    keyboard = send_message.await_args.kwargs["reply_markup"]

    assert "recurring_payments" in text
    assert "no_recurring_payments" in text
    assert keyboard.inline_keyboard[0][0].callback_data == "add_recurring"
    assert keyboard.inline_keyboard[-1][0].callback_data == "close"


@pytest.mark.asyncio
async def test_show_recurring_menu_edits_callback_message():
    state = make_state()
    callback_message = AsyncMock()
    callback_message.message_id = 202
    callback_message.edit_text = AsyncMock()
    callback = types.CallbackQuery.model_construct(
        id="recurring-menu",
        from_user=SimpleNamespace(id=123456789, language_code="ru"),
        chat_instance="private",
        message=callback_message,
        data="recurring_menu",
    )

    with patch("bot.routers.recurring.get_user_default_currency", AsyncMock(return_value="RUB")), patch(
        "bot.routers.recurring.get_user_recurring_payments", AsyncMock(return_value=[])
    ), patch(
        "bot.routers.recurring.send_message_with_cleanup", AsyncMock()
    ) as send_message, patch(
        "bot.routers.recurring.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ):
        await recurring_router.show_recurring_menu(callback, state, lang="ru")

    send_message.assert_not_awaited()
    callback_message.edit_text.assert_awaited_once()
    _, kwargs = callback_message.edit_text.await_args
    assert "recurring_payments" in callback_message.edit_text.await_args.args[0]
    assert kwargs["parse_mode"] == "HTML"
    assert kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "add_recurring"

    state_data = await state.get_data()
    assert state_data["last_menu_message_id"] == 202


@pytest.mark.asyncio
async def test_show_expenses_summary_saves_period_and_sends_summary_message():
    message = make_message()
    state = make_state()
    today = date.today()
    summary = {
        "total": Decimal("1500"),
        "income_total": Decimal("0"),
        "balance": Decimal("-1500"),
        "currency": "RUB",
        "count": 1,
        "by_category": [{"name": "Food", "amounts": {"RUB": Decimal("1500")}}],
        "by_income_category": [],
        "potential_cashback": Decimal("0"),
    }
    fake_profile = SimpleNamespace(household=None, settings=SimpleNamespace(view_scope="personal"))

    with patch("bot.routers.reports.check_subscription", AsyncMock(return_value=True)), patch(
        "bot.routers.reports.get_expenses_summary", AsyncMock(return_value=summary)
    ), patch(
        "bot.routers.reports.send_message_with_cleanup", AsyncMock()
    ) as send_message, patch(
        "bot.routers.reports.expenses_summary_keyboard", return_value="KEYBOARD"
    ), patch(
        "bot.routers.reports.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ), patch(
        "bot.routers.reports.get_month_name", side_effect=lambda month, lang="ru": f"month-{month}"
    ), patch(
        "bot.routers.reports.format_amount", side_effect=lambda amount, currency, lang="ru": f"{amount} {currency}"
    ), patch(
        "expenses.models.Profile.objects.get", return_value=fake_profile
    ), patch(
        "expenses.models.Profile.objects.filter", return_value=DummyProfileFilter()
    ):
        await reports_router.show_expenses_summary(message, today, today, "ru", state=state)

    send_message.assert_awaited_once()
    _, _, text = send_message.await_args.args[:3]

    assert "summary" in text
    assert "expenses_label" in text
    assert "Food: 1500 RUB" in text
    assert send_message.await_args.kwargs["reply_markup"] == "KEYBOARD"

    state_data = await state.get_data()
    assert state_data["report_start_date"] == today.isoformat()
    assert state_data["report_end_date"] == today.isoformat()


@pytest.mark.asyncio
async def test_month_summary_renders_limits_in_their_currencies():
    message = make_message()
    state = make_state()
    today = date.today()
    start_date = today.replace(day=1)
    end_date = today.replace(day=monthrange(today.year, today.month)[1])
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)

    summary = {
        "total": Decimal("1500"),
        "income_total": Decimal("2000"),
        "income_currency_totals": {"RUB": Decimal("2000"), "USD": Decimal("500")},
        "balance": Decimal("500"),
        "currency": "RUB",
        "currency_totals": {"RUB": 1500.0, "USD": 800.0},
        "count": 2,
        "by_category": [
            {
                "id": 7,
                "name": "Food",
                "amounts": {"RUB": Decimal("900"), "USD": Decimal("300")},
            },
            {
                "id": 8,
                "name": "Travel",
                "amounts": {"USD": Decimal("500")},
            },
        ],
        "by_income_category": [
            {
                "id": 11,
                "name": "Salary",
                "total": Decimal("2000"),
                "amounts": {"RUB": Decimal("1700"), "USD": Decimal("300")},
            },
        ],
        "potential_cashback": Decimal("0"),
    }
    limits = {
        None: SimpleNamespace(
            amount=Decimal("1000"),
            currency="USD",
            start_date=start_date,
        ),
        7: SimpleNamespace(
            amount=Decimal("400"),
            currency="USD",
            start_date=start_date,
        ),
        8: SimpleNamespace(
            amount=Decimal("500"),
            currency="USD",
            start_date=next_month,
        ),
    }
    goals = {
        None: SimpleNamespace(
            amount=Decimal("1000"),
            currency="USD",
            start_date=start_date,
        ),
        11: SimpleNamespace(
            amount=Decimal("400"),
            currency="USD",
            start_date=start_date,
        ),
    }
    fake_profile = SimpleNamespace(household=None, settings=SimpleNamespace(view_scope="personal"))

    with patch("bot.routers.reports.check_subscription", AsyncMock(return_value=True)), patch(
        "bot.routers.reports.get_expenses_summary", AsyncMock(return_value=summary)
    ), patch(
        "bot.routers.reports.get_active_limits_map", AsyncMock(return_value=limits)
    ) as get_limits, patch(
        "bot.routers.reports.get_active_goals_map", AsyncMock(return_value=goals)
    ) as get_goals, patch(
        "bot.routers.reports.send_message_with_cleanup", AsyncMock()
    ) as send_message, patch(
        "bot.routers.reports.expenses_summary_keyboard", return_value="KEYBOARD"
    ), patch(
        "bot.routers.reports.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ), patch(
        "bot.routers.reports.get_month_name", side_effect=lambda month, lang="ru": f"month-{month}"
    ), patch(
        "bot.routers.reports.format_amount", side_effect=lambda amount, currency, lang="ru": f"{amount} {currency}"
    ), patch(
        "expenses.models.Profile.objects.get", return_value=fake_profile
    ), patch(
        "expenses.models.Profile.objects.filter", return_value=DummyProfileFilter()
    ):
        await reports_router.show_expenses_summary(
            message, start_date, end_date, "ru", state=state
        )

    get_limits.assert_awaited_once_with(message.from_user.id)
    get_goals.assert_awaited_once_with(message.from_user.id)
    _, _, text = send_message.await_args.args[:3]
    # Общий лимит и общая цель показываются шкалой (в «тонком» категорийном формате).
    assert reports_router.format_total_bar_line(80) in text
    assert reports_router.format_total_goal_bar_line(50) in text
    assert (
        f"💸 expenses_label: 1500 RUB\n{reports_router.format_total_bar_line(80)}\n\n"
        f"💰 income_label: 2000 RUB\n{reports_router.format_total_goal_bar_line(50)}"
    ) in text
    assert "balance_label" not in text
    assert "⚖️" not in text
    # Категорийные лимиты/цели теперь без шкалы — только процент в скобках.
    assert "(75%)" in text
