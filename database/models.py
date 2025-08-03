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
    expense_reminders_enabled = models.BooleanField(default=False)
    
    # Часовой пояс
    timezone = models.CharField(max_length=50, default='Europe/Moscow')
    
    # Язык интерфейса
    language = models.CharField(max_length=2, default='ru')
    
    # Бюджеты по умолчанию
    monthly_budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    weekly_budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    daily_budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Настройки отображения
    show_category_icons = models.BooleanField(default=True)
    compact_mode = models.BooleanField(default=False)
    
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
    
    # Бюджет на категорию
    monthly_budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
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
    
    # Метаданные
    location = models.CharField(max_length=255, null=True, blank=True)
    tags = ArrayField(models.CharField(max_length=50), blank=True, default=list)
    
    # Для регулярных платежей
    is_recurring = models.BooleanField(default=False)
    recurring_id = models.UUIDField(null=True, blank=True)
    
    # Вложения
    photo_url = models.URLField(null=True, blank=True)
    receipt_data = models.JSONField(null=True, blank=True)  # Для данных из чеков
    
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
            models.Index(fields=['profile', '-date'], condition=Q(is_deleted=False)),
            models.Index(fields=['recurring_id'], condition=Q(is_recurring=True)),
        ]
    
    def __str__(self):
        return f"{self.amount} {self.currency} - {self.description[:30]}"
    
    def save(self, *args, **kwargs):
        """Установка валюты по умолчанию из настроек пользователя"""
        if not self.currency and hasattr(self.profile, 'settings'):
            self.currency = self.profile.settings.currency
        super().save(*args, **kwargs)
    
    def soft_delete(self):
        """Мягкое удаление"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()


class Budget(models.Model):
    """Бюджеты пользователя"""
    PERIOD_CHOICES = [
        ('daily', 'Ежедневный'),
        ('weekly', 'Еженедельный'),
        ('monthly', 'Ежемесячный'),
        ('yearly', 'Годовой'),
        ('custom', 'Произвольный'),
    ]
    
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='budgets')
    name = models.CharField(max_length=100)
    
    period_type = models.CharField(max_length=10, choices=PERIOD_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)  # Для custom периодов
    
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    currency = models.CharField(max_length=3, default='RUB')
    
    # Категории бюджета (если не указаны - общий бюджет)
    categories = models.ManyToManyField(ExpenseCategory, blank=True, related_name='budgets')
    
    # Уведомления
    notify_on_exceed = models.BooleanField(default=True)
    notify_on_approach = models.BooleanField(default=True)
    approach_threshold = models.IntegerField(default=80, validators=[MinValueValidator(50), MaxValueValidator(95)])
    
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'budgets'
        verbose_name = 'Бюджет'
        verbose_name_plural = 'Бюджеты'
        indexes = [
            models.Index(fields=['profile', 'is_active']),
            models.Index(fields=['start_date', 'end_date']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.amount} {self.currency}"
    
    def get_spent_amount(self):
        """Получить потраченную сумму за период бюджета"""
        expenses_query = Expense.objects.filter(
            profile=self.profile,
            date__gte=self.start_date,
            is_deleted=False
        )
        
        if self.end_date:
            expenses_query = expenses_query.filter(date__lte=self.end_date)
        
        if self.categories.exists():
            expenses_query = expenses_query.filter(category__in=self.categories.all())
        
        return expenses_query.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    @property
    def spent_percentage(self):
        """Процент потраченного бюджета"""
        spent = self.get_spent_amount()
        if self.amount > 0:
            return min(100, int((spent / self.amount) * 100))
        return 0


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
        
        if expenses.exists():
            self.last_expense_date = expenses.first().date
            
            # Расчет средних показателей за последние 30 дней
            thirty_days_ago = timezone.now().date() - timedelta(days=30)
            recent_expenses = expenses.filter(date__gte=thirty_days_ago)
            
            if recent_expenses.exists():
                days_count = (timezone.now().date() - thirty_days_ago).days or 1
                total_recent = recent_expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
                
                self.avg_daily_expense = total_recent / days_count
                self.avg_weekly_expense = self.avg_daily_expense * 7
                self.avg_monthly_expense = self.avg_daily_expense * 30
        
        self.save()


class ExportHistory(models.Model):
    """История экспорта данных"""
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='exports')
    
    file_name = models.CharField(max_length=255)
    file_url = models.URLField()
    file_size = models.IntegerField()  # В байтах
    
    period_start = models.DateField()
    period_end = models.DateField()
    
    categories_included = models.ManyToManyField(ExpenseCategory, blank=True)
    total_expenses = models.IntegerField()
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    export_format = models.CharField(max_length=10, default='xlsx')
    
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        db_table = 'export_history'
        verbose_name = 'История экспорта'
        verbose_name_plural = 'История экспортов'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['profile', '-created_at']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Экспорт {self.profile} от {self.created_at.strftime('%d.%m.%Y')}"