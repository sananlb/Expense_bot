"""
Роутер для работы с PDF отчетами
"""
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, BufferedInputFile
from datetime import datetime, date
import logging
import io

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


@router.callback_query(lambda c: c.data.startswith("pdf_report_") and not c.data == "pdf_report_select_month")
async def process_pdf_report_request(callback: types.CallbackQuery, state: FSMContext):
    """Обработка запроса на генерацию отчета"""
    await callback.answer()
    
    # Парсим год и месяц
    parts = callback.data.split("_")
    year = int(parts[1])
    month = int(parts[2])
    
    # Отправляем сообщение о начале генерации
    lang = await get_user_language(callback.from_user.id)
    progress_msg = await callback.message.edit_text(
        get_text('generating_report', lang)
    )
    
    try:
        # Генерируем отчет
        pdf_service = PDFReportService()
        pdf_bytes = await pdf_service.generate_monthly_report(
            user_id=callback.from_user.id,
            year=year,
            month=month,
            lang=lang
        )
        
        if not pdf_bytes:
            await progress_msg.edit_text(
                get_text('no_data_for_report', lang)
            )
            return
        
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
        await callback.message.answer_document(
            document=pdf_file,
            caption=get_text('pdf_report_caption', lang).format(
                month=months[month-1].title() if lang == 'en' else months[month-1],
                year=year
            )
        )
        
        # Удаляем сообщение о прогрессе
        await progress_msg.delete()
        
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        await progress_msg.edit_text(
            get_text('report_generation_error', lang)
        )


