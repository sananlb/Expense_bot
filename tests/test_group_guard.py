from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from aiogram.types import Message

from bot.middlewares.group_guard import GroupChatGuardMiddleware


def make_group_message(text: str):
    bot = AsyncMock()
    bot.me.return_value = SimpleNamespace(username="expense_bot")
    message = Mock(spec=Message)
    message.bot = bot
    message.chat = SimpleNamespace(type="group")
    message.from_user = SimpleNamespace(id=123)
    message.text = text
    return message


@pytest.mark.asyncio
async def test_guard_allows_leading_mention_of_this_bot():
    handler = AsyncMock(return_value="handled")
    message = make_group_message("@Expense_Bot coffee 200")

    result = await GroupChatGuardMiddleware()(handler, message, {})

    assert result == "handled"
    handler.assert_awaited_once_with(message, {})


@pytest.mark.asyncio
async def test_guard_drops_leading_mention_of_other_bot():
    handler = AsyncMock()
    message = make_group_message("@other_bot coffee 200")

    result = await GroupChatGuardMiddleware()(handler, message, {})

    assert result is None
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_guard_drops_mention_when_bot_username_is_unavailable():
    handler = AsyncMock()
    message = make_group_message("@expense_bot coffee 200")
    message.bot.me.side_effect = RuntimeError("Telegram unavailable")

    result = await GroupChatGuardMiddleware()(handler, message, {})

    assert result is None
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_guard_allows_bang_entry():
    handler = AsyncMock(return_value="handled")
    message = make_group_message("!coffee 200")

    result = await GroupChatGuardMiddleware()(handler, message, {})

    assert result == "handled"
    handler.assert_awaited_once_with(message, {})


@pytest.mark.asyncio
async def test_guard_drops_slash_entry():
    handler = AsyncMock()
    message = make_group_message("/coffee 200")

    result = await GroupChatGuardMiddleware()(handler, message, {})

    assert result is None
    handler.assert_not_awaited()
