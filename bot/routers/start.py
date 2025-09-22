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
from bot.services.utm_tracking import parse_utm_source, save_utm_data  # UTM-метки
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

    # Проверяем параметры команды (реферальный код, семейный токен, UTM-метки)
    referral_code = None
    family_token = None
    utm_data = None
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
            # Формат: /start ref_ABCD1234 - реферальная система Telegram Stars
            referral_code = start_args[4:]
        elif start_args.startswith('family_'):
            # Формат: /start family_TOKEN - приглашение в семейный бюджет
            family_token = start_args[7:]
        else:
            # Пробуем распарсить как UTM-метку
            utm_data = await parse_utm_source(start_args)
    
    # Пытаемся получить существующий профиль пользователя, чтобы не создавать
    # записи до принятия политики конфиденциальности
    try:
        profile = await Profile.objects.aget(telegram_id=user_id)
        profile_exists = True
    except Profile.DoesNotExist:
        profile = None
        profile_exists = False

    if profile_exists:
        # Проверяем, новый ли это пользователь
        # Считаем пользователя новым, если у него:
        # 1. Нет записей о тратах
        # 2. Нет записей о доходах
        # 3. Нет истории подписок (включая истёкшие)
        has_expenses = await Expense.objects.filter(profile=profile).aexists()
        has_incomes = await Income.objects.filter(profile=profile).aexists()
        has_subscription_history = await Subscription.objects.filter(profile=profile).aexists()

        is_new_user = not has_expenses and not has_incomes and not has_subscription_history

        logger.info(
            "[START] User %s status: has_expenses=%s, has_incomes=%s, has_subscription_history=%s, is_new_user=%s, is_beta_tester=%s",
            user_id,
            has_expenses,
            has_incomes,
            has_subscription_history,
            is_new_user,
            profile.is_beta_tester,
        )

        # Определяем язык для отображения
        # Если у пользователя уже есть сохраненный язык - используем его
        # Если поле пустое — определяем по языку системы Telegram
        if profile.language_code:
            display_lang = profile.language_code
        else:
            user_language_code = message.from_user.language_code or 'en'
            display_lang = 'ru' if user_language_code.startswith('ru') else 'en'
            profile.language_code = display_lang
            await profile.asave()

        # Сохраняем UTM-данные для существующего пользователя (если есть)
        if utm_data and is_new_user:
            logger.info(f"[START] Processing UTM for new user {user_id}: {start_args}")
            saved = await save_utm_data(profile, utm_data)
            if saved:
                logger.info(f"[START] UTM data saved for user {user_id}: source={utm_data.get('source')}, campaign={utm_data.get('campaign')}")
            else:
                logger.info(f"[START] UTM data NOT saved for user {user_id} (already has source or error)")

        # Проверка принятия политики конфиденциальности до выполнения
        # остальных действий
        if not profile.accepted_privacy:
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
                    InlineKeyboardButton(
                        text=get_text('btn_decline_privacy', display_lang),
                        callback_data='privacy_decline'
                    ),
                    InlineKeyboardButton(
                        text=get_text('btn_accept_privacy', display_lang),
                        callback_data='privacy_accept'
                    ),
                ]
            ])
            await message.answer(text_priv, reply_markup=kb, parse_mode='HTML')
            return

        # Обработка приглашения в семейный бюджет для существующих пользователей
        if family_token:
            from bot.routers.household import process_family_invite
            await process_family_invite(message, family_token)
            return  # Прекращаем выполнение команды /start

    else:
        # Новый пользователь — сохраняем данные во временное состояние FSM
        user_language_code = message.from_user.language_code or 'en'
        display_lang = 'ru' if user_language_code and user_language_code.startswith('ru') else 'en'

        await state.update_data(
            start_command_args=start_args,
            pending_profile_data={
                'telegram_id': user_id,
                'language_code': display_lang,
                'raw_language_code': message.from_user.language_code,
                'username': message.from_user.username,
                'first_name': message.from_user.first_name,
                'last_name': message.from_user.last_name,
            },
        )

        short = get_text('short_privacy_for_acceptance', display_lang)
        policy_url = get_privacy_url_for(display_lang)
        text_priv = (
            f"<b>📄 Политика конфиденциальности</b>\n\n"
            f"{short}\n\n"
            f"Полный текст: <a href=\"{policy_url}\">по ссылке</a>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text('btn_decline_privacy', display_lang),
                    callback_data='privacy_decline'
                ),
                InlineKeyboardButton(
                    text=get_text('btn_accept_privacy', display_lang),
                    callback_data='privacy_accept'
                ),
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
                kb.button(text=no_text, callback_data="close")
                kb.button(text=yes_text, callback_data=f"family_accept:{inv.token}")
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
    # Обрабатываем реферальные коды только если это не UTM-метка
    if is_new_user and referral_code and not utm_data:
        logger.info(f"[START] Processing referral code '{referral_code}' for new user {user_id}")
        try:
            # Сначала пробуем обработать как реферальную ссылку Telegram Stars
            affiliate_referral = await process_referral_link(user_id, referral_code)
            
            if affiliate_referral:
                # Успешно обработана ссылка Telegram Stars
                # ВАЖНО: НЕ привязываем к старой системе, если пользователь в новой!
                if display_lang == 'en':
                    referral_message = (
                        "\n\n🤝 You joined via an affiliate link! "
                        "Your friend will get a one-time subscription extension matching your first plan."
                    )
                else:
                    referral_message = (
                        "\n\n🤝 Вы перешли по партнёрской ссылке! "
                        "Ваш друг получит однократное продление подписки на срок вашей первой покупки."
                    )

                logger.info(f"New user {user_id} registered via Telegram Stars affiliate link from {affiliate_referral.referrer.telegram_id}")
                # Старая система с бонусными днями ПОЛНОСТЬЮ УДАЛЕНА
                # Используется только новая система Telegram Stars
        except Exception as e:
            logger.error(f"Error processing referral code: {e}")
    
    # НЕ создаем пробную подписку здесь - она будет создана после принятия политики конфиденциальности
    # Это предотвращает дублирование подписок
    logger.info(f"[START] User {user_id}: is_new_user={is_new_user}, is_beta_tester={profile.is_beta_tester}")
    
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
        user_id = callback.from_user.id
        data = await state.get_data()
        start_args = data.get('start_command_args')
        pending_profile_data = data.get('pending_profile_data') or {}

        try:
            profile = await Profile.objects.aget(telegram_id=user_id)
        except Profile.DoesNotExist:
            profile = None

        if profile is None:
            language_code = pending_profile_data.get('language_code')
            raw_language_code = pending_profile_data.get('raw_language_code')
            if not language_code:
                user_language_code = raw_language_code or callback.from_user.language_code or 'en'
                language_code = 'ru' if user_language_code and user_language_code.startswith('ru') else 'en'
            profile = await get_or_create_profile(
                telegram_id=user_id,
                language_code=language_code,
            )
            if not profile.language_code:
                profile.language_code = language_code
        else:
            language_code = profile.language_code

        display_lang = language_code or pending_profile_data.get('language_code') or 'ru'

        if not profile.language_code:
            profile.language_code = display_lang
        profile.accepted_privacy = True
        await profile.asave()

        # Обрабатываем UTM-данные после принятия политики
        if start_args and not start_args.startswith('ref_') and not start_args.startswith('family_'):
            utm_data = await parse_utm_source(start_args)
            if utm_data:
                await save_utm_data(profile, utm_data)
                logger.info(f"[PRIVACY_ACCEPT] UTM data saved for user {user_id}: source={utm_data.get('source')}")

        await callback.answer('Согласие принято')
        try:
            await callback.message.delete()
        except Exception:
            pass

        await create_default_categories(user_id)
        await create_default_income_categories(user_id)

        has_expenses = await Expense.objects.filter(profile=profile).aexists()
        has_incomes = await Income.objects.filter(profile=profile).aexists()
        has_subscription_history = await Subscription.objects.filter(profile=profile).aexists()

        is_new_user = not has_expenses and not has_incomes and not has_subscription_history

        logger.info(
            "[PRIVACY_ACCEPT] User %s status: has_expenses=%s, has_incomes=%s, has_subscription_history=%s, is_new_user=%s, is_beta_tester=%s",
            user_id,
            has_expenses,
            has_incomes,
            has_subscription_history,
            is_new_user,
            profile.is_beta_tester,
        )

        if not profile.is_beta_tester and is_new_user:
            existing_trial = await profile.subscriptions.filter(type='trial').aexists()
            has_active_subscription = await profile.subscriptions.filter(
                is_active=True,
                end_date__gt=timezone.now()
            ).aexists()

            logger.info(
                "[PRIVACY_ACCEPT] Subscription check for user %s: is_new_user=%s, has_active_subscription=%s, existing_trial=%s",
                user_id,
                is_new_user,
                has_active_subscription,
                existing_trial,
            )

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
                    logger.info(
                        "[PRIVACY_ACCEPT] Successfully created trial subscription for new user %s, expires: %s",
                        user_id,
                        trial_end,
                    )
                except Exception as e:
                    logger.error(
                        "[PRIVACY_ACCEPT] Failed to create trial subscription for user %s: %s",
                        user_id,
                        e,
                    )
            else:
                logger.info(
                    "[PRIVACY_ACCEPT] Not creating trial subscription for user %s: has_active_subscription=%s, existing_trial=%s",
                    user_id,
                    has_active_subscription,
                    existing_trial,
                )
        elif profile.is_beta_tester:
            logger.info("[PRIVACY_ACCEPT] User %s is a beta tester, skipping trial subscription", user_id)

        family_token = None
        if start_args and start_args.startswith('family_'):
            family_token = start_args[7:]

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
                    kb.button(text=no_text, callback_data='close')
                    kb.button(text=yes_text, callback_data=f"family_accept:{inv.token}")
                    kb.adjust(2)
                    await callback.message.answer(confirm_text, reply_markup=kb.as_markup(), parse_mode="HTML")
                else:
                    await callback.message.answer(
                        "Invite link is invalid or expired" if display_lang == 'en' else "Ссылка-приглашение недействительна или истек срок действия"
                    )
            except Exception as e:
                logger.error(f"Error handling family invite after privacy acceptance: {e}")

        referral_message = ""
        if is_new_user and start_args and start_args.startswith('ref_'):
            referral_code = start_args[4:]
            logger.info(
                "[PRIVACY_ACCEPT] Processing referral code '%s' for new user %s",
                referral_code,
                user_id,
            )
            try:
                affiliate_referral = await process_referral_link(user_id, referral_code)

                if affiliate_referral:
                    if display_lang == 'en':
                        referral_message = "\n\n🤝 You joined via an affiliate link! Your friend will get a one-time subscription extension matching your first purchase."
                    else:
                        referral_message = "\n\n🤝 Вы перешли по партнёрской ссылке! Ваш друг получит однократное продление подписки на срок вашей первой покупки."

                    logger.info("New user %s registered via Telegram Stars affiliate link after privacy acceptance", user_id)
            except Exception as e:
                logger.error(f"Error processing referral code after privacy acceptance: {e}")

        await update_user_commands(callback.bot, user_id)

        text = get_welcome_message(display_lang, referral_message)
        await callback.message.answer(text, parse_mode="HTML")

        await state.update_data(start_command_args=None, pending_profile_data=None)

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
