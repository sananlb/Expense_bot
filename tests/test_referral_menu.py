"""Tests for the referral/share bot menu."""

from bot.routers.referral import get_referral_keyboard
from bot.routers.subscription import get_subscription_keyboard


def _callbacks(keyboard) -> list[str | None]:
    return [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
    ]


def test_referral_keyboard_hides_stats_button():
    callbacks = _callbacks(
        get_referral_keyboard(
            lang="ru",
            share_url="https://t.me/test_bot?start=ref_code",
            share_text="Invite text",
        )
    )

    assert "referral_stats" not in callbacks
    assert "referral_rewards" in callbacks
    assert "menu_subscription" in callbacks
    assert "close" in callbacks


def test_subscription_keyboard_still_links_to_referral_menu():
    callbacks = _callbacks(get_subscription_keyboard(is_beta_tester=False, lang="ru"))

    assert "menu_referral" in callbacks
