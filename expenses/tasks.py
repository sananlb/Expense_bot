from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging
import time

from admin_panel.models import BroadcastMessage, BroadcastRecipient
from bot.telegram_utils import send_telegram_message
from django.db import transaction

from expenses.models import AffiliateCommission
from bot.utils.logging_safe import log_safe_id

logger = logging.getLogger(__name__)


@shared_task
def send_broadcast_message(broadcast_id):
    """Задача для отправки массовой рассылки"""
    try:
        broadcast = BroadcastMessage.objects.get(id=broadcast_id)
    except BroadcastMessage.DoesNotExist:
        logger.error(f"Broadcast {broadcast_id} not found")
        return False
    
    # Проверяем статус
    if broadcast.status == 'cancelled':
        logger.info(f"Broadcast {broadcast_id} was cancelled")
        return False
    
    # Обновляем статус на "отправляется"
    broadcast.status = 'sending'
    broadcast.started_at = timezone.now()
    broadcast.save()
    
    # Получаем ID получателей и синхронизируем записи
    recipient_ids = set(
        broadcast.get_recipients_queryset().values_list('id', flat=True)
    )
    if recipient_ids:
        BroadcastRecipient.objects.filter(broadcast=broadcast).exclude(
            profile_id__in=recipient_ids
        ).delete()
    else:
        BroadcastRecipient.objects.filter(broadcast=broadcast).delete()
    
    existing_recipient_ids = set(
        BroadcastRecipient.objects.filter(broadcast=broadcast).values_list('profile_id', flat=True)
    )
    new_recipient_ids = recipient_ids - existing_recipient_ids
    BroadcastRecipient.objects.bulk_create([
        BroadcastRecipient(
            broadcast=broadcast,
            profile_id=profile_id,
            status='pending'
        )
        for profile_id in new_recipient_ids
    ])
    
    # Отправляем сообщения
    sent_count = 0
    failed_count = 0
    
    for recipient in BroadcastRecipient.objects.filter(broadcast=broadcast, status='pending'):
        # Проверяем, не отменена ли рассылка
        broadcast.refresh_from_db()
        if broadcast.status == 'cancelled':
            logger.info(f"Broadcast {broadcast_id} was cancelled during sending")
            return False
        
        try:
            # Отправляем сообщение
            send_telegram_message(
                chat_id=recipient.profile.telegram_id,
                text=broadcast.message_text,
                parse_mode='Markdown'
            )
            
            # Обновляем статус получателя
            recipient.status = 'sent'
            recipient.sent_at = timezone.now()
            recipient.save()
            
            sent_count += 1
            
            # Небольшая задержка между сообщениями (защита от лимитов Telegram)
            time.sleep(0.05)  # 50ms между сообщениями
            
        except Exception as e:
            logger.error(
                "Error sending broadcast message to %s: %s",
                log_safe_id(recipient.profile.telegram_id, "user"),
                e,
            )
            recipient.status = 'failed'
            recipient.error_message = str(e)
            recipient.save()
            failed_count += 1
        
        # Обновляем счетчики в рассылке
        if sent_count % 10 == 0 or failed_count % 10 == 0:
            broadcast.sent_count = sent_count
            broadcast.failed_count = failed_count
            broadcast.save()
    
    # Финальное обновление
    broadcast.sent_count = sent_count
    broadcast.failed_count = failed_count
    broadcast.completed_at = timezone.now()
    
    if failed_count > 0 and sent_count == 0:
        broadcast.status = 'failed'
    else:
        broadcast.status = 'completed'
    
    broadcast.save()
    
    logger.info(f"Broadcast {broadcast_id} completed: {sent_count} sent, {failed_count} failed")
    return True


@shared_task
def process_scheduled_broadcasts():
    """Задача для обработки запланированных рассылок"""
    now = timezone.now()
    
    # Находим рассылки, которые нужно отправить
    scheduled = BroadcastMessage.objects.filter(
        status='scheduled',
        scheduled_at__lte=now
    )
    
    for broadcast in scheduled:
        logger.info(f"Starting scheduled broadcast {broadcast.id}")
        send_broadcast_message.delay(broadcast.id)
    
    return scheduled.count()


@shared_task
def cleanup_old_broadcasts():
    """Очистка старых рассылок и их получателей"""
    # Удаляем получателей рассылок старше 90 дней
    cutoff_date = timezone.now() - timedelta(days=90)
    
    old_broadcasts = BroadcastMessage.objects.filter(
        created_at__lt=cutoff_date,
        status__in=['completed', 'cancelled', 'failed']
    )
    
    count = 0
    for broadcast in old_broadcasts:
        # Удаляем записи получателей
        deleted = BroadcastRecipient.objects.filter(broadcast=broadcast).delete()
        count += deleted[0]
    
    logger.info(f"Cleaned up {count} broadcast recipient records")
    return count


def _notify_commission_paid(commission):
    try:
        from bot.telegram_utils import send_telegram_message

        message = (
            f"🎉 <b>Комиссия выплачена!</b>\n\n"
            f"Вам начислено <b>{commission.commission_amount} ⭐</b> "
            f"за привлечение пользователя.\n\n"
            f"Спасибо за участие в партнёрской программе!"
        )
        send_telegram_message(
            commission.referrer.telegram_id,
            message,
            parse_mode='HTML'
        )
    except Exception as exc:
        logger.error(
            "Failed to send commission notification to %s: %s",
            log_safe_id(commission.referrer.telegram_id, "user"),
            exc,
        )


def _finalize_commission(commission: AffiliateCommission, *, now=None):
    now = now or timezone.now()

    if commission.status != 'hold':
        return {
            'status': 'already_processed',
            'commission_id': commission.id,
            'amount': commission.commission_amount,
        }

    with transaction.atomic():
        commission.status = 'paid'
        commission.paid_at = now
        commission.save(update_fields=['status', 'paid_at'])

    logger.info(
        "[COMMISSION] Released commission %s: %s stars to %s",
        commission.id,
        commission.commission_amount,
        log_safe_id(commission.referrer.telegram_id, "user"),
    )

    _notify_commission_paid(commission)

    return {
        'status': 'success',
        'commission_id': commission.id,
        'amount': commission.commission_amount,
        'referrer_id': commission.referrer.telegram_id,
    }


@shared_task
def release_affiliate_commission(commission_id, requeue_if_not_ready: bool = True):
    """Завершить конкретную комиссию после окончания холда."""

    try:
        commission = AffiliateCommission.objects.select_related('referrer').get(id=commission_id)

        if commission.status != 'hold':
            logger.info(
                "[COMMISSION] Commission %s already processed, status: %s",
                commission_id,
                commission.status,
            )
            return {'status': 'already_processed', 'commission_id': commission_id}

        now = timezone.now()
        if commission.hold_until and commission.hold_until > now:
            logger.info(
                "[COMMISSION] Commission %s hold ends at %s (now=%s)",
                commission_id,
                commission.hold_until,
                now,
            )

            if requeue_if_not_ready:
                eta = commission.hold_until + timedelta(minutes=1)
                release_affiliate_commission.apply_async(
                    args=[commission_id],
                    kwargs={'requeue_if_not_ready': False},
                    eta=eta,
                    queue='maintenance',
                )
                logger.info(
                    "[COMMISSION] Rescheduled commission %s release for %s",
                    commission_id,
                    eta,
                )

            return {'status': 'hold_not_expired', 'commission_id': commission_id}

        return _finalize_commission(commission, now=now)

    except AffiliateCommission.DoesNotExist:
        logger.error(f"[COMMISSION] Commission {commission_id} not found")
        return {'status': 'not_found', 'commission_id': commission_id}
    except Exception as exc:
        logger.error(
            f"[COMMISSION] Failed to release commission {commission_id}: {exc}"
        )
        return {
            'status': 'error',
            'commission_id': commission_id,
            'error': str(exc),
        }


@shared_task
def process_affiliate_commissions(batch_size: int = 200):
    """Ежедневный бэкап-проход по комиссиям, у которых истёк холд."""

    now = timezone.now()
    processed = 0
    total_amount = 0

    while True:
        qs = (
            AffiliateCommission.objects
            .select_related('referrer')
            .filter(status='hold', hold_until__lte=now)
            .order_by('hold_until')[:batch_size]
        )

        if not qs:
            break

        for commission in qs:
            result = _finalize_commission(commission, now=now)
            if result['status'] == 'success':
                processed += 1
                total_amount += result['amount']

    logger.info(
        "[COMMISSION] Daily sweep processed %s commissions totalling %s stars",
        processed,
        total_amount,
    )

    return {
        'processed': processed,
        'total_amount': total_amount,
        'timestamp': now.isoformat(),
    }


@shared_task
def check_subscription_refunds():
    """
    Периодическая задача для проверки возвратов подписок.
    Запускается раз в день для проверки отменённых подписок.
    """
    from django.db import transaction

    now = timezone.now()
    refunded_count = 0

    # Проверяем и отменяем комиссии при возврате средств (если подписка была отменена)
    cancelled_subscriptions = AffiliateCommission.objects.filter(
        status__in=['hold', 'paid'],
        subscription__is_active=False,
        subscription__end_date__lt=now  # Подписка истекла досрочно
    ).select_related('subscription')

    for commission in cancelled_subscriptions:
        # Проверяем, была ли подписка отменена досрочно
        subscription = commission.subscription
        expected_end = subscription.start_date + timedelta(days=30 if subscription.type == 'month' else 180)

        if subscription.end_date < expected_end - timedelta(days=2):  # Допуск 2 дня
            try:
                with transaction.atomic():
                    commission.status = 'refunded'
                    commission.save(update_fields=['status'])
                    refunded_count += 1

                    logger.info(
                        f"[COMMISSION] Refunded commission {commission.id} due to subscription cancellation"
                    )

            except Exception as e:
                logger.error(f"[COMMISSION] Failed to refund commission {commission.id}: {e}")

    if refunded_count > 0:
        logger.info(f"[COMMISSION] Refunded {refunded_count} commissions due to subscription cancellations")

    return {'refunded': refunded_count, 'timestamp': now.isoformat()}


@shared_task
def send_expense_reminders():
    """
    Отправка напоминаний о внесении финансовых операций пользователям.

    Логика работы:
    1. Новый пользователь зарегистрировался и не внес ни одной операции
       → Если прошло 24-48 часов с регистрации, в 20:00 отправляется напоминание
       → Флаг "напоминание отправлено" ставится БЕЗ срока действия

    2. Пользователь не вносил операции (траты или доходы) от 24 до 48 часов
       → В 20:00 отправляется напоминание
       → Флаг "напоминание отправлено" ставится БЕЗ срока действия
       → Если пользователь неактивен более 48 часов - напоминание НЕ отправляется

    3. После отправки напоминания:
       → Если пользователь НЕ внес операцию - больше НЕ напоминаем (флаг остается навсегда)
       → Если пользователь ВНЕС операцию - флаг сбрасывается, логика повторяется с шага 2

    Ключевые моменты:
    - Напоминание отправляется ОДИН РАЗ до внесения операции
    - Окно для отправки: 24-48 часов после последней активности
    - Пользователи неактивные более 48 часов не получают напоминания (не спамим)
    - Флаг в Redis хранится бессрочно (timeout=None)
    - Единственный способ сбросить флаг - внести любую операцию (трату или доход)
    - После внесения операции через 24-48ч бездействия придет новое напоминание
    """
    from django.core.cache import cache
    from expenses.models import Profile, Expense, Income

    now = timezone.now()
    yesterday = now - timedelta(hours=24)
    two_days_ago = now - timedelta(hours=48)

    sent_count = 0
    skipped_count = 0

    # Получаем всех активных пользователей
    active_profiles = Profile.objects.filter(is_active=True)

    for profile in active_profiles:
        try:
            # Ключ в Redis для отслеживания отправленного напоминания
            reminder_key = f"expense_reminder_sent:{profile.telegram_id}"

            # Проверяем, было ли уже отправлено напоминание
            if cache.get(reminder_key):
                skipped_count += 1
                continue

            # Получаем последнюю трату пользователя
            last_expense = Expense.objects.filter(
                profile=profile
            ).order_by('-created_at').first()

            # Получаем последний доход пользователя
            last_income = Income.objects.filter(
                profile=profile
            ).order_by('-created_at').first()

            # Определяем последнюю финансовую операцию (трата или доход)
            last_operation = None
            last_operation_type = None

            if last_expense and last_income:
                # Есть и траты, и доходы - берем самое свежее
                if last_expense.created_at > last_income.created_at:
                    last_operation = last_expense
                    last_operation_type = 'expense'
                else:
                    last_operation = last_income
                    last_operation_type = 'income'
            elif last_expense:
                last_operation = last_expense
                last_operation_type = 'expense'
            elif last_income:
                last_operation = last_income
                last_operation_type = 'income'

            # Условие для отправки напоминания
            should_remind = False

            if not last_operation:
                # Новый пользователь без операций
                # Проверяем, что прошло от 24 до 48 часов с регистрации
                if profile.created_at and two_days_ago < profile.created_at < yesterday:
                    should_remind = True
                    logger.info(
                        "[REMINDER] New user %s needs reminder (no operations, registered 24-48h ago)",
                        log_safe_id(profile.telegram_id, "user"),
                    )
            else:
                # Пользователь с операциями - проверяем что последняя операция была 24-48 часов назад
                if two_days_ago < last_operation.created_at < yesterday:
                    should_remind = True
                    logger.info(
                        "[REMINDER] User %s needs reminder (last %s 24-48h ago: %s)",
                        log_safe_id(profile.telegram_id, "user"),
                        last_operation_type,
                        last_operation.created_at,
                    )

            if should_remind:
                # Проверяем не заблокирован ли бот ПЕРЕД попыткой отправки
                if profile.bot_blocked:
                    logger.debug("[REMINDER] Skipping %s (bot blocked)", log_safe_id(profile.telegram_id, "user"))
                    skipped_count += 1
                    continue

                # Получаем язык пользователя
                lang = profile.language_code or 'ru'

                # Отправляем напоминание
                from bot.telegram_utils import send_telegram_message
                from bot.texts import get_text

                message = get_text('expense_reminder', lang)

                try:
                    send_telegram_message(
                        chat_id=profile.telegram_id,
                        text=message,
                        parse_mode='HTML'
                    )

                    # Устанавливаем флаг в Redis БЕЗ ограничения по времени
                    # Флаг будет сброшен только при создании новой операции
                    cache.set(reminder_key, True, timeout=None)  # Бессрочно

                    sent_count += 1
                    logger.info("[REMINDER] Sent reminder to %s", log_safe_id(profile.telegram_id, "user"))

                    # Небольшая задержка между отправками
                    time.sleep(0.05)

                except Exception as e:
                    error_message = str(e).lower()

                    # Если бот заблокирован - устанавливаем флаг
                    if "bot was blocked by the user" in error_message or "forbidden" in error_message:
                        profile.bot_blocked = True
                        profile.bot_blocked_at = timezone.now()
                        profile.save(update_fields=['bot_blocked', 'bot_blocked_at'])
                        logger.info(
                            "[REMINDER] %s has blocked the bot. Profile marked.",
                            log_safe_id(profile.telegram_id, "user"),
                        )
                    else:
                        # Другие ошибки логируем как ERROR
                        logger.error(
                            "[REMINDER] Failed to send reminder to %s: %s",
                            log_safe_id(profile.telegram_id, "user"),
                            e,
                        )
            else:
                skipped_count += 1

        except Exception as e:
            logger.error("[REMINDER] Error processing %s: %s", log_safe_id(profile.telegram_id, "user"), e)
            continue

    logger.info(
        f"[REMINDER] Completed: {sent_count} reminders sent, {skipped_count} users skipped"
    )

    return {
        'sent': sent_count,
        'skipped': skipped_count,
        'timestamp': now.isoformat()
    }


def clear_expense_reminder(telegram_id: int):
    """
    Сброс флага напоминания при создании новой финансовой операции (траты или дохода).

    После сброса флага пользователь снова может получить напоминание через 24 часа
    бездействия. Это единственный способ сбросить флаг - внести операцию.

    Вызывается из:
    - create_expense() - при создании траты
    - create_income() - при создании дохода
    - recurring payments processor - при автоматических операциях

    Args:
        telegram_id: ID пользователя в Telegram
    """
    from django.core.cache import cache

    reminder_key = f"expense_reminder_sent:{telegram_id}"
    cache.delete(reminder_key)

    logger.debug("[REMINDER] Cleared reminder flag for %s", log_safe_id(telegram_id, "user"))
