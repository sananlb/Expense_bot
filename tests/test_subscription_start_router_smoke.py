from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.routers import start as start_router
from bot.routers import subscription as subscription_router


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
    message.text = "/subscription"
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
    callback.message.text = "menu"
    callback.message.edit_text = AsyncMock()
    callback.message.answer = AsyncMock()
    return callback


@pytest.mark.asyncio
async def test_cmd_subscription_sends_info_text_with_subscription_keyboard():
    message = make_message()
    state = make_state()
    profile = SimpleNamespace(is_beta_tester=False)

    with patch("bot.routers.subscription.Profile.objects.aget", AsyncMock(return_value=profile)), patch(
        "bot.routers.subscription.get_subscription_info_text", AsyncMock(return_value="INFO")
    ) as get_info, patch(
        "bot.routers.subscription.get_subscription_keyboard", return_value="KEYBOARD"
    ) as get_keyboard, patch(
        "bot.routers.subscription.send_message_with_cleanup", AsyncMock()
    ) as send_message:
        await subscription_router.cmd_subscription(message, state, lang="ru")

    get_info.assert_awaited_once_with(profile, "ru")
    get_keyboard.assert_called_once_with(is_beta_tester=False, lang="ru")
    send_message.assert_awaited_once_with(
        message,
        state,
        "INFO",
        reply_markup="KEYBOARD",
        parse_mode="HTML",
    )


@pytest.mark.asyncio
async def test_show_subscription_menu_clears_invoice_state_and_deletes_old_invoice():
    callback = make_callback()
    state = make_state()
    await state.update_data(invoice_msg_id=777)
    profile = SimpleNamespace(is_beta_tester=True)

    with patch("bot.routers.subscription.Profile.objects.aget", AsyncMock(return_value=profile)), patch(
        "bot.routers.subscription.get_subscription_info_text", AsyncMock(return_value="INFO")
    ), patch(
        "bot.routers.subscription.get_subscription_keyboard", return_value="KEYBOARD"
    ), patch(
        "bot.routers.subscription.send_message_with_cleanup", AsyncMock()
    ) as send_message, patch(
        "bot.routers.subscription.safe_delete_message", AsyncMock()
    ) as safe_delete:
        await subscription_router.show_subscription_menu(callback, state, lang="ru")

    data = await state.get_data()
    assert data["invoice_msg_id"] is None
    send_message.assert_awaited_once_with(
        callback.message,
        state,
        "INFO",
        reply_markup="KEYBOARD",
        parse_mode="HTML",
    )
    safe_delete.assert_awaited_once_with(
        bot=callback.bot,
        chat_id=callback.from_user.id,
        message_id=777,
    )
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_ask_promocode_sets_state_and_remembers_new_menu_message():
    callback = make_callback()
    state = make_state()
    promo_message = AsyncMock()
    promo_message.message_id = 909
    callback.message.answer = AsyncMock(return_value=promo_message)

    with patch("bot.routers.subscription.safe_delete_message", AsyncMock()) as safe_delete:
        await subscription_router.ask_promocode(callback, state)

    data = await state.get_data()
    assert data["last_menu_message_id"] == 909
    assert await state.get_state() == subscription_router.PromoCodeStates.waiting_for_promo.state
    safe_delete.assert_awaited_once_with(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
    )
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_offer_decline_uses_profile_language_for_decline_text():
    callback = make_callback()
    state = make_state()
    profile = SimpleNamespace(language_code="en")

    with patch("bot.routers.subscription.Profile.objects.aget", AsyncMock(return_value=profile)), patch(
        "bot.routers.subscription.get_text", side_effect=lambda key, lang="ru", **kwargs: f"{key}:{lang}"
    ):
        await subscription_router.offer_decline(callback, state, lang="ru")

    callback.message.edit_text.assert_awaited_once_with("offer_decline_message:en")
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_privacy_decline_uses_profile_language_for_message_text():
    callback = make_callback()
    profile = SimpleNamespace(language_code="en")

    with patch("bot.routers.start.Profile.objects.aget", AsyncMock(return_value=profile)), patch(
        "bot.routers.start.get_text", side_effect=lambda key, lang="ru", **kwargs: f"{key}:{lang}"
    ):
        await start_router.privacy_decline(callback)

    callback.message.edit_text.assert_awaited_once_with("privacy_decline_message:en")
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_help_main_stores_help_message_id_and_deletes_source_message():
    callback = make_callback()
    state = make_state()
    profile = SimpleNamespace(language_code="en")
    help_message = AsyncMock()
    help_message.message_id = 515
    callback.message.answer = AsyncMock(return_value=help_message)

    with patch("bot.routers.start.Profile.objects.aget", AsyncMock(return_value=profile)), patch(
        "bot.routers.start.get_text", side_effect=lambda key, lang="ru", **kwargs: f"{key}:{lang}"
    ), patch("bot.routers.start.safe_delete_message", AsyncMock()) as safe_delete:
        await start_router.help_main_handler(callback, state, lang="ru")

    data = await state.get_data()
    assert data["help_message_id"] == 515
    callback.message.answer.assert_awaited_once()
    safe_delete.assert_awaited_once_with(message=callback.message)
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_help_back_restores_welcome_message_and_clears_help_message_id():
    callback = make_callback()
    state = make_state()
    await state.update_data(help_message_id=515)
    profile = SimpleNamespace(language_code="en", currency="USD")

    with patch("bot.routers.start.Profile.objects.aget", AsyncMock(return_value=profile)), patch(
        "bot.routers.start.get_welcome_message", return_value="WELCOME"
    ) as get_welcome:
        await start_router.help_back_handler(callback, state, lang="ru")

    data = await state.get_data()
    assert data["help_message_id"] is None
    get_welcome.assert_called_once_with("en", currency="USD")
    callback.message.edit_text.assert_awaited_once()
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_callback_start_falls_back_to_new_message_when_edit_fails():
    callback = make_callback()
    state = make_state()
    callback.message.edit_text.side_effect = RuntimeError("edit failed")
    profile = SimpleNamespace(currency="USD")

    with patch("bot.routers.start.update_user_commands", AsyncMock()) as update_commands, patch(
        "bot.routers.start.Profile.objects.aget", AsyncMock(return_value=profile)
    ), patch(
        "bot.routers.start.get_welcome_message", return_value="WELCOME"
    ) as get_welcome, patch(
        "bot.routers.start.send_message_with_cleanup", AsyncMock()
    ) as send_message:
        await start_router.callback_start(callback, state, lang="en")

    update_commands.assert_awaited_once_with(callback.bot, callback.from_user.id)
    get_welcome.assert_called_once_with("en", currency="USD")
    send_message.assert_awaited_once_with(callback, state, "WELCOME", parse_mode="HTML")
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_privacy_accept_creates_profile_trial_and_clears_pending_state_for_new_user():
    callback = make_callback()
    state = make_state()
    await state.update_data(
        start_command_args="utm_campaign=spring",
        pending_profile_data={
            "language_code": "en",
            "raw_language_code": "en-US",
        },
    )
    profile_subscriptions = SimpleNamespace(
        filter=Mock(
            side_effect=[
                SimpleNamespace(aexists=AsyncMock(return_value=False)),
                SimpleNamespace(aexists=AsyncMock(return_value=False)),
            ]
        )
    )
    profile = SimpleNamespace(
        language_code=None,
        accepted_privacy=False,
        is_beta_tester=False,
        currency="USD",
        subscriptions=profile_subscriptions,
        asave=AsyncMock(),
    )

    with patch(
        "bot.routers.start.Profile.objects.aget",
        AsyncMock(side_effect=start_router.Profile.DoesNotExist),
    ), patch(
        "bot.routers.start.get_or_create_profile", AsyncMock(return_value=profile)
    ) as get_or_create_profile, patch(
        "bot.routers.start.parse_utm_source", AsyncMock(return_value={"utm_campaign": "spring"})
    ) as parse_utm_source, patch(
        "bot.routers.start.save_utm_data", AsyncMock()
    ) as save_utm_data, patch(
        "bot.routers.start.safe_delete_message", AsyncMock()
    ) as safe_delete_message, patch(
        "bot.routers.start.create_default_categories", AsyncMock()
    ) as create_default_categories, patch(
        "bot.routers.start.create_default_income_categories", AsyncMock()
    ) as create_default_income_categories, patch(
        "bot.routers.start.Subscription.objects.filter",
        return_value=SimpleNamespace(aexists=AsyncMock(return_value=False)),
    ), patch(
        "bot.routers.start.Subscription.objects.acreate", AsyncMock()
    ) as create_subscription, patch(
        "bot.routers.start.update_user_commands", AsyncMock()
    ) as update_user_commands, patch(
        "bot.routers.start.get_welcome_message", return_value="WELCOME"
    ) as get_welcome_message:
        await start_router.privacy_accept(callback, state)

    get_or_create_profile.assert_awaited_once_with(
        telegram_id=callback.from_user.id,
        language_code="en",
    )
    parse_utm_source.assert_awaited_once_with("utm_campaign=spring")
    save_utm_data.assert_awaited_once_with(profile, {"utm_campaign": "spring"})
    safe_delete_message.assert_awaited_once_with(message=callback.message)
    create_default_categories.assert_awaited_once_with(callback.from_user.id)
    create_default_income_categories.assert_awaited_once_with(callback.from_user.id)
    create_subscription.assert_awaited_once()
    update_user_commands.assert_awaited_once_with(callback.bot, callback.from_user.id)
    get_welcome_message.assert_called_once_with("en", "", "USD")
    callback.message.answer.assert_awaited_once_with("WELCOME", parse_mode="HTML")
    callback.answer.assert_awaited_once_with("Согласие принято")

    data = await state.get_data()
    assert data["start_command_args"] is None
    assert data["pending_profile_data"] is None
    assert profile.language_code == "en"
    assert profile.accepted_privacy is True
    profile.asave.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_stars_invoice_stores_invoice_message_id_and_deletes_previous_message():
    callback = make_callback()
    state = make_state()
    profile = SimpleNamespace(language_code="en")
    invoice_message = SimpleNamespace(message_id=333)
    callback.bot.send_invoice = AsyncMock(return_value=invoice_message)

    with patch("bot.routers.subscription.Profile.objects.aget", AsyncMock(return_value=profile)), patch(
        "bot.routers.subscription.safe_delete_message", AsyncMock()
    ) as safe_delete_message:
        await subscription_router.send_stars_invoice(callback, state, "month")

    callback.bot.send_invoice.assert_awaited_once()
    send_invoice_kwargs = callback.bot.send_invoice.await_args.kwargs
    assert send_invoice_kwargs["chat_id"] == callback.from_user.id
    assert send_invoice_kwargs["title"] == "💎 Premium for 1 month"
    assert send_invoice_kwargs["payload"] == f"subscription_month_{callback.from_user.id}"
    assert send_invoice_kwargs["currency"] == "XTR"
    assert send_invoice_kwargs["start_parameter"] == "sub_month"
    assert send_invoice_kwargs["prices"][0].label == "Pay"
    assert send_invoice_kwargs["prices"][0].amount == 150
    safe_delete_message.assert_awaited_once_with(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
    )
    callback.answer.assert_awaited_once()

    data = await state.get_data()
    assert data["invoice_msg_id"] == 333


@pytest.mark.asyncio
async def test_process_subscription_purchase_shows_offer_acceptance_before_invoice():
    callback = make_callback()
    state = make_state()
    callback.data = "subscription_buy_month"
    profile = SimpleNamespace(language_code="en", accepted_offer=False)

    with patch("bot.routers.subscription.Profile.objects.aget", AsyncMock(return_value=profile)), patch(
        "bot.routers.subscription.get_text",
        side_effect=lambda key, lang="ru", **kwargs: f"{key}:{lang}",
    ), patch(
        "bot.routers.subscription.get_offer_url_for", return_value="https://example.com/offer"
    ), patch(
        "bot.routers.subscription.send_stars_invoice", AsyncMock()
    ) as send_stars_invoice:
        await subscription_router.process_subscription_purchase(callback, state)

    send_stars_invoice.assert_not_awaited()
    callback.message.edit_text.assert_awaited_once()
    edit_text_args = callback.message.edit_text.await_args
    assert "short_offer_for_acceptance:en" in edit_text_args.args[0]
    assert "https://example.com/offer" in edit_text_args.args[0]
    assert edit_text_args.kwargs["parse_mode"] == "HTML"
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_subscription_purchase_sends_invoice_when_offer_is_already_accepted():
    callback = make_callback()
    state = make_state()
    callback.data = "subscription_buy_six_months"
    profile = SimpleNamespace(language_code="ru", accepted_offer=True)

    with patch("bot.routers.subscription.Profile.objects.aget", AsyncMock(return_value=profile)), patch(
        "bot.routers.subscription.send_stars_invoice", AsyncMock()
    ) as send_stars_invoice:
        await subscription_router.process_subscription_purchase(callback, state)

    send_stars_invoice.assert_awaited_once_with(callback, state, "six_months")
    callback.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_promocode_with_missing_code_clears_state_and_restores_menu_in_profile_language():
    message = make_message()
    message.text = "MISSING"
    state = make_state()
    await state.set_state(subscription_router.PromoCodeStates.waiting_for_promo)
    profile = SimpleNamespace(language_code="en")

    with patch("bot.routers.subscription.Profile.objects.aget", AsyncMock(return_value=profile)), patch(
        "bot.routers.subscription.PromoCode.objects.filter",
        return_value=SimpleNamespace(afirst=AsyncMock(return_value=None)),
    ), patch(
        "bot.routers.subscription.get_subscription_info_text", AsyncMock(return_value="INFO")
    ) as get_subscription_info_text, patch(
        "bot.routers.subscription.get_subscription_keyboard", return_value="KEYBOARD"
    ) as get_subscription_keyboard, patch(
        "bot.routers.subscription.send_message_with_cleanup", AsyncMock()
    ) as send_message_with_cleanup:
        await subscription_router.process_promocode(message, state)

    message.answer.assert_awaited_once_with(
        "❌ <b>Промокод не найден</b>\n\nПроверьте правильность ввода и попробуйте снова.",
        parse_mode="HTML",
    )
    get_subscription_info_text.assert_awaited_once_with(profile, "en")
    get_subscription_keyboard.assert_called_once_with(lang="en")
    send_message_with_cleanup.assert_awaited_once_with(
        message,
        state,
        "INFO",
        reply_markup="KEYBOARD",
        parse_mode="HTML",
    )
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_process_promocode_rejects_reused_code_and_restores_menu():
    message = make_message()
    message.text = "USED-CODE"
    state = make_state()
    await state.set_state(subscription_router.PromoCodeStates.waiting_for_promo)
    profile = SimpleNamespace(id=1, language_code="ru")
    promocode = SimpleNamespace(id=77)

    with patch("bot.routers.subscription.Profile.objects.aget", AsyncMock(return_value=profile)), patch(
        "bot.routers.subscription.PromoCode.objects.filter",
        return_value=SimpleNamespace(afirst=AsyncMock(return_value=promocode)),
    ), patch(
        "bot.routers.subscription.validate_promocode_for_checkout",
        AsyncMock(side_effect=subscription_router.PromoCodeValidationError("already_used")),
    ), patch(
        "bot.routers.subscription.get_subscription_info_text", AsyncMock(return_value="INFO")
    ) as get_subscription_info_text, patch(
        "bot.routers.subscription.get_subscription_keyboard", return_value="KEYBOARD"
    ) as get_subscription_keyboard, patch(
        "bot.routers.subscription.send_message_with_cleanup", AsyncMock()
    ) as send_message_with_cleanup:
        await subscription_router.process_promocode(message, state)

    message.answer.assert_awaited_once_with(
        "❌ <b>Вы уже использовали этот промокод</b>\n\nКаждый промокод можно использовать только один раз.",
        parse_mode="HTML",
    )
    get_subscription_info_text.assert_awaited_once_with(profile, "ru")
    get_subscription_keyboard.assert_called_once_with(lang="ru")
    send_message_with_cleanup.assert_awaited_once_with(
        message,
        state,
        "INFO",
        reply_markup="KEYBOARD",
        parse_mode="HTML",
    )
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_process_promocode_days_promo_creates_subscription_records_usage_and_clears_state():
    message = make_message()
    message.text = "BONUS30"
    state = make_state()
    await state.set_state(subscription_router.PromoCodeStates.waiting_for_promo)
    profile = SimpleNamespace(id=1, language_code="ru")
    promocode = SimpleNamespace(
        id=55,
        discount_type="days",
        discount_value=30,
        is_valid=Mock(return_value=True),
    )
    subscription = SimpleNamespace(end_date=SimpleNamespace(strftime=Mock(return_value="15.04.2026")))

    with patch("bot.routers.subscription.Profile.objects.aget", AsyncMock(return_value=profile)), patch(
        "bot.routers.subscription.PromoCode.objects.filter",
        return_value=SimpleNamespace(afirst=AsyncMock(return_value=promocode)),
    ), patch(
        "bot.routers.subscription.validate_promocode_for_checkout",
        AsyncMock(return_value=promocode),
    ), patch(
        "bot.routers.subscription.apply_promocode_grant", AsyncMock(return_value=subscription)
    ) as apply_promocode_grant:
        await subscription_router.process_promocode(message, state)

    apply_promocode_grant.assert_awaited_once_with(
        profile.id,
        promocode.id,
        sub_type="month",
        days_to_add=30,
    )
    message.answer.assert_awaited_once()
    answer_text = message.answer.await_args.args[0]
    assert "30 дней подписки" in answer_text
    assert "15.04.2026" in answer_text
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_process_promocode_discount_promo_keeps_active_promocode_in_state_for_followup_purchase():
    message = make_message()
    message.text = "SAVE20"
    state = make_state()
    await state.set_state(subscription_router.PromoCodeStates.waiting_for_promo)
    profile = SimpleNamespace(id=1, language_code="ru")
    promocode = SimpleNamespace(
        id=77,
        code="SAVE20",
        discount_type="percent",
        applicable_subscription_types="all",
        is_valid=Mock(return_value=True),
        apply_discount=Mock(side_effect=lambda price: price - 20),
        get_discount_display=Mock(return_value="-20 stars"),
    )

    with patch("bot.routers.subscription.Profile.objects.aget", AsyncMock(return_value=profile)), patch(
        "bot.routers.subscription.PromoCode.objects.filter",
        return_value=SimpleNamespace(afirst=AsyncMock(return_value=promocode)),
    ), patch(
        "bot.routers.subscription.validate_promocode_for_checkout",
        AsyncMock(return_value=promocode),
    ):
        await subscription_router.process_promocode(message, state)

    data = await state.get_data()
    assert data["active_promocode"] == 77
    assert await state.get_state() == subscription_router.PromoCodeStates.waiting_for_promo.state
    message.answer.assert_awaited_once()
    answer_text = message.answer.await_args.args[0]
    assert "Промокод: SAVE20" in answer_text
    assert "Скидка: -20 stars" in answer_text


@pytest.mark.asyncio
async def test_process_subscription_purchase_with_promo_rejects_missing_active_promocode():
    callback = make_callback()
    state = make_state()
    callback.data = "subscription_buy_month_promo"

    await subscription_router.process_subscription_purchase_with_promo(callback, state)

    callback.answer.assert_awaited_once_with("Промокод не найден", show_alert=True)


@pytest.mark.asyncio
async def test_process_subscription_purchase_with_promo_handles_free_month_subscription_without_invoice():
    callback = make_callback()
    state = make_state()
    callback.data = "subscription_buy_month_promo"
    await state.update_data(active_promocode=77)
    promocode = SimpleNamespace(
        id=77,
        code="FREE100",
        apply_discount=Mock(return_value=0),
    )
    subscription = SimpleNamespace(end_date=SimpleNamespace(strftime=Mock(return_value="20.04.2026")))
    profile = SimpleNamespace(id=1)

    with patch("bot.routers.subscription.Profile.objects.aget", AsyncMock(return_value=profile)), patch(
        "bot.routers.subscription.validate_promocode_for_checkout", AsyncMock(return_value=promocode)
    ), patch(
        "bot.routers.subscription.apply_promocode_grant", AsyncMock(return_value=subscription)
    ) as apply_promocode_grant, patch(
        "bot.routers.subscription.safe_delete_message", AsyncMock()
    ) as safe_delete_message:
        await subscription_router.process_subscription_purchase_with_promo(callback, state)

    callback.answer.assert_awaited_once()
    callback.bot.send_invoice.assert_not_called()
    callback.bot.send_message.assert_awaited_once()
    send_message_kwargs = callback.bot.send_message.await_args.kwargs
    assert send_message_kwargs["chat_id"] == callback.from_user.id
    assert "На месяц (бесплатно)" in send_message_kwargs["text"]
    assert "20.04.2026" in send_message_kwargs["text"]
    apply_promocode_grant.assert_awaited_once_with(
        profile.id,
        promocode.id,
        sub_type="month",
        days_to_add=30,
    )
    safe_delete_message.assert_awaited_once_with(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
    )
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_process_subscription_purchase_with_promo_sends_discounted_invoice_and_keeps_state():
    callback = make_callback()
    state = make_state()
    callback.data = "subscription_buy_six_months_promo"
    await state.update_data(active_promocode=88)
    profile = SimpleNamespace(id=1)
    promocode = SimpleNamespace(
        id=88,
        code="SAVE20",
        apply_discount=Mock(return_value=580),
        get_discount_display=Mock(return_value="-20 stars"),
    )
    invoice_message = SimpleNamespace(message_id=444)
    callback.bot.send_invoice = AsyncMock(return_value=invoice_message)

    with patch("bot.routers.subscription.Profile.objects.aget", AsyncMock(return_value=profile)), patch(
        "bot.routers.subscription.validate_promocode_for_checkout", AsyncMock(return_value=promocode)
    ), patch(
        "bot.routers.subscription.safe_delete_message", AsyncMock()
    ) as safe_delete_message:
        await subscription_router.process_subscription_purchase_with_promo(callback, state)

    callback.answer.assert_awaited_once()
    callback.bot.send_invoice.assert_awaited_once()
    send_invoice_kwargs = callback.bot.send_invoice.await_args.kwargs
    assert send_invoice_kwargs["chat_id"] == callback.from_user.id
    assert send_invoice_kwargs["title"] == "💎 Premium на 6 месяцев (со скидкой)"
    assert send_invoice_kwargs["payload"] == f"subscription_six_months_{callback.from_user.id}_promo_88"
    assert send_invoice_kwargs["start_parameter"] == "sub_six_months_promo"
    assert send_invoice_kwargs["prices"][0].amount == 580
    assert "-20 stars" in send_invoice_kwargs["description"]
    safe_delete_message.assert_awaited_once_with(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
    )

    data = await state.get_data()
    assert data["active_promocode"] == 88
    assert data["invoice_msg_id"] == 444


@pytest.mark.asyncio
async def test_process_subscription_purchase_with_promo_rejects_invalid_promocode_before_invoice():
    callback = make_callback()
    state = make_state()
    callback.data = "subscription_buy_month_promo"
    await state.update_data(active_promocode=77)
    profile = SimpleNamespace(id=1)

    with patch("bot.routers.subscription.Profile.objects.aget", AsyncMock(return_value=profile)), patch(
        "bot.routers.subscription.validate_promocode_for_checkout",
        AsyncMock(side_effect=subscription_router.PromoCodeValidationError("invalid")),
    ):
        await subscription_router.process_subscription_purchase_with_promo(callback, state)

    callback.answer.assert_awaited_once_with("Промокод недействителен.", show_alert=True)
    callback.bot.send_invoice.assert_not_called()


@pytest.mark.asyncio
async def test_process_subscription_purchase_with_free_promo_handles_race_without_double_callback_answer():
    callback = make_callback()
    state = make_state()
    callback.data = "subscription_buy_month_promo"
    await state.update_data(active_promocode=77)
    profile = SimpleNamespace(id=1)
    promocode = SimpleNamespace(
        id=77,
        code="FREE100",
        apply_discount=Mock(return_value=0),
    )

    with patch("bot.routers.subscription.Profile.objects.aget", AsyncMock(return_value=profile)), patch(
        "bot.routers.subscription.validate_promocode_for_checkout", AsyncMock(return_value=promocode)
    ), patch(
        "bot.routers.subscription.apply_promocode_grant",
        AsyncMock(side_effect=subscription_router.PromoCodeValidationError("invalid")),
    ):
        await subscription_router.process_subscription_purchase_with_promo(callback, state)

    callback.answer.assert_awaited_once_with("Промокод недействителен.", show_alert=True)
    callback.bot.send_message.assert_not_called()
    callback.bot.send_invoice.assert_not_called()


@pytest.mark.asyncio
async def test_pre_checkout_with_invalid_promo_is_rejected():
    pre_checkout_query = AsyncMock()
    pre_checkout_query.invoice_payload = "subscription_month_123456789_promo_77"
    pre_checkout_query.from_user = SimpleNamespace(id=123456789)
    profile = SimpleNamespace(id=1)

    with patch("bot.routers.subscription.Profile.objects.aget", AsyncMock(return_value=profile)), patch(
        "bot.routers.subscription.validate_promocode_for_checkout",
        AsyncMock(side_effect=subscription_router.PromoCodeValidationError("invalid")),
    ):
        await subscription_router.process_pre_checkout_updated(pre_checkout_query)

    pre_checkout_query.answer.assert_awaited_once_with(ok=False, error_message="Промокод недействителен.")
