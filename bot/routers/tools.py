"""Роутер меню «Инструменты» (команда /tools).

Собирает функции, ранее перегружавшие меню настроек: повторяющиеся платежи,
лимит трат, цель дохода, кешбэк, семейный бюджет. Сам роутер — только лаунчер:
кнопки ведут на уже существующие callback-обработчики соответствующих функций.
"""
import logging

from asgiref.sync import sync_to_async
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import tools_keyboard
from bot.utils import get_text, get_user_language
from bot.utils.message_utils import send_message_with_cleanup
from bot.utils.state_utils import clear_state_keep_cashback

logger = logging.getLogger(__name__)
router = Router(name="tools")

# Порядок инструментов в перечислении совпадает с порядком кнопок в tools_keyboard.
# Каждому ключу соответствует текст кнопки (с иконкой инструмента).
_TOOL_LABEL_KEYS = {
    'recurring': 'recurring_button',
    'limit': 'total_limit_button',
    'goal': 'total_goal_button',
    'cashback': 'cashback_button',
    'household': 'household_button',
}
_TOOL_ORDER = ['recurring', 'limit', 'goal', 'cashback', 'household']


@sync_to_async
def _collect_active_tools(user_id: int) -> list[str]:
    """Возвращает ключи инструментов, которые у пользователя активны/настроены.

    Всё считается одним синхронным блоком, чтобы не плодить отдельные запросы и
    избежать SynchronousOnlyOperation при доступе к FK.
    """
    from expenses.models import (
        Budget,
        Cashback,
        IncomeBudget,
        Profile,
        RecurringPayment,
    )

    profile = Profile.objects.filter(telegram_id=user_id).first()
    if profile is None:
        return []

    active: list[str] = []
    if RecurringPayment.objects.filter(profile=profile, is_active=True).exists():
        active.append('recurring')
    if Budget.objects.filter(
        profile=profile, is_active=True, period_type='monthly', category__isnull=True
    ).exists():
        active.append('limit')
    if IncomeBudget.objects.filter(
        profile=profile, is_active=True, period_type='monthly', category__isnull=True
    ).exists():
        active.append('goal')
    if Cashback.objects.filter(profile=profile).exists():
        active.append('cashback')
    if profile.household_id is not None:
        active.append('household')
    return active


async def _tools_text(user_id: int, lang: str) -> str:
    """Текст меню инструментов: заголовок + перечень активных инструментов с ✅."""
    text = f"<b>{get_text('tools_menu', lang)}</b>"
    active = await _collect_active_tools(user_id)
    if active:
        lines = "\n".join(
            get_text(_TOOL_LABEL_KEYS[key], lang)
            for key in _TOOL_ORDER
            if key in active
        )
        text += f"\n\n{get_text('tools_active_header', lang)}\n{lines}"
    return text


@router.message(Command("tools"))
async def cmd_tools(message: Message, state: FSMContext, lang: str = 'ru'):
    """Показать меню инструментов по команде /tools."""
    await clear_state_keep_cashback(state)
    lang = await get_user_language(message.from_user.id)
    await send_message_with_cleanup(
        message,
        state,
        await _tools_text(message.from_user.id, lang),
        reply_markup=tools_keyboard(lang),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "tools")
async def callback_tools(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать меню инструментов по callback (кнопка «Назад» из под-экранов)."""
    await clear_state_keep_cashback(state)
    lang = await get_user_language(callback.from_user.id)
    try:
        await callback.message.edit_text(
            await _tools_text(callback.from_user.id, lang),
            reply_markup=tools_keyboard(lang),
            parse_mode="HTML",
        )
    except TelegramBadRequest:
        # Сообщение не изменилось или недоступно для редактирования — не критично.
        pass
    await callback.answer()
