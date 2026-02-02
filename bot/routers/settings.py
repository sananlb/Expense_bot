"""
Router for user settings management
"""
from aiogram import Router, F
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
from bot.services.profile import get_or_create_profile, get_user_settings, toggle_cashback
from bot.services.category import update_default_categories_language
from bot.utils.commands import update_user_commands
from bot.utils.message_utils import send_message_with_cleanup

logger = logging.getLogger(__name__)
router = Router(name="settings")


class SettingsStates(StatesGroup):
    """Состояния для настроек"""
    language = State()
    timezone = State()
    currency = State()


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

        # Получаем настройки кешбэка
        user_settings = await get_user_settings(message.from_user.id)
        cashback_enabled = user_settings.cashback_enabled if hasattr(user_settings, 'cashback_enabled') else True

        await send_message_with_cleanup(
            message, 
            state, 
            text, 
            reply_markup=settings_keyboard(lang, cashback_enabled, has_subscription, view_scope),
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

        # Получаем настройки кешбэка
        user_settings = await get_user_settings(callback.from_user.id)
        cashback_enabled = user_settings.cashback_enabled if hasattr(user_settings, 'cashback_enabled') else True
        await callback.message.edit_text(
            text,
            reply_markup=settings_keyboard(lang, cashback_enabled, has_subscription, view_scope),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error showing settings: {e}")
        await callback.answer(get_text('error_occurred', lang))


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


@router.callback_query(F.data == "toggle_cashback")
async def handle_toggle_cashback(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Переключить кешбэк"""
    try:
        # Получаем настройки пользователя
        user_settings = await get_user_settings(callback.from_user.id)

        # Если кешбек выключен и пользователь хочет его включить - проверяем подписку
        if not user_settings.cashback_enabled:
            from bot.services.subscription import check_subscription
            has_subscription = await check_subscription(callback.from_user.id)

            if not has_subscription:
                # Показываем сообщение с кнопкой "Оформить подписку"
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=get_text('get_subscription', lang), callback_data="menu_subscription")],
                    [InlineKeyboardButton(text=get_text('back', lang), callback_data="settings")],
                    [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
                ])

                await callback.message.edit_text(
                    get_text('cashback_subscription_required', lang),
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                await callback.answer()
                return

        # Переключаем состояние кешбэка
        new_state = await toggle_cashback(callback.from_user.id)

        # Обновляем команды бота для пользователя (добавляем или убираем /cashback)
        await update_user_commands(callback.bot, callback.from_user.id)

        # Отправляем уведомление
        if new_state:
            await callback.answer(get_text('cashback_enabled_message', lang))
        else:
            await callback.answer(get_text('cashback_disabled_message', lang))

        # Обновляем меню настроек с новым состоянием кнопки кешбека
        await callback_settings(callback, state, lang)

    except Exception as e:
        logger.error(f"Error toggling cashback: {e}")
        await callback.answer(get_text('error_occurred', lang))


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
    await state.set_state(SettingsStates.currency)
    
    await callback.message.edit_text(
        get_text('change_currency', lang),
        reply_markup=get_currency_keyboard(lang)
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
        logger.error(f"Error deleting profile for user {user_id}: {e}")
        await callback.message.edit_text(
            get_text('delete_profile_error', lang)
        )
