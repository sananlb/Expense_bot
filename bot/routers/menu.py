"""
Обработчики для общих callback queries (расходы за сегодня, стартовое сообщение)
"""
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from datetime import date

from ..utils.message_utils import send_message_with_cleanup
from ..utils import get_text

router = Router(name="menu")


@router.callback_query(lambda c: c.data == "expenses_today")
async def show_today_expenses(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать траты за сегодня"""
    # Импортируем функцию из reports
    from ..routers.reports import show_expenses_summary
    
    today = date.today()
    
    # Используем единую функцию show_expenses_summary
    await show_expenses_summary(
        callback.message,
        today,
        today,
        lang,
        state=state,
        edit=True,
        original_message=callback.message,
        callback=callback
    )
    await callback.answer()




@router.callback_query(lambda c: c.data == "start")
async def show_start(callback: types.CallbackQuery, state: FSMContext):
    """Показать стартовое сообщение (callback на кнопку Инфо)"""
    from ..routers.start import get_start_message, get_start_keyboard
    
    text = get_start_message()
    keyboard = get_start_keyboard()
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        # Если не удалось отредактировать, отправляем новое
        await send_message_with_cleanup(callback, state, text, reply_markup=keyboard)
    await callback.answer()




