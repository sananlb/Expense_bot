"""
Обработчик команды /start и приветствия
"""
from aiogram import Router, F, types
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
import asyncio
import logging
from typing import Optional

from bot.utils import get_text
from bot.constants import get_privacy_url_for
from bot.services.profile import get_or_create_profile, get_user_settings
from bot.keyboards import main_menu_keyboard, back_close_keyboard
from bot.services.category import create_default_categories, create_default_income_categories
from bot.utils.message_utils import send_message_with_cleanup, delete_message_with_effect
from bot.utils.commands import update_user_commands
from bot.services.affiliate import process_referral_link  # Новая реферальная система Telegram Stars
from expenses.models import Subscription, Profile, Expense, Income
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

router = Router(name="start")


def get_welcome_message(lang: str = 'ru', referral_message: str = '') -> str:
    """
    Генерирует приветственное сообщение для бота

    Args:
        lang: Язык сообщения ('ru' или 'en')
        referral_message: Дополнительное сообщение о реферальной ссылке

    Returns:
        Готовое приветственное сообщение
    """
    if lang == 'en':
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
Get beautiful PDF reports with charts

<b>🏠 Household:</b>
Track finances together with your family. Switch between personal and family views. Create a household and add members by sending them an invite link."""
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
Получайте красивые PDF отчеты с графиками

<b>🏠 Семейный бюджет:</b>
Ведите общий учет с семьёй. Переключайтесь между личным и семейным режимом просмотра. Создайте семью и добавляйте участников, отправив им приглашение."""

    # Добавляем реферальное сообщение, если есть
    if referral_message:
        text += referral_message

    return text


@router.message(Command("start"))
async def cmd_start(
    message: types.Message,
    state: FSMContext,
    command: Optional[CommandObject] = None,
    lang: str = 'ru'
):
    """Обработка команды /start - показать информацию о боте"""
    user_id = message.from_user.id

    # Проверяем, есть ли реферальный код или приглашение в семейный бюджет в команде
    referral_code = None
    family_token = None
    start_args = None
    if command and command.args:
        start_args = command.args.strip()
    else:
        data = await state.get_data()
        stored_args = data.get('start_command_args')
        if stored_args:
            start_args = stored_args.strip()

    if start_args:
        if start_args.startswith('ref_'):
            # Формат: /start ref_ABCD1234
            referral_code = start_args[4:]
        elif start_args.startswith('family_'):
            # Формат: /start family_TOKEN
            family_token = start_args[7:]
    
    # Создаем или получаем профиль пользователя
    profile = await get_or_create_profile(
        telegram_id=user_id,
        language_code=message.from_user.language_code
    )
    
    # Проверяем, новый ли это пользователь
    # Считаем пользователя новым, если у него:
    # 1. Нет записей о тратах
    # 2. Нет записей о доходах
    # 3. Нет истории подписок (включая истёкшие)
    has_expenses = await Expense.objects.filter(profile=profile).aexists()
    has_incomes = await Income.objects.filter(profile=profile).aexists()
    has_subscription_history = await Subscription.objects.filter(profile=profile).aexists()

    is_new_user = not has_expenses and not has_incomes and not has_subscription_history

    logger.info(f"[START] User {user_id} status: has_expenses={has_expenses}, has_incomes={has_incomes}, has_subscription_history={has_subscription_history}, is_new_user={is_new_user}, is_beta_tester={profile.is_beta_tester}")
    
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
    
    # Проверка принятия политики конфиденциальности
    if not profile.accepted_privacy:
        # Сохраняем аргументы /start для обработки после принятия политики
        await state.update_data(start_command_args=start_args)
        short = get_text('short_privacy_for_acceptance', display_lang)
        policy_url = get_privacy_url_for(display_lang)
        text_priv = (
            f"<b>📄 Политика конфиденциальности</b>\n\n"
            f"{short}\n\n"
            f"Полный текст: <a href=\"{policy_url}\">по ссылке</a>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=get_text('btn_decline_privacy', display_lang), callback_data='privacy_decline'),
                InlineKeyboardButton(text=get_text('btn_accept_privacy', display_lang), callback_data='privacy_accept'),
            ]
        ])
        await message.answer(text_priv, reply_markup=kb, parse_mode='HTML')
        return

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
        logger.info(f"[START] Processing referral code '{referral_code}' for new user {user_id}")
        try:
            # Сначала пробуем обработать как реферальную ссылку Telegram Stars
            affiliate_referral = await process_referral_link(user_id, referral_code)
            
            if affiliate_referral:
                # Успешно обработана ссылка Telegram Stars
                # ВАЖНО: НЕ привязываем к старой системе, если пользователь в новой!
                if display_lang == 'en':
                    referral_message = "\n\n⭐ You joined via an affiliate link! Your friend will receive commission from your purchases."
                else:
                    referral_message = "\n\n⭐ Вы перешли по партнёрской ссылке! Ваш друг будет получать комиссию с ваших покупок."

                logger.info(f"New user {user_id} registered via Telegram Stars affiliate link from {affiliate_referral.referrer.telegram_id}")
                # Старая система с бонусными днями ПОЛНОСТЬЮ УДАЛЕНА
                # Используется только новая система Telegram Stars
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
        
        logger.info(f"[START] Subscription check for user {user_id}: is_new_user={is_new_user}, has_active_subscription={has_active_subscription}, existing_trial={existing_trial}")

        # Создаем пробную подписку только если:
        # 1. Это новый пользователь
        # 2. У него нет активной подписки
        # 3. У него никогда не было пробной подписки
        # 4. Он не beta_tester
        if is_new_user and not has_active_subscription and not existing_trial:
            try:
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
                logger.info(f"[START] Successfully created trial subscription for new user {user_id}, expires: {trial_end}")
            except Exception as e:
                logger.error(f"[START] Failed to create trial subscription for user {user_id}: {e}")
        else:
            logger.info(f"[START] Not creating trial subscription for user {user_id}: is_new_user={is_new_user}, has_active_subscription={has_active_subscription}, existing_trial={existing_trial}")
    else:
        logger.info(f"[START] User {user_id} is a beta tester, skipping trial subscription")
    
    # Обновляем команды бота для пользователя
    await update_user_commands(message.bot, user_id)

    # Получаем приветственное сообщение
    text = get_welcome_message(display_lang, referral_message)

    # Отправляем информацию без кнопок
    await send_message_with_cleanup(message, state, text, parse_mode="HTML")
    # Сбрасываем сохраненные аргументы /start после успешной обработки
    await state.update_data(start_command_args=None)




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


@router.callback_query(F.data == 'privacy_accept')
async def privacy_accept(callback: types.CallbackQuery, state: FSMContext):
    try:
        profile = await Profile.objects.aget(telegram_id=callback.from_user.id)
        profile.accepted_privacy = True
        await profile.asave()
        await callback.answer('Согласие принято')
        try:
            await callback.message.delete()
        except Exception:
            pass

        # После принятия политики выполняем полную инициализацию нового пользователя
        user_id = callback.from_user.id
        display_lang = profile.language_code or 'ru'

        # Создаем базовые категории для нового пользователя
        categories_created = await create_default_categories(user_id)
        # Создаем базовые категории доходов
        income_categories_created = await create_default_income_categories(user_id)

        # Проверяем, новый ли это пользователь для создания пробной подписки
        # Считаем пользователя новым, если у него:
        # 1. Нет записей о тратах
        # 2. Нет записей о доходах
        # 3. Нет истории подписок (включая истёкшие)
        has_expenses = await Expense.objects.filter(profile=profile).aexists()
        has_incomes = await Income.objects.filter(profile=profile).aexists()
        has_subscription_history = await Subscription.objects.filter(profile=profile).aexists()

        is_new_user = not has_expenses and not has_incomes and not has_subscription_history

        logger.info(f"[PRIVACY_ACCEPT] User {user_id} status: has_expenses={has_expenses}, has_incomes={has_incomes}, has_subscription_history={has_subscription_history}, is_new_user={is_new_user}, is_beta_tester={profile.is_beta_tester}")

        # Создаем пробную подписку для новых пользователей (если не beta_tester)
        if not profile.is_beta_tester and is_new_user:
            # Проверяем существующие подписки
            existing_trial = await profile.subscriptions.filter(
                type='trial'
            ).aexists()

            has_active_subscription = await profile.subscriptions.filter(
                is_active=True,
                end_date__gt=timezone.now()
            ).aexists()

            logger.info(f"[PRIVACY_ACCEPT] Subscription check for user {user_id}: is_new_user={is_new_user}, has_active_subscription={has_active_subscription}, existing_trial={existing_trial}")

            # Создаем пробную подписку только если:
            # 1. Это новый пользователь
            # 2. У него нет активной подписки
            # 3. У него никогда не было пробной подписки
            # 4. Он не beta_tester
            if not has_active_subscription and not existing_trial:
                try:
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
                    logger.info(f"[PRIVACY_ACCEPT] Successfully created trial subscription for new user {user_id}, expires: {trial_end}")
                except Exception as e:
                    logger.error(f"[PRIVACY_ACCEPT] Failed to create trial subscription for user {user_id}: {e}")
            else:
                logger.info(f"[PRIVACY_ACCEPT] Not creating trial subscription for user {user_id}: has_active_subscription={has_active_subscription}, existing_trial={existing_trial}")
        elif profile.is_beta_tester:
            logger.info(f"[PRIVACY_ACCEPT] User {user_id} is a beta tester, skipping trial subscription")

        # Получаем сохраненные аргументы /start для обработки реферальных ссылок
        data = await state.get_data()
        start_args = data.get('start_command_args')

        # Обработка реферальной ссылки для новых пользователей
        referral_message = ""
        if is_new_user and start_args and start_args.startswith('ref_'):
            referral_code = start_args[4:]
            logger.info(f"[PRIVACY_ACCEPT] Processing referral code '{referral_code}' for new user {user_id}")
            try:
                # Обрабатываем реферальную ссылку Telegram Stars
                affiliate_referral = await process_referral_link(user_id, referral_code)

                if affiliate_referral:
                    # Успешно обработана ссылка Telegram Stars
                    if display_lang == 'en':
                        referral_message = "\n\n⭐ You joined via an affiliate link! Your friend will receive commission from your purchases."
                    else:
                        referral_message = "\n\n⭐ Вы перешли по партнёрской ссылке! Ваш друг будет получать комиссию с ваших покупок."

                    logger.info(f"New user {user_id} registered via Telegram Stars affiliate link after privacy acceptance")
            except Exception as e:
                logger.error(f"Error processing referral code after privacy acceptance: {e}")

        # Обновляем команды бота для пользователя
        await update_user_commands(callback.bot, user_id)

        # Получаем приветственное сообщение
        text = get_welcome_message(display_lang, referral_message)

        # Отправляем приветственное сообщение
        await callback.message.answer(text, parse_mode="HTML")

        # Сбрасываем сохраненные аргументы /start после успешной обработки
        await state.update_data(start_command_args=None)

    except Exception as e:
        import traceback
        logger.error(f"privacy_accept error: {e}\n{traceback.format_exc()}")
        await callback.answer('Ошибка. Попробуйте /start', show_alert=True)


@router.callback_query(F.data == 'privacy_decline')
async def privacy_decline(callback: types.CallbackQuery):
    # Определяем язык
    try:
        profile = await Profile.objects.aget(telegram_id=callback.from_user.id)
        display_lang = profile.language_code or 'ru'
    except Exception:
        display_lang = 'ru'
    msg = get_text('privacy_decline_message', display_lang)
    await callback.message.edit_text(msg)
    await callback.answer()






@router.callback_query(F.data == "start")
async def callback_start(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать информацию о боте через callback"""
    # Обновляем команды бота для пользователя
    await update_user_commands(callback.bot, callback.from_user.id)

    # Получаем приветственное сообщение
    text = get_welcome_message(lang)

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
