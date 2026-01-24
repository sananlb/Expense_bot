"""
Роутер для работы с PDF отчетами
"""
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, BufferedInputFile
from datetime import datetime, date
import logging
import io
import asyncio
import time
import os
from django.core.cache import cache

from ..utils.message_utils import send_message_with_cleanup
from ..utils import get_text, get_user_language
from ..services.pdf_report import PDFReportService
from ..decorators import require_subscription
from expenses.models import Profile

router = Router(name="pdf_report")
logger = logging.getLogger(__name__)


@router.callback_query(lambda c: c.data == "pdf_report_select_month")
async def show_month_selection(callback: types.CallbackQuery, state: FSMContext):
    """Показать меню выбора месяца для PDF отчета"""
    await callback.answer()
    lang = await get_user_language(callback.from_user.id)
    
    # Показываем меню выбора месяца
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    
    # Создаем кнопки для последних 6 месяцев
    if lang == 'en':
        months = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']
    else:
        months = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
    
    keyboard_buttons = []
    for i in range(6):
        month = current_month - i
        year = current_year
        
        if month <= 0:
            month += 12
            year -= 1
        
        # Пропускаем будущие месяцы
        if year > current_year or (year == current_year and month > current_month):
            continue
            
        button_text = f"{months[month-1]} {year}"
        callback_data = f"pdf_report_{year}_{month}"
        
        keyboard_buttons.append([
            InlineKeyboardButton(text=button_text, callback_data=callback_data)
        ])
    
    # Добавляем кнопку "Назад"
    keyboard_buttons.append([
        InlineKeyboardButton(text=get_text('back_arrow', lang), callback_data="show_month_start")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(
        get_text('select_month_pdf', lang),
        reply_markup=keyboard
    )


async def _generate_and_send_pdf_background(
    user_id: int,
    chat_id: int,
    year: int,
    month: int,
    lang: str,
    progress_msg_id: int,
    lock_key: str
):
    """
    Фоновая генерация и отправка PDF отчета.
    Не блокирует handler, выполняется асинхронно.

    Args:
        user_id: ID пользователя
        chat_id: ID чата для отправки
        year: Год отчета
        month: Месяц отчета
        lang: Язык пользователя
        progress_msg_id: ID сообщения с прогрессом
        lock_key: Ключ lock в Redis для снятия после завершения
    """
    start_time = time.time()
    bot = None

    try:
        # Логируем начало генерации
        logger.info(f"[PDF_START] user={user_id}, period={year}/{month}")

        # Создаем экземпляр бота для фоновой отправки
        bot = Bot(token=os.getenv('BOT_TOKEN'))

        # Генерируем PDF
        pdf_service = PDFReportService()
        pdf_bytes = await pdf_service.generate_monthly_report(
            user_id=user_id,
            year=year,
            month=month,
            lang=lang
        )

        duration = time.time() - start_time

        if not pdf_bytes:
            # Нет данных для отчета
            logger.warning(f"[PDF_NO_DATA] user={user_id}, period={year}/{month}, duration={duration:.2f}s")
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_msg_id,
                text=get_text('no_data_for_report', lang),
                parse_mode='HTML'
            )
            return

        # Логируем успешную генерацию
        logger.info(
            f"[PDF_SUCCESS] user={user_id}, period={year}/{month}, "
            f"duration={duration:.2f}s, size={len(pdf_bytes)}"
        )

        # Алерт если генерация заняла > 30 секунд
        if duration > 30:
            from bot.services.admin_notifier import send_admin_alert
            await send_admin_alert(
                f"⚠️ Slow PDF generation\n"
                f"User: {user_id}\n"
                f"Period: {year}/{month}\n"
                f"Duration: {duration:.2f}s\n"
                f"Size: {len(pdf_bytes)} bytes",
                disable_notification=True
            )

        # Формируем имя файла
        if lang == 'en':
            months = ['january', 'february', 'march', 'april', 'may', 'june',
                      'july', 'august', 'september', 'october', 'november', 'december']
            filename = f"Report_Coins_{months[month-1]}_{year}.pdf"
        else:
            months = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
                      'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
            filename = f"Отчет_Coins_{months[month-1]}_{year}.pdf"

        # Создаем файл для отправки
        pdf_file = BufferedInputFile(pdf_bytes, filename=filename)

        # Отправляем PDF
        await bot.send_document(
            chat_id=chat_id,
            document=pdf_file,
            caption=get_text('pdf_report_caption', lang).format(
                month=months[month-1].title() if lang == 'en' else months[month-1],
                year=year
            ),
            parse_mode='HTML'
        )

        # Удаляем сообщение о прогрессе
        try:
            await bot.delete_message(chat_id=chat_id, message_id=progress_msg_id)
        except Exception as e:
            logger.debug(f"Could not delete progress message: {e}")

    except asyncio.TimeoutError:
        duration = time.time() - start_time
        logger.error(f"[PDF_TIMEOUT] user={user_id}, period={year}/{month}, duration={duration:.2f}s")

        # Уведомляем пользователя
        if bot:
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=progress_msg_id,
                    text=get_text('report_generation_error', lang),
                    parse_mode='HTML'
                )
            except Exception:
                pass

        # Критический алерт админу
        from bot.services.admin_notifier import send_admin_alert
        await send_admin_alert(
            f"🔴 PDF Timeout\n"
            f"User: {user_id}\n"
            f"Period: {year}/{month}\n"
            f"Duration: {duration:.2f}s"
        )

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            f"[PDF_ERROR] user={user_id}, period={year}/{month}, "
            f"duration={duration:.2f}s, error={str(e)}"
        )

        # Уведомляем пользователя
        if bot:
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=progress_msg_id,
                    text=get_text('report_generation_error', lang),
                    parse_mode='HTML'
                )
            except Exception:
                pass

    finally:
        # Всегда снимаем lock
        cache.delete(lock_key)
        logger.info(f"Released PDF lock for user {user_id}, {year}/{month}")

        # Закрываем сессию бота
        if bot:
            await bot.session.close()


@router.callback_query(lambda c: c.data.startswith("pdf_report_") and not c.data == "pdf_report_select_month")
async def process_pdf_report_request(callback: types.CallbackQuery, state: FSMContext):
    """
    Обработка запроса на генерацию отчета.
    Handler завершается немедленно, PDF генерируется в фоне.
    """
    await callback.answer()

    # Парсим год и месяц
    parts = callback.data.split("_")
    year = int(parts[2])
    month = int(parts[3])

    user_id = callback.from_user.id
    lang = await get_user_language(user_id)

    # Создаем ключ lock для предотвращения дубликатов
    lock_key = f"pdf_generation:{user_id}:{year}:{month}"

    # Проверяем существующий lock
    if cache.get(lock_key):
        await callback.answer(
            "⏳ PDF уже генерируется для этого периода. Пожалуйста, подождите..."
            if lang == 'ru' else
            "⏳ PDF is already being generated for this period. Please wait...",
            show_alert=True
        )
        return

    # Устанавливаем lock на 10 минут (с запасом)
    cache.set(lock_key, True, timeout=600)

    try:
        # Отправляем сообщение о начале генерации
        progress_msg = await callback.message.edit_text(
            "⏳ " + get_text('generating_report', lang) +
            "\n\n" + (
                "Это может занять 1-2 минуты. Я пришлю PDF когда он будет готов."
                if lang == 'ru' else
                "This may take 1-2 minutes. I'll send the PDF when it's ready."
            )
        )

        # Запускаем фоновую задачу (НЕ блокирует handler!)
        asyncio.create_task(
            _generate_and_send_pdf_background(
                user_id=user_id,
                chat_id=callback.message.chat.id,
                year=year,
                month=month,
                lang=lang,
                progress_msg_id=progress_msg.message_id,
                lock_key=lock_key
            )
        )

        # Handler завершается НЕМЕДЛЕННО - другие запросы пользователя обрабатываются!

    except Exception as e:
        # Снимаем lock при ошибке создания задачи
        cache.delete(lock_key)
        logger.error(f"Error creating PDF background task: {e}")
        raise


