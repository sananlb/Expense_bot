from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List


# Shared default icon grid for categories (used for both expense and income)
DEFAULT_ICON_GRID: List[List[str]] = [
    ['💰', '💵', '💳', '💸', '🏦'],
    ['🛒', '🍽️', '☕', '🍕', '👪'],
    ['🚗', '🚕', '🚌', '✈️', '⛽'],
    ['🏠', '💡', '🔧', '🛠️', '🏡'],
    ['👕', '👟', '👜', '💄', '💍'],
    ['💊', '🏥', '💉', '🩺', '🏋️'],
    ['📱', '💻', '🎮', '📷', '🎧'],
    ['🎭', '🎬', '🎪', '🎨', '🎯'],
    ['📚', '✏️', '🎓', '📖', '🖊️'],
    ['🎁', '🎉', '🎂', '💐', '🎈']
]


def get_default_icons() -> List[List[str]]:
    return DEFAULT_ICON_GRID


def build_icon_keyboard(
    *,
    back_callback: str,
    include_no_icon: bool = True,
    include_custom_icon: bool = True,
) -> InlineKeyboardMarkup:
    """Builds an icon selection keyboard with unified callbacks.

    - Buttons for icons use callback_data: `set_icon_<emoji>`
    - Optional trailing rows for `no_icon` and `custom_icon`
    - Always appends a Back button with provided callback
    """
    keyboard_buttons: List[List[InlineKeyboardButton]] = []

    for row in get_default_icons():
        buttons_row = [InlineKeyboardButton(text=icon, callback_data=f"set_icon_{icon}") for icon in row]
        keyboard_buttons.append(buttons_row)

    if include_no_icon:
        keyboard_buttons.append([InlineKeyboardButton(text="➡️ Без иконки", callback_data="no_icon")])
    if include_custom_icon:
        keyboard_buttons.append([InlineKeyboardButton(text="✏️ Ввести свой эмодзи", callback_data="custom_icon")])

    keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)])

    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

