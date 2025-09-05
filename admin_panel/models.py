from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from expenses.models import Profile


class BroadcastMessage(models.Model):
    """Модель для массовых рассылок"""
    
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('scheduled', 'Запланирована'),
        ('sending', 'Отправляется'),
        ('completed', 'Завершена'),
        ('cancelled', 'Отменена'),
        ('failed', 'Ошибка'),
    ]
    
    RECIPIENT_TYPE_CHOICES = [
        ('all', 'Все пользователи'),
        ('active', 'Активные пользователи'),
        ('subscribed', 'Подписчики'),
        ('trial', 'На пробном периоде'),
        ('inactive', 'Неактивные'),
        ('beta', 'Бета-тестеры'),
        ('custom', 'Выборочно'),
    ]
    
    # Основные поля
    title = models.CharField(
        max_length=200,
        verbose_name='Название рассылки',
        help_text='Для внутреннего использования'
    )
    
    message_text = models.TextField(
        verbose_name='Текст сообщения',
        help_text='Поддерживается Markdown форматирование'
    )
    
    # Настройки получателей
    recipient_type = models.CharField(
        max_length=20,
        choices=RECIPIENT_TYPE_CHOICES,
        default='all',
        verbose_name='Тип получателей'
    )
    
    custom_recipients = models.ManyToManyField(
        Profile,
        blank=True,
        verbose_name='Выбранные получатели',
        help_text='Используется только при типе "Выборочно"'
    )
    
    # Статус и планирование
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name='Статус'
    )
    
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата и время отправки',
        help_text='Оставьте пустым для немедленной отправки'
    )
    
    # Статистика
    total_recipients = models.IntegerField(
        default=0,
        verbose_name='Всего получателей'
    )
    
    sent_count = models.IntegerField(
        default=0,
        verbose_name='Отправлено'
    )
    
    failed_count = models.IntegerField(
        default=0,
        verbose_name='Ошибок'
    )
    
    # Метаданные
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Создал'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Создана'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Обновлена'
    )
    
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Начало отправки'
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Завершена'
    )
    
    # Дополнительные настройки
    include_inactive_days = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Неактивные более N дней',
        help_text='Для типа "Неактивные"'
    )
    
    error_message = models.TextField(
        blank=True,
        verbose_name='Сообщение об ошибке'
    )
    
    class Meta:
        verbose_name = 'Рассылка'
        verbose_name_plural = 'Рассылки'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
    
    def get_recipients_count(self):
        """Подсчет количества получателей"""
        from datetime import timedelta
        
        if self.recipient_type == 'all':
            return Profile.objects.filter(is_active=True).count()
        
        elif self.recipient_type == 'active':
            # Активные за последние 7 дней
            week_ago = timezone.now() - timedelta(days=7)
            return Profile.objects.filter(
                is_active=True,
                last_activity__gte=week_ago
            ).count()
        
        elif self.recipient_type == 'subscribed':
            # Пользователи с активной подпиской
            return Profile.objects.filter(
                is_active=True,
                subscriptions__is_active=True,
                subscriptions__end_date__gt=timezone.now()
            ).distinct().count()
        
        elif self.recipient_type == 'trial':
            # На пробном периоде
            return Profile.objects.filter(
                is_active=True,
                subscriptions__type='trial',
                subscriptions__is_active=True,
                subscriptions__end_date__gt=timezone.now()
            ).distinct().count()
        
        elif self.recipient_type == 'inactive':
            days = self.include_inactive_days or 30
            inactive_date = timezone.now() - timedelta(days=days)
            return Profile.objects.filter(
                is_active=True,
                last_activity__lt=inactive_date
            ).count()
        
        elif self.recipient_type == 'beta':
            # Бета-тестеры
            return Profile.objects.filter(
                is_active=True,
                is_beta_tester=True
            ).count()
        
        elif self.recipient_type == 'custom':
            return self.custom_recipients.count()
        
        return 0
    
    def get_recipients_queryset(self):
        """Получить QuerySet получателей"""
        from datetime import timedelta
        
        if self.recipient_type == 'all':
            return Profile.objects.filter(is_active=True)
        
        elif self.recipient_type == 'active':
            week_ago = timezone.now() - timedelta(days=7)
            return Profile.objects.filter(
                is_active=True,
                last_activity__gte=week_ago
            )
        
        elif self.recipient_type == 'subscribed':
            return Profile.objects.filter(
                is_active=True,
                subscriptions__is_active=True,
                subscriptions__end_date__gt=timezone.now()
            ).distinct()
        
        elif self.recipient_type == 'trial':
            return Profile.objects.filter(
                is_active=True,
                subscriptions__type='trial',
                subscriptions__is_active=True,
                subscriptions__end_date__gt=timezone.now()
            ).distinct()
        
        elif self.recipient_type == 'inactive':
            days = self.include_inactive_days or 30
            inactive_date = timezone.now() - timedelta(days=days)
            return Profile.objects.filter(
                is_active=True,
                last_activity__lt=inactive_date
            )
        
        elif self.recipient_type == 'beta':
            return Profile.objects.filter(
                is_active=True,
                is_beta_tester=True
            )
        
        elif self.recipient_type == 'custom':
            return self.custom_recipients.filter(is_active=True)
        
        return Profile.objects.none()


class BroadcastRecipient(models.Model):
    """Отслеживание отправки каждому получателю"""
    
    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('sent', 'Отправлено'),
        ('failed', 'Ошибка'),
    ]
    
    broadcast = models.ForeignKey(
        BroadcastMessage,
        on_delete=models.CASCADE,
        related_name='recipients'
    )
    
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    sent_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    error_message = models.TextField(
        blank=True
    )
    
    class Meta:
        unique_together = ['broadcast', 'profile']
        verbose_name = 'Получатель рассылки'
        verbose_name_plural = 'Получатели рассылки'
    
    def __str__(self):
        return f"{self.profile} - {self.get_status_display()}"
