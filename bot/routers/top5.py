"""
Router for Top-5 quick operations
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from datetime import date
from decimal import Decimal
import logging

from bot.utils import get_text
from bot.utils.message_utils import send_message_with_cleanup
from bot.services.top5 import (
    calculate_top5_sync, build_top5_keyboard, save_snapshot,
)
from expenses.models import Profile, Top5Snapshot, Top5Pin
from asgiref.sync import sync_to_async


logger = logging.getLogger(__name__)

router = Router(name="top5")


def _get_rolling_90d_window(today: date) -> tuple[date, date]:
    """Окно последних 90 дней включительно, заканчивается сегодня."""
    from datetime import timedelta
    window_end = today
    window_start = today - timedelta(days=89)
    return window_start, window_end


@router.callback_query(F.data == "top5_menu")
async def show_top5(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    try:
        today = date.today()
        window_start, window_end = _get_rolling_90d_window(today)

        # Получаем профиль
        profile = await sync_to_async(Profile.objects.filter(telegram_id=callback.from_user.id).first)()
        if not profile:
            await callback.answer(get_text('error_occurred', lang), show_alert=True)
            return

        # Пытаемся взять снепшот, иначе считаем
        snapshot = await sync_to_async(Top5Snapshot.objects.filter(profile=profile).first)()
        items = []
        if snapshot and snapshot.window_start == window_start and snapshot.window_end == window_end:
            items = snapshot.items or []
        else:
            items, digest = await calculate_top5_sync(profile, window_start, window_end)
            await save_snapshot(profile, window_start, window_end, items, digest)

        # Формируем текст
        title_line = get_text('top5_info_title', lang)
        # Вторая строка курсивом через HTML
        hint_raw = get_text('top5_info_pin_hint', lang)
        # Уберём markdown-символы и оставим HTML курсив
        hint_line = hint_raw.replace('💡 ', '').replace('_', '').replace('*', '')
        text = f"{title_line}\n\n💡 <i>{hint_line}</i>"

        # Клавиатура
        if not items:
            text += f"\n\n{get_text('top5_empty', lang)}"
        kb = build_top5_keyboard(items, lang)

        # Отправляем как и другие меню: удаляем предыдущее и сохраняем новое
        await send_message_with_cleanup(callback, state, text, reply_markup=kb, parse_mode='HTML')
        await callback.answer()
    except Exception as e:
        logger.error(f"Error showing Top-5: {e}")
        await callback.answer("Ошибка загрузки Топ-5", show_alert=True)


@router.callback_query(F.data.startswith("t5:"))
async def handle_top5_click(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """
    Обработка нажатия на кнопку топ-5.
    Эмулирует отправку текстового сообщения пользователем для полной идентичности обработки.
    """
    try:
        key = callback.data.split(':', 1)[1]
        # Находим профиль и актуальный снепшот
        profile = await sync_to_async(Profile.objects.filter(telegram_id=callback.from_user.id).first)()
        if not profile:
            await callback.answer(get_text('error_occurred', lang), show_alert=True)
            return
        snapshot = await sync_to_async(Top5Snapshot.objects.filter(profile=profile).first)()
        item = None
        if snapshot and snapshot.items:
            for it in snapshot.items:
                if it.get('id') == key:
                    item = it
                    break
        if not item:
            await callback.answer(get_text('top5_empty', lang), show_alert=True)
            return

        # Извлекаем данные операции
        op_type = item.get('op_type')
        title = item.get('title_display') or ''
        amount = Decimal(str(item.get('amount_norm')))

        # Формируем текст сообщения как если бы пользователь сам его написал
        # Для дохода добавляем "+" в начале
        if op_type == 'income':
            message_text = f"+{amount} {title}"
        else:
            message_text = f"{amount} {title}"

        # Создаем эмулированное сообщение от пользователя
        # ВАЖНО: Копируем существующее сообщение чтобы сохранить привязку к боту
        fake_message = callback.message.model_copy(
            update={
                'message_id': callback.message.message_id + 1,
                'text': message_text
            }
        )

        # Подтверждаем нажатие кнопки
        await callback.answer()

        # Вызываем основной обработчик текстовых сообщений
        from bot.routers.expense import handle_text_expense
        await handle_text_expense(
            message=fake_message,
            state=state,
            text=message_text,
            lang=lang
        )

    except Exception as e:
        logger.error(f"Error handling Top-5 click: {e}")
        await callback.answer("Ошибка обработки кнопки", show_alert=True)


@router.message(F.pinned_message)
async def on_pinned_message(msg: Message):
    """Сохраняем chat_id/message_id, если закрепили наше сообщение Топ‑5."""
    try:
        pinned = msg.pinned_message
        if not pinned:
            return
        # Проверяем, что это наше сообщение и текст соответствует Топ‑5
        if not pinned.from_user or not pinned.from_user.is_bot:
            return
        if not pinned.text:
            return
        if '5 самых популярных' not in pinned.text:
            return
        # Находим профиль по чату (для приватного чата chat.id == telegram_id)
        profile = await sync_to_async(Profile.objects.filter(telegram_id=msg.chat.id).first)()
        if not profile:
            return
        # Сохраняем или обновляем пин
        await sync_to_async(Top5Pin.objects.update_or_create)(
            profile=profile,
            defaults={'chat_id': msg.chat.id, 'message_id': pinned.message_id}
        )
    except Exception as e:
        logger.error(f"Error handling pinned message: {e}")
