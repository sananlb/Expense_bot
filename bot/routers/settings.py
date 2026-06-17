"""
Router for user settings management
"""
from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from asgiref.sync import sync_to_async
from datetime import datetime
import pytz
import logging

from bot.keyboards import settings_keyboard, back_close_keyboard, get_language_keyboard, get_timezone_keyboard, get_currency_keyboard, delete_profile_step1_keyboard, delete_profile_final_keyboard
from bot.utils import get_text, set_user_language, get_user_language, format_amount
from bot.services.profile import get_or_create_profile
from bot.services.category import update_default_categories_language
from bot.utils.commands import update_user_commands
from bot.utils.logging_safe import log_safe_id
from bot.utils.message_utils import send_message_with_cleanup

logger = logging.getLogger(__name__)
router = Router(name="settings")


class SettingsStates(StatesGroup):
    """Состояния для настроек"""
    language = State()
    timezone = State()
    currency = State()
    waiting_for_total_limit_amount = State()
    waiting_for_total_goal_amount = State()


@router.callback_query(F.data == "toggle_view_scope")
async def toggle_view_scope(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Переключить глобальный режим отображения (личный/семья)"""
    try:
        from django.db import transaction
        from expenses.models import UserSettings

        user_id = callback.from_user.id

        @sync_to_async
        def toggle_scope_atomic():
            """Атомарное переключение view_scope с блокировкой"""
            with transaction.atomic():
                from expenses.models import Profile
                # Блокируем профиль для предотвращения race condition
                profile = Profile.objects.select_for_update().select_related('household').get(telegram_id=user_id)

                # Получаем или создаем настройки
                settings, _ = UserSettings.objects.select_for_update().get_or_create(profile=profile)

                current = getattr(settings, 'view_scope', 'personal')

                # Нельзя переключиться в семейный режим, если нет домохозяйства
                if current == 'personal' and not profile.household_id:
                    return None, 'no_household'

                new_scope = 'household' if current == 'personal' else 'personal'
                settings.view_scope = new_scope
                settings.save()
                return new_scope, 'ok'

        new_scope, status = await toggle_scope_atomic()

        if status == 'no_household':
            warn = 'Нет семейного бюджета' if lang == 'ru' else 'No household'
            await callback.answer(warn, show_alert=True)
            return

        msg_key = 'scope_switched_to_household' if new_scope == 'household' else 'scope_switched_to_personal'
        await callback.answer(get_text(msg_key, lang))
        # Обновляем меню настроек
        await callback_settings(callback, state, lang)
    except Exception as e:
        logger.error(f"Error toggling view scope: {e}")
        await callback.answer(get_text('error_occurred', lang))


@router.message(Command("settings"))
async def cmd_settings(message: Message, state: FSMContext, lang: str = 'ru'):
    """Показать меню настроек"""
    from bot.utils.state_utils import clear_state_keep_cashback
    await clear_state_keep_cashback(state)
    
    try:
        profile = await get_or_create_profile(message.from_user.id)
        settings = await sync_to_async(lambda: profile.settings)()
        
        # Обновляем команды бота для пользователя
        await update_user_commands(message.bot, message.from_user.id)
        
        # Формируем текст с текущими настройками
        lang_text = 'Русский' if profile.language_code == 'ru' else 'English'
        
        # Форматируем часовой пояс в виде UTC+X
        if profile.timezone:
            try:
                tz = pytz.timezone(profile.timezone)
                now = datetime.now(tz)
                offset = now.utcoffset().total_seconds() / 3600
                if offset >= 0:
                    timezone_text = f"UTC+{int(offset)}"
                else:
                    timezone_text = f"UTC{int(offset)}"
            except (pytz.UnknownTimeZoneError, AttributeError, TypeError) as e:
                logger.debug(f"Error processing timezone {profile.timezone}: {e}")
                timezone_text = 'UTC+0'
        else:
            timezone_text = 'UTC+0'
            
        currency_text = profile.currency or 'RUB'
        view_scope = settings.view_scope if hasattr(settings, 'view_scope') else 'personal'

        # Базовый текст настроек
        text_lines = [
            f"{get_text('settings_menu', lang)}",
            "",
            f"{get_text('language', lang)}: {lang_text}",
            f"{get_text('timezone', lang)}: {timezone_text}",
            f"{get_text('currency', lang)}: {currency_text}",
        ]
        # Режим отображения больше не показываем в настройках
        # Проверяем подписку
        from bot.services.subscription import check_subscription
        has_subscription = await check_subscription(message.from_user.id)

        text = "\n".join(text_lines)

        await send_message_with_cleanup(
            message,
            state,
            text,
            reply_markup=settings_keyboard(lang, has_subscription, view_scope),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error showing settings: {e}")
        await send_message_with_cleanup(message, state, get_text('error_occurred', lang))


@router.callback_query(F.data == "settings")
async def callback_settings(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать меню настроек по callback"""
    from bot.utils.state_utils import clear_state_keep_cashback
    await clear_state_keep_cashback(state)

    try:
        profile = await get_or_create_profile(callback.from_user.id)
        settings = await sync_to_async(lambda: profile.settings)()

        # Обновляем команды бота для пользователя
        await update_user_commands(callback.bot, callback.from_user.id)
        
        # Формируем текст с текущими настройками
        lang_text = 'Русский' if profile.language_code == 'ru' else 'English'
        
        # Форматируем часовой пояс в виде UTC+X
        if profile.timezone:
            try:
                tz = pytz.timezone(profile.timezone)
                now = datetime.now(tz)
                offset = now.utcoffset().total_seconds() / 3600
                if offset >= 0:
                    timezone_text = f"UTC+{int(offset)}"
                else:
                    timezone_text = f"UTC{int(offset)}"
            except (pytz.UnknownTimeZoneError, AttributeError, TypeError) as e:
                logger.debug(f"Error processing timezone {profile.timezone}: {e}")
                timezone_text = 'UTC+0'
        else:
            timezone_text = 'UTC+0'
            
        currency_text = profile.currency or 'RUB'
        view_scope = settings.view_scope if hasattr(settings, 'view_scope') else 'personal'

        # Базовый текст настроек
        text_lines = [
            f"{get_text('settings_menu', lang)}",
            "",
            f"{get_text('language', lang)}: {lang_text}",
            f"{get_text('timezone', lang)}: {timezone_text}",
            f"{get_text('currency', lang)}: {currency_text}",
        ]
        # Режим отображения больше не показываем в настройках
        # Проверяем подписку
        from bot.services.subscription import check_subscription
        has_subscription = await check_subscription(callback.from_user.id)

        text = "\n".join(text_lines)

        await callback.message.edit_text(
            text,
            reply_markup=settings_keyboard(lang, has_subscription, view_scope),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error showing settings: {e}")
        await callback.answer(get_text('error_occurred', lang))


# ===== Общий лимит трат =====

def _total_limit_keyboard(lang: str, has_limit: bool) -> InlineKeyboardMarkup:
    """Клавиатура экрана общего лимита трат."""
    rows = []
    if has_limit:
        rows.append([InlineKeyboardButton(text=get_text('limit_edit_button', lang), callback_data="total_limit_edit")])
        rows.append([InlineKeyboardButton(text=get_text('limit_remove_button', lang), callback_data="total_limit_remove")])
    rows.append([InlineKeyboardButton(text=get_text('back', lang), callback_data="tools")])
    rows.append([InlineKeyboardButton(text=get_text('close', lang), callback_data="close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _prompt_total_limit_amount(callback: CallbackQuery, state: FSMContext, lang: str, change: bool = False):
    """Показывает приглашение ввести сумму общего лимита и переводит в FSM."""
    from bot.services.budget import get_limit
    if change:
        limit = await get_limit(callback.from_user.id, None)
        current = format_amount(limit.amount, limit.currency, lang) if limit else ''
        text = get_text('total_limit_input_prompt_change', lang).format(amount=current)
    else:
        text = get_text('total_limit_input_prompt', lang)

    await state.update_data(lang=lang)
    await state.set_state(SettingsStates.waiting_for_total_limit_amount)
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text('back', lang), callback_data="tools")],
            [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")],
        ]),
        parse_mode='HTML',
    )


@router.callback_query(F.data == "total_limit_edit")
async def total_limit_change(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Изменить общий лимит — сразу к вводу суммы."""
    lang = await get_user_language(callback.from_user.id)
    await _prompt_total_limit_amount(callback, state, lang, change=True)
    await callback.answer()


@router.callback_query(F.data == "total_limit_remove")
async def total_limit_remove(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Убрать общий лимит."""
    from bot.services.budget import remove_limit
    from bot.routers.tools import callback_tools
    lang = await get_user_language(callback.from_user.id)
    await remove_limit(callback.from_user.id, None)
    await callback.answer(get_text('limit_removed_success', lang))
    # Лимит вынесен в меню «Инструменты» — возвращаемся туда, а не в Настройки.
    await callback_tools(callback, state, lang)


@router.callback_query(F.data == "total_limit")
async def total_limit_entry(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Точка входа в общий лимит трат из меню «Инструменты»."""
    from bot.services.budget import get_limit_status
    from bot.utils.budget_display import format_limit_screen_body
    lang = await get_user_language(callback.from_user.id)
    status = await get_limit_status(callback.from_user.id, None)

    header = get_text('total_limit_header', lang)
    if status is not None:
        # Лимит установлен — показываем текущую настройку: сумму, потрачено, остаток, дни.
        try:
            await callback.message.edit_text(
                f"{header}\n\n{format_limit_screen_body(status, lang)}",
                reply_markup=_total_limit_keyboard(lang, has_limit=True),
                parse_mode='HTML',
            )
        except TelegramBadRequest:
            pass
        await callback.answer()
    else:
        # Лимита нет — приглашение ввести сумму.
        await _prompt_total_limit_amount(callback, state, lang, change=False)
        await callback.answer()


@router.message(SettingsStates.waiting_for_total_limit_amount)
async def process_total_limit_amount(message: Message, state: FSMContext,
                                     voice_text: str | None = None,
                                     voice_no_subscription: bool = False,
                                     voice_transcribe_failed: bool = False):
    """Обработка ввода суммы общего лимита (текст или голос)."""
    from bot.utils.expense_parser import convert_words_to_numbers
    from bot.utils.validators import parse_description_amount
    from bot.services.budget import set_limit

    lang = await get_user_language(message.from_user.id)

    # Извлекаем текст
    if message.voice:
        if voice_no_subscription:
            from bot.services.subscription import subscription_required_message, get_subscription_button
            await message.answer(subscription_required_message(), reply_markup=get_subscription_button(), parse_mode="HTML")
            return
        if voice_transcribe_failed or not voice_text:
            await message.answer("❌ Не удалось распознать голосовое сообщение. Попробуйте ещё раз или введите текстом.")
            return
        raw = voice_text
    elif message.text:
        raw = message.text.strip()
    else:
        await message.answer(get_text('limit_invalid_amount', lang))
        return

    # Парсим сумму
    try:
        parsed = parse_description_amount(convert_words_to_numbers(raw), allow_only_amount=True)
        amount = parsed.get('amount')
    except ValueError:
        amount = None

    if not amount or amount <= 0:
        await send_message_with_cleanup(message, state, get_text('limit_invalid_amount', lang))
        return

    try:
        await set_limit(message.from_user.id, None, amount)
    except ValueError as e:
        await send_message_with_cleanup(message, state, f"❌ {str(e)}")
        return

    await state.set_state(None)

    # Показываем экран общего лимита с текущей настройкой: сумма, потрачено, остаток, дни.
    from bot.services.budget import get_limit_status
    from bot.utils.budget_display import format_limit_screen_body
    status = await get_limit_status(message.from_user.id, None)
    header = get_text('total_limit_header', lang)
    body = format_limit_screen_body(status, lang) if status else ''
    await send_message_with_cleanup(
        message, state,
        f"{header}\n\n{body}",
        reply_markup=_total_limit_keyboard(lang, has_limit=True),
        parse_mode='HTML',
    )


# ===== Общая цель дохода =====

def _total_goal_keyboard(lang: str, has_goal: bool) -> InlineKeyboardMarkup:
    """Клавиатура экрана общей цели дохода."""
    rows = []
    if has_goal:
        rows.append([
            InlineKeyboardButton(
                text=get_text('goal_edit_button', lang),
                callback_data="total_goal_edit",
            )
        ])
        rows.append([
            InlineKeyboardButton(
                text=get_text('goal_remove_button', lang),
                callback_data="total_goal_remove",
            )
        ])
    rows.append([InlineKeyboardButton(text=get_text('back', lang), callback_data="tools")])
    rows.append([InlineKeyboardButton(text=get_text('close', lang), callback_data="close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _prompt_total_goal_amount(
    callback: CallbackQuery,
    state: FSMContext,
    lang: str,
    change: bool = False,
) -> None:
    """Показывает приглашение ввести общую цель и переводит в FSM."""
    from bot.services.income_goal import get_goal

    if change:
        goal = await get_goal(callback.from_user.id, None)
        current = format_amount(goal.amount, goal.currency, lang) if goal else ''
        text = get_text('total_goal_input_prompt_change', lang).format(amount=current)
    else:
        text = get_text('total_goal_input_prompt', lang)

    await state.update_data(lang=lang)
    await state.set_state(SettingsStates.waiting_for_total_goal_amount)
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text('back', lang), callback_data="tools")],
            [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")],
        ]),
        parse_mode='HTML',
    )


@router.callback_query(F.data == "total_goal_edit")
async def total_goal_change(
    callback: CallbackQuery,
    state: FSMContext,
    lang: str = 'ru',
):
    """Изменяет общую цель дохода."""
    lang = await get_user_language(callback.from_user.id)
    await _prompt_total_goal_amount(callback, state, lang, change=True)
    await callback.answer()


@router.callback_query(F.data == "total_goal_remove")
async def total_goal_remove(
    callback: CallbackQuery,
    state: FSMContext,
    lang: str = 'ru',
):
    """Убирает общую цель дохода."""
    from bot.services.income_goal import remove_goal
    from bot.routers.tools import callback_tools

    lang = await get_user_language(callback.from_user.id)
    await remove_goal(callback.from_user.id, None)
    await callback.answer(get_text('goal_removed_success', lang))
    # Цель дохода вынесена в меню «Инструменты» — возвращаемся туда.
    await callback_tools(callback, state, lang)


@router.callback_query(F.data == "total_goal")
async def total_goal_entry(
    callback: CallbackQuery,
    state: FSMContext,
    lang: str = 'ru',
):
    """Открывает общую цель дохода из меню «Инструменты»."""
    from bot.services.income_goal import get_goal_status
    from bot.utils.income_goal_display import format_goal_screen_body

    lang = await get_user_language(callback.from_user.id)
    status = await get_goal_status(callback.from_user.id, None)
    header = get_text('total_goal_header', lang)
    if status is not None:
        # Цель установлена — показываем текущую настройку: сумму, получено, остаток, дни.
        try:
            await callback.message.edit_text(
                f"{header}\n\n{format_goal_screen_body(status, lang)}",
                reply_markup=_total_goal_keyboard(lang, has_goal=True),
                parse_mode='HTML',
            )
        except TelegramBadRequest:
            pass
        await callback.answer()
    else:
        await _prompt_total_goal_amount(callback, state, lang)
        await callback.answer()


@router.message(SettingsStates.waiting_for_total_goal_amount)
async def process_total_goal_amount(
    message: Message,
    state: FSMContext,
    voice_text: str | None = None,
    voice_no_subscription: bool = False,
    voice_transcribe_failed: bool = False,
):
    """Обрабатывает текстовый или голосовой ввод общей цели дохода."""
    from bot.services.income_goal import set_goal
    from bot.utils.expense_parser import convert_words_to_numbers
    from bot.utils.validators import parse_description_amount

    lang = await get_user_language(message.from_user.id)
    if message.voice:
        if voice_no_subscription:
            from bot.services.subscription import (
                get_subscription_button,
                subscription_required_message,
            )
            await message.answer(
                subscription_required_message(),
                reply_markup=get_subscription_button(),
                parse_mode="HTML",
            )
            return
        if voice_transcribe_failed or not voice_text:
            await message.answer(get_text('voice_recognition_failed', lang))
            return
        raw = voice_text
    elif message.text:
        raw = message.text.strip()
    else:
        await message.answer(get_text('goal_invalid_amount', lang))
        return

    try:
        parsed = parse_description_amount(
            convert_words_to_numbers(raw),
            allow_only_amount=True,
        )
        amount = parsed.get('amount')
    except ValueError:
        amount = None

    if not amount or amount <= 0:
        await send_message_with_cleanup(
            message,
            state,
            get_text('goal_invalid_amount', lang),
        )
        return

    try:
        await set_goal(message.from_user.id, None, amount)
    except ValueError as exc:
        await send_message_with_cleanup(message, state, f"❌ {exc}")
        return

    await state.set_state(None)
    # Показываем экран цели с текущей настройкой: сумма, получено, остаток, дни.
    from bot.services.income_goal import get_goal_status
    from bot.utils.income_goal_display import format_goal_screen_body
    status = await get_goal_status(message.from_user.id, None)
    body = format_goal_screen_body(status, lang) if status else ''
    await send_message_with_cleanup(
        message,
        state,
        f"{get_text('total_goal_header', lang)}\n\n{body}",
        reply_markup=_total_goal_keyboard(lang, has_goal=True),
        parse_mode='HTML',
    )


@router.callback_query(F.data == "change_language")
async def change_language(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Изменить язык интерфейса"""
    await state.set_state(SettingsStates.language)
    
    await callback.message.edit_text(
        get_text('change_language_prompt', lang),
        reply_markup=get_language_keyboard(lang)
    )


@router.callback_query(SettingsStates.language, F.data.startswith("lang_"))
async def process_language_change(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Обработать изменение языка"""
    new_lang = callback.data.replace('lang_', '')
    
    try:
        # Сохраняем язык в профиле
        profile = await get_or_create_profile(callback.from_user.id)
        profile.language_code = new_lang
        await sync_to_async(profile.save)()
        
        # Обновляем язык в middleware
        await set_user_language(callback.from_user.id, new_lang)
        
        # Обновляем язык стандартных категорий
        await update_default_categories_language(callback.from_user.id, new_lang)
        
        # Обновляем команды бота для пользователя
        await update_user_commands(callback.bot, callback.from_user.id)
        
        await callback.answer(get_text('language_changed', new_lang))
        lang = new_lang
        
    except Exception as e:
        logger.error(f"Error changing language: {e}")
        await callback.answer(get_text('error_occurred', lang))
    
    # Возвращаемся в меню настроек
    await callback_settings(callback, state, lang)


@router.callback_query(F.data == "change_timezone")
async def change_timezone(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Изменить часовой пояс"""
    await state.set_state(SettingsStates.timezone)
    
    await callback.message.edit_text(
        get_text('change_timezone', lang),
        reply_markup=get_timezone_keyboard(lang)
    )


@router.callback_query(SettingsStates.timezone, F.data.startswith("tz_"))
async def process_timezone_change(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Обработать изменение часового пояса"""
    # Извлекаем смещение UTC
    offset_str = callback.data.replace('tz_', '')
    
    try:
        # Преобразуем смещение в часовой пояс
        if offset_str == '0':
            timezone_str = 'UTC'
        else:
            offset = int(offset_str)
            # Используем стандартные часовые пояса
            timezone_map = {
                -11: 'Pacific/Midway', -10: 'Pacific/Honolulu', -9: 'America/Anchorage',
                -8: 'America/Los_Angeles', -7: 'America/Denver', -6: 'America/Chicago',
                -5: 'America/New_York', -4: 'America/Halifax', -3: 'America/Sao_Paulo',
                -2: 'Atlantic/South_Georgia', -1: 'Atlantic/Azores', 0: 'UTC',
                1: 'Europe/Paris', 2: 'Europe/Athens', 3: 'Europe/Moscow',
                4: 'Asia/Dubai', 5: 'Asia/Karachi', 6: 'Asia/Almaty',
                7: 'Asia/Bangkok', 8: 'Asia/Hong_Kong', 9: 'Asia/Tokyo',
                10: 'Australia/Sydney', 11: 'Pacific/Noumea', 12: 'Pacific/Auckland'
            }
            timezone_str = timezone_map.get(offset, 'UTC')
        
        # Сохраняем часовой пояс в профиле
        profile = await get_or_create_profile(callback.from_user.id)
        profile.timezone = timezone_str
        await sync_to_async(profile.save)()
        
        await callback.answer(get_text('timezone_changed', lang))
        
    except Exception as e:
        logger.error(f"Error changing timezone: {e}")
        await callback.answer(get_text('error_occurred', lang))
    
    # Возвращаемся в меню настроек
    await callback_settings(callback, state, lang)


@router.callback_query(F.data == "change_currency")
async def change_currency(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Изменить валюту"""
    from expenses.models import UserSettings

    await state.set_state(SettingsStates.currency)

    # Получаем статус автоконвертации
    profile = await get_or_create_profile(callback.from_user.id)
    user_settings = await sync_to_async(
        lambda: UserSettings.objects.filter(profile=profile).first()
    )()
    auto_convert = user_settings.auto_convert_currency if user_settings else True

    await callback.message.edit_text(
        get_text('change_currency', lang),
        reply_markup=get_currency_keyboard(lang, auto_convert=auto_convert)
    )


@router.callback_query(SettingsStates.currency, F.data.startswith("curr_"))
async def process_currency_change(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Обработать изменение валюты"""
    currency = callback.data.replace('curr_', '').upper()

    try:
        # Сохраняем валюту в профиле
        profile = await get_or_create_profile(callback.from_user.id)
        profile.currency = currency
        await sync_to_async(profile.save)()

        await callback.answer(get_text('currency_changed', lang))

    except Exception as e:
        logger.error(f"Error changing currency: {e}")
        await callback.answer(get_text('error_occurred', lang))

    # Возвращаемся в меню настроек
    await callback_settings(callback, state, lang)


@router.callback_query(F.data == "toggle_auto_convert")
async def toggle_auto_convert(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Переключатель автоконвертации валют"""
    from expenses.models import UserSettings

    profile = await get_or_create_profile(callback.from_user.id)

    user_settings, created = await sync_to_async(
        lambda: UserSettings.objects.get_or_create(profile=profile)
    )()

    user_settings.auto_convert_currency = not user_settings.auto_convert_currency
    await sync_to_async(user_settings.save)()

    status = "enabled" if user_settings.auto_convert_currency else "disabled"

    await callback.answer(get_text(f'auto_convert_{status}', lang))

    # Обновляем клавиатуру валют с новым статусом конвертации
    keyboard = get_currency_keyboard(lang=lang, auto_convert=user_settings.auto_convert_currency)
    await callback.message.edit_reply_markup(reply_markup=keyboard)


# ═══════════════════════════════════════════════════════════
# DELETE PROFILE HANDLERS
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "delete_profile")
async def delete_profile_step1(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Экран 2: Показать что будет удалено"""
    await callback.answer()

    confirm_text = (
        f"{get_text('delete_profile_confirm_title', lang)}\n\n"
        f"{get_text('delete_profile_confirm_list', lang)}\n\n"
        f"{get_text('delete_profile_warning', lang)}"
    )

    await callback.message.edit_text(
        confirm_text,
        reply_markup=delete_profile_step1_keyboard(lang),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "delete_profile_step2")
async def delete_profile_step2(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Экран 3: Финальная проверка перед удалением"""
    await callback.answer()

    final_text = (
        f"{get_text('delete_profile_final_title', lang)}\n\n"
        f"{get_text('delete_profile_final_question', lang)}"
    )

    await callback.message.edit_text(
        final_text,
        reply_markup=delete_profile_final_keyboard(lang),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "cancel_delete_profile")
async def cancel_delete_profile(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Отмена удаления — вернуться в настройки"""
    await callback.answer()
    await callback_settings(callback, state, lang)


@router.callback_query(F.data == "confirm_delete_profile")
async def confirm_delete_profile(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Экран 4: Выполнить удаление профиля"""
    await callback.answer()

    user_id = callback.from_user.id

    # Вспомогательная функция очистки состояния
    async def cleanup_user_state():
        """Очистка FSM state и Redis ключей"""
        await state.clear()
        try:
            from django.core.cache import cache
            cache.delete(f"expense_reminder_sent:{user_id}")
        except Exception:
            pass  # Не критично

    try:
        from bot.services.profile import delete_user_profile
        success, error_code = await delete_user_profile(user_id)

        if success:
            await cleanup_user_state()
            await callback.message.edit_text(
                get_text('delete_profile_success', lang)
            )
        elif error_code == "NOT_FOUND":
            # Профиль уже удалён — тоже чистим состояние
            await cleanup_user_state()
            await callback.message.edit_text(
                get_text('delete_profile_not_found', lang)
            )
        else:
            await callback.message.edit_text(
                get_text('delete_profile_error', lang)
            )

    except Exception as e:
        logger.error("Error deleting profile for %s: %s", log_safe_id(user_id, "user"), e)
        await callback.message.edit_text(
            get_text('delete_profile_error', lang)
        )
