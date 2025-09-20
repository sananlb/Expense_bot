"""
Роутер для партнерской программы Telegram Stars
"""
from aiogram import Router, F, types
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging
from expenses.models import Profile, AffiliateLink, AffiliateReferral
from bot.utils.message_utils import send_message_with_cleanup
from bot.services.subscription import check_subscription
from bot.utils import get_user_language, get_text
from bot.services.affiliate import (
    get_or_create_affiliate_link,
    get_referrer_stats,
    get_reward_history,
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
        text="📅 История бонусов" if lang == 'ru' else "📅 Bonus history",
        callback_data="referral_rewards"
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

    # Получаем статистику
    stats = await get_referrer_stats(profile.telegram_id)

    rewards_months = stats['rewarded_months']
    if lang == 'en':
        text = (
            "🌟 <b>Partner Program</b>\n\n"
            "Your referral link:\n"
            f"<code>{affiliate_link.telegram_link}</code>\n\n"
            "🎁 <b>Internal bonus</b>\n"
            "Invite a friend: when they buy their first paid plan, your subscription is extended for the same duration once.\n\n"
            "📊 <b>Your stats:</b>\n"
            f"• Users attracted: {stats['referrals_count']}\n"
            f"• Bonuses granted: {stats['rewarded_referrals']}\n"
            f"• Waiting for first payment: {stats['pending_referrals']}\n"
            f"• Total months rewarded: {rewards_months}\n\n"
            "⭐ <b>Telegram Stars affiliate</b>\n"
            "You can also join the official Telegram program: open <i>Settings → My Stars → Earn Stars</i>, find our bot and subscribe to the campaign. Telegram will track and credit Stars commissions automatically."
        )
    else:
        text = (
            "🌟 <b>Партнёрская программа</b>\n\n"
            "Ваша реферальная ссылка:\n"
            f"<code>{affiliate_link.telegram_link}</code>\n\n"
            "🎁 <b>Наш бонус</b>\n"
            "Приглашайте друзей: когда приглашённый оплатит первую подписку, мы продлим вашу на такой же срок (один раз).\n\n"
            "📊 <b>Статистика:</b>\n"
            f"• Привлечено пользователей: {stats['referrals_count']}\n"
            f"• Бонусы выданы: {stats['rewarded_referrals']}\n"
            f"• Ожидают первую оплату: {stats['pending_referrals']}\n"
            f"• Всего месяцев подарено: {rewards_months}\n\n"
            "⭐ <b>Официальная программа Telegram Stars</b>\n"
            "Хотите получать комиссию звёздами? Откройте <i>Настройки → Мои звёзды → Заработать звёзды</i>, найдите наш бот и подключитесь к кампании. Telegram сам начислит и выплатит комиссию в Stars."
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

    stats = await get_referrer_stats(user_id)

    if lang == 'en':
        text = (
            "📊 <b>Detailed statistics</b>\n\n"
            f"• Link clicks: {stats['clicks']}\n"
            f"• Users attracted: {stats['referrals_count']}\n"
            f"• Bonuses granted: {stats['rewarded_referrals']}\n"
            f"• Waiting for first payment: {stats['pending_referrals']}\n"
            f"• Conversion rate: {stats['conversion_rate']}%\n"
            f"• Total months rewarded: {stats['rewarded_months']}\n"
        )
    else:
        text = (
            "📊 <b>Подробная статистика</b>\n\n"
            f"• Переходов по ссылке: {stats['clicks']}\n"
            f"• Привлечено пользователей: {stats['referrals_count']}\n"
            f"• Бонусы выданы: {stats['rewarded_referrals']}\n"
            f"• Ожидают первую оплату: {stats['pending_referrals']}\n"
            f"• Конверсия: {stats['conversion_rate']}%\n"
            f"• Всего месяцев подарено: {stats['rewarded_months']}\n"
        )

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


@router.callback_query(F.data == "referral_rewards")
async def show_referral_rewards(callback: CallbackQuery, state: FSMContext):
    """Показать историю бонусов"""
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)

    rewards = await get_reward_history(user_id, limit=10)

    if lang == 'en':
        text = "📅 <b>Bonus history</b>\n\n"
        if not rewards:
            text += "No referral activity yet.\n\n"
            text += "💡 <i>Share your link — the first paid plan of a friend will extend your subscription.</i>"
        else:
            for reward in rewards:
                if reward['reward_granted']:
                    granted_at = reward['reward_granted_at'].strftime('%d.%m.%Y') if reward['reward_granted_at'] else '—'
                    months_text = '1 month' if reward['reward_months'] == 1 else f"{reward['reward_months']} months"
                    text += (
                        f"✅ {granted_at}\n"
                        f"   Bonus: {months_text}\n"
                        f"   Referred user: {reward['referred_user_id']}\n\n"
                    )
                else:
                    joined = reward['joined_at'].strftime('%d.%m.%Y') if reward.get('joined_at') else '—'
                    text += (
                        f"⏳ {joined}\n"
                        "   Waiting for the first payment\n"
                        f"   Referred user: {reward['referred_user_id']}\n\n"
                    )
    else:
        text = "📅 <b>История бонусов</b>\n\n"
        if not rewards:
            text += "Пока нет данных.\n\n"
            text += "💡 <i>Поделитесь ссылкой: первая покупка друга продлит вашу подписку.</i>"
        else:
            for reward in rewards:
                if reward['reward_granted']:
                    granted_at = reward['reward_granted_at'].strftime('%d.%m.%Y') if reward['reward_granted_at'] else '—'
                    months_text = '1 месяц' if reward['reward_months'] == 1 else f"{reward['reward_months']} месяцев"
                    text += (
                        f"✅ {granted_at}\n"
                        f"   Бонус: {months_text}\n"
                        f"   Пользователь: {reward['referred_user_id']}\n\n"
                    )
                else:
                    joined = reward['joined_at'].strftime('%d.%m.%Y') if reward.get('joined_at') else '—'
                    text += (
                        f"⏳ {joined}\n"
                        "   Ожидаем первую оплату\n"
                        f"   Пользователь: {reward['referred_user_id']}\n\n"
                    )

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
