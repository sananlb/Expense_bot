"""
Router for family (household) budget
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from asgiref.sync import sync_to_async
import logging

from expenses.models import Profile
from bot.utils import get_text, get_user_language
from bot.utils.message_utils import send_message_with_cleanup
from bot.services.family import generate_family_invite, get_invite_by_token, accept_invite

logger = logging.getLogger(__name__)

router = Router(name="family")


def family_menu_keyboard(has_link: bool, lang: str = 'ru'):
    b = InlineKeyboardBuilder()
    if not has_link:
        b.button(text=get_text('family_generate_link', lang), callback_data="family_generate")
    else:
        b.button(text=get_text('family_copy_link', lang), callback_data="family_copy")
    b.button(text=get_text('back', lang), callback_data="settings")
    b.button(text=get_text('close', lang), callback_data="close")
    b.adjust(1, 2)
    return b.as_markup()


@router.callback_query(F.data == "menu_family")
async def show_family_menu(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    profile = await Profile.objects.aget(telegram_id=user_id)

    # show info text and generate/copy link button
    # We don't persist a permanent link; generate on demand
    has_link = False
    text = get_text('family_budget_info', lang)
    if profile.household_id:
        # show current members count
        members = Profile.objects.filter(household_id=profile.household_id)
        count = await members.acount()
        text += "\n\n" + get_text('family_members_count', lang).format(count=count)

    try:
        await callback.message.edit_text(text, reply_markup=family_menu_keyboard(has_link, lang), parse_mode="HTML")
    except Exception:
        await send_message_with_cleanup(callback, state, text, reply_markup=family_menu_keyboard(has_link, lang), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "family_generate")
async def family_generate(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)

    invite = await generate_family_invite(user_id)
    bot_info = await callback.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=family_{invite.token}"

    await callback.message.answer(get_text('family_link_created', lang).format(link=link), parse_mode="HTML")
    await callback.answer(get_text('link_sent_for_copy', lang))


@router.callback_query(F.data == "family_copy")
async def family_copy(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    # generate a new link for safety
    invite = await generate_family_invite(user_id)
    bot_info = await callback.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=family_{invite.token}"
    await callback.message.answer(get_text('family_link_created', lang).format(link=link), parse_mode="HTML")
    await callback.answer(get_text('link_sent_for_copy', lang))


@router.callback_query(F.data.startswith("family_accept:"))
async def family_accept(callback: CallbackQuery):
    token = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)

    success, code = await accept_invite(user_id, token)
    if success:
        await callback.answer(get_text('family_joined_success', lang), show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    else:
        key = 'family_already_in_same' if code == 'already_in_same' else 'family_invite_invalid'
        await callback.answer(get_text(key, lang), show_alert=True)

