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

logger = logging.getLogger(__name__)

router = Router(name='referral')


def get_referral_keyboard(has_code: bool = False):
    """Клавиатура для реферального меню"""
    builder = InlineKeyboardBuilder()
    
    if not has_code:
        builder.button(
            text="🔗 Получить реферальную ссылку",
            callback_data="referral_generate"
        )
    else:
        builder.button(
            text="📋 Скопировать ссылку",
            callback_data="referral_copy"
        )
        builder.button(
            text="📊 Моя статистика",
            callback_data="referral_stats"
        )
    
    builder.button(
        text="◀️ Назад",
        callback_data="menu_main"
    )
    
    builder.adjust(1)
    return builder.as_markup()


async def get_referral_info_text(profile: Profile, bot_username: str) -> tuple[str, bool]:
    """Получить текст с информацией о реферальной программе"""
    # Проверяем, есть ли у пользователя реферальный код
    has_code = bool(profile.referral_code)
    
    if not has_code:
        text = (
            "🎁 <b>Реферальная программа</b>\n\n"
            "Приглашайте друзей и получайте бонусы!\n\n"
            "За каждого друга, который оформит платную подписку, "
            "вы получите <b>30 дней</b> бесплатной подписки.\n\n"
            "Нажмите кнопку ниже, чтобы получить вашу персональную ссылку."
        )
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
        
        text = (
            f"🎁 <b>Ваша реферальная программа</b>\n\n"
            f"Ваша ссылка:\n"
            f"<code>{referral_link}</code>\n\n"
            f"📊 Статистика:\n"
            f"Приглашено друзей: {total_referrals}\n"
            f"Активных подписок: {active_referrals}\n"
            f"Получено бонусов: {total_bonuses} × 30 дней\n\n"
            f"За каждого друга с платной подпиской вы получаете 30 дней бесплатно!"
        )
    
    return text, has_code


@router.callback_query(F.data == "menu_referral")
async def show_referral_menu(callback: CallbackQuery, state: FSMContext):
    """Показать меню реферальной программы"""
    # Проверяем подписку
    has_subscription = await check_subscription(callback.from_user.id)
    if not has_subscription:
        await callback.answer(
            "Реферальная программа доступна только с активной подпиской",
            show_alert=True
        )
        return
    
    profile = await Profile.objects.aget(telegram_id=callback.from_user.id)
    
    # Получаем username бота
    bot_info = await callback.bot.get_me()
    bot_username = bot_info.username
    
    text, has_code = await get_referral_info_text(profile, bot_username)
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_referral_keyboard(has_code),
            parse_mode="HTML"
        )
    except Exception:
        await send_message_with_cleanup(
            callback, 
            state, 
            text, 
            reply_markup=get_referral_keyboard(has_code), 
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
            reply_markup=get_referral_keyboard(has_code),
            parse_mode="HTML"
        )
    except Exception:
        await send_message_with_cleanup(
            callback, 
            state, 
            text, 
            reply_markup=get_referral_keyboard(has_code), 
            parse_mode="HTML"
        )
    
    await callback.answer("✅ Реферальная ссылка создана!")


@router.callback_query(F.data == "referral_copy")
async def copy_referral_link(callback: CallbackQuery):
    """Показать ссылку для копирования"""
    profile = await Profile.objects.aget(telegram_id=callback.from_user.id)
    
    if not profile.referral_code:
        await callback.answer("Сначала создайте реферальную ссылку", show_alert=True)
        return
    
    # Получаем username бота
    bot_info = await callback.bot.get_me()
    bot_username = bot_info.username
    
    referral_link = f"https://t.me/{bot_username}?start=ref_{profile.referral_code}"
    
    # Отправляем ссылку отдельным сообщением для удобного копирования
    await callback.message.answer(
        f"<b>Ваша реферальная ссылка:</b>\n\n"
        f"<code>{referral_link}</code>\n\n"
        f"Нажмите на ссылку, чтобы скопировать её.",
        parse_mode="HTML"
    )
    
    await callback.answer("📋 Ссылка отправлена для копирования")


@router.callback_query(F.data == "referral_stats")
async def show_referral_stats(callback: CallbackQuery, state: FSMContext):
    """Показать детальную статистику рефералов"""
    profile = await Profile.objects.aget(telegram_id=callback.from_user.id)
    
    # Получаем список рефералов
    referrals = profile.referrals.select_related().all()
    
    text = "📊 <b>Детальная статистика рефералов</b>\n\n"
    
    if not await referrals.aexists():
        text += "У вас пока нет приглашенных друзей."
    else:
        async for i, ref in enumerate(referrals, 1):
            # Проверяем подписку реферала
            has_paid_sub = await ref.subscriptions.filter(
                is_active=True,
                type__in=['month', 'six_months']
            ).aexists()
            
            status = "✅ Активная подписка" if has_paid_sub else "⏳ Ожидает подписки"
            
            # Проверяем, получен ли бонус
            bonus = await ReferralBonus.objects.filter(
                referrer=profile,
                referred=ref,
                is_activated=True
            ).afirst()
            
            bonus_text = " (бонус получен)" if bonus else ""
            
            text += f"{i}. {status}{bonus_text}\n"
    
    # Кнопка назад
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад", callback_data="menu_referral")
    
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
        await message.answer(
            "❌ Реферальная программа доступна только с активной подпиской.\n"
            "Оформите подписку, чтобы начать приглашать друзей!",
            parse_mode="HTML"
        )
        return
    
    profile = await Profile.objects.aget(telegram_id=message.from_user.id)
    
    # Получаем username бота
    bot_info = await message.bot.get_me()
    bot_username = bot_info.username
    
    text, has_code = await get_referral_info_text(profile, bot_username)
    
    await send_message_with_cleanup(
        message, 
        state,
        text,
        reply_markup=get_referral_keyboard(has_code),
        parse_mode="HTML"
    )