"""
Privacy Check Middleware - проверяет принятие политики конфиденциальности
Блокирует использование бота до принятия политики (GDPR compliance)
"""
import logging
from typing import Dict, Any, Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Update, Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext

from bot.utils import get_text
from bot.constants import get_privacy_url_for
from bot.utils.logging_safe import log_safe_id
from expenses.models import Profile

logger = logging.getLogger(__name__)


class PrivacyCheckMiddleware(BaseMiddleware):
    """
    Middleware для проверки принятия политики конфиденциальности

    КРИТИЧЕСКИ ВАЖНО для GDPR compliance:
    - Блокирует ВСЕ действия пользователя до принятия политики
    - Показывает политику конфиденциальности на правильном языке
    - Разрешает только callback для принятия/отклонения политики
    """

    # Callback которые разрешены БЕЗ принятия политики
    ALLOWED_CALLBACKS = {
        'privacy_accept',
        'privacy_decline',
        'close',  # Закрытие сообщения с политикой
    }

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        """Проверка принятия политики перед обработкой запроса"""

        # Получаем пользователя и state
        user = None
        state: FSMContext = data.get('state')

        if isinstance(event, Message):
            user = event.from_user
            message = event
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            message = event.message

            # Разрешаем callback для принятия/отклонения политики
            if event.data in self.ALLOWED_CALLBACKS:
                return await handler(event, data)
        else:
            # Для других типов событий (InlineQuery и т.д.) пропускаем проверку
            return await handler(event, data)

        if not user:
            return await handler(event, data)

        # Пытаемся получить профиль пользователя
        try:
            profile = await Profile.objects.aget(telegram_id=user.id)
        except Profile.DoesNotExist:
            profile = None

        # Если профиль не существует или политика не принята - показываем политику
        if profile is None or not profile.accepted_privacy:
            # Определяем язык пользователя
            user_language_code = user.language_code
            display_lang = None

            if user_language_code:
                display_lang = 'ru' if user_language_code.startswith('ru') else 'en'
            elif profile and profile.language_code:
                stored_language_code = profile.language_code
                display_lang = 'ru' if stored_language_code.startswith('ru') else 'en'

            if not display_lang:
                display_lang = 'ru'

            logger.info(
                "[PRIVACY_CHECK] %s attempted action without accepted privacy policy. profile_exists=%s, accepted_privacy=%s",
                log_safe_id(user.id, "user"),
                profile is not None,
                profile.accepted_privacy if profile else "N/A",
            )

            # Сохраняем информацию о pending профиле для нового пользователя
            if profile is None and state:
                await state.update_data(
                    pending_profile_data={
                        'telegram_id': user.id,
                        'language_code': display_lang,
                        'raw_language_code': user.language_code,
                        # username, first_name, last_name - УДАЛЕНЫ для privacy (GDPR compliance)
                    }
                )

            # Формируем текст политики конфиденциальности
            header = get_text('privacy_policy_header', display_lang)
            short = get_text('short_privacy_for_acceptance', display_lang)
            policy_url = get_privacy_url_for(display_lang)
            full_text_link = get_text('privacy_policy_full_text', display_lang).format(url=policy_url)

            privacy_text = (
                f"<b>{header}</b>\n\n"
                f"{short}\n\n"
                f"{full_text_link}"
            )

            # Кнопки принятия/отклонения
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=get_text('btn_decline_privacy', display_lang),
                        callback_data='privacy_decline'
                    ),
                    InlineKeyboardButton(
                        text=get_text('btn_accept_privacy', display_lang),
                        callback_data='privacy_accept'
                    ),
                ]
            ])

            # Отправляем политику
            if isinstance(event, Message):
                await message.answer(
                    privacy_text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            elif isinstance(event, CallbackQuery):
                try:
                    await event.answer(
                        get_text('privacy_required_alert', display_lang),
                        show_alert=True
                    )
                    # Пытаемся обновить сообщение с политикой
                    await message.edit_text(
                        privacy_text,
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                except Exception as e:
                    # Если не удалось отредактировать - отправляем новое
                    logger.warning("Failed to edit privacy message for %s: %s", log_safe_id(user.id, "user"), e)
                    await message.answer(
                        privacy_text,
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )

            # БЛОКИРУЕМ выполнение обработчика - политика не принята!
            return None

        # Политика принята - продолжаем обработку
        return await handler(event, data)
