"""
Роутер для реферальной системы
"""
from aiogram import Router, F, types
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging

from expenses.models import Profile, ReferralBonus
from bot.utils.message_utils import send_message_with_cleanup
from bot.services.subscription import check_subscription
from bot.utils import get_user_language, get_text

logger = logging.getLogger(__name__)

router = Router(name='referral')


def get_referral_keyboard(has_code: bool = False, lang: str = 'ru'):
    """Клавиатура для реферального меню"""
    builder = InlineKeyboardBuilder()
    
    if not has_code:
        builder.button(
            text=get_text('get_referral_link', lang),
            callback_data="referral_generate"
        )
    else:
        builder.button(
            text=get_text('copy_link', lang),
            callback_data="referral_copy"
        )
        builder.button(
            text=get_text('my_statistics', lang),
            callback_data="referral_stats"
        )
    
    builder.button(
        text=get_text('close', lang),
        callback_data="close"
    )
    
    builder.adjust(1)
    return builder.as_markup()


async def get_referral_info_text(profile: Profile, bot_username: str, lang: str = 'ru') -> tuple[str, bool]:
    """Получить текст с информацией о реферальной программе"""
    # Проверяем, есть ли у пользователя реферальный код
    has_code = bool(profile.referral_code)
    
    if not has_code:
        text = get_text('referral_program_text', lang)
    else:
        # Формируем ссылку
        referral_link = f"https://t.me/{bot_username}?start=ref_{profile.referral_code}"
        
        # Получаем статистику
        total_referrals = await profile.referrals.acount()
        active_referrals = await profile.referrals.filter(
            subscriptions__is_active=True,
            subscriptions__type__in=['month', 'six_months']
        ).distinct().acount()
        
        # Получаем бонусы
        total_bonuses = await ReferralBonus.objects.filter(
            referrer=profile,
            is_activated=True
        ).acount()
        
        text = get_text('referral_your_program', lang).format(
            link=referral_link,
            total_referrals=total_referrals,
            active_referrals=active_referrals,
            total_bonuses=total_bonuses
        )
    
    return text, has_code


@router.callback_query(F.data == "menu_referral")
async def show_referral_menu(callback: CallbackQuery, state: FSMContext):
    """Показать меню реферальной программы"""
    # Проверяем подписку
    has_subscription = await check_subscription(callback.from_user.id)
    if not has_subscription:
        lang = await get_user_language(callback.from_user.id)
        await callback.answer(
            get_text('referral_subscription_required', lang),
            show_alert=True
        )
        return
    
    profile = await Profile.objects.aget(telegram_id=callback.from_user.id)
    
    # Получаем username бота
    bot_info = await callback.bot.get_me()
    bot_username = bot_info.username
    
    lang = await get_user_language(callback.from_user.id)
    text, has_code = await get_referral_info_text(profile, bot_username, lang)
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_referral_keyboard(has_code, lang),
            parse_mode="HTML"
        )
    except Exception:
        await send_message_with_cleanup(
            callback, 
            state, 
            text, 
            reply_markup=get_referral_keyboard(has_code, lang), 
            parse_mode="HTML"
        )
    
    await callback.answer()


@router.callback_query(F.data == "referral_generate")
async def generate_referral_code(callback: CallbackQuery, state: FSMContext):
    """Генерация реферального кода"""
    profile = await Profile.objects.aget(telegram_id=callback.from_user.id)
    
    # Генерируем код
    profile.generate_referral_code()
    
    # Получаем username бота
    bot_info = await callback.bot.get_me()
    bot_username = bot_info.username
    
    # Обновляем сообщение
    text, has_code = await get_referral_info_text(profile, bot_username)
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_referral_keyboard(has_code, lang),
            parse_mode="HTML"
        )
    except Exception:
        await send_message_with_cleanup(
            callback, 
            state, 
            text, 
            reply_markup=get_referral_keyboard(has_code, lang), 
            parse_mode="HTML"
        )
    
    await callback.answer(get_text('referral_link_created', lang))


@router.callback_query(F.data == "referral_copy")
async def copy_referral_link(callback: CallbackQuery):
    """Показать ссылку для копирования"""
    profile = await Profile.objects.aget(telegram_id=callback.from_user.id)
    
    lang = await get_user_language(callback.from_user.id)
    if not profile.referral_code:
        await callback.answer(get_text('create_referral_first', lang), show_alert=True)
        return
    
    # Получаем username бота
    bot_info = await callback.bot.get_me()
    bot_username = bot_info.username
    
    referral_link = f"https://t.me/{bot_username}?start=ref_{profile.referral_code}"
    
    # Отправляем ссылку отдельным сообщением для удобного копирования
    await callback.message.answer(
        get_text('your_referral_link', lang).format(link=referral_link),
        parse_mode="HTML"
    )
    
    await callback.answer(get_text('link_sent_for_copy', lang))


@router.callback_query(F.data == "referral_stats")
async def show_referral_stats(callback: CallbackQuery, state: FSMContext):
    """Показать детальную статистику рефералов"""
    profile = await Profile.objects.aget(telegram_id=callback.from_user.id)
    
    # Получаем список рефералов
    referrals = profile.referrals.select_related().all()
    
    lang = await get_user_language(callback.from_user.id)
    text = get_text('referral_stats_title', lang) + "\n\n"
    
    if not await referrals.aexists():
        text += get_text('no_referrals_yet', lang)
    else:
        async for i, ref in enumerate(referrals, 1):
            # Проверяем подписку реферала
            has_paid_sub = await ref.subscriptions.filter(
                is_active=True,
                type__in=['month', 'six_months']
            ).aexists()
            
            status = get_text('active_subscription', lang) if has_paid_sub else get_text('waiting_subscription', lang)
            
            # Проверяем, получен ли бонус
            bonus = await ReferralBonus.objects.filter(
                referrer=profile,
                referred=ref,
                is_activated=True
            ).afirst()
            
            bonus_text = get_text('bonus_received', lang) if bonus else ""
            
            text += f"{i}. {status}{bonus_text}\n"
    
    # Кнопка назад
    builder = InlineKeyboardBuilder()
    builder.button(text=get_text('back', lang), callback_data="menu_referral")
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    except Exception:
        await send_message_with_cleanup(
            callback,
            state,
            text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    
    await callback.answer()


@router.message(Command("referral"))
async def cmd_referral(message: Message, state: FSMContext):
    """Команда для просмотра реферальной программы"""
    # Проверяем подписку
    has_subscription = await check_subscription(message.from_user.id)
    if not has_subscription:
        lang = await get_user_language(message.from_user.id)
        await message.answer(
            get_text('referral_sub_required_full', lang),
            parse_mode="HTML"
        )
        return
    
    profile = await Profile.objects.aget(telegram_id=message.from_user.id)
    
    # Получаем username бота
    bot_info = await message.bot.get_me()
    bot_username = bot_info.username
    
    lang = await get_user_language(message.from_user.id)
    text, has_code = await get_referral_info_text(profile, bot_username, lang)
    
    await send_message_with_cleanup(
        message, 
        state,
        text,
        reply_markup=get_referral_keyboard(has_code),
        parse_mode="HTML"
    )