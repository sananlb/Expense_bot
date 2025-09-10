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
from bot.services.profile import get_or_create_profile, get_user_settings
from bot.keyboards import main_menu_keyboard, back_close_keyboard
from bot.services.category import create_default_categories, create_default_income_categories
from bot.utils.message_utils import send_message_with_cleanup, delete_message_with_effect
from bot.utils.commands import update_user_commands
from bot.services.affiliate import process_referral_link  # Новая реферальная система Telegram Stars
from expenses.models import Subscription, Profile, ReferralBonus
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

router = Router(name="start")


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext, command: CommandObject, lang: str = 'ru'):
    """Обработка команды /start - показать информацию о боте"""
    user_id = message.from_user.id
    
    # Проверяем, есть ли реферальный код или приглашение в семейный бюджет в команде
    referral_code = None
    family_token = None
    if command.args:
        args = command.args.strip()
        if args.startswith('ref_'):
            # Формат: /start ref_ABCD1234
            referral_code = args[4:]  # Убираем префикс ref_
        elif args.startswith('family_'):
            # Формат: /start family_TOKEN
            family_token = args[7:]  # Убираем префикс family_
    
    # Создаем или получаем профиль пользователя
    profile = await get_or_create_profile(
        telegram_id=user_id,
        language_code=message.from_user.language_code
    )
    
    # Проверяем, новый ли это пользователь (по наличию подписок)
    is_new_user = not await Subscription.objects.filter(profile=profile).aexists()
    
    # Определяем язык для отображения
    # Если у пользователя уже есть сохраненный язык - используем его
    # Если это новый пользователь - определяем по языку системы Telegram
    if profile.language_code:
        display_lang = profile.language_code
    else:
        # Для новых пользователей определяем язык по системному языку Telegram
        user_language_code = message.from_user.language_code or 'en'
        display_lang = 'ru' if user_language_code.startswith('ru') else 'en'
        # Сохраняем язык только для новых пользователей
        profile.language_code = display_lang
        await profile.asave()
    
    # Обработка приглашения в семейный бюджет
    if family_token:
        # Импортируем функцию обработки приглашения
        from bot.routers.household import process_family_invite
        await process_family_invite(message, family_token)
        return  # Прекращаем выполнение команды /start
    
    # Создаем базовые категории для нового пользователя
    categories_created = await create_default_categories(user_id)
    # Создаем базовые категории доходов
    income_categories_created = await create_default_income_categories(user_id)
    
    # Если пришли по семейной ссылке, предлагаем подтвердить присоединение
    if family_token:
        try:
            from bot.services.family import get_invite_by_token
            inv = await get_invite_by_token(family_token)
            if inv and inv.is_valid():
                inviter_tid = inv.inviter.telegram_id
                if display_lang == 'en':
                    confirm_text = (
                        "👥 Do you want to share a family budget with user "
                        f"<code>{inviter_tid}</code>?"
                    )
                    yes_text, no_text = "✅ Yes", "✖️ No"
                else:
                    confirm_text = (
                        "👥 Вы действительно хотите вести совместный бюджет с пользователем "
                        f"<code>{inviter_tid}</code>?"
                    )
                    yes_text, no_text = "✅ Да", "✖️ Нет"
                from aiogram.utils.keyboard import InlineKeyboardBuilder
                kb = InlineKeyboardBuilder()
                kb.button(text=yes_text, callback_data=f"family_accept:{inv.token}")
                kb.button(text=no_text, callback_data="close")
                kb.adjust(2)
                await message.answer(confirm_text, reply_markup=kb.as_markup(), parse_mode="HTML")
            else:
                await message.answer(
                    "Invite link is invalid or expired" if display_lang=='en' else "Ссылка-приглашение недействительна или истек срок действия"
                )
        except Exception as e:
            logger.error(f"Error handling family invite: {e}")
    
    # Обработка реферальной ссылки для новых пользователей
    referral_message = ""
    if is_new_user and referral_code:
        try:
            # Сначала пробуем обработать как реферальную ссылку Telegram Stars
            affiliate_referral = await process_referral_link(user_id, referral_code)
            
            if affiliate_referral:
                # Успешно обработана ссылка Telegram Stars
                if display_lang == 'en':
                    referral_message = "\n\n⭐ You joined via an affiliate link! Your friend will receive commission from your purchases."
                else:
                    referral_message = "\n\n⭐ Вы перешли по партнёрской ссылке! Ваш друг будет получать комиссию с ваших покупок."
                
                logger.info(f"New user {user_id} registered via Telegram Stars affiliate link from {affiliate_referral.referrer.telegram_id}")
            else:
                # Если не удалось обработать как Telegram Stars, пробуем старую систему
                # Находим реферера по коду (старая система с бонусными днями)
                referrer = await Profile.objects.filter(referral_code=referral_code).afirst()
                if referrer and referrer.telegram_id != user_id:
                    # Привязываем реферера (старая система)
                    profile.referrer = referrer
                    await profile.asave()
                    
                    if display_lang == 'en':
                        referral_message = "\n\n🎁 You joined via a referral link! After paying for your first subscription, your friend will receive a bonus."
                    else:
                        referral_message = "\n\n🎁 Вы перешли по реферальной ссылке! После оплаты первой подписки ваш друг получит бонус."
                    
                    logger.info(f"New user {user_id} registered with referral code from {referrer.telegram_id}")
        except Exception as e:
            logger.error(f"Error processing referral code: {e}")
    
    # Проверяем, есть ли у пользователя подписка (только если не beta_tester)
    if not profile.is_beta_tester:
        # Проверяем существующие подписки
        existing_trial = await profile.subscriptions.filter(
            type='trial'
        ).aexists()
        
        has_active_subscription = await profile.subscriptions.filter(
            is_active=True,
            end_date__gt=timezone.now()
        ).aexists()
        
        # Создаем пробную подписку только если:
        # 1. Это новый пользователь
        # 2. У него нет активной подписки
        # 3. У него никогда не было пробной подписки
        # 4. Он не beta_tester
        if is_new_user and not has_active_subscription and not existing_trial:
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
    else:
        logger.info(f"User {user_id} is a beta tester, skipping trial subscription")
    
    # Обновляем команды бота для пользователя
    await update_user_commands(message.bot, user_id)
    
    # Информация о боте на нужном языке
    if display_lang == 'en':
        text = """<b>🪙 Coins - smart finance tracking</b>

<b>💸 Adding expenses and income:</b>
Send a text or voice message:
"Coffee", "Gas 4050", "Bonus +40000"
The amount and category will be selected based on your previous entries.
You can backdate entries, e.g., "10.09 1200 groceries" or "coffee 340 10.09.2025".

<b>📁 Categories:</b>
Customize categories for yourself - add your own, delete unnecessary ones. AI will automatically determine the category for each entry.

<b>💳 Bank card cashbacks:</b>
Add information about cashbacks on your bank cards. All cashbacks are calculated automatically and displayed in reports. Pin the cashback message in the chat for one-click access.

<b>📋 Transaction diary:</b>
View the history of all transactions for any period in a convenient format. The diary shows expenses and income by day with totals.

<b>📊 Reports:</b>
Request a report in natural language:
"Show expenses for July", "How much did I earn this month"
Get beautiful PDF reports with charts"""
    else:
        text = """<b>🪙 Coins - умный учет ваших финансов</b>

<b>💸 Добавление расходов и доходов:</b>
Отправьте текст или голосовое сообщение:
"Кофе", "Дизель 4050", "Премия +40000"
Сумма и категория подберутся на основании ваших предыдущих записей.
Можно добавлять задним числом: например, "10.09 1200 продукты" или "кофе 340 10.09.2025".

<b>📁 Категории:</b>
Редактируйте категории под себя - добавляйте свои, удаляйте ненужные. ИИ автоматически определит категорию для каждой записи.

<b>💳 Кешбэки по банковским картам:</b>
Добавьте информацию о кешбеках по вашим банковским картам. Все кешбеки рассчитываются автоматически и отображаются в отчетах. Закрепите сообщение с кешбэком в чате, чтобы оно было доступно по одному клику.

<b>📋 Дневник операций:</b>
Просматривайте историю всех операций за любой период в удобном формате. Дневник показывает расходы и доходы по дням с итогами.

<b>📊 Отчеты:</b>
Попросите отчет естественным языком:
"Покажи траты за июль", "Сколько я заработал в этом месяце"
Получайте красивые PDF отчеты с графиками"""
    
    # Добавляем реферальное сообщение, если есть
    text += referral_message

    # Добавляем блок про семейный бюджет внизу
    if display_lang == 'en':
        household_footer = (
            "\n\n"
            "<b>🏠 Household:</b>\n"
            "Track finances together with your family. "
            "Switch between personal and family views. "
            "Create a household and add members by sending them an invite link."
        )
    else:
        household_footer = (
            "\n\n"
            "<b>🏠 Семейный бюджет:</b>\n"
            "Ведите общий учет с семьёй. "
            "Переключайтесь между личным и семейным режимом просмотра. "
            "Создайте семью и добавляйте участников, отправив им приглашение."
        )
    text += household_footer
    
    # Отправляем информацию без кнопок
    await send_message_with_cleanup(message, state, text, parse_mode="HTML")




@router.callback_query(F.data == "menu")
async def callback_menu(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать главное меню по callback"""
    text = f"{get_text('main_menu', lang)}\n\n{get_text('choose_action', lang)}"
    
    # Получаем настройки кешбэка
    user_settings = await get_user_settings(callback.from_user.id)
    cashback_enabled = user_settings.cashback_enabled if hasattr(user_settings, 'cashback_enabled') else True
    
    sent_message = await send_message_with_cleanup(
        callback, state, text,
        reply_markup=main_menu_keyboard(lang, cashback_enabled)
    )
    
    # Сохраняем, что это главное меню
    await state.update_data(main_menu_message_id=sent_message.message_id)
    
    await callback.answer()






@router.callback_query(F.data == "start")
async def callback_start(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать информацию о боте через callback"""
    # Обновляем команды бота для пользователя
    await update_user_commands(callback.bot, callback.from_user.id)
    
    # Информация о боте на нужном языке
    if lang == 'en':
        text = """<b>🪙 Coins - smart finance tracking</b>

<b>💸 Adding expenses:</b>
Send a text or voice message:
"Coffee 200" or "Gas 4095 station"
You can backdate entries, e.g., "10.09 1200 groceries" or "coffee 340 10.09.2025".

<b>📁 Expense categories:</b>
Customize categories for yourself - add your own, delete unnecessary ones. AI will automatically determine the category for each expense.

<b>💳 Bank card cashbacks:</b>
Add information about cashbacks on your bank cards. All cashbacks are calculated automatically and displayed in reports. Pin the cashback message in the chat for one-click access.

<b>📊 Expense reports:</b>
Request a report in natural language:
"Show expenses for July" or "How much did I spend yesterday"
Get beautiful PDF reports with charts"""
    else:
        text = """<b>🪙 Coins - умный учет ваших финансов</b>

<b>💸 Добавление расходов и доходов:</b>
Отправьте текст или голосовое сообщение:
"Кофе", "Дизель 4050", "Премия +40000"
Сумма и категория подберутся на основании ваших предыдущих записей.
Можно добавлять задним числом: например, "10.09 1200 продукты" или "кофе 340 10.09.2025".

<b>📁 Категории:</b>
Редактируйте категории под себя - добавляйте свои, удаляйте ненужные. ИИ автоматически определит категорию для каждой записи.

<b>💳 Кешбэки по банковским картам:</b>
Добавьте информацию о кешбеках по вашим банковским картам. Все кешбеки рассчитываются автоматически и отображаются в отчетах. Закрепите сообщение с кешбэком в чате, чтобы оно было доступно по одному клику.

<b>📋 Дневник операций:</b>
Просматривайте историю всех операций за любой период в удобном формате. Дневник показывает расходы и доходы по дням с итогами.

<b>📊 Отчеты:</b>
Попросите отчет естественным языком:
"Покажи траты за июль", "Сколько я заработал в этом месяце"
Получайте красивые PDF отчеты с графиками"""
    
    # Добавляем блок про семейный бюджет внизу
    if lang == 'en':
        household_footer = (
            "\n\n"
            "<b>🏠 Household:</b>\n"
            "Track finances together with your family. "
            "Switch between personal and family views. "
            "Create a household and add members by sending them an invite link."
        )
    else:
        household_footer = (
            "\n\n"
            "<b>🏠 Семейный бюджет:</b>\n"
            "Ведите общий учет с семьёй. "
            "Переключайтесь между личным и семейным режимом просмотра. "
            "Создайте семью и добавляйте участников, отправив им приглашение."
        )
    
    text += household_footer

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
    # НЕ трогаем флаг persistent_cashback_menu - он управляется только в cashback.py
    await state.update_data(
        last_menu_message_id=None
    )


@router.callback_query(F.data == "close_menu")
async def close_menu_compat(callback: types.CallbackQuery, state: FSMContext):
    """Совместимость: обработка старого callback 'close_menu' как обычного закрытия"""
    await callback.message.delete()
    await state.update_data(
        last_menu_message_id=None
    )
