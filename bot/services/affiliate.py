"""
Сервис для работы с реферальной программой Telegram Stars
"""
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum, Count, F
from django.utils import timezone
from asgiref.sync import sync_to_async

from expenses.models import (
    Profile, 
    Subscription,
    AffiliateProgram,
    AffiliateLink,
    AffiliateReferral,
    AffiliateCommission
)


# ============================================
# УПРАВЛЕНИЕ РЕФЕРАЛЬНОЙ ПРОГРАММОЙ
# ============================================

@sync_to_async
def get_or_create_affiliate_program(commission_percent: int = 10, duration_months: Optional[int] = None) -> AffiliateProgram:
    """
    Получить или создать реферальную программу
    
    Args:
        commission_percent: Процент комиссии (10 = 10%)
        duration_months: Срок действия в месяцах (None = бессрочно)
    
    Returns:
        AffiliateProgram: Объект программы
    """
    # Конвертируем проценты в промилле
    commission_permille = commission_percent * 10
    
    # Ищем активную программу
    program = AffiliateProgram.objects.filter(is_active=True).first()
    
    if not program:
        # Создаём новую программу
        end_date = None
        if duration_months:
            end_date = timezone.now() + timedelta(days=30 * duration_months)
        
        program = AffiliateProgram.objects.create(
            commission_permille=commission_permille,
            duration_months=duration_months,
            end_date=end_date,
            is_active=True
        )
    
    return program


@sync_to_async
def deactivate_affiliate_program() -> bool:
    """Деактивировать текущую реферальную программу"""
    try:
        program = AffiliateProgram.objects.filter(is_active=True).first()
        if program:
            program.is_active = False
            program.end_date = timezone.now()
            program.save()
            return True
        return False
    except Exception:
        return False


# ============================================
# УПРАВЛЕНИЕ РЕФЕРАЛЬНЫМИ ССЫЛКАМИ
# ============================================

def generate_affiliate_code(length: int = 8) -> str:
    """Генерировать уникальный реферальный код"""
    characters = string.ascii_letters + string.digits
    while True:
        code = ''.join(secrets.choice(characters) for _ in range(length))
        if not AffiliateLink.objects.filter(affiliate_code=code).exists():
            return code


@sync_to_async
def get_or_create_affiliate_link(user_id: int, bot_username: str) -> AffiliateLink:
    """
    Получить или создать реферальную ссылку для пользователя
    
    Args:
        user_id: Telegram ID пользователя
        bot_username: Username бота для формирования ссылки
    
    Returns:
        AffiliateLink: Объект реферальной ссылки
    """
    try:
        profile = Profile.objects.get(telegram_id=user_id)
    except Profile.DoesNotExist:
        raise ValueError(f"Profile not found for user {user_id}")
    
    # Проверяем существующую ссылку
    affiliate_link = AffiliateLink.objects.filter(profile=profile).first()
    
    if not affiliate_link:
        # Генерируем новый код
        code = generate_affiliate_code()
        
        # Создаём ссылку
        telegram_link = f"https://t.me/{bot_username}?start=ref_{code}"
        
        affiliate_link = AffiliateLink.objects.create(
            profile=profile,
            affiliate_code=code,
            telegram_link=telegram_link,
            is_active=True
        )
    
    return affiliate_link


@sync_to_async
def process_referral_link(new_user_id: int, referral_code: str) -> Optional[AffiliateReferral]:
    """
    Обработать переход по реферальной ссылке
    
    Args:
        new_user_id: ID нового пользователя
        referral_code: Реферальный код из ссылки
    
    Returns:
        AffiliateReferral или None если ссылка невалидна
    """
    # Удаляем префикс ref_ если есть
    if referral_code.startswith('ref_'):
        referral_code = referral_code[4:]
    
    try:
        # Находим реферальную ссылку
        affiliate_link = AffiliateLink.objects.get(
            affiliate_code=referral_code,
            is_active=True
        )
        
        # Получаем профиль нового пользователя
        new_profile = Profile.objects.get(telegram_id=new_user_id)
        
        # Проверяем, что пользователь не приглашает сам себя
        if affiliate_link.profile.telegram_id == new_user_id:
            return None
        
        # Проверяем, не был ли пользователь уже приглашён кем-то
        existing_referral = AffiliateReferral.objects.filter(
            referred=new_profile
        ).first()
        
        if existing_referral:
            return existing_referral
        
        # Создаём связь реферер-реферал
        with transaction.atomic():
            # Увеличиваем счётчик кликов
            affiliate_link.clicks = F('clicks') + 1
            affiliate_link.save()
            
            # Создаём реферальную связь
            referral = AffiliateReferral.objects.create(
                referrer=affiliate_link.profile,
                referred=new_profile,
                affiliate_link=affiliate_link
            )
        
        return referral
        
    except (AffiliateLink.DoesNotExist, Profile.DoesNotExist):
        return None


# ============================================
# ОБРАБОТКА КОМИССИЙ
# ============================================

@sync_to_async
def process_referral_commission(subscription: Subscription) -> Optional[AffiliateCommission]:
    """
    Обработать комиссию при оплате подписки
    
    Args:
        subscription: Оплаченная подписка
    
    Returns:
        AffiliateCommission или None если комиссия не начислена
    """
    # Проверяем, есть ли активная реферальная программа
    program = AffiliateProgram.objects.filter(is_active=True).first()
    if not program:
        return None
    
    # Проверяем, что это платная подписка (не trial, не referral)
    if subscription.payment_method != 'stars' or subscription.amount == 0:
        return None
    
    try:
        # Находим реферальную связь
        referral = AffiliateReferral.objects.select_related(
            'referrer', 'referred', 'affiliate_link'
        ).get(referred=subscription.profile)
        
        # Рассчитываем комиссию
        commission_amount = program.calculate_commission(subscription.amount)
        
        if commission_amount <= 0:
            return None
        
        with transaction.atomic():
            # Создаём запись о комиссии
            commission = AffiliateCommission.objects.create(
                referrer=referral.referrer,
                referred=referral.referred,
                subscription=subscription,
                referral=referral,
                payment_amount=subscription.amount,
                commission_amount=commission_amount,
                commission_rate=program.commission_permille,
                status='hold',  # Сразу ставим на холд
                hold_until=timezone.now() + timedelta(days=21)  # 21 день холда
            )
            
            # Обновляем статистику реферала
            if not referral.first_payment_at:
                referral.first_payment_at = timezone.now()
            
            referral.total_payments = F('total_payments') + 1
            referral.total_spent = F('total_spent') + subscription.amount
            referral.save()
            
            # Обновляем статистику реферальной ссылки
            if referral.total_payments == 1:  # Первый платёж = конверсия
                referral.affiliate_link.conversions = F('conversions') + 1
            
            referral.affiliate_link.total_earned = F('total_earned') + commission_amount
            referral.affiliate_link.save()
        
        return commission
        
    except AffiliateReferral.DoesNotExist:
        # Пользователь не был приглашён по реферальной ссылке
        return None


@sync_to_async
def update_commission_status(commission_id: int, status: str, telegram_transaction_id: Optional[str] = None) -> bool:
    """
    Обновить статус комиссии
    
    Args:
        commission_id: ID комиссии
        status: Новый статус ('pending', 'hold', 'paid', 'cancelled', 'refunded')
        telegram_transaction_id: ID транзакции от Telegram
    
    Returns:
        bool: Успешность обновления
    """
    try:
        commission = AffiliateCommission.objects.get(id=commission_id)
        commission.status = status
        
        if telegram_transaction_id:
            commission.telegram_transaction_id = telegram_transaction_id
        
        if status == 'paid':
            commission.paid_at = timezone.now()
        
        commission.save()
        return True
    except AffiliateCommission.DoesNotExist:
        return False


# ============================================
# СТАТИСТИКА И ОТЧЁТЫ
# ============================================

@sync_to_async
def get_referrer_stats(user_id: int) -> Dict[str, Any]:
    """
    Получить статистику реферера
    
    Args:
        user_id: Telegram ID реферера
    
    Returns:
        Словарь со статистикой
    """
    try:
        profile = Profile.objects.get(telegram_id=user_id)
        affiliate_link = AffiliateLink.objects.filter(profile=profile).first()
        
        if not affiliate_link:
            return {
                'has_link': False,
                'link': None,
                'clicks': 0,
                'conversions': 0,
                'conversion_rate': 0,
                'total_earned': 0,
                'pending_amount': 0,
                'referrals_count': 0,
                'active_referrals': 0
            }
        
        # Получаем статистику по комиссиям
        commissions_stats = AffiliateCommission.objects.filter(
            referrer=profile
        ).aggregate(
            total_earned=Sum('commission_amount', filter=Q(status='paid')),
            pending_amount=Sum('commission_amount', filter=Q(status__in=['pending', 'hold'])),
            total_commissions=Count('id')
        )
        
        # Получаем количество рефералов
        referrals = AffiliateReferral.objects.filter(
            referrer=profile
        ).aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(total_payments__gt=0))
        )
        
        return {
            'has_link': True,
            'link': affiliate_link.telegram_link,
            'code': affiliate_link.affiliate_code,
            'clicks': affiliate_link.clicks,
            'conversions': affiliate_link.conversions,
            'conversion_rate': affiliate_link.get_conversion_rate(),
            'total_earned': commissions_stats['total_earned'] or 0,
            'pending_amount': commissions_stats['pending_amount'] or 0,
            'referrals_count': referrals['total'] or 0,
            'active_referrals': referrals['active'] or 0
        }
        
    except Profile.DoesNotExist:
        return {
            'has_link': False,
            'error': 'Profile not found'
        }


@sync_to_async
def get_referral_history(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Получить историю рефералов пользователя
    
    Args:
        user_id: Telegram ID реферера
        limit: Максимальное количество записей
    
    Returns:
        Список рефералов с информацией
    """
    try:
        profile = Profile.objects.get(telegram_id=user_id)
        
        referrals = AffiliateReferral.objects.filter(
            referrer=profile
        ).select_related('referred').order_by('-joined_at')[:limit]
        
        history = []
        for referral in referrals:
            history.append({
                'user_id': referral.referred.telegram_id,
                'joined_at': referral.joined_at,
                'first_payment_at': referral.first_payment_at,
                'total_payments': referral.total_payments,
                'total_spent': referral.total_spent,
                'is_active': referral.total_payments > 0
            })
        
        return history
        
    except Profile.DoesNotExist:
        return []


@sync_to_async
def get_commission_history(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Получить историю комиссий пользователя
    
    Args:
        user_id: Telegram ID реферера
        limit: Максимальное количество записей
    
    Returns:
        Список комиссий с информацией
    """
    try:
        profile = Profile.objects.get(telegram_id=user_id)
        
        commissions = AffiliateCommission.objects.filter(
            referrer=profile
        ).select_related('referred', 'subscription').order_by('-created_at')[:limit]
        
        history = []
        for commission in commissions:
            history.append({
                'id': commission.id,
                'referred_user_id': commission.referred.telegram_id,
                'payment_amount': commission.payment_amount,
                'commission_amount': commission.commission_amount,
                'commission_rate': commission.get_commission_percent(),
                'status': commission.status,
                'status_display': commission.get_status_display(),
                'created_at': commission.created_at,
                'paid_at': commission.paid_at,
                'hold_until': commission.hold_until
            })
        
        return history
        
    except Profile.DoesNotExist:
        return []


# ============================================
# CELERY ЗАДАЧИ
# ============================================

@sync_to_async
def process_held_commissions():
    """
    Обработать комиссии, у которых закончился холд
    (Должна вызываться периодически через Celery)
    """
    now = timezone.now()
    
    # Находим комиссии, у которых закончился холд
    commissions = AffiliateCommission.objects.filter(
        status='hold',
        hold_until__lte=now
    )
    
    for commission in commissions:
        # Меняем статус на 'paid'
        # В реальности здесь должна быть интеграция с Telegram API
        # для проверки статуса транзакции
        commission.status = 'paid'
        commission.paid_at = now
        commission.save()
        
        # TODO: Отправить уведомление рефереру о выплате


@sync_to_async
def send_referral_notification(referrer_id: int, referred_id: int, commission_amount: int):
    """
    Отправить уведомление рефереру о новом платеже реферала
    
    Args:
        referrer_id: Telegram ID реферера
        referred_id: Telegram ID реферала
        commission_amount: Сумма комиссии
    """
    # TODO: Реализовать отправку уведомления через бота
    pass