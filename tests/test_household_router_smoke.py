from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.routers import household as household_router


def make_state(user_id: int = 123456789, chat_id: int = 123456789, bot_id: int = 42) -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=bot_id, chat_id=chat_id, user_id=user_id)
    return FSMContext(storage=storage, key=key)


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
    callback.message.text = "household"
    callback.message.edit_text = AsyncMock()
    callback.message.answer = AsyncMock()
    return callback


def make_message(bot: AsyncMock | None = None, user_id: int = 123456789):
    bot = bot or AsyncMock()
    message = AsyncMock()
    message.bot = bot
    message.from_user = SimpleNamespace(id=user_id, language_code="ru")
    message.chat = SimpleNamespace(id=user_id, type="private")
    message.text = "/start family_token"
    message.message_id = 101
    message.answer = AsyncMock()
    return message


@pytest.mark.asyncio
async def test_household_menu_requires_subscription_before_showing_actions():
    callback = make_callback()
    state = make_state()

    with patch("bot.routers.household.check_subscription", AsyncMock(return_value=False)), patch(
        "bot.routers.household.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ), patch(
        "bot.routers.household.get_household_menu_keyboard", return_value="MENU"
    ):
        await household_router.household_menu(callback, state, lang="ru")

    callback.answer.assert_awaited_once()
    callback.message.edit_text.assert_awaited_once_with(
        "household_subscription_required",
        reply_markup="MENU",
        parse_mode="HTML",
    )


@pytest.mark.asyncio
async def test_household_menu_renders_existing_household_for_creator():
    callback = make_callback()
    state = make_state()
    household = SimpleNamespace(name="Семья", members_count=3, max_members=5, creator_id=7)
    profile = SimpleNamespace(id=7, household_id=11, household=household)

    with patch("bot.routers.household.check_subscription", AsyncMock(return_value=True)), patch(
        "bot.routers.household.get_or_create_profile", AsyncMock(return_value=profile)
    ), patch(
        "bot.routers.household.get_text",
        side_effect=lambda key, lang="ru", **kwargs: f"{key}:{kwargs}" if kwargs else key,
    ), patch(
        "bot.routers.household.get_household_settings_keyboard", return_value="SETTINGS"
    ):
        await household_router.household_menu(callback, state, lang="ru")

    callback.message.edit_text.assert_awaited_once()
    args, kwargs = callback.message.edit_text.await_args
    assert "Семья" in args[0]
    assert "household_members_count" in args[0]
    assert "choose_action" in args[0]
    assert kwargs["reply_markup"] == "SETTINGS"
    assert kwargs["parse_mode"] == "HTML"


@pytest.mark.asyncio
async def test_generate_invite_renders_copyable_link():
    callback = make_callback()
    callback.bot.get_me = AsyncMock(return_value=SimpleNamespace(username="expense_bot"))
    profile = SimpleNamespace(household_id=11)

    with patch("bot.routers.household.get_or_create_profile", AsyncMock(return_value=profile)), patch(
        "bot.routers.household.HouseholdService.generate_invite_link",
        return_value=(True, "https://t.me/expense_bot?start=family_token"),
    ), patch(
        "bot.routers.household.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ):
        await household_router.generate_invite(callback, lang="ru")

    callback.answer.assert_awaited_once()
    callback.message.edit_text.assert_awaited_once()
    args, kwargs = callback.message.edit_text.await_args
    assert "invite_link_title" in args[0]
    assert "<code>https://t.me/expense_bot?start=family_token</code>" in args[0]
    assert kwargs["parse_mode"] == "HTML"


@pytest.mark.asyncio
async def test_process_family_invite_rejects_self_invite_without_join_prompt():
    message = make_message(user_id=555)
    profile = SimpleNamespace(language_code="ru", household_id=None)
    invite = SimpleNamespace(
        inviter=SimpleNamespace(telegram_id=555),
        household=SimpleNamespace(name="Семья", members_count=2, max_members=5),
        is_valid=Mock(return_value=True),
    )

    class InviteQuery:
        def __init__(self, value):
            self.value = value

        def first(self):
            return self.value

    with patch("bot.routers.household.get_or_create_profile", AsyncMock(return_value=profile)), patch(
        "bot.routers.household.get_text", side_effect=lambda key, lang="ru", **kwargs: key
    ), patch(
        "expenses.models.FamilyInvite.objects.filter", return_value=InviteQuery(invite)
    ):
        await household_router.process_family_invite(message, "family-token")

    message.answer.assert_awaited_once_with("invite_self_error", parse_mode="HTML")
