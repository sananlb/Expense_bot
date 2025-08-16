"""
Утилиты для работы с состоянием FSM
"""
from aiogram.fsm.context import FSMContext


async def clear_state_keep_cashback(state: FSMContext):
    """
    Очищает состояние, но сохраняет флаг персистентного меню кешбека
    """
    # Сохраняем флаг персистентного меню кешбека перед очисткой
    data = await state.get_data()
    persistent_cashback = data.get('persistent_cashback_menu', False)
    cashback_menu_month = data.get('cashback_menu_month')
    cashback_menu_ids = data.get('cashback_menu_ids', [])
    cashback_menu_message_id = data.get('cashback_menu_message_id')
    
    # Определяем last_menu_id: если есть меню кешбека, используем последний ID из списка
    if cashback_menu_ids:
        last_menu_id = cashback_menu_ids[-1]
    else:
        last_menu_id = data.get('last_menu_message_id')
    
    # Очищаем состояние
    await state.clear()
    
    # Восстанавливаем флаг после очистки
    if persistent_cashback and cashback_menu_ids:
        await state.update_data(
            persistent_cashback_menu=True,
            cashback_menu_month=cashback_menu_month,
            cashback_menu_ids=cashback_menu_ids,
            cashback_menu_message_id=cashback_menu_message_id,
            last_menu_message_id=last_menu_id
        )