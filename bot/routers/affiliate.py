"""
Роутер для управления реферальной программой Telegram Stars
"""
from aiogram import Router, F, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
from django.utils import timezone
import logging

from bot.utils import get_text
from bot.utils.message_utils import send_message_with_cleanup
from bot.services.affiliate import (
    get_or_create_affiliate_link,
    get_referrer_stats,
    get_referral_history,
    get_commission_history,
    get_or_create_affiliate_program
)
from expenses.models import Profile

logger = logging.getLogger(__name__)

router = Router(name='affiliate')


@router.message(Command("affiliate"))
async def cmd_affiliate(message: Message, state: FSMContext, lang: str = 'ru'):
    """Команда /affiliate - показать информацию о реферальной программе"""
    user_id = message.from_user.id
    
    # Получаем профиль пользователя
    try:
        profile = await Profile.objects.aget(telegram_id=user_id)
    except Profile.DoesNotExist:
        if lang == 'en':
            error_text = "⚠️ Profile not found. Please use /start command first."
        else:
            error_text = "⚠️ Профиль не найден. Используйте команду /start."
        await message.answer(error_text)
        return
    
    # Убеждаемся, что реферальная программа активна с 50% комиссией
    affiliate_program = await get_or_create_affiliate_program(commission_percent=50)
    
    # Получаем или создаём реферальную ссылку
    bot_info = await message.bot.get_me()
    affiliate_link = await get_or_create_affiliate_link(user_id, bot_info.username)
    
    # Получаем статистику
    stats = await get_referrer_stats(user_id)
    
    # Формируем сообщение
    if lang == 'en':
        message_text = (
            "Referral link:\n"
            f"<code>{affiliate_link.telegram_link}</code>\n\n"
            f"📊 <b>Your statistics:</b>\n"
            f"• Clicks: {stats['clicks']}\n"
            f"• Registrations: {stats['referrals_count']}\n\n"
            f"💰 <b>Earnings:</b>\n"
            f"• Earned: {stats['total_earned']} ⭐\n"
            f"• Pending: {stats['pending_amount']} ⭐\n\n"
            f"ℹ️ <b>How it works:</b>\n"
            f"1. Share your referral link\n"
            f"2. Get {affiliate_program.get_commission_percent()}% from each payment\n"
            f"3. Commissions are held for 21 days\n"
            f"4. After the hold period, stars are credited to your account\n\n"
            f"💡 <i>Share your link and earn Telegram Stars!</i>"
        )
    else:
        message_text = (
            "Ваша реферальная ссылка:\n"
            f"<code>{affiliate_link.telegram_link}</code>\n\n"
            f"📊 <b>Ваша статистика:</b>\n"
            f"• Переходов: {stats['clicks']}\n"
            f"• Регистраций: {stats['referrals_count']}\n\n"
            f"💰 <b>Заработок:</b>\n"
            f"• Заработано: {stats['total_earned']} ⭐\n"
            f"• В ожидании: {stats['pending_amount']} ⭐\n\n"
            f"ℹ️ <b>Как это работает:</b>\n"
            f"1. Делитесь своей реферальной ссылкой\n"
            f"2. Получайте {affiliate_program.get_commission_percent()}% от каждого платежа\n"
            f"3. Комиссии держатся на холде 21 день\n"
            f"4. После холда звёзды начисляются на ваш счёт\n\n"
            f"💡 <i>Делитесь ссылкой и зарабатывайте Telegram Stars!</i>"
        )
    
    # Создаём клавиатуру с действиями (только необходимые кнопки)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📊 Подробная статистика" if lang == 'ru' else "📊 Detailed stats",
                callback_data="affiliate_stats"
            )
        ],
        [
            InlineKeyboardButton(
                text="💸 История выплат" if lang == 'ru' else "💸 Payment history",
                callback_data="affiliate_commissions"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Закрыть" if lang == 'ru' else "❌ Close",
                callback_data="close"
            )
        ]
    ])
    
    await send_message_with_cleanup(
        message, state,
        message_text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )


@router.callback_query(F.data == "affiliate_stats")
async def show_affiliate_stats(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать подробную статистику"""
    user_id = callback.from_user.id
    
    # Получаем статистику
    stats = await get_referrer_stats(user_id)
    
    if not stats['has_link']:
        if lang == 'en':
            text = "⚠️ You don't have an affiliate link yet. Use /affiliate command."
        else:
            text = "⚠️ У вас ещё нет реферальной ссылки. Используйте команду /affiliate."
        await callback.answer(text, show_alert=True)
        return
    
    # Формируем детальную статистику
    if lang == 'en':
        text = (
            "📊 <b>Detailed Statistics</b>\n\n"
            f"<b>Link performance:</b>\n"
            f"• Total clicks: {stats['clicks']}\n"
            f"• Registrations: {stats['referrals_count']}\n"
            f"• Paying users: {stats['active_referrals']}\n\n"
            f"<b>Earnings:</b>\n"
            f"• Total earned: {stats['total_earned']} ⭐\n"
            f"• On hold (21 days): {stats['pending_amount']} ⭐\n"
            f"• Available: {stats['total_earned'] - stats['pending_amount']} ⭐"
        )
        if stats['referrals_count'] > 0:
            avg_earning = stats['total_earned'] / stats['referrals_count']
            text += f"\n• Average per user: {avg_earning:.1f} ⭐"
    else:
        text = (
            "📊 <b>Детальная статистика</b>\n\n"
            f"<b>Эффективность ссылки:</b>\n"
            f"• Всего переходов: {stats['clicks']}\n"
            f"• Регистраций: {stats['referrals_count']}\n"
            f"• Платящих пользователей: {stats['active_referrals']}\n\n"
            f"<b>Заработок:</b>\n"
            f"• Всего заработано: {stats['total_earned']} ⭐\n"
            f"• На холде (21 день): {stats['pending_amount']} ⭐\n"
            f"• Доступно: {stats['total_earned'] - stats['pending_amount']} ⭐"
        )
        if stats['referrals_count'] > 0:
            avg_earning = stats['total_earned'] / stats['referrals_count']
            text += f"\n• В среднем с пользователя: {avg_earning:.1f} ⭐"
    
    # Клавиатура возврата
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="◀️ Назад" if lang == 'ru' else "◀️ Back",
                callback_data="back_to_affiliate"
            )
        ]
    ])
    
    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data == "affiliate_referrals")
async def show_referrals(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать список рефералов"""
    user_id = callback.from_user.id
    
    # Получаем историю рефералов
    referrals = await get_referral_history(user_id, limit=10)
    
    if not referrals:
        if lang == 'en':
            text = "👥 <b>Your referrals</b>\n\nYou don't have any referrals yet.\nShare your link to start earning!"
        else:
            text = "👥 <b>Ваши рефералы</b>\n\nУ вас пока нет рефералов.\nПоделитесь ссылкой, чтобы начать зарабатывать!"
    else:
        if lang == 'en':
            text = "👥 <b>Your referrals (last 10)</b>\n\n"
            for ref in referrals:
                status = "✅ Active" if ref['is_active'] else "⏳ Inactive"
                joined = ref['joined_at'].strftime('%d.%m.%Y')
                text += f"• User {ref['user_id'][:6]}...\n"
                text += f"  Joined: {joined}\n"
                text += f"  Status: {status}\n"
                if ref['total_payments'] > 0:
                    text += f"  Payments: {ref['total_payments']}\n"
                    text += f"  Spent: {ref['total_spent']} ⭐\n"
                text += "\n"
        else:
            text = "👥 <b>Ваши рефералы (последние 10)</b>\n\n"
            for ref in referrals:
                status = "✅ Активный" if ref['is_active'] else "⏳ Неактивный"
                joined = ref['joined_at'].strftime('%d.%m.%Y')
                text += f"• Пользователь {ref['user_id'][:6]}...\n"
                text += f"  Регистрация: {joined}\n"
                text += f"  Статус: {status}\n"
                if ref['total_payments'] > 0:
                    text += f"  Платежей: {ref['total_payments']}\n"
                    text += f"  Потрачено: {ref['total_spent']} ⭐\n"
                text += "\n"
    
    # Клавиатура возврата
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="◀️ Назад" if lang == 'ru' else "◀️ Back",
                callback_data="back_to_affiliate"
            )
        ]
    ])
    
    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data == "affiliate_commissions")
async def show_commissions(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать историю выплат"""
    user_id = callback.from_user.id
    
    # Получаем историю комиссий
    commissions = await get_commission_history(user_id, limit=10)
    
    if not commissions:
        if lang == 'en':
            text = "💸 <b>Payment history</b>\n\nYou don't have any payments yet.\nYour referrals need to make purchases."
        else:
            text = "💸 <b>История выплат</b>\n\nУ вас пока нет выплат.\nВаши рефералы должны совершить покупки."
    else:
        if lang == 'en':
            text = "💸 <b>Payment history (last 10)</b>\n\n"
            for comm in commissions:
                date = comm['created_at'].strftime('%d.%m.%Y %H:%M')
                status_emoji = {
                    'pending': '⏳',
                    'hold': '🔒',
                    'paid': '✅',
                    'cancelled': '❌',
                    'refunded': '↩️'
                }.get(comm['status'], '❓')
                
                text += f"{status_emoji} {date}\n"
                text += f"  Amount: {comm['commission_amount']} ⭐\n"
                text += f"  From payment: {comm['payment_amount']} ⭐\n"
                text += f"  Status: {comm['status_display']}\n"
                if comm['hold_until'] and comm['status'] == 'hold':
                    hold_date = comm['hold_until'].strftime('%d.%m.%Y')
                    text += f"  Available after: {hold_date}\n"
                text += "\n"
        else:
            text = "💸 <b>История выплат (последние 10)</b>\n\n"
            for comm in commissions:
                date = comm['created_at'].strftime('%d.%m.%Y %H:%M')
                status_emoji = {
                    'pending': '⏳',
                    'hold': '🔒',
                    'paid': '✅',
                    'cancelled': '❌',
                    'refunded': '↩️'
                }.get(comm['status'], '❓')
                
                text += f"{status_emoji} {date}\n"
                text += f"  Сумма: {comm['commission_amount']} ⭐\n"
                text += f"  С платежа: {comm['payment_amount']} ⭐\n"
                text += f"  Статус: {comm['status_display']}\n"
                if comm['hold_until'] and comm['status'] == 'hold':
                    hold_date = comm['hold_until'].strftime('%d.%m.%Y')
                    text += f"  Доступно после: {hold_date}\n"
                text += "\n"
    
    # Клавиатура возврата
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="◀️ Назад" if lang == 'ru' else "◀️ Back",
                callback_data="back_to_affiliate"
            )
        ]
    ])
    
    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_affiliate")
async def back_to_affiliate(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Вернуться к главному меню affiliate"""
    await cmd_affiliate(callback.message, state, lang)
    await callback.answer()