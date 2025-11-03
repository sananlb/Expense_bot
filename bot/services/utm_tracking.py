"""
Сервис для обработки UTM-меток и трекинга источников привлечения пользователей
"""
import logging
from typing import Optional, Dict, Any
from django.utils import timezone
from expenses.models import Profile

logger = logging.getLogger(__name__)


async def parse_utm_source(start_args: str) -> Optional[Dict[str, Any]]:
    """
    Парсинг UTM-меток из параметра команды /start

    Поддерживаемые форматы:
    - b_ivan - блогер ivan
    - b_ivan_stories - блогер ivan, кампания stories
    - ads_yandex - реклама в Яндексе
    - ads_google_blackfriday - реклама в Google, кампания blackfriday
    - p_partner1 - партнер partner1
    - social_tg - соцсети, Telegram
    - org_coins-bot.ru_landing - лендинг сайта coins-bot.ru, страница landing
    - organic - органический трафик

    Returns:
        Dict с полями source, campaign, details или None
    """
    if not start_args:
        return None

    try:
        # Блогеры: b_NAME или b_NAME_CAMPAIGN
        if start_args.startswith('b_'):
            parts = start_args[2:].split('_', 1)
            blogger_name = parts[0]
            campaign = parts[1] if len(parts) > 1 else blogger_name

            return {
                'source': 'blogger',
                'campaign': f"{blogger_name}_{campaign}" if len(parts) > 1 else blogger_name,
                'details': {
                    'blogger_name': blogger_name,
                    'campaign_type': campaign if len(parts) > 1 else 'default'
                }
            }

        # Реклама: ads_SOURCE или ads_SOURCE_CAMPAIGN
        elif start_args.startswith('ads_'):
            parts = start_args[4:].split('_', 1)
            ad_source = parts[0]
            campaign = parts[1] if len(parts) > 1 else 'general'

            return {
                'source': 'ads',
                'campaign': f"{ad_source}_{campaign}",
                'details': {
                    'ad_platform': ad_source,
                    'campaign_name': campaign
                }
            }

        # Партнеры: p_PARTNER или p_PARTNER_ACTION
        elif start_args.startswith('p_'):
            parts = start_args[2:].split('_', 1)
            partner_name = parts[0]
            action = parts[1] if len(parts) > 1 else 'default'

            return {
                'source': 'other',
                'campaign': f"partner_{partner_name}_{action}",
                'details': {
                    'partner': partner_name,
                    'action': action
                }
            }

        # Социальные сети: social_NETWORK
        elif start_args.startswith('social_'):
            network = start_args[7:]

            return {
                'source': 'social',
                'campaign': network,
                'details': {
                    'network': network
                }
            }

        # Лендинг/органический трафик с сайта: org_DOMAIN_PAGE
        # Например: org_coins-bot.ru_landing
        elif start_args.startswith('org_'):
            parts = start_args[4:].split('_', 1)
            domain = parts[0]
            page = parts[1] if len(parts) > 1 else 'unknown'

            return {
                'source': 'organic',
                'campaign': f"{domain}_{page}",
                'details': {
                    'domain': domain,
                    'page': page,
                    'type': 'website_landing'
                }
            }

        # Органический трафик
        elif start_args == 'organic':
            return {
                'source': 'organic',
                'campaign': 'direct',
                'details': {}
            }

        # Реферальная программа (существующая система)
        elif start_args.startswith('ref_'):
            # Не трогаем существующую реферальную систему
            return {
                'source': 'referral',
                'campaign': 'telegram_stars',
                'details': {
                    'system': 'telegram_stars'
                }
            }

        # Семейный бюджет (существующая система)
        elif start_args.startswith('family_'):
            # Не трогаем существующую систему семейного бюджета
            return None

    except Exception as e:
        logger.error(f"Error parsing UTM source from '{start_args}': {e}")

    return None


async def save_utm_data(profile: Profile, utm_data: Dict[str, Any]) -> bool:
    """
    Сохранение UTM-данных в профиль пользователя

    Args:
        profile: Профиль пользователя
        utm_data: Данные UTM-меток из parse_utm_source

    Returns:
        True если данные сохранены успешно
    """
    try:
        # Сохраняем только если у пользователя еще нет данных об источнике
        # (первое касание атрибуция)
        if not profile.acquisition_source:
            # Валидация длины кампании (максимум 100 символов в БД)
            campaign = utm_data.get('campaign', '')
            if len(campaign) > 100:
                logger.warning(f"Campaign name too long ({len(campaign)} chars), truncating: {campaign}")
                campaign = campaign[:100]

            profile.acquisition_source = utm_data['source']
            profile.acquisition_campaign = campaign
            profile.acquisition_date = timezone.now()
            profile.acquisition_details = utm_data.get('details', {})

            await profile.asave(update_fields=[
                'acquisition_source',
                'acquisition_campaign',
                'acquisition_date',
                'acquisition_details'
            ])

            logger.info(
                f"UTM data saved for user {profile.telegram_id}: "
                f"source={utm_data['source']}, campaign={utm_data.get('campaign')}"
            )
            return True
        else:
            logger.info(
                f"User {profile.telegram_id} already has acquisition source: "
                f"{profile.acquisition_source}/{profile.acquisition_campaign}"
            )

    except Exception as e:
        logger.error(f"Error saving UTM data for user {profile.telegram_id}: {e}")

    return False


async def get_blogger_stats_by_name(blogger_name: str) -> Dict[str, Any]:
    """
    Получение статистики для конкретного блогера по имени

    Args:
        blogger_name: Имя блогера (например, 'ivan' для ссылки b_ivan)

    Returns:
        Словарь со статистикой блогера
    """
    from django.db.models import Count, Q, Sum
    from expenses.models import Subscription, Expense
    from datetime import timedelta

    try:
        # Ищем всех пользователей от этого блогера
        # Учитываем разные кампании: b_ivan, b_ivan_stories, b_ivan_reels и т.д.
        # Используем istartwith для регистронезависимого поиска
        queryset = Profile.objects.filter(
            acquisition_source='blogger',
            acquisition_campaign__istartswith=blogger_name
        )

        # Общее количество привлеченных
        total_users = await queryset.acount()

        if total_users == 0:
            return {
                'found': False,
                'blogger_name': blogger_name,
                'message': 'Нет данных по этому блогеру'
            }

        # Активные пользователи (были активны последние 7 дней)
        week_ago = timezone.now() - timedelta(days=7)
        active_users = await queryset.filter(
            last_activity__gte=week_ago
        ).acount()

        # Платящие пользователи
        paying_users = await queryset.filter(
            subscriptions__is_active=True,
            subscriptions__type__in=['month', 'six_months']
        ).distinct().acount()

        # Пользователи с пробной подпиской
        trial_users = await queryset.filter(
            subscriptions__is_active=True,
            subscriptions__type='trial'
        ).distinct().acount()

        # Считаем общий доход (в звездах)
        total_revenue_stars = 0
        async for profile in queryset:
            total_revenue_stars += profile.total_stars_paid or 0

        # Считаем общее количество трат пользователей
        total_expenses = 0
        expenses_count = 0
        async for profile in queryset:
            user_expenses = await Expense.objects.filter(profile=profile).aggregate(
                total=Sum('amount'),
                count=Count('id')
            )
            if user_expenses['total']:
                total_expenses += user_expenses['total']
                expenses_count += user_expenses['count']

        # Средний LTV
        avg_ltv = (total_revenue_stars / total_users) if total_users > 0 else 0

        # Конверсии
        conversion_to_active = (active_users / total_users * 100) if total_users > 0 else 0
        conversion_to_paying = (paying_users / total_users * 100) if total_users > 0 else 0

        # Получаем список кампаний
        campaigns = await queryset.values_list('acquisition_campaign', flat=True).distinct()
        campaigns_list = list(campaigns)

        return {
            'found': True,
            'blogger_name': blogger_name,
            'total_users': total_users,
            'active_users': active_users,
            'paying_users': paying_users,
            'trial_users': trial_users,
            'total_revenue_stars': total_revenue_stars,
            'total_revenue_rubles': total_revenue_stars * 2,  # Примерный курс
            'avg_ltv_stars': avg_ltv,
            'avg_ltv_rubles': avg_ltv * 2,
            'conversion_to_active': conversion_to_active,
            'conversion_to_paying': conversion_to_paying,
            'total_expenses': total_expenses,
            'expenses_count': expenses_count,
            'campaigns': campaigns_list
        }

    except Exception as e:
        logger.error(f"Error getting blogger stats for {blogger_name}: {e}")
        return {
            'found': False,
            'blogger_name': blogger_name,
            'error': str(e)
        }


async def get_acquisition_stats(source: Optional[str] = None, campaign: Optional[str] = None) -> Dict[str, Any]:
    """
    Получение статистики по источникам привлечения

    Args:
        source: Фильтр по источнику (blogger, ads, etc)
        campaign: Фильтр по кампании

    Returns:
        Словарь со статистикой
    """
    from django.db.models import Count, Q, F
    from expenses.models import Subscription
    from datetime import timedelta

    try:
        # Базовый queryset
        queryset = Profile.objects.all()

        # Фильтрация
        if source:
            queryset = queryset.filter(acquisition_source=source)
        if campaign:
            queryset = queryset.filter(acquisition_campaign=campaign)

        # Общее количество пользователей
        total_users = await queryset.acount()

        # Активные пользователи (были активны последние 7 дней)
        week_ago = timezone.now() - timedelta(days=7)
        active_users = await queryset.filter(
            last_activity__gte=week_ago
        ).acount()

        # Платящие пользователи
        paying_users = await queryset.filter(
            subscriptions__is_active=True,
            subscriptions__type__in=['month', 'six_months']
        ).distinct().acount()

        # Статистика по источникам
        sources_stats = await Profile.objects.values('acquisition_source').annotate(
            count=Count('id')
        ).order_by('-count')

        # Статистика по кампаниям (топ-10)
        campaigns_stats = await Profile.objects.exclude(
            acquisition_campaign__isnull=True
        ).values('acquisition_campaign').annotate(
            count=Count('id')
        ).order_by('-count')[:10]

        return {
            'total_users': total_users,
            'active_users': active_users,
            'paying_users': paying_users,
            'conversion_to_active': (active_users / total_users * 100) if total_users > 0 else 0,
            'conversion_to_paying': (paying_users / total_users * 100) if total_users > 0 else 0,
            'sources': list(sources_stats),
            'top_campaigns': list(campaigns_stats)
        }

    except Exception as e:
        logger.error(f"Error getting acquisition stats: {e}")
        return {
            'error': str(e)
        }
