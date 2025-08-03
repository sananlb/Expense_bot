"""
Router for user settings management
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
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
from bot.utils.message_utils import send_message_with_cleanup
from expenses.models import Profile, UserSettings

logger = logging.getLogger(__name__)

router = Router(name="settings")


class SettingsStates(StatesGroup):
    language = State()
    timezone = State()
    currency = State()
    notifications = State()


@router.message(Command("settings"))
async def cmd_settings(message: Message, state: FSMContext, lang: str = 'ru'):
    """Показать меню настроек"""
    await state.clear()
    
    try:
        profile = await get_or_create_profile(message.from_user.id)
        settings = await sync_to_async(lambda: profile.settings)()
        
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
        
        # Статус уведомлений
        daily_status = '✅' if settings.daily_reminder_enabled else '❌'
        weekly_status = '✅' if settings.weekly_summary_enabled else '❌'
        daily_time = settings.daily_reminder_time.strftime('%H:%M') if settings.daily_reminder_time else '21:00'
        
        text = f"""{get_text('settings_menu', lang)}

{get_text('language', lang)}: {lang_text}
{get_text('timezone', lang)}: {timezone_text}
{get_text('currency', lang)}: {currency_text}

{get_text('notifications', lang)}:
{daily_status} {get_text('daily_reports', lang)}: {daily_time}
{weekly_status} {get_text('weekly_reports', lang)}: {get_text('monday', lang)}"""
        
        await send_message_with_cleanup(
            message, 
            state, 
            text, 
            reply_markup=settings_keyboard(lang)
        )
        
    except Exception as e:
        logger.error(f"Error showing settings: {e}")
        await message.answer(get_text('error_occurred', lang))


@router.callback_query(F.data == "settings")
async def callback_settings(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать меню настроек по callback"""
    await state.clear()
    
    try:
        profile = await get_or_create_profile(callback.from_user.id)
        settings = await sync_to_async(lambda: profile.settings)()
        
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
        
        # Статус уведомлений
        daily_status = '✅' if settings.daily_reminder_enabled else '❌'
        weekly_status = '✅' if settings.weekly_summary_enabled else '❌'
        daily_time = settings.daily_reminder_time.strftime('%H:%M') if settings.daily_reminder_time else '21:00'
        
        text = f"""{get_text('settings_menu', lang)}

{get_text('language', lang)}: {lang_text}
{get_text('timezone', lang)}: {timezone_text}
{get_text('currency', lang)}: {currency_text}

{get_text('notifications', lang)}:
{daily_status} {get_text('daily_reports', lang)}: {daily_time}
{weekly_status} {get_text('weekly_reports', lang)}: {get_text('monday', lang)}"""
        
        await callback.message.edit_text(
            text,
            reply_markup=settings_keyboard(lang)
        )
        
    except Exception as e:
        logger.error(f"Error showing settings: {e}")
        await callback.answer(get_text('error_occurred', lang))


@router.callback_query(F.data == "change_language")
async def change_language(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Изменить язык"""
    await state.set_state(SettingsStates.language)
    
    await callback.message.edit_text(
        get_text('change_language', lang),
        reply_markup=get_language_keyboard(lang)
    )


@router.callback_query(SettingsStates.language, F.data.in_(["lang_ru", "lang_en"]))
async def process_language_change(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Обработать изменение языка"""
    new_lang = callback.data.split('_')[1]
    
    try:
        success = await set_user_language(callback.from_user.id, new_lang)
        
        if success:
            await callback.answer(get_text('language_changed', new_lang))
            # Обновляем язык в текущем контексте
            lang = new_lang
        else:
            await callback.answer(get_text('error_occurred', lang))
            
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
            # В Etc/GMT знаки инвертированы
            if offset > 0:
                timezone_str = f'Etc/GMT-{offset}'
            else:
                timezone_str = f'Etc/GMT+{abs(offset)}'
        
        # Проверяем валидность часового пояса
        pytz.timezone(timezone_str)
        
        profile = await get_or_create_profile(callback.from_user.id)
        profile.timezone = timezone_str
        await sync_to_async(profile.save)()
        
        await callback.answer(get_text('timezone_changed', lang))
        
    except (ValueError, pytz.exceptions.UnknownTimeZoneError) as e:
        logger.error(f"Invalid timezone offset: {offset_str}, error: {e}")
        await callback.answer(get_text('error_occurred', lang))
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
    currency = callback.data.split('_')[1].upper()
    
    try:
        profile = await get_or_create_profile(callback.from_user.id)
        profile.currency = currency
        await sync_to_async(profile.save)()
        
        await callback.answer(get_text('currency_changed', lang))
        
    except Exception as e:
        logger.error(f"Error changing currency: {e}")
        await callback.answer(get_text('error_occurred', lang))
    
    # Возвращаемся в меню настроек
    await callback_settings(callback, state, lang)


@router.callback_query(F.data == "configure_reports")
async def configure_reports(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Настроить уведомления и отчеты"""
    await state.clear()
    
    try:
        profile = await get_or_create_profile(callback.from_user.id)
        settings = await sync_to_async(lambda: profile.settings)()
        
        # Форматируем время отчета
        report_time = settings.daily_reminder_time.strftime('%H:%M') if settings.daily_reminder_time else '21:00'
        
        # Статусы отчетов
        daily_icon = '✅' if settings.daily_reminder_enabled else '❌'
        weekly_icon = '✅' if settings.weekly_summary_enabled else '❌'
        
        text = f"""{get_text('report_settings', lang)}

{get_text('report_time', lang)}: {report_time}

{get_text('report_types', lang)}:
{daily_icon} {get_text('daily_reports', lang)}
{weekly_icon} {get_text('weekly_reports', lang)} ({get_text('sunday', lang)})
ℹ️ {get_text('monthly_reports', lang)} ({get_text('enabled_by_default', lang)})"""
        
        # Создаем клавиатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"⏰ {get_text('change_time', lang)}", 
                callback_data="set_report_time"
            )],
            [InlineKeyboardButton(
                text=f"{daily_icon} {get_text('daily_reports', lang)}", 
                callback_data="toggle_daily_reports"
            )],
            [InlineKeyboardButton(
                text=f"{weekly_icon} {get_text('weekly_reports', lang)}", 
                callback_data="toggle_weekly_reports"
            )],
            [
                InlineKeyboardButton(text=get_text('back', lang), callback_data="settings"),
                InlineKeyboardButton(text=get_text('close', lang), callback_data="close")
            ]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error configuring reports: {e}")
        await callback.answer(get_text('error_occurred', lang), show_alert=True)


@router.callback_query(F.data == "toggle_daily_reports")
async def toggle_daily_reports(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Переключить ежедневные отчеты"""
    try:
        profile = await get_or_create_profile(callback.from_user.id)
        settings = await sync_to_async(lambda: profile.settings)()
        
        # Переключаем статус
        settings.daily_reminder_enabled = not settings.daily_reminder_enabled
        await sync_to_async(settings.save)()
        
        # Обновляем меню
        await configure_reports(callback, state, lang)
        
    except Exception as e:
        logger.error(f"Error toggling daily reports: {e}")
        await callback.answer(get_text('error_occurred', lang), show_alert=True)


@router.callback_query(F.data == "toggle_weekly_reports")
async def toggle_weekly_reports(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Переключить еженедельные отчеты"""
    try:
        profile = await get_or_create_profile(callback.from_user.id)
        settings = await sync_to_async(lambda: profile.settings)()
        
        # Переключаем статус
        settings.weekly_summary_enabled = not settings.weekly_summary_enabled
        await sync_to_async(settings.save)()
        
        # Обновляем меню
        await configure_reports(callback, state, lang)
        
    except Exception as e:
        logger.error(f"Error toggling weekly reports: {e}")
        await callback.answer(get_text('error_occurred', lang), show_alert=True)


@router.callback_query(F.data == "set_report_time")
async def set_report_time(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Установить время отправки отчетов"""
    # Создаем клавиатуру с популярными временами
    times = ["07:00", "08:00", "09:00", "12:00", "18:00", "20:00", "21:00", "22:00"]
    
    keyboard_buttons = []
    for i in range(0, len(times), 2):
        row = []
        for j in range(2):
            if i + j < len(times):
                time = times[i + j]
                row.append(InlineKeyboardButton(
                    text=f"🕐 {time}", 
                    callback_data=f"report_time_{time.replace(':', '_')}"
                ))
        keyboard_buttons.append(row)
    
    keyboard_buttons.append([
        InlineKeyboardButton(text=get_text('back', lang), callback_data="configure_reports"),
        InlineKeyboardButton(text=get_text('close', lang), callback_data="close")
    ])
    
    await callback.message.edit_text(
        f"{get_text('select_time', lang)}:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("report_time_"))
async def save_report_time(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Сохранить выбранное время отчетов"""
    try:
        # Извлекаем время из callback_data
        time_str = callback.data.replace("report_time_", "").replace("_", ":")
        hour, minute = map(int, time_str.split(':'))
        
        profile = await get_or_create_profile(callback.from_user.id)
        settings = await sync_to_async(lambda: profile.settings)()
        
        # Устанавливаем новое время
        from datetime import time
        settings.daily_reminder_time = time(hour, minute)
        await sync_to_async(settings.save)()
        
        await callback.answer(f"✅ {get_text('time_saved', lang)}: {time_str}")
        
        # Возвращаемся в меню отчетов
        await configure_reports(callback, state, lang)
        
    except Exception as e:
        logger.error(f"Error saving report time: {e}")
        await callback.answer(get_text('error_occurred', lang), show_alert=True)
