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
from bot.utils.message_utils import send_message_with_cleanup
from bot.utils.commands import update_user_commands
from expenses.models import Profile, UserSettings

logger = logging.getLogger(__name__)

router = Router(name="settings")


class SettingsStates(StatesGroup):
    language = State()
    timezone = State()
    currency = State()
    notifications = State()


class NotificationStates(StatesGroup):
    selecting_weekday = State()
    selecting_time = State()
    configuring = State()


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
        
        # Статус уведомлений
        weekly_status = '✅' if settings.weekly_summary_enabled else '❌'
        weekday = settings.weekly_summary_day
        weekdays = {
            0: 'Понедельник', 1: 'Вторник', 2: 'Среда', 3: 'Четверг',
            4: 'Пятница', 5: 'Суббота', 6: 'Воскресенье'
        }
        weekday_text = weekdays.get(weekday, 'Понедельник')
        
        text = f"""{get_text('settings_menu', lang)}

{get_text('language', lang)}: {lang_text}
{get_text('timezone', lang)}: {timezone_text}
{get_text('currency', lang)}: {currency_text}

{get_text('notifications', lang)}:
{weekly_status} {get_text('weekly_reports', lang)}: {weekday_text}
✅ {get_text('monthly_reports', lang)}"""
        
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
    await state.clear()
    
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
        
        # Статус уведомлений
        weekly_status = '✅' if settings.weekly_summary_enabled else '❌'
        weekday = settings.weekly_summary_day
        weekdays = {
            0: 'Понедельник', 1: 'Вторник', 2: 'Среда', 3: 'Четверг',
            4: 'Пятница', 5: 'Суббота', 6: 'Воскресенье'
        }
        weekday_text = weekdays.get(weekday, 'Понедельник')
        
        text = f"""{get_text('settings_menu', lang)}

{get_text('language', lang)}: {lang_text}
{get_text('timezone', lang)}: {timezone_text}
{get_text('currency', lang)}: {currency_text}

{get_text('notifications', lang)}:
{weekly_status} {get_text('weekly_reports', lang)}: {weekday_text}
✅ {get_text('monthly_reports', lang)}"""
        
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
    
    # Получаем текущую валюту пользователя
    try:
        profile = await get_or_create_profile(callback.from_user.id)
        current_currency = profile.currency or 'RUB'
        
        # Словарь валют с их названиями
        currencies = {
            'RUB': '🇷🇺 Российский рубль',
            'USD': '🇺🇸 Доллар США', 
            'EUR': '🇪🇺 Евро',
            'GBP': '🇬🇧 Фунт стерлингов',
            'CNY': '🇨🇳 Китайский юань',
            'JPY': '🇯🇵 Японская иена',
            'KRW': '🇰🇷 Корейская вона',
            'INR': '🇮🇳 Индийская рупия',
            'TRY': '🇹🇷 Турецкая лира',
            'AED': '🇦🇪 Дирхам ОАЭ',
            'KZT': '🇰🇿 Казахстанский тенге',
            'BYN': '🇧🇾 Белорусский рубль',
            'UAH': '🇺🇦 Украинская гривна',
            'PLN': '🇵🇱 Польский злотый',
            'CZK': '🇨🇿 Чешская крона'
        }
        
        current_currency_name = currencies.get(current_currency, current_currency)
        
        text = f"{get_text('change_currency', lang)}\n\n"
        text += f"💰 Текущая валюта: {current_currency_name}"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_currency_keyboard(lang)
        )
    except Exception as e:
        logger.error(f"Error getting current currency: {e}")
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
async def configure_notifications(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Настроить уведомления"""
    await state.set_state(NotificationStates.configuring)
    
    try:
        profile = await get_or_create_profile(callback.from_user.id)
        settings = await sync_to_async(lambda: profile.settings)()
        
        # Получаем настройки уведомлений
        weekly_enabled = settings.weekly_summary_enabled
        
        # День недели для еженедельных отчетов
        weekday = settings.weekly_summary_day
        weekdays = {
            0: 'Понедельник', 1: 'Вторник', 2: 'Среда', 3: 'Четверг',
            4: 'Пятница', 5: 'Суббота', 6: 'Воскресенье'
        }
        weekday_text = weekdays.get(weekday, 'Понедельник')
        
        # Время отправки
        notification_time = settings.notification_time
        time_text = notification_time.strftime('%H:%M') if notification_time else '18:00'
        
        # Статусы
        weekly_icon = '✅' if weekly_enabled else '❌'
        
        text = f"""⚙️ <b>Настройка отчетов</b>

📅 <b>Еженедельные отчеты:</b> {weekly_icon}
День: {weekday_text}
Время: {time_text}

📊 <b>Ежемесячные отчеты:</b> ✅
Последний день месяца в {time_text}

💡 Выберите, что хотите настроить:"""
        
        # Создаем клавиатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{weekly_icon} Еженедельные отчеты",
                callback_data="toggle_weekly_notif"
            )],
            [InlineKeyboardButton(
                text="📅 Изменить день недели",
                callback_data="notif_change_weekday"
            )],
            [InlineKeyboardButton(
                text="⏰ Изменить время",
                callback_data="notif_change_time"
            )],
            [InlineKeyboardButton(text="← Назад", callback_data="settings")],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data="close")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error configuring notifications: {e}")
        await callback.answer(get_text('error_occurred', lang), show_alert=True)


@router.callback_query(NotificationStates.configuring, F.data == "toggle_weekly_notif")
async def toggle_weekly_notifications(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Переключить еженедельные уведомления"""
    try:
        profile = await get_or_create_profile(callback.from_user.id)
        settings = await sync_to_async(lambda: profile.settings)()
        
        # Переключаем статус
        settings.weekly_summary_enabled = not settings.weekly_summary_enabled
        await sync_to_async(settings.save)()
        
        status = "включены" if settings.weekly_summary_enabled else "отключены"
        await callback.answer(f"Еженедельные отчеты {status}")
        
        # Обновляем меню
        await configure_notifications(callback, state, lang)
        
    except Exception as e:
        logger.error(f"Error toggling weekly notifications: {e}")
        await callback.answer(get_text('error_occurred', lang), show_alert=True)


# Удаляем функцию toggle_monthly_notif - ежемесячные отчеты всегда включены


@router.callback_query(NotificationStates.configuring, F.data == "notif_change_weekday")
async def change_notification_weekday(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Изменить день недели для еженедельных отчетов"""
    await state.set_state(NotificationStates.selecting_weekday)
    
    weekdays = [
        ("Понедельник", "weekday_0"),
        ("Вторник", "weekday_1"),
        ("Среда", "weekday_2"),
        ("Четверг", "weekday_3"),
        ("Пятница", "weekday_4"),
        ("Суббота", "weekday_5"),
        ("Воскресенье", "weekday_6")
    ]
    
    keyboard_buttons = []
    for i in range(0, len(weekdays), 2):
        row = []
        for j in range(2):
            if i + j < len(weekdays):
                text, data = weekdays[i + j]
                row.append(InlineKeyboardButton(text=f"📅 {text}", callback_data=data))
        if row:
            keyboard_buttons.append(row)
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="← Назад", callback_data="back_to_notifications")
    ])
    
    await callback.message.edit_text(
        "📅 Выберите день недели для еженедельных отчетов:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    await callback.answer()


@router.callback_query(NotificationStates.selecting_weekday, F.data.startswith("weekday_"))
async def save_notification_weekday(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Сохранить выбранный день недели"""
    try:
        weekday = int(callback.data.split('_')[1])
        
        profile = await get_or_create_profile(callback.from_user.id)
        settings = await sync_to_async(lambda: profile.settings)()
        
        # Сохраняем день недели (добавляем поле если его нет)
        if not hasattr(settings, 'weekly_summary_day'):
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute(
                    "ALTER TABLE expenses_usersettings ADD COLUMN weekly_summary_day INTEGER DEFAULT 0"
                )
        
        settings.weekly_summary_day = weekday
        await sync_to_async(settings.save)()
        
        weekdays = {
            0: 'Понедельник', 1: 'Вторник', 2: 'Среда', 3: 'Четверг',
            4: 'Пятница', 5: 'Суббота', 6: 'Воскресенье'
        }
        
        await callback.answer(f"✅ День изменен на {weekdays[weekday]}")
        
        # Возвращаемся в меню настроек
        await state.set_state(NotificationStates.configuring)
        await configure_notifications(callback, state, lang)
        
    except Exception as e:
        logger.error(f"Error saving weekday: {e}")
        await callback.answer(get_text('error_occurred', lang), show_alert=True)


@router.callback_query(NotificationStates.configuring, F.data == "notif_change_time")
async def change_notification_time(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Изменить время отправки уведомлений"""
    await state.set_state(NotificationStates.selecting_time)
    
    # Предлагаем популярное время, но можно выбрать любое
    times = ["06:00", "09:00", "12:00", "15:00", "18:00", "19:00", "20:00", "21:00", "22:00"]
    
    keyboard_buttons = []
    for i in range(0, len(times), 3):
        row = []
        for j in range(3):
            if i + j < len(times):
                time = times[i + j]
                row.append(InlineKeyboardButton(
                    text=f"🕐 {time}", 
                    callback_data=f"time_{time.replace(':', '_')}"
                ))
        if row:
            keyboard_buttons.append(row)
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="← Назад", callback_data="back_to_notifications")
    ])
    
    await callback.message.edit_text(
        "⏰ Выберите время для отправки отчетов:\n\n"
        "Вы можете нажать на кнопку или ввести время в формате ЧЧ:ММ\n"
        "(например: 18:30)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    await callback.answer()


@router.callback_query(NotificationStates.selecting_time, F.data.startswith("time_"))
async def save_notification_time(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Сохранить выбранное время"""
    try:
        time_str = callback.data.replace("time_", "").replace("_", ":")
        hour, minute = map(int, time_str.split(':'))
        
        profile = await get_or_create_profile(callback.from_user.id)
        settings = await sync_to_async(lambda: profile.settings)()
        
        # Сохраняем время уведомлений
        from datetime import time
        settings.notification_time = time(hour, minute)
        await sync_to_async(settings.save)()
        
        await callback.answer(f"✅ Время изменено на {time_str}")
        
        # Возвращаемся в меню настроек
        await state.set_state(NotificationStates.configuring)
        await configure_notifications(callback, state, lang)
        
    except Exception as e:
        logger.error(f"Error saving time: {e}")
        await callback.answer(get_text('error_occurred', lang), show_alert=True)


@router.message(NotificationStates.selecting_time)
async def process_time_input(message: Message, state: FSMContext, lang: str = 'ru'):
    """Обработка ввода времени текстом"""
    import re
    from datetime import time
    from bot.utils.message_utils import send_message_with_cleanup
    
    text = message.text.strip()
    
    # Проверяем формат времени (ЧЧ:ММ или ЧЧ.ММ)
    time_pattern = r'^([0-2]?[0-9])[:.]([0-5][0-9])$'
    match = re.match(time_pattern, text)
    
    if not match:
        await send_message_with_cleanup(
            message, state,
            "❌ Неверный формат времени.\n\n"
            "Введите время в формате ЧЧ:ММ (например: 18:30)"
        )
        return
    
    hour = int(match.group(1))
    minute = int(match.group(2))
    
    # Проверяем корректность времени (0-23 часов)
    if hour > 23:
        await send_message_with_cleanup(
            message, state,
            "❌ Неверное время. Часы должны быть от 0 до 23.\n\n"
            "Пожалуйста, введите корректное время."
        )
        return
    
    try:
        # Сохраняем время
        profile = await get_or_create_profile(message.from_user.id)
        settings = await sync_to_async(lambda: profile.settings)()
        
        settings.notification_time = time(hour, minute)
        await sync_to_async(settings.save)()
        
        time_str = f"{hour:02d}:{minute:02d}"
        await send_message_with_cleanup(
            message, state,
            f"✅ Время изменено на {time_str}\n\n"
            "Отчеты будут приходить в это время."
        )
        
        # Возвращаемся в меню настроек
        await state.set_state(NotificationStates.configuring)
        
        # Показываем обновленное меню настроек
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        
        # Получаем обновленные настройки
        weekly_enabled = settings.weekly_summary_enabled
        weekday = settings.weekly_summary_day
        weekdays = {
            0: 'Понедельник', 1: 'Вторник', 2: 'Среда', 3: 'Четверг',
            4: 'Пятница', 5: 'Суббота', 6: 'Воскресенье'
        }
        weekday_text = weekdays.get(weekday, 'Понедельник')
        
        weekly_icon = '✅' if weekly_enabled else '❌'
        
        text = f"""⚙️ <b>Настройка отчетов</b>

📅 <b>Еженедельные отчеты:</b> {weekly_icon}
День: {weekday_text}
Время: {time_str}

📊 <b>Ежемесячные отчеты:</b> ✅
Последний день месяца в {time_str}

💡 Выберите, что хотите настроить:"""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{weekly_icon} Еженедельные отчеты",
                callback_data="toggle_weekly_notif"
            )],
            [InlineKeyboardButton(
                text="📅 Изменить день недели",
                callback_data="notif_change_weekday"
            )],
            [InlineKeyboardButton(
                text="⏰ Изменить время",
                callback_data="notif_change_time"
            )],
            [InlineKeyboardButton(text="← Назад", callback_data="settings")],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data="close")]
        ])
        
        await send_message_with_cleanup(
            message, state, text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error saving time from text: {e}")
        await send_message_with_cleanup(
            message, state,
            "❌ Произошла ошибка при сохранении времени.\n"
            "Попробуйте еще раз."
        )


@router.callback_query(F.data == "back_to_notifications")
async def back_to_notifications(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Вернуться в меню настроек уведомлений"""
    await state.set_state(NotificationStates.configuring)
    await configure_notifications(callback, state, lang)
