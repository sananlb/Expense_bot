import asyncio
from io import BytesIO
from contextlib import nullcontext
from datetime import date, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.routers import expense as expense_router
from bot.routers import reports as reports_router


class FakeQuerySet:
    def __init__(self, items):
        self._items = items

    def select_related(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def __getitem__(self, item):
        return self._items[item]


def immediate_sync_to_async(func):
    async def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


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
    message.text = "/expenses"
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
    callback.message.text = "reports"
    callback.message.edit_text = AsyncMock()
    callback.message.answer = AsyncMock()
    return callback


@pytest.mark.asyncio
async def test_cmd_expenses_delegates_to_reports_today_summary():
    message = make_message()
    state = make_state()
    today = date.today()

    with patch("bot.routers.reports.show_expenses_summary", AsyncMock()) as show_summary:
        await expense_router.cmd_expenses(message, state, lang="ru")

    show_summary.assert_awaited_once_with(
        message,
        today,
        today,
        "ru",
        state=state,
        edit=False,
    )


@pytest.mark.asyncio
async def test_show_month_expenses_delegates_to_reports_with_current_month_start():
    callback = make_callback()
    state = make_state()
    today = date.today()
    month_start = today.replace(day=1)

    with patch("bot.routers.reports.show_expenses_summary", AsyncMock()) as show_summary:
        await expense_router.show_month_expenses(callback, state, lang="ru")

    show_summary.assert_awaited_once_with(
        callback.message,
        month_start,
        today,
        "ru",
        state=state,
        edit=True,
        original_message=callback.message,
        callback=callback,
    )
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_callback_expenses_today_refreshes_today_summary():
    callback = make_callback()
    state = make_state()
    today = date.today()

    with patch("bot.routers.reports.show_expenses_summary", AsyncMock()) as show_summary:
        await reports_router.callback_expenses_today(callback, state, lang="ru")

    show_summary.assert_awaited_once_with(
        callback.message,
        today,
        today,
        "ru",
        state=state,
        edit=True,
        original_message=callback.message,
        callback=callback,
    )
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_callback_show_month_start_uses_full_current_month_range():
    callback = make_callback()
    state = make_state()
    today = date.today()
    month_start = today.replace(day=1)

    if today.month == 12:
        expected_end = date(today.year, 12, 31)
    else:
        expected_end = date(today.year, today.month + 1, 1).replace(day=1) - date.resolution

    with patch("bot.routers.reports.show_expenses_summary", AsyncMock()) as show_summary:
        await reports_router.callback_show_month_start(callback, state, lang="ru")

    show_summary.assert_awaited_once_with(
        callback.message,
        month_start,
        expected_end,
        "ru",
        state=state,
        edit=True,
        original_message=callback.message,
        callback=callback,
    )
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_show_prev_month_expenses_rolls_back_year_boundary():
    callback = make_callback()
    state = make_state()
    await state.update_data(current_month=1, current_year=2026)

    with patch("bot.routers.reports.show_expenses_summary", AsyncMock()) as show_summary:
        await expense_router.show_prev_month_expenses(callback, state, lang="ru")

    show_summary.assert_awaited_once_with(
        callback.message,
        date(2025, 12, 1),
        date(2025, 12, 31),
        "ru",
        state=state,
        edit=True,
        original_message=callback.message,
        callback=callback,
    )
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_show_next_month_expenses_rolls_forward_year_boundary():
    callback = make_callback()
    state = make_state()
    await state.update_data(current_month=12, current_year=2025)

    with patch("bot.routers.reports.show_expenses_summary", AsyncMock()) as show_summary:
        await expense_router.show_next_month_expenses(callback, state, lang="ru")

    show_summary.assert_awaited_once_with(
        callback.message,
        date(2026, 1, 1),
        date(2026, 1, 31),
        "ru",
        state=state,
        edit=True,
        original_message=callback.message,
        callback=callback,
    )
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_show_today_expenses_delegates_to_reports_today_summary():
    callback = make_callback()
    state = make_state()
    today = date.today()

    with patch("bot.routers.reports.show_expenses_summary", AsyncMock()) as show_summary:
        await expense_router.show_today_expenses(callback, state, lang="ru")

    show_summary.assert_awaited_once_with(
        callback.message,
        today,
        today,
        "ru",
        state=state,
        edit=True,
        original_message=callback.message,
        callback=callback,
    )
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_toggle_view_scope_expenses_switches_setting_and_refreshes_summary():
    callback = make_callback()
    state = make_state()
    await state.update_data(
        report_start_date="2026-03-01",
        report_end_date="2026-03-16",
    )

    class DummySettings:
        def __init__(self):
            self.view_scope = "personal"
            self.saved = False

        def save(self):
            self.saved = True

    settings = DummySettings()
    profile = SimpleNamespace(household_id=11, settings=settings)

    with patch("bot.routers.reports.show_expenses_summary", AsyncMock()) as show_summary, patch(
        "expenses.models.Profile.objects.get", return_value=profile
    ), patch(
        "bot.routers.reports.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ):
        await reports_router.toggle_view_scope_expenses(callback, state, lang="ru")

    assert settings.view_scope == "household"
    assert settings.saved is True
    show_summary.assert_awaited_once_with(
        callback.message,
        date(2026, 3, 1),
        date(2026, 3, 16),
        "ru",
        state=state,
        edit=True,
        original_message=callback.message,
        callback=callback,
    )
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_toggle_view_scope_expenses_rejects_users_without_household():
    callback = make_callback()
    state = make_state()
    profile = SimpleNamespace(household_id=None)

    with patch("bot.routers.reports.show_expenses_summary", AsyncMock()) as show_summary, patch(
        "expenses.models.Profile.objects.get", return_value=profile
    ):
        await reports_router.toggle_view_scope_expenses(callback, state, lang="ru")

    show_summary.assert_not_awaited()
    callback.answer.assert_awaited_once_with("Нет семейного бюджета", show_alert=True)


@pytest.mark.asyncio
async def test_callback_back_to_summary_uses_saved_dates_from_state():
    callback = make_callback()
    state = make_state()
    await state.update_data(
        report_start_date="2026-02-01",
        report_end_date="2026-02-28",
    )

    with patch("bot.routers.reports.show_expenses_summary", AsyncMock()) as show_summary:
        await reports_router.callback_back_to_summary(callback, state, lang="ru")

    show_summary.assert_awaited_once_with(
        callback.message,
        date(2026, 2, 1),
        date(2026, 2, 28),
        "ru",
        state=state,
        edit=True,
        original_message=callback.message,
        callback=callback,
    )
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_callback_back_to_summary_falls_back_to_current_month_when_state_is_empty():
    callback = make_callback()
    state = make_state()
    today = date.today()
    month_start = today.replace(day=1)

    with patch("bot.routers.reports.show_expenses_summary", AsyncMock()) as show_summary:
        await reports_router.callback_back_to_summary(callback, state, lang="ru")

    show_summary.assert_awaited_once_with(
        callback.message,
        month_start,
        today,
        "ru",
        state=state,
        edit=True,
        original_message=callback.message,
        callback=callback,
    )
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_callback_select_month_uses_previous_year_for_future_month_number():
    callback = make_callback()
    state = make_state()
    today = date.today()
    selected_month = 12 if today.month != 12 else 11
    callback.data = f"month_{selected_month}"
    expected_year = today.year - 1 if selected_month > today.month else today.year

    if selected_month == 12:
        expected_end = date(expected_year, 12, 31)
    else:
        expected_end = date(expected_year, selected_month + 1, 1) - date.resolution

    with patch("bot.routers.reports.show_expenses_summary", AsyncMock()) as show_summary:
        await reports_router.callback_select_month(callback, state, lang="ru")

    show_summary.assert_awaited_once_with(
        callback.message,
        date(expected_year, selected_month, 1),
        expected_end,
        "ru",
        state=state,
        edit=True,
        original_message=callback.message,
        callback=callback,
    )
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_callback_show_diary_renders_empty_personal_diary_without_scope_toggle():
    callback = make_callback()
    state = make_state()
    callback.data = "show_diary"
    profile = SimpleNamespace(currency="USD", timezone="UTC", household=None)
    settings = SimpleNamespace(view_scope="personal")

    with patch("asgiref.sync.sync_to_async", side_effect=immediate_sync_to_async), patch(
        "pytz.timezone", return_value=timezone.utc
    ), patch(
        "expenses.models.Profile.objects.get", return_value=profile
    ), patch(
        "expenses.models.Expense.objects.filter", return_value=FakeQuerySet([])
    ), patch(
        "expenses.models.Income.objects.filter", return_value=FakeQuerySet([])
    ), patch(
        "bot.services.profile.get_user_settings", SimpleNamespace(__wrapped__=lambda _uid: settings)
    ), patch(
        "bot.services.subscription.check_subscription", AsyncMock(return_value=False)
    ), patch(
        "bot.routers.reports.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ):
        await reports_router.callback_show_diary(callback, state, lang="ru")

    callback.message.edit_text.assert_awaited_once()
    edit_text_args = callback.message.edit_text.await_args
    assert "📋 <b>diary</b>" in edit_text_args.args[0]
    assert "no_operations" in edit_text_args.args[0]
    keyboard = edit_text_args.kwargs["reply_markup"]
    button_texts = [button.text for row in keyboard.inline_keyboard for button in row]
    assert button_texts == ["top5_button", "back_button", "close"]
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_callback_show_diary_renders_empty_household_diary_with_scope_toggle():
    callback = make_callback()
    state = make_state()
    callback.data = "show_diary"
    profile = SimpleNamespace(currency="USD", timezone="UTC", household=SimpleNamespace(id=1))
    settings = SimpleNamespace(view_scope="household")

    with patch("asgiref.sync.sync_to_async", side_effect=immediate_sync_to_async), patch(
        "pytz.timezone", return_value=timezone.utc
    ), patch(
        "expenses.models.Profile.objects.get", return_value=profile
    ), patch(
        "expenses.models.Expense.objects.filter", return_value=FakeQuerySet([])
    ), patch(
        "expenses.models.Income.objects.filter", return_value=FakeQuerySet([])
    ), patch(
        "bot.services.profile.get_user_settings", SimpleNamespace(__wrapped__=lambda _uid: settings)
    ), patch(
        "bot.services.subscription.check_subscription", AsyncMock(return_value=True)
    ), patch(
        "bot.routers.reports.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ):
        await reports_router.callback_show_diary(callback, state, lang="ru")

    callback.message.edit_text.assert_awaited_once()
    edit_text_args = callback.message.edit_text.await_args
    assert "📋 <b>diary (семейный)</b>" in edit_text_args.args[0]
    keyboard = edit_text_args.kwargs["reply_markup"]
    button_texts = [button.text for row in keyboard.inline_keyboard for button in row]
    assert button_texts == ["household_budget_button", "top5_button", "back_button", "close"]
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_toggle_view_scope_diary_rejects_users_without_household():
    callback = make_callback()
    state = make_state()
    callback.data = "toggle_view_scope_diary"
    profile_manager = Mock()
    profile_manager.select_for_update.return_value = profile_manager
    profile_manager.get.return_value = SimpleNamespace(household_id=None)

    with patch("asgiref.sync.sync_to_async", side_effect=immediate_sync_to_async), patch(
        "django.db.transaction.atomic", return_value=nullcontext()
    ), patch(
        "expenses.models.Profile.objects", profile_manager
    ):
        await reports_router.callback_show_diary(callback, state, lang="ru")

    callback.message.edit_text.assert_not_awaited()
    callback.answer.assert_awaited_once_with("Нет семейного бюджета", show_alert=True)


@pytest.mark.asyncio
async def test_toggle_view_scope_diary_switches_to_household_and_renders_diary():
    callback = make_callback()
    state = make_state()
    callback.data = "toggle_view_scope_diary"
    settings = SimpleNamespace(view_scope="personal", save=Mock())
    profile = SimpleNamespace(currency="USD", timezone="UTC", household_id=11, household=SimpleNamespace(id=11))
    profile_manager = Mock()
    profile_manager.select_for_update.return_value = profile_manager
    profile_manager.get.return_value = profile
    user_settings_manager = Mock()
    user_settings_manager.select_for_update.return_value = user_settings_manager
    user_settings_manager.get_or_create.return_value = (settings, False)

    with patch("asgiref.sync.sync_to_async", side_effect=immediate_sync_to_async), patch(
        "django.db.transaction.atomic", return_value=nullcontext()
    ), patch(
        "pytz.timezone", return_value=timezone.utc
    ), patch(
        "expenses.models.Profile.objects", profile_manager
    ), patch(
        "expenses.models.UserSettings.objects", user_settings_manager
    ), patch(
        "expenses.models.Expense.objects.filter", return_value=FakeQuerySet([])
    ), patch(
        "expenses.models.Income.objects.filter", return_value=FakeQuerySet([])
    ), patch(
        "bot.services.profile.get_user_settings", SimpleNamespace(__wrapped__=lambda _uid: settings)
    ), patch(
        "bot.services.subscription.check_subscription", AsyncMock(return_value=True)
    ), patch(
        "bot.routers.reports.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ):
        await reports_router.callback_show_diary(callback, state, lang="ru")

    assert settings.view_scope == "household"
    settings.save.assert_called_once()
    callback.message.edit_text.assert_awaited_once()
    edit_text_args = callback.message.edit_text.await_args
    assert "📋 <b>diary (семейный)</b>" in edit_text_args.args[0]
    keyboard = edit_text_args.kwargs["reply_markup"]
    button_texts = [button.text for row in keyboard.inline_keyboard for button in row]
    assert button_texts == ["household_budget_button", "top5_button", "back_button", "close"]
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_callback_export_month_csv_requires_subscription_before_generation():
    callback = make_callback()
    state = make_state()
    await state.update_data(report_start_date="2026-03-01", report_end_date="2026-03-31")
    premium_button = object()

    with patch("bot.routers.reports.check_subscription", AsyncMock(return_value=False)), patch(
        "bot.routers.reports.get_subscription_button", return_value=premium_button
    ), patch(
        "bot.routers.reports.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ):
        await reports_router.callback_export_month_csv(callback, state, lang="ru")

    callback.answer.assert_awaited_once_with()
    callback.message.answer.assert_awaited_once_with(
        "export_premium_required",
        reply_markup=premium_button,
        parse_mode="HTML",
    )


@pytest.mark.asyncio
async def test_callback_export_month_excel_requires_subscription_before_generation():
    callback = make_callback()
    state = make_state()
    await state.update_data(report_start_date="2026-03-01", report_end_date="2026-03-31")
    premium_button = object()

    with patch("bot.routers.reports.check_subscription", AsyncMock(return_value=False)), patch(
        "bot.routers.reports.get_subscription_button", return_value=premium_button
    ), patch(
        "bot.routers.reports.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ):
        await reports_router.callback_export_month_excel(callback, state, lang="ru")

    callback.answer.assert_awaited_once_with()
    callback.message.answer.assert_awaited_once_with(
        "export_premium_required",
        reply_markup=premium_button,
        parse_mode="HTML",
    )


@pytest.mark.asyncio
async def test_callback_export_month_csv_shows_error_when_report_period_is_missing():
    callback = make_callback()
    state = make_state()

    with patch("bot.routers.reports.check_subscription", AsyncMock(return_value=True)), patch(
        "bot.routers.reports.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ):
        await reports_router.callback_export_month_csv(callback, state, lang="ru")

    callback.answer.assert_awaited_once_with("export_generating", show_alert=False)
    callback.message.answer.assert_awaited_once_with(
        "export_error",
        parse_mode="HTML",
    )


@pytest.mark.asyncio
async def test_callback_export_month_excel_shows_error_when_report_period_is_missing():
    callback = make_callback()
    state = make_state()

    with patch("bot.routers.reports.check_subscription", AsyncMock(return_value=True)), patch(
        "bot.routers.reports.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ):
        await reports_router.callback_export_month_excel(callback, state, lang="ru")

    callback.answer.assert_awaited_once_with("export_generating", show_alert=False)
    callback.message.answer.assert_awaited_once_with(
        "export_error",
        parse_mode="HTML",
    )


@pytest.mark.asyncio
async def test_callback_monthly_report_pdf_rejects_duplicate_generation_lock():
    callback = make_callback()
    callback.data = "monthly_report_pdf_2026_3"

    with patch("bot.routers.reports.cache.get", return_value=True), patch(
        "bot.routers.reports.cache.set"
    ) as cache_set:
        await reports_router.callback_monthly_report_pdf(callback, state=make_state(), lang="ru")

    callback.answer.assert_awaited_once_with(
        "⏳ PDF уже генерируется для этого периода. Пожалуйста, подождите...",
        show_alert=True,
    )
    callback.message.answer.assert_not_awaited()
    cache_set.assert_not_called()


@pytest.mark.asyncio
async def test_callback_monthly_report_csv_shows_empty_message_for_empty_month():
    callback = make_callback()
    callback.data = "monthly_report_csv_2026_3"
    profile = SimpleNamespace(household=None)
    settings = SimpleNamespace(view_scope="personal")
    expense_filter = Mock(return_value=FakeQuerySet([]))
    income_filter = Mock(return_value=FakeQuerySet([]))

    with patch("asgiref.sync.sync_to_async", side_effect=immediate_sync_to_async), patch(
        "expenses.models.Profile.objects.get", return_value=profile
    ), patch(
        "expenses.models.Expense.objects.filter", expense_filter
    ), patch(
        "expenses.models.Income.objects.filter", income_filter
    ), patch(
        "bot.services.profile.get_user_settings", SimpleNamespace(__wrapped__=lambda _uid: settings)
    ), patch(
        "bot.routers.reports.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ):
        await reports_router.callback_monthly_report_csv(callback, state=make_state(), lang="ru")

    callback.answer.assert_awaited_once_with("export_generating", show_alert=False)
    expense_filter.assert_called_once_with(
        profile__telegram_id=callback.from_user.id,
        expense_date__year=2026,
        expense_date__month=3,
    )
    income_filter.assert_called_once_with(
        profile__telegram_id=callback.from_user.id,
        income_date__year=2026,
        income_date__month=3,
    )
    callback.message.answer.assert_awaited_once_with("export_empty", parse_mode="HTML")
    callback.message.answer_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_callback_monthly_report_xlsx_shows_empty_message_for_empty_month():
    callback = make_callback()
    callback.data = "monthly_report_xlsx_2026_3"
    profile = SimpleNamespace(household=None)
    settings = SimpleNamespace(view_scope="personal")
    expense_filter = Mock(return_value=FakeQuerySet([]))
    income_filter = Mock(return_value=FakeQuerySet([]))

    with patch("asgiref.sync.sync_to_async", side_effect=immediate_sync_to_async), patch(
        "expenses.models.Profile.objects.get", return_value=profile
    ), patch(
        "expenses.models.Expense.objects.filter", expense_filter
    ), patch(
        "expenses.models.Income.objects.filter", income_filter
    ), patch(
        "bot.services.profile.get_user_settings", SimpleNamespace(__wrapped__=lambda _uid: settings)
    ), patch(
        "bot.routers.reports.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ):
        await reports_router.callback_monthly_report_xlsx(callback, state=make_state(), lang="ru")

    callback.answer.assert_awaited_once_with("export_generating", show_alert=False)
    expense_filter.assert_called_once_with(
        profile__telegram_id=callback.from_user.id,
        expense_date__year=2026,
        expense_date__month=3,
    )
    income_filter.assert_called_once_with(
        profile__telegram_id=callback.from_user.id,
        income_date__year=2026,
        income_date__month=3,
    )
    callback.message.answer.assert_awaited_once_with("export_empty", parse_mode="HTML")
    callback.message.answer_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_callback_monthly_report_csv_shows_timeout_message():
    callback = make_callback()
    callback.data = "monthly_report_csv_2026_3"
    profile = SimpleNamespace(household=None)
    settings = SimpleNamespace(view_scope="personal")

    async def raise_timeout(_awaitable, timeout=None):
        if hasattr(_awaitable, "close"):
            _awaitable.close()
        raise asyncio.TimeoutError

    with patch("asgiref.sync.sync_to_async", side_effect=immediate_sync_to_async), patch(
        "expenses.models.Profile.objects.get", return_value=profile
    ), patch(
        "expenses.models.Expense.objects.filter", return_value=FakeQuerySet([SimpleNamespace(id=1)])
    ), patch(
        "expenses.models.Income.objects.filter", return_value=FakeQuerySet([])
    ), patch(
        "bot.services.profile.get_user_settings", SimpleNamespace(__wrapped__=lambda _uid: settings)
    ), patch(
        "bot.routers.reports.asyncio.wait_for", side_effect=raise_timeout
    ), patch(
        "bot.routers.reports.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ):
        await reports_router.callback_monthly_report_csv(callback, state=make_state(), lang="ru")

    callback.answer.assert_awaited_once_with("export_generating", show_alert=False)
    callback.message.answer.assert_awaited_once_with(
        "❌ Превышено время ожидания при генерации отчета. Попробуйте позже.",
        parse_mode="HTML",
    )
    callback.message.answer_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_callback_monthly_report_xlsx_shows_timeout_message():
    callback = make_callback()
    callback.data = "monthly_report_xlsx_2026_3"
    profile = SimpleNamespace(household=None)
    settings = SimpleNamespace(view_scope="personal")

    async def raise_timeout(_awaitable, timeout=None):
        if hasattr(_awaitable, "close"):
            _awaitable.close()
        raise asyncio.TimeoutError

    with patch("asgiref.sync.sync_to_async", side_effect=immediate_sync_to_async), patch(
        "expenses.models.Profile.objects.get", return_value=profile
    ), patch(
        "expenses.models.Expense.objects.filter", return_value=FakeQuerySet([SimpleNamespace(id=1)])
    ), patch(
        "expenses.models.Income.objects.filter", return_value=FakeQuerySet([])
    ), patch(
        "bot.services.profile.get_user_settings", SimpleNamespace(__wrapped__=lambda _uid: settings)
    ), patch(
        "bot.routers.reports.asyncio.wait_for", side_effect=raise_timeout
    ), patch(
        "bot.routers.reports.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ):
        await reports_router.callback_monthly_report_xlsx(callback, state=make_state(), lang="ru")

    callback.answer.assert_awaited_once_with("export_generating", show_alert=False)
    callback.message.answer.assert_awaited_once_with(
        "❌ Превышено время ожидания при генерации отчета. Попробуйте позже.",
        parse_mode="HTML",
    )
    callback.message.answer_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_callback_monthly_report_csv_sends_generated_document():
    callback = make_callback()
    callback.data = "monthly_report_csv_2026_3"
    profile = SimpleNamespace(household=None)
    settings = SimpleNamespace(view_scope="personal")
    expense = SimpleNamespace(id=1)
    generated_csv = b"id,amount\n1,100\n"

    def fake_get_text(key, lang="ru", **kwargs):
        if key == "export_success":
            return "export_success {month}"
        return key

    with patch("asgiref.sync.sync_to_async", side_effect=immediate_sync_to_async), patch(
        "expenses.models.Profile.objects.get", return_value=profile
    ), patch(
        "expenses.models.Expense.objects.filter", return_value=FakeQuerySet([expense])
    ), patch(
        "expenses.models.Income.objects.filter", return_value=FakeQuerySet([])
    ), patch(
        "bot.services.profile.get_user_settings", SimpleNamespace(__wrapped__=lambda _uid: settings)
    ), patch(
        "bot.services.export_service.ExportService.generate_csv", return_value=generated_csv
    ) as generate_csv, patch(
        "bot.routers.reports.get_text", side_effect=fake_get_text
    ):
        await reports_router.callback_monthly_report_csv(callback, state=make_state(), lang="ru")

    generate_csv.assert_called_once_with([expense], [], 2026, 3, "ru", callback.from_user.id, False)
    callback.answer.assert_awaited_once_with("export_generating", show_alert=False)
    callback.message.answer.assert_not_awaited()
    callback.message.answer_document.assert_awaited_once()
    doc_call = callback.message.answer_document.await_args
    document = doc_call.args[0]
    assert document.filename == "coins_март_2026.csv"
    assert doc_call.kwargs["caption"].startswith("export_success март 2026")
    assert doc_call.kwargs["parse_mode"] == "HTML"


@pytest.mark.asyncio
async def test_callback_monthly_report_xlsx_sends_generated_document():
    callback = make_callback()
    callback.data = "monthly_report_xlsx_2026_3"
    profile = SimpleNamespace(household=None)
    settings = SimpleNamespace(view_scope="personal")
    income = SimpleNamespace(id=2)
    generated_xlsx = BytesIO(b"xlsx-bytes")

    def fake_get_text(key, lang="ru", **kwargs):
        if key == "export_success":
            return "export_success {month}"
        return key

    with patch("asgiref.sync.sync_to_async", side_effect=immediate_sync_to_async), patch(
        "expenses.models.Profile.objects.get", return_value=profile
    ), patch(
        "expenses.models.Expense.objects.filter", return_value=FakeQuerySet([])
    ), patch(
        "expenses.models.Income.objects.filter", return_value=FakeQuerySet([income])
    ), patch(
        "bot.services.profile.get_user_settings", SimpleNamespace(__wrapped__=lambda _uid: settings)
    ), patch(
        "bot.services.export_service.ExportService.generate_xlsx_with_charts", return_value=generated_xlsx
    ) as generate_xlsx, patch(
        "bot.routers.reports.get_text", side_effect=fake_get_text
    ):
        await reports_router.callback_monthly_report_xlsx(callback, state=make_state(), lang="ru")

    generate_xlsx.assert_called_once_with([], [income], 2026, 3, callback.from_user.id, "ru", False)
    callback.answer.assert_awaited_once_with("export_generating", show_alert=False)
    callback.message.answer.assert_not_awaited()
    callback.message.answer_document.assert_awaited_once()
    doc_call = callback.message.answer_document.await_args
    document = doc_call.args[0]
    assert document.filename == "coins_март_2026.xlsx"
    assert doc_call.kwargs["caption"].startswith("export_success март 2026")
    assert doc_call.kwargs["parse_mode"] == "HTML"


@pytest.mark.asyncio
async def test_callback_export_month_csv_sends_generated_document():
    callback = make_callback()
    state = make_state()
    await state.update_data(report_start_date="2026-03-01", report_end_date="2026-03-31")
    profile = SimpleNamespace(household=None)
    settings = SimpleNamespace(view_scope="personal")
    expense = SimpleNamespace(id=11)
    generated_csv = b"id,amount\n11,500\n"

    def fake_get_text(key, lang="ru", **kwargs):
        if key == "export_success":
            return "export_success {month}"
        return key

    with patch("bot.routers.reports.check_subscription", AsyncMock(return_value=True)), patch(
        "asgiref.sync.sync_to_async", side_effect=immediate_sync_to_async
    ), patch(
        "expenses.models.Profile.objects.get", return_value=profile
    ), patch(
        "expenses.models.Expense.objects.filter", return_value=FakeQuerySet([expense])
    ), patch(
        "expenses.models.Income.objects.filter", return_value=FakeQuerySet([])
    ), patch(
        "bot.services.profile.get_user_settings", SimpleNamespace(__wrapped__=lambda _uid: settings)
    ), patch(
        "bot.services.export_service.ExportService.generate_csv", return_value=generated_csv
    ) as generate_csv, patch(
        "bot.routers.reports.get_text", side_effect=fake_get_text
    ):
        await reports_router.callback_export_month_csv(callback, state, lang="ru")

    generate_csv.assert_called_once_with([expense], [], 2026, 3, "ru", callback.from_user.id, False)
    callback.answer.assert_awaited_once_with("export_generating", show_alert=False)
    callback.message.answer.assert_not_awaited()
    callback.message.answer_document.assert_awaited_once()
    doc_call = callback.message.answer_document.await_args
    document = doc_call.args[0]
    assert document.filename == "coins_март_2026.csv"
    assert doc_call.kwargs["caption"].startswith("export_success март 2026")
    assert doc_call.kwargs["parse_mode"] == "HTML"


@pytest.mark.asyncio
async def test_callback_export_month_excel_sends_generated_document():
    callback = make_callback()
    state = make_state()
    await state.update_data(report_start_date="2026-03-01", report_end_date="2026-03-31")
    profile = SimpleNamespace(household=None)
    settings = SimpleNamespace(view_scope="personal")
    income = SimpleNamespace(id=12)
    generated_xlsx = BytesIO(b"excel-bytes")

    def fake_get_text(key, lang="ru", **kwargs):
        if key == "export_success":
            return "export_success {month}"
        return key

    with patch("bot.routers.reports.check_subscription", AsyncMock(return_value=True)), patch(
        "asgiref.sync.sync_to_async", side_effect=immediate_sync_to_async
    ), patch(
        "expenses.models.Profile.objects.get", return_value=profile
    ), patch(
        "expenses.models.Expense.objects.filter", return_value=FakeQuerySet([])
    ), patch(
        "expenses.models.Income.objects.filter", return_value=FakeQuerySet([income])
    ), patch(
        "bot.services.profile.get_user_settings", SimpleNamespace(__wrapped__=lambda _uid: settings)
    ), patch(
        "bot.services.export_service.ExportService.generate_xlsx_with_charts", return_value=generated_xlsx
    ) as generate_xlsx, patch(
        "bot.routers.reports.get_text", side_effect=fake_get_text
    ):
        await reports_router.callback_export_month_excel(callback, state, lang="ru")

    generate_xlsx.assert_called_once_with([], [income], 2026, 3, callback.from_user.id, "ru", False)
    callback.answer.assert_awaited_once_with("export_generating", show_alert=False)
    callback.message.answer.assert_not_awaited()
    callback.message.answer_document.assert_awaited_once()
    doc_call = callback.message.answer_document.await_args
    document = doc_call.args[0]
    assert document.filename == "coins_март_2026.xlsx"
    assert doc_call.kwargs["caption"].startswith("export_success март 2026")
    assert doc_call.kwargs["parse_mode"] == "HTML"
