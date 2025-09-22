"""
Модель для агрегации данных по блогерам
"""
from django.db import models
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta
from expenses.models import Profile, Subscription


class BloggerAggregateManager(models.Manager):
    """Менеджер для получения агрегированных данных по блогерам"""

    def get_queryset(self):
        """Получаем только уникальных блогеров с их статистикой"""
        from django.db.models import Count, Sum, Q, F, Value
        from django.db.models.functions import Substr

        # Получаем уникальные имена блогеров (первая часть до _)
        bloggers = Profile.objects.filter(
            acquisition_source='blogger',
            acquisition_campaign__isnull=False
        ).values(
            'acquisition_campaign'
        ).distinct()

        # Создаем список уникальных блогеров
        unique_bloggers = {}
        for item in bloggers:
            campaign = item['acquisition_campaign']
            if campaign:
                # Извлекаем имя блогера (часть до первого _)
                blogger_name = campaign.split('_')[0]
                if blogger_name not in unique_bloggers:
                    unique_bloggers[blogger_name] = {
                        'campaigns': [],
                        'first_campaign': campaign
                    }
                unique_bloggers[blogger_name]['campaigns'].append(campaign)

        return unique_bloggers


class BloggerAggregate(models.Model):
    """
    Виртуальная модель для отображения агрегированной статистики блогеров.
    Не сохраняется в БД, используется только для админки.
    """

    blogger_name = models.CharField(max_length=100, primary_key=True, verbose_name='Имя блогера')
    total_users = models.IntegerField(default=0, verbose_name='Всего пользователей')
    active_users = models.IntegerField(default=0, verbose_name='Активных (7д)')
    paying_users = models.IntegerField(default=0, verbose_name='Платящих')
    trial_users = models.IntegerField(default=0, verbose_name='На пробном')
    conversion_to_paying = models.FloatField(default=0, verbose_name='Конверсия в платящих (%)')
    total_revenue = models.IntegerField(default=0, verbose_name='Общий доход (⭐)')
    campaigns = models.JSONField(default=list, verbose_name='Кампании')
    first_user_date = models.DateTimeField(null=True, verbose_name='Первый пользователь')
    last_user_date = models.DateTimeField(null=True, verbose_name='Последний пользователь')

    class Meta:
        managed = False  # Не создаем таблицу в БД
        verbose_name = 'Статистика блогера'
        verbose_name_plural = '📹 Статистика блогеров'

    def __str__(self):
        return self.blogger_name

    @classmethod
    def get_all_bloggers(cls):
        """Получить список всех блогеров со статистикой"""
        bloggers_data = []

        # Получаем все уникальные кампании блогеров
        campaigns = Profile.objects.filter(
            acquisition_source='blogger',
            acquisition_campaign__isnull=False
        ).values_list('acquisition_campaign', flat=True).distinct()

        # Группируем по блогерам
        blogger_campaigns = {}
        for campaign in campaigns:
            if campaign:
                blogger_name = campaign.split('_')[0]
                if blogger_name not in blogger_campaigns:
                    blogger_campaigns[blogger_name] = []
                blogger_campaigns[blogger_name].append(campaign)

        # Для каждого блогера считаем статистику
        for blogger_name, campaigns_list in blogger_campaigns.items():
            # Получаем всех пользователей этого блогера
            users = Profile.objects.filter(
                acquisition_source='blogger',
                acquisition_campaign__in=campaigns_list
            )

            total = users.count()
            if total == 0:
                continue

            # Активные за последние 7 дней
            week_ago = timezone.now() - timedelta(days=7)
            active = users.filter(last_activity__gte=week_ago).count()

            # Платящие
            paying = users.filter(
                subscriptions__is_active=True,
                subscriptions__type__in=['month', 'six_months']
            ).distinct().count()

            # На пробном периоде
            trial = users.filter(
                subscriptions__is_active=True,
                subscriptions__type='trial'
            ).distinct().count()

            # Общий доход
            total_revenue = users.aggregate(
                total=Sum('total_stars_paid')
            )['total'] or 0

            # Даты
            dates = users.aggregate(
                first=models.Min('acquisition_date'),
                last=models.Max('acquisition_date')
            )

            # Конверсия
            conversion = (paying / total * 100) if total > 0 else 0

            blogger_data = cls(
                blogger_name=blogger_name,
                total_users=total,
                active_users=active,
                paying_users=paying,
                trial_users=trial,
                conversion_to_paying=conversion,
                total_revenue=total_revenue,
                campaigns=campaigns_list,
                first_user_date=dates['first'],
                last_user_date=dates['last']
            )
            bloggers_data.append(blogger_data)

        return bloggers_data

    @property
    def personal_link(self):
        """Персональная ссылка блогера"""
        return f"https://t.me/showmecoinbot?start=b_{self.blogger_name}"

    @property
    def efficiency_rating(self):
        """Оценка эффективности"""
        if self.conversion_to_paying >= 15:
            return "🔥 Отлично"
        elif self.conversion_to_paying >= 10:
            return "✅ Хорошо"
        elif self.conversion_to_paying >= 5:
            return "📈 Нормально"
        else:
            return "📊 Низкая"

    def get_users_queryset(self):
        """Получить queryset всех пользователей блогера"""
        return Profile.objects.filter(
            acquisition_source='blogger',
            acquisition_campaign__in=self.campaigns
        )