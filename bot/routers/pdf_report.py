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
from ..services.pdf_report import PDFReportService
from ..decorators import require_subscription
from expenses.models import Profile

router = Router(name="pdf_report")
logger = logging.getLogger(__name__)


@router.callback_query(lambda c: c.data == "pdf_report_select_month")
async def show_month_selection(callback: types.CallbackQuery, state: FSMContext):
    """Показать меню выбора месяца для PDF отчета"""
    await callback.answer()
    
    # Показываем меню выбора месяца
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    
    # Создаем кнопки для последних 6 месяцев
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
        InlineKeyboardButton(text="← Назад", callback_data="show_month_start")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(
        "📊 <b>Выберите месяц для PDF отчета</b>\n\n"
        "Я сгенерирую для вас подробный отчет с графиками и статистикой.",
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
    progress_msg = await callback.message.edit_text(
        "⏳ <b>Генерирую отчет...</b>\n\n"
        "Это может занять несколько секунд."
    )
    
    try:
        # Генерируем отчет
        pdf_service = PDFReportService()
        pdf_bytes = await pdf_service.generate_monthly_report(
            user_id=callback.from_user.id,
            year=year,
            month=month
        )
        
        if not pdf_bytes:
            await progress_msg.edit_text(
                "❌ <b>Нет данных для отчета</b>\n\n"
                "За выбранный месяц не найдено расходов."
            )
            return
        
        # Формируем имя файла
        months = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
                  'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
        filename = f"Отчет_Coins_{months[month-1]}_{year}.pdf"
        
        # Создаем файл для отправки
        pdf_file = BufferedInputFile(pdf_bytes, filename=filename)
        
        # Отправляем PDF
        await callback.message.answer_document(
            document=pdf_file,
            caption=(
                f"📊 <b>Отчет за {months[month-1]} {year}</b>\n\n"
                "В отчете содержится:\n"
                "• Общая статистика расходов\n"
                "• Распределение по категориям\n"
                "• Динамика трат по дням\n"
                "• Информация о кешбеке\n\n"
                "💡 <i>Совет: сохраните отчет для отслеживания динамики расходов</i>"
            )
        )
        
        # Удаляем сообщение о прогрессе
        await progress_msg.delete()
        
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        await progress_msg.edit_text(
            "❌ <b>Ошибка при генерации отчета</b>\n\n"
            "Попробуйте позже или обратитесь в поддержку."
        )


