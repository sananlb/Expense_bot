"""
Обработчик команды /start и приветствия
"""
from aiogram import Router, F, types
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
import asyncio
import logging

from bot.utils import get_text
from bot.services.profile import get_or_create_profile
from bot.keyboards import main_menu_keyboard, back_close_keyboard
from bot.services.category import create_default_categories
from bot.utils.message_utils import send_message_with_cleanup, delete_message_with_effect
from bot.utils.commands import update_user_commands
from expenses.models import Subscription, Profile, ReferralBonus
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

router = Router(name="start")


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext, command: CommandObject, lang: str = 'ru'):
    """Обработка команды /start - показать информацию о боте"""
    user_id = message.from_user.id
    
    # Определяем язык пользователя (если не русский, используем английский)
    user_language_code = message.from_user.language_code or 'en'
    display_lang = 'ru' if user_language_code.startswith('ru') else 'en'
    
    # Проверяем, есть ли реферальный код в команде
    referral_code = None
    if command.args:
        # Формат: /start ref_ABCD1234
        args = command.args.strip()
        if args.startswith('ref_'):
            referral_code = args[4:]  # Убираем префикс ref_
    
    # Создаем или получаем профиль пользователя
    profile = await get_or_create_profile(
        telegram_id=user_id,
        language_code=message.from_user.language_code
    )
    
    # Проверяем, новый ли это пользователь (по наличию подписок)
    is_new_user = not await Subscription.objects.filter(profile=profile).aexists()
    
    # Обновляем язык профиля если он не установлен или отличается
    if profile.language_code != display_lang:
        profile.language_code = display_lang
        await profile.asave()
    
    # Создаем базовые категории для нового пользователя
    categories_created = await create_default_categories(user_id)
    
    # Обработка реферальной ссылки для новых пользователей
    referral_message = ""
    if is_new_user and referral_code:
        try:
            # Находим реферера по коду
            referrer = await Profile.objects.filter(referral_code=referral_code).afirst()
            if referrer and referrer.telegram_id != user_id:
                # Привязываем реферера
                profile.referrer = referrer
                await profile.asave()
                
                if display_lang == 'en':
                    referral_message = "\n\n🎁 You joined via a referral link! After paying for your first subscription, your friend will receive a bonus."
                else:
                    referral_message = "\n\n🎁 Вы перешли по реферальной ссылке! После оплаты первой подписки ваш друг получит бонус."
                
                logger.info(f"New user {user_id} registered with referral code from {referrer.telegram_id}")
        except Exception as e:
            logger.error(f"Error processing referral code: {e}")
    
    # Проверяем, есть ли у пользователя подписка
    has_subscription = await profile.subscriptions.filter(
        is_active=True,
        end_date__gt=timezone.now()
    ).aexists()
    
    # Если нет подписки и это новый пользователь, создаем пробный период на 7 дней
    if not has_subscription and is_new_user:
        trial_end = timezone.now() + timedelta(days=7)
        await Subscription.objects.acreate(
            profile=profile,
            type='trial',
            payment_method='trial',
            amount=0,
            start_date=timezone.now(),
            end_date=trial_end,
            is_active=True
        )
        logger.info(f"Created trial subscription for new user {user_id}")
    
    # Обновляем команды бота для пользователя
    await update_user_commands(message.bot, user_id)
    
    # Информация о боте на нужном языке
    if display_lang == 'en':
        text = """<b>🪙 Coins - your expense tracking assistant</b>

<b>💸 Adding expenses:</b>
Send a text or voice message:
"Coffee 200" or "Gas 4095 station"

<b>📁 Expense categories:</b>
Customize categories for yourself - add your own, delete unnecessary ones. The system will automatically determine the category for each expense.

<b>💳 Bank card cashbacks:</b>
Add information about cashbacks on your bank cards to have it always at hand. All cashbacks are calculated automatically and displayed in reports.

<b>📊 Expense reports:</b>
Request a report in natural language:
"Show expenses for July" or "How much did I spend yesterday"
Get beautiful PDF reports with charts"""
    else:
        text = """<b>🪙 Coins - ваш помощник в учете расходов</b>

<b>💸 Добавление расходов:</b>
Отправьте текст или голосовое сообщение:
"Кофе 200" или "Дизель 4095 АЗС"

<b>📁 Категории трат:</b>
Редактируйте категории под себя - добавляйте свои, удаляйте ненужные. Система автоматически определит категорию для каждой траты.

<b>💳 Кешбэки по банковским картам:</b>
Добавьте информацию о кешбеках по вашим банковским картам, чтобы она всегда была под рукой. Все кешбеки рассчитываются автоматически и отображаются в отчетах.

<b>📊 Отчеты о тратах:</b>
Попросите отчет естественным языком:
"Покажи траты за июль" или "Сколько я потратил вчера"
Получайте красивые PDF отчеты с графиками"""
    
    # Добавляем реферальное сообщение, если есть
    text += referral_message
    
    # Отправляем информацию без кнопок
    await send_message_with_cleanup(message, state, text, parse_mode="HTML")




@router.callback_query(F.data == "menu")
async def callback_menu(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать главное меню по callback"""
    text = f"{get_text('main_menu', lang)}\n\n{get_text('choose_action', lang)}"
    
    await send_message_with_cleanup(
        callback, state, text,
        reply_markup=main_menu_keyboard(lang)
    )
    await callback.answer()






@router.callback_query(F.data == "start")
async def callback_start(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать информацию о боте через callback"""
    # Обновляем команды бота для пользователя
    await update_user_commands(callback.bot, callback.from_user.id)
    
    # Информация о боте на нужном языке
    if lang == 'en':
        text = """<b>🪙 Coins - your expense tracking assistant</b>

<b>💸 Adding expenses:</b>
Send a text or voice message:
"Coffee 200" or "Gas 4095 station"

<b>📁 Expense categories:</b>
Customize categories for yourself - add your own, delete unnecessary ones. The system will automatically determine the category for each expense.

<b>💳 Bank card cashbacks:</b>
Add information about cashbacks on your bank cards to have it always at hand. All cashbacks are calculated automatically and displayed in reports.

<b>📊 Expense reports:</b>
Request a report in natural language:
"Show expenses for July" or "How much did I spend yesterday"
Get beautiful PDF reports with charts"""
    else:
        text = """<b>🪙 Coins - ваш помощник в учете расходов</b>

<b>💸 Добавление расходов:</b>
Отправьте текст или голосовое сообщение:
"Кофе 200" или "Дизель 4095 АЗС"

<b>📁 Категории трат:</b>
Редактируйте категории под себя - добавляйте свои, удаляйте ненужные. Система автоматически определит категорию для каждой траты.

<b>💳 Кешбэки по банковским картам:</b>
Добавьте информацию о кешбеках по вашим банковским картам, чтобы она всегда была под рукой. Все кешбеки рассчитываются автоматически и отображаются в отчетах.

<b>📊 Отчеты о тратах:</b>
Попросите отчет естественным языком:
"Покажи траты за июль" или "Сколько я потратил вчера"
Получайте красивые PDF отчеты с графиками"""
    
    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        # Если не удалось отредактировать, отправляем новое
        await send_message_with_cleanup(callback, state, text, parse_mode="HTML")
    
    await callback.answer()


@router.callback_query(F.data == "close")
async def close_message(callback: types.CallbackQuery, state: FSMContext):
    """Закрытие сообщения"""
    await callback.message.delete()
    # Очищаем последнее сохраненное сообщение меню
    await state.update_data(last_menu_message_id=None)