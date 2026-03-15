"""
Глобальный обработчик ошибок для бота.

Ловит необработанные исключения в handlers и:
1. Логирует ошибку с correlation ID
2. Отправляет пользователю дружелюбное сообщение
3. Опционально уведомляет админа о критических ошибках
4. Очищает FSM state при необходимости
"""
import logging
import uuid
from typing import Any

from aiogram import Router, Bot
from aiogram.types import Update, ErrorEvent
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNotFound,
    TelegramRetryAfter,
    TelegramNetworkError,
)
from aiogram.fsm.context import FSMContext
from bot.utils.logging_safe import log_safe_id

logger = logging.getLogger(__name__)

router = Router(name="errors")


def generate_error_code() -> str:
    """Генерирует короткий код ошибки для пользователя"""
    return uuid.uuid4().hex[:8].upper()


@router.errors()
async def global_error_handler(event: ErrorEvent, bot: Bot) -> bool:
    """
    Глобальный обработчик всех необработанных исключений.

    Returns:
        True - ошибка обработана, не пробрасывать дальше
        False - пробросить ошибку дальше
    """
    exception = event.exception
    update = event.update

    # Получаем информацию о пользователе
    user_id = None
    chat_id = None

    if update.message:
        user_id = update.message.from_user.id if update.message.from_user else None
        chat_id = update.message.chat.id
    elif update.callback_query:
        user_id = update.callback_query.from_user.id if update.callback_query.from_user else None
        chat_id = update.callback_query.message.chat.id if update.callback_query.message else None

    # Генерируем код ошибки для отслеживания
    error_code = generate_error_code()

    # === Обработка специфичных Telegram ошибок ===

    # RetryAfter - flood wait, просто ждём
    if isinstance(exception, TelegramRetryAfter):
        logger.warning(
            "[%s] Telegram RetryAfter: %ss, user=%s",
            error_code,
            exception.retry_after,
            log_safe_id(user_id, "user"),
        )
        # Не отправляем ничего пользователю - Telegram сам справится
        return True

    # Forbidden - бот заблокирован пользователем
    if isinstance(exception, TelegramForbiddenError):
        logger.info(
            "[%s] Bot blocked by %s: %s",
            error_code,
            log_safe_id(user_id, "user"),
            exception,
        )
        # Помечаем пользователя как заблокировавшего бота
        await _mark_user_blocked(user_id)
        return True

    # NotFound - сообщение удалено или чат недоступен
    if isinstance(exception, TelegramNotFound):
        logger.warning(
            "[%s] Telegram NotFound for %s: %s",
            error_code,
            log_safe_id(user_id, "user"),
            exception,
        )
        return True

    # BadRequest - некорректный запрос (часто message not modified и т.п.)
    if isinstance(exception, TelegramBadRequest):
        error_text = str(exception).lower()

        # Игнорируем безобидные ошибки
        if any(msg in error_text for msg in [
            "message is not modified",
            "message to edit not found",
            "message can't be deleted",
            "query is too old",
            "message to delete not found",
        ]):
            logger.debug("[%s] Ignored TelegramBadRequest: %s", error_code, exception)
            return True

        # Остальные BadRequest логируем как warning
        logger.warning(
            "[%s] TelegramBadRequest for %s: %s",
            error_code,
            log_safe_id(user_id, "user"),
            exception,
        )
        return True

    # NetworkError - проблемы с сетью, ретраи на уровне aiogram
    if isinstance(exception, TelegramNetworkError):
        logger.error("[%s] TelegramNetworkError: %s", error_code, exception)
        return True

    # === Обработка остальных ошибок ===

    # Логируем полный stacktrace
    logger.exception(
        "[%s] Unhandled exception for %s",
        error_code,
        log_safe_id(user_id, "user"),
        exc_info=exception
    )

    # Пытаемся отправить пользователю дружелюбное сообщение
    if chat_id:
        try:
            await bot.send_message(
                chat_id,
                "😔 Что-то пошло не так. Попробуйте позднее.",
                parse_mode="HTML"
            )
        except TelegramAPIError as send_error:
            logger.warning("[%s] Failed to send error message to user: %s", error_code, send_error)

    # Уведомляем админа о критических ошибках (не чаще чем раз в минуту на тип ошибки)
    await _notify_admin_if_needed(error_code, exception, user_id)

    return True


async def _mark_user_blocked(user_id: int) -> None:
    """Помечает пользователя как заблокировавшего бота"""
    if not user_id:
        return

    try:
        from expenses.models import Profile
        from django.utils import timezone
        from asgiref.sync import sync_to_async

        @sync_to_async
        def update_blocked_status():
            try:
                profile = Profile.objects.get(telegram_id=user_id)
                if not profile.bot_blocked:
                    profile.bot_blocked = True
                    profile.bot_blocked_at = timezone.now()
                    profile.save(update_fields=['bot_blocked', 'bot_blocked_at'])
                    logger.info("Marked %s as bot_blocked", log_safe_id(user_id, "user"))
            except Profile.DoesNotExist:
                pass

        await update_blocked_status()

    except Exception as e:
        logger.error("Error marking %s as blocked: %s", log_safe_id(user_id, "user"), e)


async def _notify_admin_if_needed(error_code: str, exception: Exception, user_id: int) -> None:
    """Уведомляет админа о критических ошибках с дедупликацией"""
    try:
        from django.core.cache import cache
        from bot.services.admin_notifier import notify_critical_error

        # Дедупликация по типу ошибки (не чаще раза в 5 минут)
        error_type = type(exception).__name__
        cache_key = f"admin_error_notify:{error_type}"

        if not cache.get(cache_key):
            cache.set(cache_key, True, 300)  # 5 минут

            await notify_critical_error(
                error_type=error_type,
                details=f"Code: {error_code}\n{str(exception)[:500]}",
                user_id=user_id
            )

    except Exception as e:
        logger.error("Failed to notify admin about error: %s", e)
