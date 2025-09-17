"""
Роутер для партнерской программы Telegram Stars
"""
from aiogram import Router, F, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q, Sum, Count
from asgiref.sync import sync_to_async

from expenses.models import Profile, AffiliateLink, AffiliateReferral, AffiliateCommission, AffiliateProgram
from bot.utils.message_utils import send_message_with_cleanup
from bot.services.subscription import check_subscription
from bot.utils import get_user_language, get_text
from bot.services.affiliate import (
    get_or_create_affiliate_link,
    get_referrer_stats,
    get_commission_history,
    get_or_create_affiliate_program
)

logger = logging.getLogger(__name__)

router = Router(name='referral')


def get_referral_keyboard(lang: str = 'ru'):
    """Клавиатура для партнерской программы"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="📊 Подробная статистика" if lang == 'ru' else "📊 Detailed statistics",
        callback_data="referral_stats"
    )
    builder.button(
        text="📅 История выплат" if lang == 'ru' else "📅 Payment history",
        callback_data="referral_commissions"
    )
    builder.button(
        text=get_text('close', lang),
        callback_data="close"
    )

    builder.adjust(1)
    return builder.as_markup()


async def get_referral_info_text(profile: Profile, bot_username: str, lang: str = 'ru') -> tuple[str, bool]:
    """Получить текст с информацией о партнерской программе Telegram Stars"""
    # Получаем или создаем партнерскую ссылку
    affiliate_link = await get_or_create_affiliate_link(profile.telegram_id, bot_username)

    # Получаем программу
    affiliate_program = await get_or_create_affiliate_program(commission_percent=50)

    # Получаем статистику
    stats = await get_referrer_stats(profile.telegram_id)

    if lang == 'en':
        text = (
            f"🌟 <b>Partner Program</b>\n\n"
            f"Your referral link:\n"
            f"<code>{affiliate_link.telegram_link}</code>\n\n"
            f"📊 <b>Your statistics:</b>\n"
            f"• Users attracted: {stats['referrals_count']}\n"
            f"• Paid subscriptions: {stats['active_referrals']}\n"
            f"• Earned: {stats['total_earned']} ⭐\n"
            f"• Pending: {stats['pending_amount']} ⭐\n\n"
            f"💡 Share your link and earn {affiliate_program.get_commission_percent()}% commission in Telegram Stars!"
        )
    else:
        text = (
            f"🌟 <b>Партнёрская программа</b>\n\n"
            f"Ваша реферальная ссылка:\n"
            f"<code>{affiliate_link.telegram_link}</code>\n\n"
            f"📊 <b>Ваша статистика:</b>\n"
            f"• Привлечено пользователей: {stats['referrals_count']}\n"
            f"• Оплатили подписку: {stats['active_referrals']}\n"
            f"• Заработано: {stats['total_earned']} ⭐\n"
            f"• В ожидании: {stats['pending_amount']} ⭐\n\n"
            f"💡 Делитесь ссылкой и получайте {affiliate_program.get_commission_percent()}% комиссии звёздами Telegram!"
        )

    return text, True  # Всегда есть код, так как создаём автоматически


@router.callback_query(F.data == "menu_referral")
async def show_referral_menu(callback: CallbackQuery, state: FSMContext):
    """Показать меню партнерской программы"""
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
            reply_markup=get_referral_keyboard(lang),
            parse_mode="HTML"
        )
    except Exception:
        await send_message_with_cleanup(
            callback,
            state,
            text,
            reply_markup=get_referral_keyboard(lang),
            parse_mode="HTML"
        )

    await callback.answer()


@router.callback_query(F.data == "referral_stats")
async def show_referral_stats(callback: CallbackQuery, state: FSMContext):
    """Показать детальную статистику партнерской программы"""
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)

    # Автоматически создаём ссылку если её нет
    bot_info = await callback.bot.get_me()
    affiliate_link = await get_or_create_affiliate_link(user_id, bot_info.username)

    # Получаем статистику
    stats = await get_referrer_stats(user_id)

    # Формируем детальную статистику
    if lang == 'en':
        text = (
            "📊 <b>Detailed Statistics</b>\n\n"
            f"<b>Your referrals:</b>\n"
            f"• Users attracted: {stats['referrals_count']}\n"
            f"• Paid users: {stats['active_referrals']}\n"
            f"• Conversion rate: {stats['conversion_rate']}%\n\n"
            f"<b>Earnings:</b>\n"
            f"• Earned: {stats['total_earned']} ⭐\n"
            f"• Pending: {stats['pending_amount']} ⭐"
        )
        if stats['referrals_count'] > 0:
            avg_earning = stats['total_earned'] / stats['referrals_count'] if stats['referrals_count'] > 0 else 0
            text += f"\n• Average per user: {avg_earning:.1f} ⭐"
    else:
        text = (
            "📊 <b>Подробная статистика</b>\n\n"
            f"<b>Ваши рефералы:</b>\n"
            f"• Привлечено пользователей: {stats['referrals_count']}\n"
            f"• Оплатили подписку: {stats['active_referrals']}\n"
            f"• Конверсия: {stats['conversion_rate']}%\n\n"
            f"<b>Заработок:</b>\n"
            f"• Заработано: {stats['total_earned']} ⭐\n"
            f"• В ожидании: {stats['pending_amount']} ⭐"
        )
        if stats['referrals_count'] > 0:
            avg_earning = stats['total_earned'] / stats['referrals_count'] if stats['referrals_count'] > 0 else 0
            text += f"\n• В среднем с пользователя: {avg_earning:.1f} ⭐"

    # Кнопка назад
    builder = InlineKeyboardBuilder()
    builder.button(text=get_text('back', lang), callback_data="menu_referral")
    builder.button(text=get_text('close', lang), callback_data="close")
    builder.adjust(1)

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


@router.callback_query(F.data == "referral_commissions")
async def show_referral_commissions(callback: CallbackQuery, state: FSMContext):
    """Показать историю комиссий"""
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)

    # Получаем историю комиссий
    commissions = await get_commission_history(user_id, limit=10)

    # Формируем текст с историей
    if lang == 'en':
        text = "📅 <b>Payment History</b>\n\n"
        if not commissions:
            text += "No payments yet.\n\n"
            text += "💡 <i>Share your referral link to start earning!</i>"
        else:
            for commission in commissions:
                status_emoji = {
                    'pending': '⏳',
                    'hold': '🔒',
                    'paid': '✅',
                    'cancelled': '❌',
                    'refunded': '↩️'
                }.get(commission['status'], '❓')

                text += (
                    f"{status_emoji} {commission['created_at'].strftime('%d.%m.%Y')}\n"
                    f"   Amount: {commission['commission_amount']} ⭐\n"
                    f"   Status: {commission['status']}\n"
                )
                if commission['status'] == 'hold' and commission['hold_until']:
                    days_left = (commission['hold_until'] - timezone.now()).days
                    text += f"   Release in: {days_left} days\n"
                text += "\n"
    else:
        text = "📅 <b>История выплат</b>\n\n"
        if not commissions:
            text += "Выплат пока нет.\n\n"
            text += "💡 <i>Делитесь вашей реферальной ссылкой, чтобы начать зарабатывать!</i>"
        else:
            for commission in commissions:
                status_emoji = {
                    'pending': '⏳',
                    'hold': '🔒',
                    'paid': '✅',
                    'cancelled': '❌',
                    'refunded': '↩️'
                }.get(commission['status'], '❓')

                status_text = {
                    'pending': 'Ожидание',
                    'hold': 'Холд',
                    'paid': 'Выплачено',
                    'cancelled': 'Отменено',
                    'refunded': 'Возврат'
                }.get(commission['status'], commission['status'])

                text += (
                    f"{status_emoji} {commission['created_at'].strftime('%d.%m.%Y')}\n"
                    f"   Сумма: {commission['commission_amount']} ⭐\n"
                    f"   Статус: {status_text}\n"
                )
                if commission['status'] == 'hold' and commission['hold_until']:
                    days_left = (commission['hold_until'] - timezone.now()).days
                    text += f"   До выплаты: {days_left} дн.\n"
                text += "\n"

    # Кнопки навигации
    builder = InlineKeyboardBuilder()
    builder.button(text=get_text('back', lang), callback_data="menu_referral")
    builder.button(text=get_text('close', lang), callback_data="close")
    builder.adjust(1)

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
    """Команда для просмотра партнерской программы"""
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
    text, _ = await get_referral_info_text(profile, bot_username, lang)

    await send_message_with_cleanup(
        message,
        state,
        text,
        reply_markup=get_referral_keyboard(lang),
        parse_mode="HTML"
    )