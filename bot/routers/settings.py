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

from bot.keyboards import settings_keyboard, back_close_keyboard, get_language_keyboard, get_timezone_keyboard, get_currency_keyboard
from bot.utils import get_text, set_user_language, get_user_language, format_amount
from bot.services.profile import get_or_create_profile
from bot.middleware.language import update_user_commands
from bot.utils.state_utils import clear_state_with_message, get_clean_state
from bot.utils.message_utils import send_message_with_cleanup

logger = logging.getLogger(__name__)
router = Router(name="settings")


class SettingsStates(StatesGroup):
    """Состояния для настроек"""
    language = State()
    timezone = State()
    currency = State()


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
            except:
                timezone_text = 'UTC+0'
        else:
            timezone_text = 'UTC+0'
            
        currency_text = profile.currency or 'RUB'
        
        text = f"""{get_text('settings_menu', lang)}

{get_text('language', lang)}: {lang_text}
{get_text('timezone', lang)}: {timezone_text}
{get_text('currency', lang)}: {currency_text}"""
        
        await send_message_with_cleanup(
            message, 
            state, 
            text, 
            reply_markup=settings_keyboard(lang)
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
            except:
                timezone_text = 'UTC+0'
        else:
            timezone_text = 'UTC+0'
            
        currency_text = profile.currency or 'RUB'
        
        text = f"""{get_text('settings_menu', lang)}

{get_text('language', lang)}: {lang_text}
{get_text('timezone', lang)}: {timezone_text}
{get_text('currency', lang)}: {currency_text}"""
        
        await callback.message.edit_text(
            text,
            reply_markup=settings_keyboard(lang)
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
    await state.set_state(SettingsStates.currency)
    
    await callback.message.edit_text(
        get_text('change_currency', lang),
        reply_markup=get_currency_keyboard(lang)
    )


@router.callback_query(SettingsStates.currency, F.data.startswith("curr_"))
async def process_currency_change(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Обработать изменение валюты"""
    currency = callback.data.replace('curr_', '')
    
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