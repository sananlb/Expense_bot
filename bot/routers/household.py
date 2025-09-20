"""
Роутер для работы с семейным бюджетом
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.services.household import HouseholdService
from asgiref.sync import sync_to_async
from bot.services.profile import get_or_create_profile
from bot.services.subscription import check_subscription
from bot.utils import get_text
from bot.keyboards_household import (
    get_household_menu_keyboard,
    get_household_settings_keyboard,
    get_confirm_join_keyboard,
    get_household_members_keyboard,
    get_invite_link_keyboard,
    get_household_rename_keyboard
)
from bot.services.expense import get_expenses_summary
from datetime import datetime, date, timedelta
import logging

logger = logging.getLogger(__name__)

router = Router(name='household')


class HouseholdStates(StatesGroup):
    """Состояния для работы с семейным бюджетом"""
    waiting_for_household_name = State()
    waiting_for_rename = State()


@router.callback_query(F.data == "household_budget")
async def household_menu(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Главное меню семейного бюджета"""
    await callback.answer()

    has_subscription = await check_subscription(callback.from_user.id)
    if not has_subscription:
        text = get_text('household_subscription_required', lang)
        keyboard = get_household_menu_keyboard(lang, subscription_active=False)
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return

    profile = await get_or_create_profile(callback.from_user.id)

    has_household = await sync_to_async(lambda: bool(profile.household_id))()
    if has_household:
        # Пользователь уже в семейном бюджете — собираем данные через ORM в sync контексте
        household_name, members_count, max_members, is_creator = await sync_to_async(
            lambda default_name=get_text('household_default_name', lang): (
                (profile.household.name or default_name),
                profile.household.members_count,
                profile.household.max_members,
                (profile.household.creator_id == profile.id)
            )
        )()

        text = (
            f"🏠 <b>{household_name}</b>\n\n"
            f"{get_text('household_members_count', lang).format(count=members_count, max=max_members)}\n\n"
            f"{get_text('choose_action', lang)}"
        )
        
        keyboard = get_household_settings_keyboard(is_creator=is_creator, lang=lang)
    else:
        # Пользователь не в семейном бюджете
        text = f"{get_text('household_intro', lang)}\n\n{get_text('choose_action', lang)}"
        keyboard = get_household_menu_keyboard(lang, subscription_active=True)
    
    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "create_household")
async def create_household_start(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Начало создания семейного бюджета"""
    if not await check_subscription(callback.from_user.id):
        await callback.answer(get_text('household_subscription_required', lang).replace('<b>', '').replace('</b>', ''), show_alert=True)
        return

    await callback.answer()

    await callback.message.edit_text(
        get_text('enter_household_name', lang),
        parse_mode="HTML",
        reply_markup=get_household_rename_keyboard(lang)
    )
    
    await state.set_state(HouseholdStates.waiting_for_household_name)


@router.message(HouseholdStates.waiting_for_household_name, ~F.text.startswith('/'))
async def process_household_name(message: Message, state: FSMContext, lang: str = 'ru'):
    """Обработка названия домохозяйства"""
    profile = await get_or_create_profile(message.from_user.id)
    
    success, msg, household = await sync_to_async(HouseholdService.create_household)(
        profile=profile,
        name=message.text
    )
    
    if success:
        # Показываем подменю семейного бюджета вместо сообщения об успехе
        household_name, members_count, max_members, is_creator = await sync_to_async(
            lambda default_name=get_text('household_default_name', lang): (
                (profile.household.name or default_name),
                profile.household.members_count,
                profile.household.max_members,
                (profile.household.creator_id == profile.id)
            )
        )()

        text = (
            f"🏠 <b>{household_name}</b>\n\n"
            f"{get_text('household_members_count', lang).format(count=members_count, max=max_members)}\n\n"
            f"{get_text('choose_action', lang)}"
        )
        keyboard = get_household_settings_keyboard(is_creator=is_creator, lang=lang)
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await message.answer(f"❌ {msg}", parse_mode="HTML")
    
    await state.clear()


@router.callback_query(F.data == "generate_invite")
async def generate_invite(callback: CallbackQuery, lang: str = 'ru'):
    """Генерация ссылки-приглашения"""
    await callback.answer()
    
    profile = await get_or_create_profile(callback.from_user.id)
    bot_info = await callback.bot.get_me()
    
    success, result = await sync_to_async(HouseholdService.generate_invite_link)(
        profile=profile,
        bot_username=bot_info.username
    )
    
    if success:
        await callback.message.edit_text(
            f"{get_text('invite_link_title', lang)}\n\n"
            f"<code>{result}</code>\n\n"
            f"{get_text('invite_link_note', lang)}\n"
            f"{get_text('invite_link_valid', lang)}",
            parse_mode="HTML",
            reply_markup=get_invite_link_keyboard(lang)
        )
    else:
        await callback.message.edit_text(
            f"❌ {result}",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "show_members")
async def show_members(callback: CallbackQuery, lang: str = 'ru'):
    """Показ участников домохозяйства"""
    await callback.answer()
    
    profile = await get_or_create_profile(callback.from_user.id)
    
    has_household = await sync_to_async(lambda: bool(profile.household_id))()
    if not has_household:
        await callback.message.answer(get_text('not_in_household', lang))
        return
    
    members = await sync_to_async(lambda: HouseholdService.get_household_members(profile.household))()
    household_name, max_members, creator_id = await sync_to_async(lambda default_name=get_text('household_default_name', lang): (profile.household.name or default_name, profile.household.max_members, profile.household.creator_id))()
    
    text = f"🏠 <b>{household_name}</b>\n\n"
    text += get_text('household_members_count', lang).format(count=len(members), max=max_members) + "\n\n"
    
    for i, member in enumerate(members, 1):
        status = "👑" if member.id == creator_id else "👤"
        text += f"{i}. {status} {member.telegram_id}\n\n"
    
    keyboard = get_household_members_keyboard(lang)
    
    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "rename_household")
async def rename_household_start(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Начало переименования домохозяйства"""
    await callback.answer()
    
    profile = await get_or_create_profile(callback.from_user.id)
    
    has_household = await sync_to_async(lambda: bool(profile.household_id))()
    if not has_household:
        await callback.message.answer(get_text('not_in_household', lang))
        return
    
    is_creator = await sync_to_async(lambda: profile.household and profile.household.creator_id == profile.id)()
    if not is_creator:
        await callback.message.answer(get_text('only_creator_can_rename', lang))
        return
    
    await callback.message.edit_text(
        get_text('enter_new_household_name', lang),
        parse_mode="HTML",
        reply_markup=get_household_rename_keyboard(lang)
    )
    
    await state.set_state(HouseholdStates.waiting_for_rename)



@router.message(HouseholdStates.waiting_for_rename, ~F.text.startswith('/'))
async def process_rename(message: Message, state: FSMContext, lang: str = 'ru'):
    """Обработка нового названия"""
    profile = await get_or_create_profile(message.from_user.id)
    
    has_household = await sync_to_async(lambda: bool(profile.household_id))()
    if not has_household:
        await message.answer(get_text('not_in_household', lang))
        await state.clear()
        return
    
    # Переименовать может только создатель семьи
    is_creator = await sync_to_async(lambda: profile.household and profile.household.creator_id == profile.id)()
    if not is_creator:
        await message.answer(get_text('only_creator_can_rename', lang))
        await state.clear()
        return
    
    success, msg = await sync_to_async(lambda: HouseholdService.rename_household(profile.household, message.text))()

    if success:
        # Возвращаем в подменю семейного бюджета
        household_name, members_count, max_members, is_creator = await sync_to_async(
            lambda: (
                (profile.household.name or "Семейный бюджет"),
                profile.household.members_count,
                profile.household.max_members,
                (profile.household.creator_id == profile.id)
            )
        )()

        text = (
            f"🏠 <b>{household_name}</b>\n\n"
            f"{get_text('household_members_count', lang).format(count=members_count, max=max_members)}\n\n"
            f"{get_text('choose_action', lang)}"
        )
        keyboard = get_household_settings_keyboard(is_creator=is_creator, lang=lang)
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await message.answer(f"❌ {msg}", parse_mode="HTML")

    await state.clear()


@router.callback_query(F.data == "leave_household")
async def leave_household_confirm(callback: CallbackQuery, lang: str = 'ru'):
    """Подтверждение выхода из домохозяйства"""
    await callback.answer()
    
    await callback.message.edit_text(
        get_text('household_leave_confirm', lang),
        reply_markup=get_confirm_join_keyboard(action="leave", lang=lang),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "confirm_leave")
async def confirm_leave(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Подтверждение выхода"""
    await callback.answer()
    
    profile = await get_or_create_profile(callback.from_user.id)

    # Собираем данные перед выходом, чтобы отправить уведомления
    has_household = await sync_to_async(lambda: bool(profile.household_id))()
    recipients = []
    is_creator = False
    if has_household:
        def collect():
            hh = profile.household
            ids = list(hh.profiles.values_list('telegram_id', flat=True))
            return ids, (hh.creator_id == profile.id)
        recipients, is_creator = await sync_to_async(collect)()
        recipients = [uid for uid in recipients if uid != profile.telegram_id]

    success, msg = await sync_to_async(HouseholdService.leave_household)(profile)

    # Уведомляем участников
    if success and recipients:
        text = (
            get_text('household_disbanded_notification', lang).format(user_id=profile.telegram_id)
            if is_creator else
            get_text('member_left_notification', lang).format(user_id=profile.telegram_id)
        )
        for uid in recipients:
            try:
                await callback.bot.send_message(uid, text)
            except Exception:
                pass

    # Показываем актуальное подменю семейного бюджета
    await household_menu(callback, state, lang)


@router.callback_query(F.data == "cancel_action")
async def cancel_action(callback: CallbackQuery, lang: str = 'ru'):
    """Отмена действия"""
    await callback.answer()
    await callback.message.edit_text(get_text('action_cancelled', lang))


async def process_family_invite(message: Message, token: str):
    """
    Обработка приглашения в семейный бюджет
    Вызывается из start.py при обработке deep-link
    """
    profile = await get_or_create_profile(message.from_user.id)
    
    # Проверяем приглашение
    from expenses.models import FamilyInvite
    invite = await sync_to_async(lambda: FamilyInvite.objects.filter(token=token).first())()
    
    if not invite or not invite.is_valid():
        await message.answer(
            "❌ Приглашение недействительно или истекло",
            parse_mode="HTML"
        )
        return
    
    # Проверяем, не пытается ли пользователь присоединиться к своему же домохозяйству
    inviter_id = await sync_to_async(lambda: invite.inviter_id)()
    if inviter_id == profile.id:
        await message.answer(
            "❌ Вы не можете использовать собственное приглашение",
            parse_mode="HTML"
        )
        return
    
    has_household = await sync_to_async(lambda: bool(profile.household_id))()
    if has_household:
        await message.answer(
            "❌ Вы уже состоите в семейном бюджете.\n"
            "Сначала выйдите из текущего, чтобы присоединиться к новому.",
            parse_mode="HTML"
        )
        return
    
    # Собираем данные домохозяйства синхронно, чтобы не трогать ORM в async
    household_name, members_count, max_members = await sync_to_async(
        lambda: (
            (invite.household.name or "семейному бюджету"),
            invite.household.members_count,
            invite.household.max_members,
        )
    )()
    
    await message.answer(
        f"🏠 <b>Приглашение в </b>\n\n"
        f"Участников: {members_count}/{max_members}\n\n"
        "После присоединения вы будете вести общий учет финансов "
        "с другими участниками.\n\n"
        "Присоединиться?",
        reply_markup=get_confirm_join_keyboard(action="join", token=token, lang='ru'),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("confirm_join:"))
async def confirm_join(callback: CallbackQuery):
    """Подтверждение присоединения к домохозяйству"""
    await callback.answer()
    
    token = callback.data.split(":")[1]
    profile = await get_or_create_profile(callback.from_user.id)
    
    success, msg = await sync_to_async(HouseholdService.join_household)(profile, token)
    
    if success:
        await callback.message.edit_text(
            f"✅ {msg}\n\n"
            "Теперь вы ведете общий учет финансов с другими участниками.",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            f"❌ {msg}",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "household_back")
async def back_to_household_menu(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Возврат в меню домохозяйства с сохранением языка"""
    await household_menu(callback, state, lang)
