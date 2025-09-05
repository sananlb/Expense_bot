from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging
import time

from admin_panel.models import BroadcastMessage, BroadcastRecipient
from bot.telegram_utils import send_telegram_message

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