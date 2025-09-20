from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging
import time

from admin_panel.models import BroadcastMessage, BroadcastRecipient
from bot.telegram_utils import send_telegram_message
from django.db import transaction

from expenses.models import AffiliateCommission

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
    
    # Получаем получателей
    recipients = broadcast.get_recipients_queryset()
    
    # Создаем записи получателей
    for profile in recipients:
        BroadcastRecipient.objects.get_or_create(
            broadcast=broadcast,
            profile=profile,
            defaults={'status': 'pending'}
        )
    
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
            logger.error(f"Error sending message to {recipient.profile.telegram_id}: {e}")
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
            f"Failed to send notification to {commission.referrer.telegram_id}: {exc}"
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
        commission.referrer.telegram_id,
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
