from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.routers import expense as expense_router


def make_state(user_id: int = 123456789, chat_id: int = 123456789, bot_id: int = 42) -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=bot_id, chat_id=chat_id, user_id=user_id)
    return FSMContext(storage=storage, key=key)


def make_callback():
    bot = AsyncMock()
    callback = AsyncMock()
    callback.bot = bot
    callback.from_user = SimpleNamespace(id=123456789, language_code="ru")
    callback.answer = AsyncMock()
    callback.message = AsyncMock()
    callback.message.bot = bot
    callback.message.chat = SimpleNamespace(id=123456789)
    callback.message.message_id = 202
    callback.message.text = "expense"
    callback.message.edit_text = AsyncMock()
    return callback


@pytest.mark.asyncio
async def test_cancel_expense_input_clears_state_and_deletes_clarification_message():
    callback = make_callback()
    state = make_state()
    await state.update_data(clarification_message_id=555)

    with patch("bot.utils.state_utils.clear_state_keep_cashback", AsyncMock()) as clear_state, patch(
        "bot.routers.expense.safe_delete_message", AsyncMock()
    ) as safe_delete:
        await expense_router.cancel_expense_input(callback, state)

    clear_state.assert_awaited_once_with(state)
    safe_delete.assert_awaited_once_with(
        bot=callback.bot,
        chat_id=callback.from_user.id,
        message_id=555,
    )
    callback.answer.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_cancel_expense_input_skips_delete_when_no_clarification_message():
    callback = make_callback()
    state = make_state()

    with patch("bot.utils.state_utils.clear_state_keep_cashback", AsyncMock()) as clear_state, patch(
        "bot.routers.expense.safe_delete_message", AsyncMock()
    ) as safe_delete:
        await expense_router.cancel_expense_input(callback, state)

    clear_state.assert_awaited_once_with(state)
    safe_delete.assert_not_awaited()
    callback.answer.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_edit_expense_shows_alert_when_expense_is_missing():
    callback = make_callback()
    callback.data = "edit_expense_77"
    state = make_state()
    missing_error = type("ExpenseDoesNotExist", (Exception,), {})
    expense_model = SimpleNamespace(
        DoesNotExist=missing_error,
        objects=SimpleNamespace(
            select_related=Mock(
                return_value=SimpleNamespace(aget=AsyncMock(side_effect=missing_error()))
            )
        ),
    )

    with patch("bot.utils.language.get_user_language", AsyncMock(return_value="ru")), patch(
        "expenses.models.Expense", expense_model
    ), patch(
        "bot.routers.expense.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ), patch(
        "bot.utils.state_utils.clear_state_keep_cashback", AsyncMock()
    ) as clear_state:
        await expense_router.edit_expense(callback, state)

    callback.answer.assert_awaited_once_with("expense_not_found", show_alert=True)
    callback.message.edit_text.assert_not_awaited()
    clear_state.assert_awaited_once_with(state)


@pytest.mark.asyncio
async def test_edit_expense_shows_alert_when_income_is_missing():
    callback = make_callback()
    callback.data = "edit_income_88"
    state = make_state()
    missing_error = type("IncomeDoesNotExist", (Exception,), {})
    income_model = SimpleNamespace(
        DoesNotExist=missing_error,
        objects=SimpleNamespace(
            select_related=Mock(
                return_value=SimpleNamespace(aget=AsyncMock(side_effect=missing_error()))
            )
        ),
    )

    with patch("bot.utils.language.get_user_language", AsyncMock(return_value="ru")), patch(
        "expenses.models.Income", income_model
    ), patch(
        "bot.routers.expense.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ), patch(
        "bot.utils.state_utils.clear_state_keep_cashback", AsyncMock()
    ) as clear_state:
        await expense_router.edit_expense(callback, state)

    callback.answer.assert_awaited_once_with("income_not_found", show_alert=True)
    callback.message.edit_text.assert_not_awaited()
    clear_state.assert_awaited_once_with(state)


@pytest.mark.asyncio
async def test_edit_expense_renders_expense_edit_menu_and_sets_state():
    callback = make_callback()
    callback.data = "edit_expense_89"
    state = make_state()
    expense = SimpleNamespace(
        id=89,
        amount=700,
        description="lunch",
        category=SimpleNamespace(id=3),
        currency="RUB",
        cashback_excluded=False,
    )
    expense_model = SimpleNamespace(
        DoesNotExist=type("ExpenseDoesNotExist", (Exception,), {}),
        objects=SimpleNamespace(
            select_related=Mock(return_value=SimpleNamespace(aget=AsyncMock(return_value=expense)))
        ),
    )

    with patch("bot.utils.language.get_user_language", AsyncMock(return_value="ru")), patch(
        "expenses.models.Expense", expense_model
    ), patch(
        "bot.services.profile.get_or_create_profile", AsyncMock(return_value=SimpleNamespace(currency="RUB"))
    ), patch(
        "bot.services.cashback.calculate_expense_cashback", AsyncMock(return_value=0)
    ), patch(
        "bot.routers.expense.get_category_display_name", return_value="Food"
    ), patch(
        "bot.routers.expense.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ):
        await expense_router.edit_expense(callback, state)

    callback.message.edit_text.assert_awaited_once()
    edit_args = callback.message.edit_text.await_args
    assert "editing_expense" in edit_args.args[0]
    keyboard = edit_args.kwargs["reply_markup"]
    assert keyboard.inline_keyboard[0][0].callback_data == "edit_field_amount_expense_89"
    assert keyboard.inline_keyboard[1][0].callback_data == "edit_field_description_expense_89"
    assert keyboard.inline_keyboard[2][0].callback_data == "edit_field_category_expense_89"
    assert keyboard.inline_keyboard[3][0].callback_data == "delete_expense_89"
    assert keyboard.inline_keyboard[4][0].callback_data == "edit_done_expense_89"
    data = await state.get_data()
    assert data["editing_expense_id"] == 89
    assert data["editing_type"] == "expense"
    assert await state.get_state() == expense_router.EditExpenseForm.choosing_field.state
    callback.answer.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_edit_expense_renders_income_edit_menu_and_sets_state():
    callback = make_callback()
    callback.data = "edit_income_90"
    state = make_state()
    income = SimpleNamespace(
        id=90,
        amount=1500,
        description="salary",
        category=None,
        currency="USD",
        cashback_excluded=False,
    )
    income_model = SimpleNamespace(
        DoesNotExist=type("IncomeDoesNotExist", (Exception,), {}),
        objects=SimpleNamespace(
            select_related=Mock(return_value=SimpleNamespace(aget=AsyncMock(return_value=income)))
        ),
    )

    with patch("bot.utils.language.get_user_language", AsyncMock(return_value="ru")), patch(
        "expenses.models.Income", income_model
    ), patch(
        "bot.routers.expense.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ):
        await expense_router.edit_expense(callback, state)

    callback.message.edit_text.assert_awaited_once()
    edit_args = callback.message.edit_text.await_args
    assert "editing_income" in edit_args.args[0]
    keyboard = edit_args.kwargs["reply_markup"]
    assert keyboard.inline_keyboard[0][0].callback_data == "edit_field_amount_income_90"
    assert keyboard.inline_keyboard[1][0].callback_data == "edit_field_description_income_90"
    assert keyboard.inline_keyboard[2][0].callback_data == "edit_field_category_income_90"
    assert keyboard.inline_keyboard[3][0].callback_data == "delete_income_90"
    assert keyboard.inline_keyboard[4][0].callback_data == "edit_done_income_90"
    data = await state.get_data()
    assert data["editing_expense_id"] == 90
    assert data["editing_type"] == "income"
    assert await state.get_state() == expense_router.EditExpenseForm.choosing_field.state
    callback.answer.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_remove_cashback_updates_expense_card_and_clears_state():
    callback = make_callback()
    callback.data = "remove_cashback_91"
    state = make_state()
    expense = SimpleNamespace(
        id=91,
        category=SimpleNamespace(id=4),
        profile=SimpleNamespace(currency="RUB"),
        cashback_excluded=False,
        asave=AsyncMock(),
    )
    expense_model = SimpleNamespace(
        DoesNotExist=type("ExpenseDoesNotExist", (Exception,), {}),
        objects=SimpleNamespace(
            select_related=Mock(return_value=SimpleNamespace(aget=AsyncMock(return_value=expense)))
        ),
    )

    with patch("expenses.models.Expense", expense_model), patch(
        "bot.utils.expense_messages.format_expense_added_message", AsyncMock(return_value="expense-without-cashback")
    ) as format_message, patch(
        "bot.utils.state_utils.clear_state_keep_cashback", AsyncMock()
    ) as clear_state, patch(
        "bot.routers.expense.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ):
        await expense_router.remove_cashback(callback, state, lang="ru")

    assert expense.cashback_excluded is True
    expense.asave.assert_awaited_once_with()
    format_message.assert_awaited_once_with(
        expense=expense,
        category=expense.category,
        cashback_text="",
        lang="ru",
    )
    callback.message.edit_text.assert_awaited_once()
    edit_args = callback.message.edit_text.await_args
    assert edit_args.args[0] == "expense-without-cashback"
    keyboard = edit_args.kwargs["reply_markup"]
    assert keyboard.inline_keyboard[0][0].callback_data == "edit_expense_91"
    assert edit_args.kwargs["parse_mode"] == "HTML"
    clear_state.assert_awaited_once_with(state)
    callback.answer.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_remove_cashback_reports_missing_expense():
    callback = make_callback()
    callback.data = "remove_cashback_92"
    state = make_state()
    missing_error = type("ExpenseDoesNotExist", (Exception,), {})
    expense_model = SimpleNamespace(
        DoesNotExist=missing_error,
        objects=SimpleNamespace(
            select_related=Mock(return_value=SimpleNamespace(aget=AsyncMock(side_effect=missing_error())))
        ),
    )

    with patch("expenses.models.Expense", expense_model):
        await expense_router.remove_cashback(callback, state, lang="ru")

    callback.message.edit_text.assert_not_awaited()
    callback.answer.assert_awaited_once_with("❌ Трата не найдена", show_alert=True)


@pytest.mark.asyncio
async def test_remove_cashback_reports_generic_error():
    callback = make_callback()
    callback.data = "remove_cashback_93"
    state = make_state()
    expense = SimpleNamespace(
        id=93,
        category=None,
        profile=SimpleNamespace(currency="RUB"),
        cashback_excluded=False,
        asave=AsyncMock(side_effect=RuntimeError("db-error")),
    )
    expense_model = SimpleNamespace(
        DoesNotExist=type("ExpenseDoesNotExist", (Exception,), {}),
        objects=SimpleNamespace(
            select_related=Mock(return_value=SimpleNamespace(aget=AsyncMock(return_value=expense)))
        ),
    )

    with patch("expenses.models.Expense", expense_model):
        await expense_router.remove_cashback(callback, state, lang="ru")

    callback.message.edit_text.assert_not_awaited()
    callback.answer.assert_awaited_once_with("❌ Ошибка при удалении кешбека", show_alert=True)


@pytest.mark.asyncio
async def test_delete_expense_success_edits_message_and_clears_state():
    callback = make_callback()
    callback.data = "delete_expense_91"
    state = make_state()

    with patch("bot.utils.language.get_user_language", AsyncMock(return_value="ru")), patch(
        "bot.utils.language.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ), patch(
        "bot.services.expense.delete_expense", AsyncMock(return_value=True)
    ), patch(
        "bot.utils.state_utils.clear_state_keep_cashback", AsyncMock()
    ) as clear_state:
        await expense_router.delete_expense(callback, state)

    callback.message.edit_text.assert_awaited_once_with("expense_deleted_message", reply_markup=None)
    callback.answer.assert_awaited_once_with("expense_deleted_success")
    clear_state.assert_awaited_once_with(state)


@pytest.mark.asyncio
async def test_delete_income_success_edits_message_and_clears_state():
    callback = make_callback()
    callback.data = "delete_income_92"
    state = make_state()

    with patch("bot.utils.language.get_user_language", AsyncMock(return_value="ru")), patch(
        "bot.utils.language.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ), patch(
        "bot.services.income.delete_income", AsyncMock(return_value=True)
    ), patch(
        "bot.utils.state_utils.clear_state_keep_cashback", AsyncMock()
    ) as clear_state:
        await expense_router.delete_expense(callback, state)

    callback.message.edit_text.assert_awaited_once_with("income_deleted_message", reply_markup=None)
    callback.answer.assert_awaited_once_with("income_deleted_success")
    clear_state.assert_awaited_once_with(state)


@pytest.mark.asyncio
async def test_delete_expense_failure_shows_alert_without_editing_message():
    callback = make_callback()
    callback.data = "delete_expense_93"
    state = make_state()

    with patch("bot.utils.language.get_user_language", AsyncMock(return_value="ru")), patch(
        "bot.utils.language.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ), patch(
        "bot.services.expense.delete_expense", AsyncMock(return_value=False)
    ), patch(
        "bot.utils.state_utils.clear_state_keep_cashback", AsyncMock()
    ) as clear_state:
        await expense_router.delete_expense(callback, state)

    callback.message.edit_text.assert_not_awaited()
    callback.answer.assert_awaited_once_with("failed_delete_expense", show_alert=True)
    clear_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_income_failure_shows_alert_without_editing_message():
    callback = make_callback()
    callback.data = "delete_income_94"
    state = make_state()

    with patch("bot.utils.language.get_user_language", AsyncMock(return_value="ru")), patch(
        "bot.utils.language.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ), patch(
        "bot.services.income.delete_income", AsyncMock(return_value=False)
    ), patch(
        "bot.utils.state_utils.clear_state_keep_cashback", AsyncMock()
    ) as clear_state:
        await expense_router.delete_expense(callback, state)

    callback.message.edit_text.assert_not_awaited()
    callback.answer.assert_awaited_once_with("failed_delete_income", show_alert=True)
    clear_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_show_edit_menu_reports_missing_expense_and_clears_state():
    message = AsyncMock()
    message.from_user = SimpleNamespace(id=123456789)
    message.answer = AsyncMock()
    state = make_state()
    missing_error = type("ExpenseDoesNotExist", (Exception,), {})
    expense_model = SimpleNamespace(
        DoesNotExist=missing_error,
        objects=SimpleNamespace(
            select_related=Mock(
                return_value=SimpleNamespace(aget=AsyncMock(side_effect=missing_error()))
            )
        ),
    )

    with patch("expenses.models.Expense", expense_model), patch(
        "bot.utils.state_utils.clear_state_keep_cashback", AsyncMock()
    ) as clear_state:
        await expense_router.show_edit_menu(message, state, expense_id=101, lang="ru")

    message.answer.assert_awaited_once_with("❌ Трата не найдена")
    clear_state.assert_awaited_once_with(state)


@pytest.mark.asyncio
async def test_show_edit_menu_renders_expense_menu_via_send_message_with_cleanup():
    message = AsyncMock()
    message.from_user = SimpleNamespace(id=123456789)
    state = make_state()
    expense = SimpleNamespace(
        id=105,
        amount=900,
        description="groceries",
        category=SimpleNamespace(id=8),
        profile=SimpleNamespace(currency="RUB"),
        currency="RUB",
    )
    expense_model = SimpleNamespace(
        DoesNotExist=type("ExpenseDoesNotExist", (Exception,), {}),
        objects=SimpleNamespace(
            select_related=Mock(return_value=SimpleNamespace(aget=AsyncMock(return_value=expense)))
        ),
    )
    await state.update_data(editing_type="expense")

    with patch("expenses.models.Expense", expense_model), patch(
        "bot.routers.expense.get_category_display_name", return_value="Food"
    ), patch(
        "bot.routers.expense.format_currency", return_value="900 RUB"
    ), patch(
        "bot.routers.expense.send_message_with_cleanup", AsyncMock()
    ) as send_message:
        await expense_router.show_edit_menu(message, state, expense_id=105, lang="ru")

    send_message.assert_awaited_once()
    send_args = send_message.await_args
    assert send_args.args[0] is message
    assert send_args.args[1] is state
    assert "Редактирование траты" in send_args.args[2]
    keyboard = send_args.kwargs["reply_markup"]
    assert keyboard.inline_keyboard[0][0].callback_data == "edit_field_amount_expense_105"
    assert keyboard.inline_keyboard[1][0].callback_data == "edit_field_description_expense_105"
    assert keyboard.inline_keyboard[2][0].callback_data == "edit_field_category_expense_105"
    assert keyboard.inline_keyboard[3][0].callback_data == "edit_done_expense_105"
    assert await state.get_state() == expense_router.EditExpenseForm.choosing_field.state


@pytest.mark.asyncio
async def test_show_edit_menu_callback_reports_missing_expense_and_clears_state():
    callback = make_callback()
    state = make_state()
    missing_error = type("ExpenseDoesNotExist", (Exception,), {})
    expense_model = SimpleNamespace(
        DoesNotExist=missing_error,
        objects=SimpleNamespace(
            select_related=Mock(
                return_value=SimpleNamespace(aget=AsyncMock(side_effect=missing_error()))
            )
        ),
    )
    income_model = SimpleNamespace(DoesNotExist=type("IncomeDoesNotExist", (Exception,), {}))

    with patch("expenses.models.Expense", expense_model), patch(
        "expenses.models.Income", income_model
    ), patch(
        "bot.utils.state_utils.clear_state_keep_cashback", AsyncMock()
    ) as clear_state:
        await expense_router.show_edit_menu_callback(callback, state, expense_id=102, lang="ru", item_type="expense")

    callback.answer.assert_awaited_once_with("❌ Трата не найдена", show_alert=True)
    callback.message.edit_text.assert_not_awaited()
    clear_state.assert_awaited_once_with(state)


@pytest.mark.asyncio
async def test_show_edit_menu_callback_reports_missing_income_and_clears_state():
    callback = make_callback()
    state = make_state()
    expense_model = SimpleNamespace(DoesNotExist=type("ExpenseDoesNotExist", (Exception,), {}))
    missing_error = type("IncomeDoesNotExist", (Exception,), {})
    income_model = SimpleNamespace(
        DoesNotExist=missing_error,
        objects=SimpleNamespace(
            select_related=Mock(
                return_value=SimpleNamespace(aget=AsyncMock(side_effect=missing_error()))
            )
        ),
    )

    with patch("expenses.models.Expense", expense_model), patch(
        "expenses.models.Income", income_model
    ), patch(
        "bot.utils.state_utils.clear_state_keep_cashback", AsyncMock()
    ) as clear_state:
        await expense_router.show_edit_menu_callback(callback, state, expense_id=103, lang="ru", item_type="income")

    callback.answer.assert_awaited_once_with("❌ Трата не найдена", show_alert=True)
    callback.message.edit_text.assert_not_awaited()
    clear_state.assert_awaited_once_with(state)


@pytest.mark.asyncio
async def test_show_edit_menu_callback_renders_expense_menu_and_sets_state():
    callback = make_callback()
    state = make_state()
    expense = SimpleNamespace(
        id=104,
        amount=500,
        description="coffee",
        category=SimpleNamespace(id=7),
        profile=SimpleNamespace(currency="RUB"),
        currency="RUB",
    )
    expense_model = SimpleNamespace(
        DoesNotExist=type("ExpenseDoesNotExist", (Exception,), {}),
        objects=SimpleNamespace(
            select_related=Mock(return_value=SimpleNamespace(aget=AsyncMock(return_value=expense)))
        ),
    )
    income_model = SimpleNamespace(DoesNotExist=type("IncomeDoesNotExist", (Exception,), {}))

    with patch("expenses.models.Expense", expense_model), patch(
        "expenses.models.Income", income_model
    ), patch(
        "bot.routers.expense.get_category_display_name", return_value="Food"
    ), patch(
        "bot.routers.expense.format_currency", return_value="500 RUB"
    ):
        await expense_router.show_edit_menu_callback(callback, state, expense_id=104, lang="ru", item_type="expense")

    callback.message.edit_text.assert_awaited_once()
    edit_args = callback.message.edit_text.await_args
    assert "Редактирование траты" in edit_args.args[0]
    keyboard = edit_args.kwargs["reply_markup"]
    assert keyboard.inline_keyboard[0][0].callback_data == "edit_field_amount_expense_104"
    assert keyboard.inline_keyboard[1][0].callback_data == "edit_field_description_expense_104"
    assert keyboard.inline_keyboard[2][0].callback_data == "edit_field_category_expense_104"
    assert keyboard.inline_keyboard[3][0].callback_data == "edit_done_expense_104"
    assert await state.get_state() == expense_router.EditExpenseForm.choosing_field.state
    callback.answer.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_show_edit_menu_callback_renders_income_menu_and_sets_state():
    callback = make_callback()
    state = make_state()
    income = SimpleNamespace(
        id=106,
        amount=1200,
        description="bonus",
        category=None,
        profile=SimpleNamespace(currency="USD"),
        currency="USD",
    )
    expense_model = SimpleNamespace(DoesNotExist=type("ExpenseDoesNotExist", (Exception,), {}))
    income_model = SimpleNamespace(
        DoesNotExist=type("IncomeDoesNotExist", (Exception,), {}),
        objects=SimpleNamespace(
            select_related=Mock(return_value=SimpleNamespace(aget=AsyncMock(return_value=income)))
        ),
    )

    with patch("expenses.models.Expense", expense_model), patch(
        "expenses.models.Income", income_model
    ), patch(
        "bot.routers.expense.get_category_display_name", return_value="Other income"
    ), patch(
        "bot.routers.expense.format_currency", return_value="1200 USD"
    ):
        await expense_router.show_edit_menu_callback(callback, state, expense_id=106, lang="ru", item_type="income")

    callback.message.edit_text.assert_awaited_once()
    edit_args = callback.message.edit_text.await_args
    assert "Редактирование траты" in edit_args.args[0]
    keyboard = edit_args.kwargs["reply_markup"]
    assert keyboard.inline_keyboard[0][0].callback_data == "edit_field_amount_income_106"
    assert keyboard.inline_keyboard[1][0].callback_data == "edit_field_description_income_106"
    assert keyboard.inline_keyboard[2][0].callback_data == "edit_field_category_income_106"
    assert keyboard.inline_keyboard[3][0].callback_data == "edit_done_income_106"
    assert await state.get_state() == expense_router.EditExpenseForm.choosing_field.state
    callback.answer.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_edit_field_amount_rejects_expired_session_without_item_id():
    callback = make_callback()
    callback.data = "edit_field_amount"
    state = make_state()

    with patch.object(state, "clear", AsyncMock()) as clear_state:
        await expense_router.edit_field_amount(callback, state, lang="ru")

    callback.message.edit_text.assert_not_awaited()
    callback.answer.assert_awaited_once_with(
        "❌ Сессия редактирования истекла. Попробуйте начать заново.",
        show_alert=True,
    )
    clear_state.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_edit_field_amount_sets_state_and_renders_prompt():
    callback = make_callback()
    callback.data = "edit_field_amount_expense_404"
    state = make_state()

    with patch("bot.routers.expense.get_text", side_effect=lambda key, lang="ru", **kwargs: key):
        await expense_router.edit_field_amount(callback, state, lang="ru")

    callback.message.edit_text.assert_awaited_once()
    edit_args = callback.message.edit_text.await_args
    assert "editing_amount" in edit_args.args[0]
    assert "enter_new_amount" in edit_args.args[0]
    keyboard = edit_args.kwargs["reply_markup"]
    assert keyboard.inline_keyboard[0][0].callback_data == "edit_back_expense_404"
    data = await state.get_data()
    assert data["editing_expense_id"] == 404
    assert data["editing_type"] == "expense"
    assert data["lang"] == "ru"
    assert data["editing_prompt_message_id"] == callback.message.message_id
    assert await state.get_state() == expense_router.EditExpenseForm.editing_amount.state
    callback.answer.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_edit_field_description_rejects_expired_session_without_item_id():
    callback = make_callback()
    callback.data = "edit_field_description"
    state = make_state()

    with patch.object(state, "clear", AsyncMock()) as clear_state:
        await expense_router.edit_field_description(callback, state, lang="ru")

    callback.message.edit_text.assert_not_awaited()
    callback.answer.assert_awaited_once_with(
        "❌ Сессия редактирования истекла. Попробуйте начать заново.",
        show_alert=True,
    )
    clear_state.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_edit_field_description_uses_state_fallback_and_renders_prompt():
    callback = make_callback()
    callback.data = "edit_field_description"
    state = make_state()
    await state.update_data(editing_expense_id=405, editing_type="income")

    with patch("bot.routers.expense.get_text", side_effect=lambda key, lang="ru", **kwargs: key):
        await expense_router.edit_field_description(callback, state, lang="ru")

    callback.message.edit_text.assert_awaited_once()
    edit_args = callback.message.edit_text.await_args
    assert "editing_description" in edit_args.args[0]
    assert "enter_new_description" in edit_args.args[0]
    keyboard = edit_args.kwargs["reply_markup"]
    assert keyboard.inline_keyboard[0][0].callback_data == "edit_back_income_405"
    data = await state.get_data()
    assert data["editing_expense_id"] == 405
    assert data["editing_type"] == "income"
    assert data["lang"] == "ru"
    assert data["editing_prompt_message_id"] == callback.message.message_id
    assert await state.get_state() == expense_router.EditExpenseForm.editing_description.state
    callback.answer.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_edit_field_category_rejects_expired_session_without_item_id():
    callback = make_callback()
    callback.data = "edit_field_category"
    state = make_state()

    with patch.object(state, "clear", AsyncMock()) as clear_state:
        await expense_router.edit_field_category(callback, state, lang="ru")

    callback.message.edit_text.assert_not_awaited()
    callback.answer.assert_awaited_once_with(
        "❌ Сессия редактирования истекла. Попробуйте начать заново.",
        show_alert=True,
    )
    clear_state.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_edit_field_category_renders_user_categories_and_sets_state():
    callback = make_callback()
    callback.data = "edit_field_category_expense_406"
    state = make_state()
    categories = [SimpleNamespace(id=1), SimpleNamespace(id=2)]

    with patch(
        "bot.services.category.get_user_categories", AsyncMock(return_value=categories)
    ), patch(
        "bot.routers.expense.get_category_display_name", side_effect=["Food", "Taxi"]
    ):
        await expense_router.edit_field_category(callback, state, lang="ru")

    callback.message.edit_text.assert_awaited_once()
    edit_args = callback.message.edit_text.await_args
    assert "Выберите новую категорию" in edit_args.args[0]
    keyboard = edit_args.kwargs["reply_markup"]
    assert keyboard.inline_keyboard[0][0].callback_data == "expense_cat_1"
    assert keyboard.inline_keyboard[0][0].text == "Food"
    assert keyboard.inline_keyboard[0][1].callback_data == "expense_cat_2"
    assert keyboard.inline_keyboard[-1][0].callback_data == "edit_cancel_expense_406"
    data = await state.get_data()
    assert data["editing_expense_id"] == 406
    assert data["editing_type"] == "expense"
    assert data["lang"] == "ru"
    assert await state.get_state() == expense_router.EditExpenseForm.editing_category.state
    callback.answer.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_edit_field_category_shows_alert_when_expense_categories_missing():
    callback = make_callback()
    callback.data = "edit_field_category_expense_411"
    state = make_state()

    with patch(
        "bot.services.category.get_user_categories", AsyncMock(return_value=[])
    ):
        await expense_router.edit_field_category(callback, state, lang="ru")

    callback.message.edit_text.assert_not_awaited()
    callback.answer.assert_awaited_once_with("У вас нет категорий. Создайте их через /categories", show_alert=True)


@pytest.mark.asyncio
async def test_edit_field_category_shows_alert_when_income_categories_missing():
    callback = make_callback()
    callback.data = "edit_field_category_income_412"
    state = make_state()

    with patch(
        "bot.services.income.get_user_income_categories", AsyncMock(return_value=[])
    ):
        await expense_router.edit_field_category(callback, state, lang="ru")

    callback.message.edit_text.assert_not_awaited()
    callback.answer.assert_awaited_once_with("У вас нет категорий доходов.", show_alert=True)


@pytest.mark.asyncio
async def test_edit_done_rejects_expired_session_without_item_id():
    callback = make_callback()
    callback.data = "edit_done"
    state = make_state()

    with patch.object(state, "clear", AsyncMock()) as clear_state:
        await expense_router.edit_done(callback, state, lang="ru")

    callback.answer.assert_awaited_once_with(
        "❌ Сессия редактирования истекла. Попробуйте начать заново.",
        show_alert=True,
    )
    clear_state.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_edit_done_renders_income_card_and_clears_state():
    callback = make_callback()
    callback.data = "edit_done_income_407"
    state = make_state()
    income = SimpleNamespace(
        id=407,
        category=None,
        profile=SimpleNamespace(currency="RUB"),
    )
    income_model = SimpleNamespace(
        DoesNotExist=type("IncomeDoesNotExist", (Exception,), {}),
        objects=SimpleNamespace(
            select_related=Mock(return_value=SimpleNamespace(aget=AsyncMock(return_value=income)))
        ),
    )

    with patch("expenses.models.Income", income_model), patch(
        "bot.utils.expense_messages.format_income_added_message", AsyncMock(return_value="income-finished")
    ) as format_message, patch(
        "bot.utils.state_utils.clear_state_keep_cashback", AsyncMock()
    ) as clear_state, patch(
        "bot.routers.expense.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ):
        await expense_router.edit_done(callback, state, lang="ru")

    format_message.assert_awaited_once_with(income=income, category=None, lang="ru")
    callback.message.edit_text.assert_awaited_once()
    edit_args = callback.message.edit_text.await_args
    assert edit_args.args[0] == "income-finished"
    keyboard = edit_args.kwargs["reply_markup"]
    assert keyboard.inline_keyboard[0][0].callback_data == "edit_income_407"
    assert edit_args.kwargs["parse_mode"] == "HTML"
    clear_state.assert_awaited_once_with(state)
    callback.answer.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_edit_done_falls_back_to_error_message_for_missing_expense_data():
    callback = make_callback()
    callback.data = "edit_done_expense_408"
    state = make_state()
    missing_error = Exception("boom")
    expense_model = SimpleNamespace(
        objects=SimpleNamespace(
            select_related=Mock(return_value=SimpleNamespace(aget=AsyncMock(side_effect=missing_error)))
        ),
    )

    with patch("expenses.models.Expense", expense_model), patch(
        "bot.utils.state_utils.clear_state_keep_cashback", AsyncMock()
    ) as clear_state:
        await expense_router.edit_done(callback, state, lang="ru")

    callback.message.edit_text.assert_awaited_once_with("❌ Ошибка при получении данных траты")
    clear_state.assert_awaited_once_with(state)
    callback.answer.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_process_edit_category_reports_missing_expense_and_clears_state():
    callback = make_callback()
    callback.data = "expense_cat_9"
    state = make_state()
    await state.update_data(editing_expense_id=409, editing_type="expense")
    missing_error = type("ExpenseDoesNotExist", (Exception,), {})
    expense_model = SimpleNamespace(
        DoesNotExist=missing_error,
        objects=SimpleNamespace(aget=AsyncMock(side_effect=missing_error())),
    )

    with patch("expenses.models.Expense", expense_model), patch(
        "bot.utils.state_utils.clear_state_keep_cashback", AsyncMock()
    ) as clear_state:
        await expense_router.process_edit_category(callback, state, lang="ru")

    callback.answer.assert_awaited_once_with("❌ Трата не найдена", show_alert=True)
    clear_state.assert_awaited_once_with(state)


@pytest.mark.asyncio
async def test_process_edit_category_updates_expense_and_shows_updated_card():
    callback = make_callback()
    callback.data = "expense_cat_10"
    state = make_state()
    await state.update_data(editing_expense_id=410, editing_type="expense")
    expense = SimpleNamespace(category_id=1, description="taxi")
    expense_model = SimpleNamespace(
        DoesNotExist=type("ExpenseDoesNotExist", (Exception,), {}),
        objects=SimpleNamespace(aget=AsyncMock(return_value=expense)),
    )

    with patch("expenses.models.Expense", expense_model), patch(
        "bot.services.expense.update_expense", AsyncMock(return_value=True)
    ) as update_expense, patch.object(
        expense_router, "show_updated_expense_callback", AsyncMock()
    ) as show_updated:
        await expense_router.process_edit_category(callback, state, lang="ru")

    update_expense.assert_awaited_once_with(callback.from_user.id, 410, category_id=10)
    show_updated.assert_awaited_once_with(callback, state, 410, "ru")


@pytest.mark.asyncio
async def test_process_edit_category_reports_missing_income_and_clears_state():
    callback = make_callback()
    callback.data = "expense_cat_11"
    state = make_state()
    await state.update_data(editing_expense_id=411, editing_type="income")
    missing_error = type("IncomeDoesNotExist", (Exception,), {})
    income_model = SimpleNamespace(
        DoesNotExist=missing_error,
        objects=SimpleNamespace(aget=AsyncMock(side_effect=missing_error())),
    )

    with patch("expenses.models.Income", income_model), patch(
        "bot.utils.state_utils.clear_state_keep_cashback", AsyncMock()
    ) as clear_state:
        await expense_router.process_edit_category(callback, state, lang="ru")

    callback.answer.assert_awaited_once_with("❌ Доход не найден", show_alert=True)
    clear_state.assert_awaited_once_with(state)


@pytest.mark.asyncio
async def test_process_edit_category_updates_income_and_shows_updated_card():
    callback = make_callback()
    callback.data = "expense_cat_12"
    state = make_state()
    await state.update_data(editing_expense_id=412, editing_type="income")
    income = SimpleNamespace(category_id=2, description="bonus")
    income_model = SimpleNamespace(
        DoesNotExist=type("IncomeDoesNotExist", (Exception,), {}),
        objects=SimpleNamespace(aget=AsyncMock(return_value=income)),
    )

    with patch("expenses.models.Income", income_model), patch(
        "bot.services.income.update_income", AsyncMock(return_value=True)
    ) as update_income, patch.object(
        expense_router, "show_updated_expense_callback", AsyncMock()
    ) as show_updated:
        await expense_router.process_edit_category(callback, state, lang="ru")

    update_income.assert_awaited_once_with(callback.from_user.id, 412, category_id=12)
    show_updated.assert_awaited_once_with(callback, state, 412, "ru")


@pytest.mark.asyncio
async def test_edit_cancel_returns_to_edit_menu_when_item_id_present():
    callback = make_callback()
    callback.data = "edit_cancel_expense_301"
    state = make_state()
    await state.update_data(lang="en")

    with patch.object(expense_router, "show_edit_menu_callback", AsyncMock()) as show_menu:
        await expense_router.edit_cancel(callback, state)

    show_menu.assert_awaited_once_with(callback, state, 301, "en", item_type="expense")
    callback.answer.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_edit_cancel_without_item_id_deletes_message_and_clears_state():
    callback = make_callback()
    callback.data = "edit_cancel"
    state = make_state()

    with patch("bot.routers.expense.safe_delete_message", AsyncMock()) as safe_delete, patch(
        "bot.utils.state_utils.clear_state_keep_cashback", AsyncMock()
    ) as clear_state:
        await expense_router.edit_cancel(callback, state)

    safe_delete.assert_awaited_once_with(message=callback.message)
    clear_state.assert_awaited_once_with(state)
    callback.answer.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_edit_back_to_menu_reports_missing_item_id():
    callback = make_callback()
    callback.data = "edit_back_"
    state = make_state()

    with patch.object(expense_router, "show_edit_menu_callback", AsyncMock()) as show_menu:
        await expense_router.edit_back_to_menu(callback, state)

    show_menu.assert_not_awaited()
    callback.answer.assert_awaited_once_with("❌ Ошибка: ID траты не найден")


@pytest.mark.asyncio
async def test_edit_back_to_menu_uses_state_language_and_item_type():
    callback = make_callback()
    callback.data = "edit_back_income_302"
    state = make_state()
    await state.update_data(lang="en")

    with patch.object(expense_router, "show_edit_menu_callback", AsyncMock()) as show_menu:
        await expense_router.edit_back_to_menu(callback, state)

    show_menu.assert_awaited_once_with(callback, state, 302, "en", item_type="income")
    callback.answer.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_show_updated_expense_reports_missing_income_and_clears_state():
    message = AsyncMock()
    message.from_user = SimpleNamespace(id=123456789)
    message.answer = AsyncMock()
    state = make_state()
    await state.update_data(editing_type="income")
    expense_model = SimpleNamespace(DoesNotExist=type("ExpenseDoesNotExist", (Exception,), {}))
    missing_error = type("IncomeDoesNotExist", (Exception,), {})
    income_model = SimpleNamespace(
        DoesNotExist=missing_error,
        objects=SimpleNamespace(
            select_related=Mock(
                return_value=SimpleNamespace(aget=AsyncMock(side_effect=missing_error()))
            )
        ),
    )

    with patch("expenses.models.Expense", expense_model), patch(
        "expenses.models.Income", income_model
    ), patch(
        "bot.utils.state_utils.clear_state_keep_cashback", AsyncMock()
    ) as clear_state:
        await expense_router.show_updated_expense(message, state, item_id=201, lang="ru")

    message.answer.assert_awaited_once_with("❌ Доход не найден")
    clear_state.assert_awaited_once_with(state)


@pytest.mark.asyncio
async def test_show_updated_expense_reports_missing_expense_and_clears_state():
    message = AsyncMock()
    message.from_user = SimpleNamespace(id=123456789)
    message.answer = AsyncMock()
    state = make_state()
    await state.update_data(editing_type="expense")
    missing_error = type("ExpenseDoesNotExist", (Exception,), {})
    expense_model = SimpleNamespace(
        DoesNotExist=missing_error,
        objects=SimpleNamespace(
            select_related=Mock(
                return_value=SimpleNamespace(aget=AsyncMock(side_effect=missing_error()))
            )
        ),
    )
    income_model = SimpleNamespace(DoesNotExist=type("IncomeDoesNotExist", (Exception,), {}))

    with patch("expenses.models.Expense", expense_model), patch(
        "expenses.models.Income", income_model
    ), patch(
        "bot.utils.state_utils.clear_state_keep_cashback", AsyncMock()
    ) as clear_state:
        await expense_router.show_updated_expense(message, state, item_id=202, lang="ru")

    message.answer.assert_awaited_once_with("❌ Трата не найдена")
    clear_state.assert_awaited_once_with(state)


@pytest.mark.asyncio
async def test_show_updated_expense_callback_reports_missing_expense_and_clears_state():
    callback = make_callback()
    state = make_state()
    await state.update_data(editing_type="expense")
    missing_error = type("ExpenseDoesNotExist", (Exception,), {})
    expense_model = SimpleNamespace(
        DoesNotExist=missing_error,
        objects=SimpleNamespace(
            select_related=Mock(
                return_value=SimpleNamespace(aget=AsyncMock(side_effect=missing_error()))
            )
        ),
    )
    income_model = SimpleNamespace(DoesNotExist=type("IncomeDoesNotExist", (Exception,), {}))

    with patch("expenses.models.Expense", expense_model), patch(
        "expenses.models.Income", income_model
    ), patch(
        "bot.utils.state_utils.clear_state_keep_cashback", AsyncMock()
    ) as clear_state:
        await expense_router.show_updated_expense_callback(callback, state, item_id=202, lang="ru")

    callback.message.edit_text.assert_not_awaited()
    callback.answer.assert_awaited_once_with("❌ Трата не найдена", show_alert=True)
    clear_state.assert_awaited_once_with(state)


@pytest.mark.asyncio
async def test_show_updated_expense_callback_reports_missing_income_and_clears_state():
    callback = make_callback()
    state = make_state()
    await state.update_data(editing_type="income")
    expense_model = SimpleNamespace(DoesNotExist=type("ExpenseDoesNotExist", (Exception,), {}))
    missing_error = type("IncomeDoesNotExist", (Exception,), {})
    income_model = SimpleNamespace(
        DoesNotExist=missing_error,
        objects=SimpleNamespace(
            select_related=Mock(
                return_value=SimpleNamespace(aget=AsyncMock(side_effect=missing_error()))
            )
        ),
    )

    with patch("expenses.models.Expense", expense_model), patch(
        "expenses.models.Income", income_model
    ), patch(
        "bot.utils.state_utils.clear_state_keep_cashback", AsyncMock()
    ) as clear_state:
        await expense_router.show_updated_expense_callback(callback, state, item_id=203, lang="ru")

    callback.message.edit_text.assert_not_awaited()
    callback.answer.assert_awaited_once_with("❌ Доход не найден", show_alert=True)
    clear_state.assert_awaited_once_with(state)


@pytest.mark.asyncio
async def test_show_updated_expense_renders_expense_message_and_clears_state():
    message = AsyncMock()
    message.from_user = SimpleNamespace(id=123456789)
    state = make_state()
    await state.update_data(editing_type="expense")
    expense = SimpleNamespace(
        id=301,
        category=None,
        profile=SimpleNamespace(currency="RUB"),
        currency="RUB",
        cashback_excluded=False,
    )
    expense_model = SimpleNamespace(
        DoesNotExist=type("ExpenseDoesNotExist", (Exception,), {}),
        objects=SimpleNamespace(
            select_related=Mock(return_value=SimpleNamespace(aget=AsyncMock(return_value=expense)))
        ),
    )
    income_model = SimpleNamespace(DoesNotExist=type("IncomeDoesNotExist", (Exception,), {}))

    with patch("expenses.models.Expense", expense_model), patch(
        "expenses.models.Income", income_model
    ), patch(
        "bot.routers.expense.check_subscription", AsyncMock(return_value=False)
    ), patch(
        "bot.routers.expense.format_expense_added_message", AsyncMock(return_value="expense-card")
    ) as format_message, patch(
        "bot.routers.expense.send_message_with_cleanup", AsyncMock()
    ) as send_message, patch(
        "bot.utils.state_utils.clear_state_keep_cashback", AsyncMock()
    ) as clear_state, patch(
        "bot.routers.expense.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ):
        await expense_router.show_updated_expense(message, state, item_id=301, lang="ru")

    format_message.assert_awaited_once_with(
        expense=expense,
        category=None,
        cashback_text="",
        lang="ru",
    )
    send_message.assert_awaited_once()
    send_args = send_message.await_args
    assert send_args.args[0] is message
    assert send_args.args[1] is state
    assert send_args.args[2] == "expense-card"
    assert send_args.kwargs["keep_message"] is True
    clear_state.assert_awaited_once_with(state)


@pytest.mark.asyncio
async def test_show_updated_expense_callback_renders_income_message_and_clears_state():
    callback = make_callback()
    state = make_state()
    await state.update_data(editing_type="income")
    income = SimpleNamespace(
        id=302,
        category=None,
        profile=SimpleNamespace(currency="RUB"),
        currency="RUB",
    )
    expense_model = SimpleNamespace(DoesNotExist=type("ExpenseDoesNotExist", (Exception,), {}))
    income_model = SimpleNamespace(
        DoesNotExist=type("IncomeDoesNotExist", (Exception,), {}),
        objects=SimpleNamespace(
            select_related=Mock(return_value=SimpleNamespace(aget=AsyncMock(return_value=income)))
        ),
    )

    with patch("expenses.models.Expense", expense_model), patch(
        "expenses.models.Income", income_model
    ), patch(
        "bot.utils.expense_messages.format_income_added_message", AsyncMock(return_value="income-card")
    ) as format_message, patch(
        "bot.utils.state_utils.clear_state_keep_cashback", AsyncMock()
    ) as clear_state, patch(
        "bot.routers.expense.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ):
        await expense_router.show_updated_expense_callback(callback, state, item_id=302, lang="ru")

    format_message.assert_awaited_once_with(
        income=income,
        category=None,
        lang="ru",
    )
    callback.message.edit_text.assert_awaited_once()
    edit_args = callback.message.edit_text.await_args
    assert edit_args.args[0] == "income-card"
    assert edit_args.kwargs["parse_mode"] == "HTML"
    clear_state.assert_awaited_once_with(state)
    callback.answer.assert_awaited_once_with()
