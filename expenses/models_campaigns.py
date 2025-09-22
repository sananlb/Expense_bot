"""
Модель для управления рекламными кампаниями и UTM-метками
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Count, Sum, Q, Avg
from datetime import timedelta
from typing import Dict, Any


class AdvertiserCampaign(models.Model):
    """
    Модель для хранения информации о рекламных кампаниях.
    Это центральная модель для управления всеми рекламными ссылками и UTM-метками.
    """

    SOURCE_TYPES = [
        ('blogger', 'Блогер/Инфлюенсер'),
        ('ads', 'Платная реклама'),
        ('social', 'Социальные сети'),
        ('referral', 'Реферальная программа'),
        ('organic', 'Органический трафик'),
        ('other', 'Другое'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('active', 'Активная'),
        ('paused', 'Приостановлена'),
        ('completed', 'Завершена'),
    ]

    # Основные поля
    name = models.CharField(
        max_length=100,
        verbose_name='Имя рекламопроизводителя',
        help_text='Например: ivan, maria, yandex'
    )
    campaign = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Название кампании',
        help_text='Например: stories, december2024, black_friday'
    )
    utm_code = models.CharField(
        max_length=200,
        unique=True,
        db_index=True,
        verbose_name='UTM-код',
        help_text='Автоматически генерируется, например: b_ivan_stories'
    )
    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_TYPES,
        default='blogger',
        verbose_name='Тип источника'
    )

    # Статус и управление
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активна',
        help_text='Неактивные кампании не отображаются в статистике'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name='Статус кампании'
    )

    # Планирование и бюджет
    budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Бюджет (₽)',
        help_text='Планируемый бюджет кампании'
    )
    target_users = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Целевое количество пользователей',
        help_text='Планируемое количество привлеченных пользователей'
    )
    target_conversion = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Целевая конверсия (%)',
        help_text='Планируемая конверсия в платящих'
    )

    # Дополнительная информация
    description = models.TextField(
        blank=True,
        verbose_name='Описание',
        help_text='Детали кампании, условия сотрудничества и т.д.'
    )
    contact_info = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Контактная информация',
        help_text='Телефон, email или Telegram рекламопроизводителя'
    )

    # Метаданные
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_campaigns',
        verbose_name='Создал'
    )

    # Период кампании
    start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата начала'
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата окончания'
    )

    class Meta:
        verbose_name = 'Рекламная кампания'
        verbose_name_plural = 'Рекламные кампании'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['utm_code']),
            models.Index(fields=['source_type', 'is_active']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        if self.campaign:
            return f"{self.name} - {self.campaign}"
        return self.name

    def _get_prefix(self) -> str:
        """Получить префикс UTM-кода для данного типа источника"""
        prefix_map = {
            'blogger': 'b',
            'ads': 'ads',
            'social': 's',
            'referral': 'ref',
            'organic': 'org',
            'other': 'oth'
        }
        return prefix_map.get(self.source_type, 'oth')

    def _get_campaign_name(self) -> str:
        """Получить название кампании без префикса из UTM-кода"""
        prefix = self._get_prefix()
        return self.utm_code.replace(f"{prefix}_", "")

    def save(self, *args, **kwargs):
        """Автоматически генерируем UTM-код при сохранении"""
        if not self.utm_code:
            prefix = self._get_prefix()

            # Формируем UTM-код
            self.utm_code = f"{prefix}_{self.name}"
            if self.campaign:
                self.utm_code += f"_{self.campaign}"

        super().save(*args, **kwargs)

    @property
    def link(self):
        """Полная ссылка для кампании"""
        return f"https://t.me/showmecoinbot?start={self.utm_code}"

    @property
    def short_link(self):
        """Короткая версия ссылки для отображения"""
        return f"t.me/showmecoinbot?start={self.utm_code}"

    def get_stats(self) -> Dict[str, Any]:
        """
        Получить полную статистику по кампании.
        Возвращает словарь с метриками.
        """
        from expenses.models import Profile

        # Получаем всех пользователей этой кампании
        users = Profile.objects.filter(
            acquisition_source=self.source_type,
            acquisition_campaign=self._get_campaign_name()
        )

        total_users = users.count()

        if total_users == 0:
            return {
                'total_users': 0,
                'active_users': 0,
                'paying_users': 0,
                'trial_users': 0,
                'conversion_to_paying': 0,
                'conversion_to_trial': 0,
                'total_revenue': 0,
                'average_check': 0,
                'ltv': 0,
                'roi': 0,
            }

        # Активные пользователи за последние 7 дней
        week_ago = timezone.now() - timedelta(days=7)
        active_users = users.filter(last_activity__gte=week_ago).count()

        # Платящие пользователи
        paying_users = users.filter(
            subscriptions__is_active=True,
            subscriptions__type__in=['month', 'six_months']
        ).distinct().count()

        # Пользователи на пробном периоде
        trial_users = users.filter(
            subscriptions__is_active=True,
            subscriptions__type='trial'
        ).distinct().count()

        # Общий доход
        total_revenue = users.aggregate(
            total=Sum('total_stars_paid')
        )['total'] or 0

        # Конверсии
        conversion_to_paying = (paying_users / total_users * 100) if total_users > 0 else 0
        conversion_to_trial = (trial_users / total_users * 100) if total_users > 0 else 0

        # Средний чек
        average_check = (total_revenue / paying_users) if paying_users > 0 else 0

        # LTV (Lifetime Value)
        ltv = (total_revenue / total_users) if total_users > 0 else 0

        # ROI (Return on Investment)
        roi = 0
        if self.budget and self.budget > 0:
            roi = ((total_revenue * 2 - float(self.budget)) / float(self.budget) * 100)

        return {
            'total_users': total_users,
            'active_users': active_users,
            'active_percent': (active_users / total_users * 100) if total_users > 0 else 0,
            'paying_users': paying_users,
            'trial_users': trial_users,
            'conversion_to_paying': round(conversion_to_paying, 1),
            'conversion_to_trial': round(conversion_to_trial, 1),
            'total_revenue': total_revenue,
            'total_revenue_rub': total_revenue * 2,  # 1 star ≈ 2 rub
            'average_check': round(average_check, 0),
            'ltv': round(ltv, 0),
            'roi': round(roi, 1),
        }

    def get_recent_users(self, limit=10):
        """Получить последних пользователей кампании"""
        from expenses.models import Profile

        return Profile.objects.filter(
            acquisition_source=self.source_type,
            acquisition_campaign=self._get_campaign_name()
        ).order_by('-acquisition_date')[:limit]

    def is_successful(self) -> bool:
        """Проверка, успешна ли кампания относительно целей"""
        stats = self.get_stats()

        # Проверяем достижение целей
        if self.target_users and stats['total_users'] >= self.target_users:
            return True

        if self.target_conversion and stats['conversion_to_paying'] >= float(self.target_conversion):
            return True

        # Если ROI больше 100% - кампания успешна
        if stats['roi'] > 100:
            return True

        return False

    @classmethod
    def get_active_campaigns(cls):
        """Получить все активные кампании"""
        return cls.objects.filter(
            is_active=True,
            status='active'
        )

    @classmethod
    def get_by_utm(cls, utm_code: str):
        """Найти кампанию по UTM-коду"""
        try:
            return cls.objects.get(utm_code=utm_code)
        except cls.DoesNotExist:
            return None