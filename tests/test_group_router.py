from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from bot.routers import group as group_router


def make_message(text: str):
    bot = AsyncMock()
    bot.me.return_value = SimpleNamespace(username="expense_bot")
    message = AsyncMock()
    message.bot = bot
    message.from_user = SimpleNamespace(id=123)
    message.text = text
    return message


@pytest.mark.parametrize(
    ("lang", "admin_text", "example"),
    [
        ("ru", "назначьте меня администратором", "!кофе 200"),
        ("en", "make me an administrator", "!coffee 200"),
    ],
)
def test_group_welcome_explains_admin_requirement_and_bang_format(lang, admin_text, example):
    text = group_router.get_text("group_welcome", lang).format(bot_username="expense_bot")

    assert admin_text in text
    assert example in text
    assert "@expense_bot" in text


@pytest.mark.asyncio
async def test_bang_entry_is_parsed_as_expense():
    message = make_message("!coffee 200")

    with patch("bot.utils.expense_parser.detect_income_intent", return_value=False), patch.object(
        group_router, "_handle_group_expense", AsyncMock()
    ) as handle_expense:
        await group_router.handle_group_explicit_entry(message, lang="en")

    handle_expense.assert_awaited_once_with(message, 123, "coffee 200", "en")


@pytest.mark.asyncio
async def test_bang_entry_is_parsed_as_income():
    message = make_message("!salary +500")

    with patch("bot.utils.expense_parser.detect_income_intent", return_value=True), patch.object(
        group_router, "_handle_group_income", AsyncMock()
    ) as handle_income:
        await group_router.handle_group_explicit_entry(message, lang="en")

    handle_income.assert_awaited_once_with(message, 123, "salary +500", "en")


@pytest.mark.asyncio
async def test_leading_mention_of_this_bot_is_parsed_as_expense():
    message = make_message("@Expense_Bot coffee 200")

    with patch("bot.utils.expense_parser.detect_income_intent", return_value=False), patch.object(
        group_router, "_handle_group_expense", AsyncMock()
    ) as handle_expense:
        await group_router.handle_group_explicit_entry(message, lang="en")

    handle_expense.assert_awaited_once_with(message, 123, "coffee 200", "en")


@pytest.mark.asyncio
async def test_bang_after_leading_mention_is_stripped():
    message = make_message("@expense_bot !coffee 200")

    with patch("bot.utils.expense_parser.detect_income_intent", return_value=False), patch.object(
        group_router, "_handle_group_expense", AsyncMock()
    ) as handle_expense:
        await group_router.handle_group_explicit_entry(message, lang="en")

    handle_expense.assert_awaited_once_with(message, 123, "coffee 200", "en")


@pytest.mark.asyncio
async def test_leading_mention_of_other_bot_is_ignored():
    message = make_message("@other_bot coffee 200")

    with patch.object(group_router, "_handle_group_expense", AsyncMock()) as handle_expense:
        await group_router.handle_group_explicit_entry(message, lang="en")

    handle_expense.assert_not_awaited()


@pytest.mark.asyncio
async def test_leading_mention_is_ignored_when_own_username_is_unavailable():
    message = make_message("@expense_bot coffee 200")
    message.bot.me.side_effect = RuntimeError("Telegram unavailable")

    with patch.object(group_router, "_handle_group_expense", AsyncMock()) as handle_expense:
        await group_router.handle_group_explicit_entry(message, lang="en")

    handle_expense.assert_not_awaited()


@pytest.mark.asyncio
async def test_slash_entry_is_not_supported_by_group_router():
    message = make_message("/coffee 200")

    with patch.object(group_router, "_handle_group_expense", AsyncMock()) as handle_expense:
        await group_router.handle_group_explicit_entry(message, lang="en")

    handle_expense.assert_not_awaited()
