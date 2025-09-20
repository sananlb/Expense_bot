"""
Сервис для работы с реферальной программой Telegram Stars
"""
import logging
import secrets
import string
from datetime import timedelta
from typing import Optional, Dict, Any, List

from django.db import transaction
from django.db.models import Sum, F
from django.utils import timezone
from asgiref.sync import sync_to_async

from expenses.models import (
    Profile, 
    Subscription,
    AffiliateProgram,
    AffiliateLink,
    AffiliateReferral
)

logger = logging.getLogger(__name__)


# ============================================
# УПРАВЛЕНИЕ РЕФЕРАЛЬНОЙ ПРОГРАММОЙ
# ============================================

@sync_to_async
def get_or_create_affiliate_program(commission_percent: int = 50, duration_months: Optional[int] = None) -> AffiliateProgram:
    """
    Получить или создать реферальную программу
    
    Args:
        commission_percent: Процент комиссии (50 = 50%)
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
    else:
        # Обновляем процент комиссии если он отличается
        if program.commission_permille != commission_permille:
            program.commission_permille = commission_permille
            program.save()
    
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

@sync_to_async
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
        # Генерируем новый код синхронно внутри sync_to_async
        characters = string.ascii_letters + string.digits
        while True:
            code = ''.join(secrets.choice(characters) for _ in range(8))
            if not AffiliateLink.objects.filter(affiliate_code=code).exists():
                break
        
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
    logger.info(f"[AFFILIATE] Processing referral link for user {new_user_id} with code: {referral_code}")
    
    # Удаляем префикс ref_ если есть
    if referral_code.startswith('ref_'):
        referral_code = referral_code[4:]
        logger.info(f"[AFFILIATE] Cleaned referral code: {referral_code}")
    
    try:
        # Находим реферальную ссылку
        affiliate_link = AffiliateLink.objects.get(
            affiliate_code=referral_code,
            is_active=True
        )
        logger.info(f"[AFFILIATE] Found affiliate link for referrer: {affiliate_link.profile.telegram_id}")
        
        # Получаем профиль нового пользователя
        new_profile = Profile.objects.get(telegram_id=new_user_id)
        logger.info(f"[AFFILIATE] Found profile for new user: {new_profile.telegram_id}")
        
        # Проверяем, что пользователь не приглашает сам себя
        if affiliate_link.profile.telegram_id == new_user_id:
            logger.warning(f"[AFFILIATE] User {new_user_id} trying to refer themselves")
            return None
        
        # Проверяем, не был ли пользователь уже приглашён кем-то
        existing_referral = AffiliateReferral.objects.filter(
            referred=new_profile
        ).first()
        
        if existing_referral:
            logger.info(f"[AFFILIATE] User {new_user_id} already has referrer: {existing_referral.referrer.telegram_id}")
            return existing_referral
        
        # Создаём связь реферер-реферал
        with transaction.atomic():
            # Увеличиваем счётчик кликов
            affiliate_link.clicks = F('clicks') + 1
            affiliate_link.save(update_fields=['clicks'])
            affiliate_link.refresh_from_db()  # Обновляем значения после F() выражений
            
            # Создаём реферальную связь
            referral = AffiliateReferral.objects.create(
                referrer=affiliate_link.profile,
                referred=new_profile,
                affiliate_link=affiliate_link
            )
            logger.info(f"[AFFILIATE] Created referral: {affiliate_link.profile.telegram_id} -> {new_user_id}")
        
        return referral
        
    except AffiliateLink.DoesNotExist:
        logger.warning(f"[AFFILIATE] Affiliate link not found for code: {referral_code}")
        return None
    except Profile.DoesNotExist:
        logger.error(f"[AFFILIATE] Profile not found for user: {new_user_id}")
        return None
    except Exception as e:
        logger.error(f"[AFFILIATE] Unexpected error in process_referral_link: {e}")
        return None


# ============================================
# ВОЗНАГРАЖДЕНИЕ ЗА ПЕРВУЮ ПОДПИСКУ
# ============================================

@sync_to_async
def reward_referrer_subscription_extension(subscription: Subscription) -> Optional[Dict[str, Any]]:
    """Продлить подписку рефереру при первой оплате реферала"""
    logger.info(
        "[AFFILIATE] Checking referral reward for subscription %s (user %s)",
        subscription.id,
        subscription.profile.telegram_id
    )

    # Учитываем только оплаченные подписки в Stars
    if subscription.payment_method != 'stars' or subscription.amount <= 0:
        logger.info(
            "[AFFILIATE] Subscription %s is not eligible for reward (method=%s, amount=%s)",
            subscription.id,
            subscription.payment_method,
            subscription.amount
        )
        return None

    months_map = {
        'month': 1,
        'six_months': 6,
    }
    reward_months = months_map.get(subscription.type)
    if not reward_months:
        logger.warning(
            "[AFFILIATE] Unsupported subscription type %s for referral reward",
            subscription.type
        )
        return None

    try:
        referral = AffiliateReferral.objects.select_related('referrer', 'affiliate_link').get(
            referred=subscription.profile
        )
    except AffiliateReferral.DoesNotExist:
        logger.info(
            "[AFFILIATE] No referral relationship found for user %s",
            subscription.profile.telegram_id
        )
        return None

    if referral.reward_granted:
        logger.info(
            "[AFFILIATE] Reward already granted for referral %s",
            referral.id
        )
        return {
            'status': 'already_rewarded',
            'referral_id': referral.id,
            'referrer_id': referral.referrer.telegram_id,
        }

    reward_duration = subscription.end_date - subscription.start_date
    if reward_duration.total_seconds() <= 0:
        logger.warning(
            "[AFFILIATE] Non-positive reward duration for subscription %s",
            subscription.id
        )
        return None

    now = timezone.now()
    referrer_profile = referral.referrer

    with transaction.atomic():
        # Деактивируем истекшие подписки реферера для корректного расчёта
        expired = Subscription.objects.filter(
            profile=referrer_profile,
            is_active=True,
            end_date__lte=now
        ).update(is_active=False)
        if expired:
            logger.debug(
                "[AFFILIATE] Marked %s expired subscriptions inactive for referrer %s",
                expired,
                referrer_profile.telegram_id
            )

        latest_subscription = Subscription.objects.filter(
            profile=referrer_profile,
            end_date__gt=now
        ).order_by('-end_date').first()

        if latest_subscription:
            reward_start = max(latest_subscription.end_date, now)
        else:
            reward_start = now

        reward_end = reward_start + reward_duration

        reward_subscription = Subscription.objects.create(
            profile=referrer_profile,
            type=subscription.type,
            payment_method='referral',
            amount=0,
            start_date=reward_start,
            end_date=reward_end,
            is_active=True
        )

        logger.info(
            "[AFFILIATE] Created referral reward subscription %s for referrer %s: %s → %s",
            reward_subscription.id,
            referrer_profile.telegram_id,
            reward_start,
            reward_end
        )

        now_ts = timezone.now()
        if not referral.first_payment_at:
            referral.first_payment_at = now_ts

        referral.total_payments = F('total_payments') + 1
        referral.total_spent = F('total_spent') + subscription.amount
        referral.reward_granted = True
        referral.reward_granted_at = now_ts
        referral.reward_subscription = reward_subscription
        referral.reward_months = reward_months
        referral.save(
            update_fields=[
                'first_payment_at',
                'total_payments',
                'total_spent',
                'reward_granted',
                'reward_granted_at',
                'reward_subscription',
                'reward_months'
            ]
        )
        referral.refresh_from_db()

        # Обновляем статистику по ссылке
        if referral.affiliate_link:
            referral.affiliate_link.conversions = F('conversions') + 1
            referral.affiliate_link.save(update_fields=['conversions'])
            referral.affiliate_link.refresh_from_db()

    return {
        'status': 'reward_granted',
        'referral_id': referral.id,
        'referrer_id': referrer_profile.telegram_id,
        'reward_subscription_id': reward_subscription.id,
        'reward_months': reward_months,
        'reward_start': reward_start,
        'reward_end': reward_end,
    }


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
                'referrals_count': 0,
                'rewarded_referrals': 0,
                'pending_referrals': 0,
                'rewarded_months': 0,
            }

        referrals_qs = AffiliateReferral.objects.filter(referrer=profile)

        referrals_count = referrals_qs.count()
        rewarded_referrals = referrals_qs.filter(reward_granted=True).count()
        pending_referrals = referrals_count - rewarded_referrals

        reward_stats = referrals_qs.filter(reward_granted=True).aggregate(
            total_months=Sum('reward_months')
        )
        total_reward_months = reward_stats['total_months'] or 0

        conversion_rate = 0
        if referrals_count > 0:
            rate = (rewarded_referrals / referrals_count) * 100
            conversion_rate = int(rate) if rate == int(rate) else round(rate, 1)

        return {
            'has_link': True,
            'link': affiliate_link.telegram_link,
            'code': affiliate_link.affiliate_code,
            'clicks': affiliate_link.clicks,
            'conversions': affiliate_link.conversions,
            'conversion_rate': conversion_rate,
            'referrals_count': referrals_count,
            'rewarded_referrals': rewarded_referrals,
            'pending_referrals': pending_referrals,
            'rewarded_months': total_reward_months,
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
                'reward_granted': referral.reward_granted,
                'reward_months': referral.reward_months,
                'reward_granted_at': referral.reward_granted_at,
                'is_active': referral.reward_granted,
            })

        return history

    except Profile.DoesNotExist:
        return []


@sync_to_async
def get_reward_history(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Получить историю бонусов за рефералов"""
    try:
        profile = Profile.objects.get(telegram_id=user_id)

        referrals = AffiliateReferral.objects.filter(
            referrer=profile
        ).select_related('referred').order_by('-reward_granted_at', '-joined_at')[:limit]

        history = []
        for referral in referrals:
            history.append({
                'referred_user_id': referral.referred.telegram_id,
                'joined_at': referral.joined_at,
                'reward_granted': referral.reward_granted,
                'reward_months': referral.reward_months,
                'reward_granted_at': referral.reward_granted_at,
            })

        return history

    except Profile.DoesNotExist:
        return []


