"""
Утилиты для обновления UserAnalytics в реальном времени.

Позволяет инкрементировать счётчики (voice_messages, photos_sent и др.)
при обработке сообщений, а не через batch-задачу collect_daily_analytics.
"""
import logging

from asgiref.sync import sync_to_async
from django.db import IntegrityError
from django.db.models import F
from django.utils import timezone

logger = logging.getLogger(__name__)


@sync_to_async
def increment_analytics_counter(
    telegram_id: int,
    field: str,
    value: int = 1,
) -> None:
    """
    Атомарно инкрементирует поле UserAnalytics для пользователя за сегодня.

    Создаёт запись, если её ещё нет. При конкурентном создании
    (unique_together race) перехватывает IntegrityError и повторяет update.

    Args:
        telegram_id: Telegram ID пользователя
        field: Имя поля модели UserAnalytics (например, 'voice_messages')
        value: На сколько увеличить счётчик (по умолчанию 1)
    """
    from expenses.models import Profile, UserAnalytics

    try:
        profile = Profile.objects.filter(telegram_id=telegram_id).first()
        if not profile:
            logger.warning(
                f"[Analytics] Profile not found for telegram_id={telegram_id}"
            )
            return

        today = timezone.localdate()

        # Пытаемся обновить атомарно через F()
        updated = UserAnalytics.objects.filter(
            profile=profile,
            date=today,
        ).update(**{field: F(field) + value})

        if not updated:
            # Записи за сегодня нет — создаём
            try:
                UserAnalytics.objects.create(
                    profile=profile,
                    date=today,
                    **{field: value},
                )
            except IntegrityError:
                # Race condition: другой процесс уже создал запись —
                # повторяем update, чтобы не потерять инкремент
                UserAnalytics.objects.filter(
                    profile=profile,
                    date=today,
                ).update(**{field: F(field) + value})

        logger.debug(
            f"[Analytics] {field} +{value} for user {telegram_id}"
        )

    except Exception as e:
        # Ошибка аналитики не должна ломать основной поток
        logger.error(
            f"[Analytics] Failed to increment {field} for user {telegram_id}: {e}"
        )
