"""
Роутер для реферальной программы и шаринга бота
"""
from aiogram import Router, F, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging
from urllib.parse import quote
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


def get_referral_keyboard(lang: str = 'ru', share_url: str = None, share_text: str = None):
    """Клавиатура для реферальной программы"""
    builder = InlineKeyboardBuilder()

    # Кнопка "Поделиться" - открывает нативное меню Telegram
    if share_url and share_text:
        share_link = f"https://t.me/share/url?url={quote(share_url)}&text={quote(share_text)}"
        builder.row(
            InlineKeyboardButton(
                text="📤 Поделиться" if lang == 'ru' else "📤 Share",
                url=share_link
            )
        )

    builder.button(
        text="📊 Статистика" if lang == 'ru' else "📊 Statistics",
        callback_data="referral_stats"
    )
    builder.button(
        text="📅 История бонусов" if lang == 'ru' else "📅 Bonus history",
        callback_data="referral_rewards"
    )
    builder.button(
        text=get_text('back', lang),
        callback_data="menu_subscription"
    )
    builder.button(
        text=get_text('close', lang),
        callback_data="close"
    )

    builder.adjust(1)
    return builder.as_markup()


async def get_referral_info_text(profile: Profile, bot_username: str, lang: str = 'ru') -> tuple[str, bool, str, str]:
    """Получить текст для шаринга бота с реферальной ссылкой

    Returns:
        tuple: (display_text, has_code, share_text, share_url)
    """
    # Получаем или создаем реферальную ссылку
    affiliate_link = await get_or_create_affiliate_link(profile.telegram_id, bot_username)

    # Получаем статистику
    stats = await get_referrer_stats(profile.telegram_id)

    rewards_months = stats['rewarded_months']
    if lang == 'en':
        share_message = (
            "Try Coins Bot — I've used it to get my budget in order! "
            "Track expenses easily right in Telegram."
        )
        text = (
            "🔗 <b>Share with friends</b>\n\n"
            "Click the 'Share' button below to invite friends!\n\n"
            "🎁 <b>Bonus</b>\n"
            "When a friend buys their first subscription, we'll extend yours for the same period (one time)."
        )
    else:
        share_message = (
            "Попробуй Coins Bot — я с его помощью навёл порядок в бюджете! "
            "Легко веду учёт трат прямо в Telegram."
        )
        text = (
            "🔗 <b>Поделитесь с друзьями</b>\n\n"
            "Нажмите кнопку «Поделиться» ниже, чтобы пригласить друзей!\n\n"
            "🎁 <b>Бонус</b>\n"
            "Когда друг купит первую подписку, мы продлим вашу на такой же срок (один раз)."
        )

    # Возвращаем текст для отображения, флаг наличия кода, текст для шаринга и URL
    return text, True, share_message, affiliate_link.telegram_link


@router.callback_query(F.data == "menu_referral")
async def show_referral_menu(callback: CallbackQuery, state: FSMContext):
    """Показать меню для шаринга бота"""
    profile = await Profile.objects.aget(telegram_id=callback.from_user.id)

    # Получаем username бота
    bot_info = await callback.bot.get_me()
    bot_username = bot_info.username

    lang = await get_user_language(callback.from_user.id)
    text, has_code, share_text, share_url = await get_referral_info_text(profile, bot_username, lang)

    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_referral_keyboard(lang, share_url, share_text),
            parse_mode="HTML"
        )
    except Exception:
        await send_message_with_cleanup(
            callback,
            state,
            text,
            reply_markup=get_referral_keyboard(lang, share_url, share_text),
            parse_mode="HTML"
        )

    await callback.answer()


@router.callback_query(F.data == "referral_stats")
async def show_referral_stats(callback: CallbackQuery, state: FSMContext):
    """Показать детальную статистику реферальной программы"""
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)

    # Автоматически создаём ссылку если её нет
    bot_info = await callback.bot.get_me()
    affiliate_link = await get_or_create_affiliate_link(user_id, bot_info.username)

    stats = await get_referrer_stats(user_id)

    if lang == 'en':
        text = (
            "📊 <b>Statistics</b>\n\n"
            f"• Link clicks: {stats['clicks']}\n"
            f"• Users attracted: {stats['referrals_count']}\n"
            f"• Conversion rate: {stats['conversion_rate']}%\n"
            f"• Total months rewarded: {stats['rewarded_months']}\n"
        )
    else:
        text = (
            "📊 <b>Статистика</b>\n\n"
            f"• Переходов по ссылке: {stats['clicks']}\n"
            f"• Привлечено пользователей: {stats['referrals_count']}\n"
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


@router.callback_query(F.data == "telegram_stars_info")
async def show_telegram_stars_info(callback: CallbackQuery, state: FSMContext):
    """Показать информацию о программе Telegram Stars (только информация, без функционала)"""
    lang = await get_user_language(callback.from_user.id)

    # Получаем bot_username для ссылки
    bot_info = await callback.bot.get_me()
    bot_username = bot_info.username

    if lang == 'en':
        text = (
            "⭐ <b>Telegram Stars Affiliate Program</b>\n\n"
            "Telegram has an official affiliate program where you can earn Stars "
            "by inviting users to bots.\n\n"
            "💰 <b>How to get your affiliate link:</b>\n\n"
            "1. Open this bot profile: @{bot_username}\n"
            "2. Click on the bot name at the top\n"
            "3. In the bot info, find and tap <b>\"Affiliate Program\"</b>\n"
            "4. Telegram will generate your unique affiliate link\n"
            "5. Share it with friends and earn up to 20% Stars from their purchases!\n\n"
            "💡 <i>This is an official Telegram feature, available in: Settings → My Stars → Earn Stars</i>"
        ).format(bot_username=bot_username)
    else:
        text = (
            "⭐ <b>Партнёрская программа Telegram Stars</b>\n\n"
            "Telegram запустил официальную партнёрскую программу, где можно зарабатывать звёзды, "
            "приглашая пользователей в ботов.\n\n"
            "💰 <b>Как получить партнёрскую ссылку:</b>\n\n"
            "1. Откройте профиль этого бота: @{bot_username}\n"
            "2. Нажмите на название бота вверху экрана\n"
            "3. В информации о боте найдите и нажмите <b>«Партнёрская программа»</b>\n"
            "4. Telegram автоматически создаст вашу уникальную партнёрскую ссылку\n"
            "5. Делитесь ей с друзьями и получайте до 20% звёзд от их покупок!\n\n"
            "💡 <i>Это официальная функция Telegram, доступна в: Настройки → Мои звёзды → Заработать звёзды</i>"
        ).format(bot_username=bot_username)

    builder = InlineKeyboardBuilder()
    builder.button(text=get_text('back', lang), callback_data="menu_subscription")
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
    """Команда для шаринга бота и реферальной программы"""
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
    text, _, share_text, share_url = await get_referral_info_text(profile, bot_username, lang)

    await send_message_with_cleanup(
        message,
        state,
        text,
        reply_markup=get_referral_keyboard(lang, share_url, share_text),
        parse_mode="HTML"
    )
