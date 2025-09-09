"""
Клавиатуры для работы с семейным бюджетом
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.utils import get_text


def get_household_menu_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Клавиатура для пользователей без семейного бюджета"""
    keyboard = [
        [InlineKeyboardButton(text=get_text('create_household_button', lang), callback_data="create_household")],
        [InlineKeyboardButton(text=get_text('back', lang), callback_data="settings")],
        [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_household_settings_keyboard(is_creator: bool = False, lang: str = 'ru') -> InlineKeyboardMarkup:
    """Клавиатура настроек семейного бюджета"""
    keyboard = [
        [InlineKeyboardButton(text=get_text('members_list_button', lang), callback_data="show_members")],
    ]
    
    if is_creator:
        keyboard.insert(0, [InlineKeyboardButton(text=get_text('invite_member_button', lang), callback_data="generate_invite")])
        keyboard.append([InlineKeyboardButton(text=get_text('rename_household_button', lang), callback_data="rename_household")])
    
    keyboard.extend([
        [InlineKeyboardButton(text=get_text('leave_household_button', lang), callback_data="leave_household")],
        [InlineKeyboardButton(text=get_text('back', lang), callback_data="settings")],
        [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_confirm_join_keyboard(action: str, token: str = None, lang: str = 'ru') -> InlineKeyboardMarkup:
    """Клавиатура подтверждения действия"""
    if action == "join":
        keyboard = [
            [
                InlineKeyboardButton(text=get_text('yes_join', lang), callback_data=f"confirm_join:{token}"),
                InlineKeyboardButton(text=get_text('cancel', lang), callback_data="cancel_action")
            ]
        ]
    elif action == "leave":
        keyboard = [
            [
                InlineKeyboardButton(text=get_text('yes_leave', lang), callback_data="confirm_leave"),
                InlineKeyboardButton(text=get_text('cancel', lang), callback_data="household_budget")
            ]
        ]
    else:
        keyboard = []
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_household_members_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Клавиатура для списка участников (только одна кнопка Назад)"""
    keyboard = [
        [InlineKeyboardButton(text=get_text('back', lang), callback_data="household_back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_household_rename_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Клавиатура на шаге ввода нового названия: Назад и Закрыть"""
    keyboard = [
        [InlineKeyboardButton(text=get_text('back', lang), callback_data="household_back")],
        [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_invite_link_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Клавиатура для сообщения со ссылкой-приглашением: Назад и Закрыть"""
    keyboard = [
        [InlineKeyboardButton(text=get_text('back', lang), callback_data="household_budget")],
        [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
