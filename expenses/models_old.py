from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q, F
from datetime import datetime, timedelta
from decimal import Decimal
import uuid


class Profile(models.Model):
    """Профиль пользователя Telegram"""
    telegram_id = models.BigIntegerField(unique=True, primary_key=True)
    first_name = models.CharField(max_length=100)
    username = models.CharField(max_length=100, null=True, blank=True)
    
    # Подписка и доступ
    subscription_end_date = models.DateTimeField(null=True, blank=True)
    trial_end_date = models.DateTimeField(null=True, blank=True)
    is_beta_tester = models.BooleanField(default=False)
    
    # Реферальная система
    referrer = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals')
    referral_code = models.CharField(max_length=20, unique=True, null=True, blank=True)
    
    # Активность
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    # Локализация
    locale = models.CharField(max_length=10, default='ru')
    
    # Согласия
    accepted_privacy = models.BooleanField(default=False)
    accepted_offer = models.BooleanField(default=False)
    
    # Временные метки
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'profiles'
        verbose_name = 'Профиль'
        verbose_name_plural = 'Профили'
        indexes = [
            models.Index(fields=['referral_code']),
            models.Index(fields=['last_activity']),
        ]
    
    def __str__(self):
        return f"{self.first_name} (@{self.username or 'no_username'})"
    
    @property
    def has_active_subscription(self):
        """Проверка активной подписки"""
        if self.subscription_end_date:
            return self.subscription_end_date > timezone.now()
        return False
    
    @property
    def is_in_trial(self):
        """Проверка триального периода"""
        if self.trial_end_date:
            return self.trial_end_date > timezone.now()
        return False
    
    @property
    def can_use_bot(self):
        """Может ли пользователь использовать бота"""
        return self.is_beta_tester or self.has_active_subscription or self.is_in_trial
    
    def save(self, *args, **kwargs):
        """Генерация реферального кода при создании"""
        if not self.referral_code:
            self.referral_code = f"EXP{self.telegram_id}"[:20]
        super().save(*args, **kwargs)


class UserSettings(models.Model):
    """Настройки пользователя"""
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name='settings')
    
    # Основная валюта
    currency = models.CharField(max_length=3, default='RUB')
    
    # Настройки уведомлений
    daily_report_enabled = models.BooleanField(default=True)
    daily_report_time = models.TimeField(default='21:00')
    weekly_report_enabled = models.BooleanField(default=True)
    monthly_report_enabled = models.BooleanField(default=True)
    
    # Часовой пояс
    timezone = models.CharField(max_length=50, default='Europe/Moscow')
    
    # Язык интерфейса
    language = models.CharField(max_length=2, default='ru')
    
    # Настройки отображения
    show_category_icons = models.BooleanField(default=True)
    compact_mode = models.BooleanField(default=False)
    
    # Настройки кешбека по умолчанию
    default_cashback_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))]
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_settings'
        verbose_name = 'Настройки пользователя'
        verbose_name_plural = 'Настройки пользователей'
    
    def __str__(self):
        return f"Настройки {self.profile}"


class ExpenseCategory(models.Model):
    """Категории расходов"""
    ICON_CHOICES = [
        ('🍔', 'Еда'),
        ('🚌', 'Транспорт'),
        ('🏠', 'Жилье'),
        ('🎮', 'Развлечения'),
        ('👕', 'Одежда'),
        ('💊', 'Здоровье'),
        ('📚', 'Образование'),
        ('🎁', 'Подарки'),
        ('💰', 'Другое'),
    ]
    
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=50)
    icon = models.CharField(max_length=2, choices=ICON_CHOICES, default='💰')
    color = models.CharField(max_length=7, default='#808080')  # HEX color
    
    # Для системных категорий
    is_system = models.BooleanField(default=False)
    
    # Кешбек для категории
    cashback_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))]
    )
    
    # Порядок отображения
    display_order = models.IntegerField(default=0)
    
    # Активность
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'expense_categories'
        verbose_name = 'Категория расходов'
        verbose_name_plural = 'Категории расходов'
        ordering = ['display_order', 'name']
        unique_together = [['profile', 'name']]
        indexes = [
            models.Index(fields=['profile', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.icon} {self.name}"
    
    def get_current_month_spent(self):
        """Расходы в текущем месяце по категории"""
        now = timezone.now()
        return self.expenses.filter(
            date__year=now.year,
            date__month=now.month,
            is_deleted=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')


class Expense(models.Model):
    """Записи о расходах"""
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='expenses')
    category = models.ForeignKey(ExpenseCategory, on_delete=models.SET_NULL, null=True, related_name='expenses')
    
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    currency = models.CharField(max_length=3, default='RUB')
    
    description = models.CharField(max_length=255, blank=True)
    
    # Дата и время расхода
    date = models.DateField(db_index=True)
    time = models.TimeField(null=True, blank=True)
    
    # Кешбек
    cashback_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))]
    )
    cashback_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    
    # Метаданные
    location = models.CharField(max_length=255, null=True, blank=True)
    tags = ArrayField(models.CharField(max_length=50), blank=True, default=list)
    
    # Для регулярных платежей
    is_recurring = models.BooleanField(default=False)
    recurring_id = models.UUIDField(null=True, blank=True)
    
    # Мягкое удаление
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # AI обработка
    ai_processed = models.BooleanField(default=False)
    ai_category_suggestion = models.ForeignKey(ExpenseCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='ai_suggestions')
    ai_confidence = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(1)])
    
    # Временные метки
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'expenses'
        verbose_name = 'Расход'
        verbose_name_plural = 'Расходы'
        ordering = ['-date', '-time']
        indexes = [
            models.Index(fields=['profile', '-date']),
            models.Index(fields=['profile', 'category', '-date']),
            models.Index(fields=['profile', '-date'], condition=Q(is_deleted=False), name='idx_profile_date_not_deleted'),
            models.Index(fields=['recurring_id'], condition=Q(is_recurring=True), name='idx_recurring_expenses'),
        ]
    
    def __str__(self):
        return f"{self.amount} {self.currency} - {self.description[:30]}"
    
    def save(self, *args, **kwargs):
        """Установка валюты по умолчанию и расчет кешбека"""
        if not self.currency and hasattr(self.profile, 'settings'):
            self.currency = self.profile.settings.currency
        
        # Расчет кешбека
        if self.cashback_rate > 0:
            self.cashback_amount = (self.amount * self.cashback_rate) / Decimal('100')
        
        super().save(*args, **kwargs)
    
    def soft_delete(self):
        """Мягкое удаление"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()


class RecurringExpense(models.Model):
    """Регулярные расходы"""
    FREQUENCY_CHOICES = [
        ('daily', 'Ежедневно'),
        ('weekly', 'Еженедельно'),
        ('monthly', 'Ежемесячно'),
        ('yearly', 'Ежегодно'),
    ]
    
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='recurring_expenses')
    category = models.ForeignKey(ExpenseCategory, on_delete=models.SET_NULL, null=True)
    
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='RUB')
    
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES)
    day_of_execution = models.IntegerField(null=True, blank=True)  # День месяца/недели
    
    next_date = models.DateField()
    last_created_date = models.DateField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    # UUID для связи с созданными расходами
    recurring_id = models.UUIDField(default=uuid.uuid4, unique=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'recurring_expenses'
        verbose_name = 'Регулярный расход'
        verbose_name_plural = 'Регулярные расходы'
        indexes = [
            models.Index(fields=['profile', 'is_active']),
            models.Index(fields=['next_date']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.amount} {self.currency} ({self.get_frequency_display()})"


class ExpenseStats(models.Model):
    """Статистика расходов пользователя"""
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name='expense_stats', primary_key=True)
    
    # Общая статистика
    total_expenses_count = models.IntegerField(default=0)
    total_expenses_sum = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    total_cashback_earned = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    
    # Средние показатели
    avg_daily_expense = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    avg_weekly_expense = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    avg_monthly_expense = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    
    # Последние обновления
    last_expense_date = models.DateField(null=True, blank=True)
    stats_updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'expense_stats'
        verbose_name = 'Статистика расходов'
        verbose_name_plural = 'Статистика расходов'
    
    def __str__(self):
        return f"Статистика {self.profile}"
    
    def update_stats(self):
        """Обновление статистики"""
        from django.db.models import Avg
        from datetime import timedelta
        
        expenses = self.profile.expenses.filter(is_deleted=False)
        
        self.total_expenses_count = expenses.count()
        self.total_expenses_sum = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        self.total_cashback_earned = expenses.aggregate(total=Sum('cashback_amount'))['total'] or Decimal('0')
        
        if expenses.exists():
            self.last_expense_date = expenses.first().expense_date
            
            # Расчет средних показателей за последние 30 дней
            thirty_days_ago = timezone.now().date() - timedelta(days=30)
            recent_expenses = expenses.filter(expense_date__gte=thirty_days_ago)
            
            if recent_expenses.exists():
                days_count = (timezone.now().date() - thirty_days_ago).days or 1
                total_recent = recent_expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
                
                self.avg_daily_expense = total_recent / days_count
                self.avg_weekly_expense = self.avg_daily_expense * 7
                self.avg_monthly_expense = self.avg_daily_expense * 30
        
        self.save()


class ReportHistory(models.Model):
    """История сгенерированных отчетов"""
    REPORT_TYPES = [
        ('daily', 'Ежедневный'),
        ('weekly', 'Еженедельный'),
        ('monthly', 'Ежемесячный'),
        ('custom', 'Произвольный'),
    ]
    
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='reports')
    
    report_type = models.CharField(max_length=10, choices=REPORT_TYPES)
    file_name = models.CharField(max_length=255)
    file_url = models.URLField()
    file_size = models.IntegerField()  # В байтах
    
    period_start = models.DateField()
    period_end = models.DateField()
    
    total_expenses = models.IntegerField()
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    total_cashback = models.DecimalField(max_digits=15, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        db_table = 'report_history'
        verbose_name = 'История отчетов'
        verbose_name_plural = 'История отчетов'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['profile', '-created_at']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Отчет {self.profile} ({self.get_report_type_display()}) от {self.created_at.strftime('%d.%m.%Y')}"