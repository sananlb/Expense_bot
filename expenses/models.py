"""
Модели ExpenseBot согласно техническому заданию
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import date, datetime, time
from decimal import Decimal
import string
import random


class Profile(models.Model):
    """Профиль пользователя согласно ТЗ"""
    telegram_id = models.BigIntegerField(unique=True, db_index=True)
    
    # Локализация и настройки
    language_code = models.CharField(
        max_length=2, 
        default='ru', 
        choices=[('ru', 'Русский'), ('en', 'English')]
    )
    timezone = models.CharField(max_length=50, default='UTC')
    currency = models.CharField(max_length=3, default='RUB')
    
    # Активность
    is_active = models.BooleanField(default=True)
    bot_blocked = models.BooleanField(
        default=False,
        verbose_name='Бот заблокирован',
        help_text='Пользователь заблокировал бота',
        db_index=True
    )
    bot_blocked_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата блокировки',
        help_text='Когда пользователь заблокировал бота'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Бета-тестирование
    is_beta_tester = models.BooleanField(
        default=False,
        verbose_name='Бета-тестер',
        help_text='Имеет доступ к боту в бета-режиме'
    )
    beta_access_key = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='Ключ бета-доступа',
        help_text='Ключ доступа для бета-тестирования'
    )
    
    # Реферальная программа - УДАЛЕНО
    # Используется новая система Telegram Stars через модели:
    # AffiliateLink, AffiliateReferral, AffiliateCommission
    last_activity = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Последняя активность',
        help_text='Время последней активности пользователя'
    )

    # Правовые согласия
    accepted_privacy = models.BooleanField(
        default=False,
        verbose_name='Принято согласие на обработку ПДн'
    )
    accepted_offer = models.BooleanField(
        default=False,
        verbose_name='Принята публичная оферта'
    )
    
    # Статистика платежей
    total_payments_count = models.IntegerField(
        default=0,
        verbose_name='Всего платежей',
        help_text='Общее количество платежей через Telegram Stars'
    )
    total_stars_paid = models.IntegerField(
        default=0,
        verbose_name='Всего уплачено звезд',
        help_text='Общее количество уплаченных Telegram Stars'
    )

    # UTM метки и источник привлечения пользователя
    acquisition_source = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Источник привлечения',
        help_text='Источник привлечения: blogger, ads, organic, referral',
        choices=[
            ('organic', 'Органический'),
            ('blogger', 'Блогер'),
            ('ads', 'Реклама'),
            ('referral', 'Реферал'),
            ('social', 'Соцсети'),
            ('other', 'Другое'),
        ]
    )
    acquisition_campaign = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Кампания/Канал',
        help_text='Название кампании или канала (имя блогера, название рекламы и т.д.)'
    )
    acquisition_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата привлечения',
        help_text='Дата первого перехода по ссылке'
    )
    acquisition_details = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        verbose_name='Дополнительные данные',
        help_text='Дополнительные данные об источнике (utm_content, utm_term и т.д.)'
    )

    # Семейный бюджет (домохозяйство)
    # Пользователь может принадлежать одному домохозяйству.
    # Если null — ведет личный бюджет.
    household = models.ForeignKey(
        'Household',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='profiles',
        verbose_name='Домохозяйство'
    )
    
    class Meta:
        db_table = 'users_profile'
        verbose_name = 'Профиль'
        verbose_name_plural = 'Профили'
        indexes = [
            models.Index(fields=['telegram_id']),
        ]
    
    def __str__(self):
        return f"User {self.telegram_id}"
    
    # Метод generate_referral_code удален - используется новая система Telegram Stars
    
    @property
    def referrals_count(self):
        """Количество приглашенных пользователей"""
        return self.referred_users.count()
    
    @property
    def active_referrals_count(self):
        """Количество активных рефералов с подпиской"""
        from django.db.models import Q
        # Получаем профили приглашенных пользователей через AffiliateReferral
        referred_profiles = Profile.objects.filter(
            referred_by__referrer=self
        )
        # Фильтруем тех, у кого есть активная подписка
        return referred_profiles.filter(
            Q(subscriptions__is_active=True) &
            Q(subscriptions__end_date__gt=timezone.now())
        ).distinct().count()


class Household(models.Model):
    """Домохозяйство (семейный бюджет)"""
    created_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=100, null=True, blank=True)
    creator = models.ForeignKey(
        Profile, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='created_households',
        verbose_name='Создатель'
    )
    max_members = models.IntegerField(default=5, verbose_name='Максимум участников')
    is_active = models.BooleanField(default=True, verbose_name='Активно')

    class Meta:
        db_table = 'households'
        verbose_name = 'Домохозяйство'
        verbose_name_plural = 'Домохозяйства'
        indexes = [
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.name or f"Household #{self.id}"
    
    @property
    def members_count(self):
        """Количество участников домохозяйства"""
        return self.profiles.count()
    
    def can_add_member(self):
        """Проверка возможности добавления нового участника"""
        return self.is_active and self.members_count < self.max_members


class FamilyInvite(models.Model):
    """Приглашение в домохозяйство через deep-link"""
    inviter = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='family_invites')
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name='invites')
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    used_by = models.ForeignKey(
        Profile, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='used_invites',
        verbose_name='Использовано пользователем'
    )
    used_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата использования')

    class Meta:
        db_table = 'family_invites'
        verbose_name = 'Приглашение в сем. бюджет'
        verbose_name_plural = 'Приглашения в сем. бюджет'
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['is_active', 'expires_at']),
        ]

    def __str__(self):
        return f"Invite {self.token} -> HH#{self.household_id} by {self.inviter_id}"

    def is_valid(self):
        from django.utils import timezone as dj_tz
        if not self.is_active:
            return False
        if self.used_by:
            return False
        if self.expires_at and dj_tz.now() > self.expires_at:
            return False
        return True
    
    @staticmethod
    def generate_token():
        """Генерация уникального токена для приглашения"""
        import secrets
        return secrets.token_urlsafe(32)


class UserSettings(models.Model):
    """Настройки пользователя согласно ТЗ"""
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name='settings')

    # Кешбэк
    cashback_enabled = models.BooleanField(default=True, verbose_name='Кешбэк включен')

    # Режим отображения данных: личный или семейный
    VIEW_SCOPE_CHOICES = [
        ('personal', 'Личный'),
        ('household', 'Семья'),
    ]
    view_scope = models.CharField(
        max_length=20,
        choices=VIEW_SCOPE_CHOICES,
        default='personal',
        verbose_name='Режим отображения'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users_settings'
        verbose_name = 'Настройки пользователя'
        verbose_name_plural = 'Настройки пользователей'


class ExpenseCategory(models.Model):
    """Категории трат согласно ТЗ"""
    LANGUAGE_CHOICES = [
        ('ru', 'Russian'),
        ('en', 'English'),
        ('mixed', 'Mixed'),
    ]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)  # Оставляем для обратной совместимости

    # Мультиязычные названия
    name_ru = models.CharField(max_length=100, blank=True, null=True, verbose_name='Название на русском')
    name_en = models.CharField(max_length=100, blank=True, null=True, verbose_name='Название на английском')

    # Язык оригинала (для определения нужно ли переводить)
    original_language = models.CharField(
        max_length=10,
        choices=LANGUAGE_CHOICES,
        default='ru',
        verbose_name='Язык оригинала'
    )

    # Флаг: категория требует перевода
    is_translatable = models.BooleanField(default=True, verbose_name='Требует перевода')

    icon = models.CharField(max_length=10, default='💰')

    # Все категории привязаны к пользователю и могут быть удалены
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'expenses_category'
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        unique_together = ['profile', 'name']
        indexes = [
            models.Index(fields=['profile', 'name']),
            models.Index(fields=['profile', 'name_ru']),
            models.Index(fields=['profile', 'name_en']),
        ]

    def save(self, *args, **kwargs):
        """Переопределяем save для синхронизации старого поля name"""
        # Синхронизируем старое поле name на основе original_language
        if self.original_language == 'ru' and self.name_ru:
            self.name = f"{self.icon} {self.name_ru}" if self.icon else self.name_ru
        elif self.original_language == 'en' and self.name_en:
            self.name = f"{self.icon} {self.name_en}" if self.icon else self.name_en
        elif self.name_en:
            # Fallback на английский
            self.name = f"{self.icon} {self.name_en}" if self.icon else self.name_en
        elif self.name_ru:
            # Fallback на русский
            self.name = f"{self.icon} {self.name_ru}" if self.icon else self.name_ru
        elif not self.name:
            self.name = "Без категории"

        super().save(*args, **kwargs)

    def __str__(self):
        # Для админки показываем категорию так, как её видит пользователь (владелец)
        # Это помогает в отладке - видим что именно показывается пользователю
        try:
            # Получаем язык пользователя-владельца категории
            user_lang = self.profile.language_code if self.profile else 'ru'
            return self.get_display_name(user_lang)
        except Exception:
            # Fallback на старое поле если что-то пошло не так
            return self.name
    
    def get_display_name(self, language_code='ru'):
        """Возвращает название категории на нужном языке"""
        
        if not self.is_translatable:
            # Категория не переводится - показываем оригинал из правильного поля
            if self.original_language == 'ru':
                name = self.name_ru
            elif self.original_language == 'en':
                name = self.name_en
            else:
                # Fallback на старое поле name для обратной совместимости
                name = self.name.replace(self.icon, '').strip()
            
            return f"{self.icon} {name}" if name else self.name
        
        # Категория переводимая - выбираем нужный язык с fallback
        if language_code == 'ru':
            name = self.name_ru or self.name_en
        else:
            name = self.name_en or self.name_ru
        
        # Последний fallback на старое поле name
        if not name:
            name = self.name.replace(self.icon, '').strip()
        
        return f"{self.icon} {name}" if name else self.name


class CategoryKeyword(models.Model):
    """Ключевые слова для автоматического определения категорий"""
    LANGUAGE_CHOICES = [
        ('ru', 'Russian'),
        ('en', 'English'),
    ]
    
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE, related_name='keywords')
    keyword = models.CharField(max_length=100, db_index=True)
    
    # Язык ключевого слова
    language = models.CharField(
        max_length=10,
        choices=LANGUAGE_CHOICES,
        default='ru',
        verbose_name='Язык ключевого слова'
    )

    # Счетчик использования (для статистики)
    usage_count = models.IntegerField(default=0, verbose_name='Количество использований')

    # Временные метки
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    last_used = models.DateTimeField(auto_now=True, verbose_name='Последнее использование')

    class Meta:
        db_table = 'expenses_category_keyword'
        verbose_name = 'Ключевое слово категории'
        verbose_name_plural = 'Ключевые слова категорий'
        unique_together = ['category', 'keyword', 'language']
        indexes = [
            models.Index(fields=['category', 'keyword']),
            models.Index(fields=['language']),
            models.Index(fields=['last_used']),  # Индекс для быстрой сортировки при очистке
        ]

    def __str__(self):
        return f"{self.keyword} ({self.language}) -> {self.category.name}"


class Expense(models.Model):
    """Траты согласно ТЗ"""
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='expenses')
    category = models.ForeignKey(
        ExpenseCategory, 
        on_delete=models.SET_NULL, 
        null=True,  # Может быть NULL для авто-определения
        blank=True,
        related_name='expenses'
    )
    
    # Основная информация
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)])
    currency = models.CharField(max_length=3, default='RUB')  # Валюта траты
    description = models.TextField(blank=True)
    
    # Дата и время (автоматические по ТЗ)
    expense_date = models.DateField(default=date.today)
    expense_time = models.TimeField(default=datetime.now)
    
    # Вложения
    receipt_photo = models.CharField(max_length=255, blank=True)
    
    # AI категоризация
    ai_categorized = models.BooleanField(default=False)  # Категория определена AI
    ai_confidence = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)]
    )  # Уверенность AI в категории
    
    # Кешбек
    cashback_excluded = models.BooleanField(default=False)  # Исключить кешбек для этой траты
    cashback_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0'),
        validators=[MinValueValidator(0)]
    )  # Сумма кешбека для этой траты
    
    # Временные метки
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'expenses_expense'
        verbose_name = 'Трата'
        verbose_name_plural = 'Траты'
        ordering = ['-expense_date', '-expense_time']
        indexes = [
            models.Index(fields=['profile', '-expense_date']),
            models.Index(fields=['profile', 'category', '-expense_date']),
        ]
    
    def __str__(self):
        return f"{self.amount} {self.profile.currency} - {self.description[:30]}"


class Budget(models.Model):
    """Бюджеты по категориям согласно ТЗ"""
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='budgets')
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE, null=True, blank=True)
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    period_type = models.CharField(
        max_length=20,
        choices=[
            ('monthly', 'Месячный'),
            ('weekly', 'Недельный'),
            ('daily', 'Дневной')
        ]
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'expenses_budget'
        verbose_name = 'Бюджет'
        verbose_name_plural = 'Бюджеты'


class RecurringPayment(models.Model):
    """Регулярные операции пользователя (доходы и расходы)"""
    
    # Типы операций
    OPERATION_TYPE_EXPENSE = 'expense'
    OPERATION_TYPE_INCOME = 'income'
    OPERATION_TYPE_CHOICES = [
        (OPERATION_TYPE_EXPENSE, 'Расход'),
        (OPERATION_TYPE_INCOME, 'Доход'),
    ]
    
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='recurring_payments')
    
    # Тип операции (доход или расход)
    operation_type = models.CharField(
        max_length=10, 
        choices=OPERATION_TYPE_CHOICES,
        default=OPERATION_TYPE_EXPENSE,
        verbose_name='Тип операции',
        db_index=True
    )
    
    # Категории - теперь оба поля опциональные
    expense_category = models.ForeignKey(
        ExpenseCategory, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='recurring_expenses',
        verbose_name='Категория расхода'
    )
    income_category = models.ForeignKey(
        'IncomeCategory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recurring_incomes',
        verbose_name='Категория дохода'
    )
    
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)])
    currency = models.CharField(max_length=3, default='RUB')
    description = models.CharField(max_length=200, verbose_name='Описание')
    day_of_month = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(30)],
        verbose_name='День месяца'
    )
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    last_processed = models.DateField(null=True, blank=True, verbose_name='Последний платеж')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'expenses_recurring_payment'
        verbose_name = 'Регулярная операция'
        verbose_name_plural = 'Регулярные операции'
        indexes = [
            models.Index(fields=['profile', 'is_active']),
            models.Index(fields=['day_of_month', 'is_active']),
            models.Index(fields=['operation_type', 'is_active']),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(operation_type='expense', expense_category__isnull=False) |
                    models.Q(operation_type='income', income_category__isnull=False)
                ),
                name='category_type_consistency'
            )
        ]
    
    def __str__(self):
        operation_sign = '+' if self.operation_type == self.OPERATION_TYPE_INCOME else '-'
        return f"{self.description} {operation_sign}{self.amount} {self.currency} ({self.day_of_month} числа)"
    
    @property
    def category(self):
        """Получить категорию в зависимости от типа операции"""
        if self.operation_type == self.OPERATION_TYPE_EXPENSE:
            return self.expense_category
        return self.income_category
    
    def clean(self):
        """Валидация модели"""
        from django.core.exceptions import ValidationError
        
        if self.operation_type == self.OPERATION_TYPE_EXPENSE and not self.expense_category:
            raise ValidationError('Для расхода должна быть указана категория расхода')
        
        if self.operation_type == self.OPERATION_TYPE_INCOME and not self.income_category:
            raise ValidationError('Для дохода должна быть указана категория дохода')
        
        # Очистка неиспользуемого поля
        if self.operation_type == self.OPERATION_TYPE_EXPENSE:
            self.income_category = None
        else:
            self.expense_category = None


class Cashback(models.Model):
    """Информация о кешбэках по категориям согласно ТЗ"""
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='cashbacks')
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE, null=True, blank=True)
    bank_name = models.CharField(max_length=100, verbose_name='Название банка')
    cashback_percent = models.DecimalField(
        max_digits=4, 
        decimal_places=2, 
        verbose_name='Процент кешбэка',
        validators=[MinValueValidator(0), MaxValueValidator(99)]
    )
    month = models.IntegerField(
        choices=[(i, i) for i in range(1, 13)], 
        verbose_name='Месяц'
    )
    limit_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        verbose_name='Лимит'
    )
    description = models.CharField(
        max_length=200, 
        blank=True, 
        default='', 
        verbose_name='Описание'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'expenses_cashback'
        verbose_name = 'Кешбэк'
        verbose_name_plural = 'Кешбэки'
        unique_together = [['profile', 'bank_name', 'month', 'category']]
        indexes = [
            models.Index(fields=['profile', 'month']),
            models.Index(fields=['profile', 'category']),
        ]
    
    def __str__(self):
        category_name = self.category.name if self.category else "Без категории"
        return f"{self.bank_name} - {category_name} - {self.cashback_percent}%"


# Базовые категории для новых пользователей
class Subscription(models.Model):
    """Модель для хранения информации о подписках пользователей"""
    SUBSCRIPTION_TYPES = [
        ('trial', 'Пробный период'),
        ('month', 'Месячная подписка'),
        ('six_months', 'Полугодовая подписка'),
    ]
    
    PAYMENT_METHODS = [
        ('trial', 'Пробный период'),
        ('stars', 'Telegram Stars'),
        ('referral', 'Реферальное продление'),
    ]
    
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='subscriptions')
    type = models.CharField(max_length=20, choices=SUBSCRIPTION_TYPES, default='month', blank=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='stars', blank=True)
    
    amount = models.IntegerField(default=0)  # Количество звезд (0 для пробного периода)
    telegram_payment_charge_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    
    is_active = models.BooleanField(default=True)
    notification_sent = models.BooleanField(default=False)  # Отправлено ли уведомление об окончании
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subscriptions'
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
        indexes = [
            models.Index(fields=['profile', 'is_active']),
            models.Index(fields=['end_date']),
        ]
    
    def __str__(self):
        return f"{self.profile} - {self.get_type_display()} до {self.end_date.strftime('%d.%m.%Y')}"
    
    
    @property
    def is_valid(self):
        """Проверка активности подписки"""
        return self.is_active and self.end_date > timezone.now()


class SubscriptionNotification(models.Model):
    """Модель для отслеживания отправленных уведомлений о подписках"""
    NOTIFICATION_TYPES = [
        ('one_day', 'За день'),
    ]
    
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES
    )
    sent_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'subscription_notifications'
        unique_together = ['subscription', 'notification_type']
        verbose_name = 'Уведомление о подписке'
        verbose_name_plural = 'Уведомления о подписках'
    
    def __str__(self):
        return f"{self.subscription} - {self.get_notification_type_display()}"


class PromoCode(models.Model):
    """Промокоды для активации подписок"""
    DISCOUNT_TYPES = [
        ('percent', 'Процент скидки'),
        ('fixed', 'Фиксированная скидка'),
        ('days', 'Дополнительные дни'),
    ]
    
    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name='Код'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание',
        help_text='Внутреннее описание промокода'
    )
    
    # Тип и размер скидки
    discount_type = models.CharField(
        max_length=10,
        choices=DISCOUNT_TYPES,
        default='percent',
        verbose_name='Тип скидки'
    )
    discount_value = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='Значение скидки',
        help_text='Процент (0-100), количество Stars или дни'
    )
    
    # Применимость к типам подписок
    applicable_subscription_types = models.CharField(
        max_length=20,
        choices=[
            ('all', 'Все подписки'),
            ('month', 'Только месячная'),
            ('six_months', 'Только на 6 месяцев'),
        ],
        default='all',
        verbose_name='Применимо к',
        help_text='К каким типам подписок применим промокод'
    )

    # Ограничения
    max_uses = models.IntegerField(
        default=0,
        verbose_name='Макс. использований',
        help_text='0 = без ограничений'
    )
    used_count = models.IntegerField(
        default=0,
        verbose_name='Использований'
    )
    
    # Период действия
    valid_from = models.DateTimeField(
        default=timezone.now,
        verbose_name='Действует с'
    )
    valid_until = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Действует до'
    )
    
    # Активность
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен'
    )
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        Profile,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_promocodes',
        verbose_name='Создан'
    )
    
    class Meta:
        db_table = 'promocodes'
        verbose_name = 'Промокод'
        verbose_name_plural = 'Промокоды'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.code} ({self.get_discount_display()})"
    
    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.upper()
        super().save(*args, **kwargs)
    
    def get_discount_display(self):
        """Отображение скидки"""
        if self.discount_type == 'percent':
            return f"-{self.discount_value}%"
        elif self.discount_type == 'fixed':
            return f"-{self.discount_value} звёзд"
        else:
            return f"+{int(self.discount_value)} дней"
    
    def is_valid(self):
        """Проверка валидности промокода"""
        now = timezone.now()
        if not self.is_active:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if now < self.valid_from:
            return False
        if self.max_uses > 0 and self.used_count >= self.max_uses:
            return False
        return True
    
    def apply_discount(self, base_price):
        """Применить скидку к базовой цене"""
        if self.discount_type == 'percent':
            # Защищаемся от некорректных значений (0-100%)
            discount_percent = max(0, min(100, float(self.discount_value)))
            result = base_price * (1 - discount_percent / 100)
            # Округляем до целого и не допускаем отрицательных значений
            return max(0, int(round(result)))
        elif self.discount_type == 'fixed':
            # Защищаемся от отрицательных скидок
            discount_amount = max(0, float(self.discount_value))
            return max(0, int(base_price - discount_amount))
        return int(base_price)


class PromoCodeUsage(models.Model):
    """История использования промокодов"""
    promocode = models.ForeignKey(
        PromoCode,
        on_delete=models.CASCADE,
        related_name='usages',
        verbose_name='Промокод'
    )
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='promocode_usages',
        verbose_name='Пользователь'
    )
    subscription = models.ForeignKey(
        'Subscription',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Подписка'
    )
    used_at = models.DateTimeField(auto_now_add=True, verbose_name='Использован')
    
    class Meta:
        db_table = 'promocode_usages'
        verbose_name = 'Использование промокода'
        verbose_name_plural = 'Использования промокодов'
        unique_together = ['promocode', 'profile']
    
    def __str__(self):
        return f"{self.promocode.code} - {self.profile}"


# Модель ReferralBonus удалена - используется новая система Telegram Stars


class IncomeCategory(models.Model):
    """Категории доходов"""
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='income_categories')
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=10, default='💵')

    # Мультиязычные поля
    name_ru = models.CharField(max_length=100, blank=True, null=True, verbose_name='Название (RU)')
    name_en = models.CharField(max_length=100, blank=True, null=True, verbose_name='Название (EN)')
    original_language = models.CharField(
        max_length=10,
        choices=[('ru', 'Русский'), ('en', 'English'), ('other', 'Other')],
        default='ru',
        verbose_name='Оригинальный язык'
    )
    is_translatable = models.BooleanField(default=True, verbose_name='Переводить автоматически')

    # Активность категории
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)  # Является ли категорией по умолчанию

    # Временные метки
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'incomes_category'
        verbose_name = 'Категория доходов'
        verbose_name_plural = 'Категории доходов'
        unique_together = ['profile', 'name']
        indexes = [
            models.Index(fields=['profile', 'name']),
            models.Index(fields=['profile', 'name_ru']),
            models.Index(fields=['profile', 'name_en']),
        ]

    def save(self, *args, **kwargs):
        """Переопределяем save для синхронизации старого поля name"""
        # Синхронизируем старое поле name на основе original_language
        if self.original_language == 'ru' and self.name_ru:
            self.name = f"{self.icon} {self.name_ru}" if self.icon else self.name_ru
        elif self.original_language == 'en' and self.name_en:
            self.name = f"{self.icon} {self.name_en}" if self.icon else self.name_en
        elif self.name_en:
            # Fallback на английский
            self.name = f"{self.icon} {self.name_en}" if self.icon else self.name_en
        elif self.name_ru:
            # Fallback на русский
            self.name = f"{self.icon} {self.name_ru}" if self.icon else self.name_ru
        elif not self.name:
            self.name = "Прочие доходы"

        super().save(*args, **kwargs)

    def __str__(self):
        # Для админки показываем категорию так, как её видит пользователь (владелец)
        # Это помогает в отладке - видим что именно показывается пользователю
        try:
            # Получаем язык пользователя-владельца категории
            user_lang = self.profile.language_code if self.profile else 'ru'
            return self.get_display_name(user_lang)
        except Exception:
            # Fallback на старое поле если что-то пошло не так
            return self.name
    
    def get_display_name(self, language_code='ru'):
        """Возвращает название категории на нужном языке"""
        
        if not self.is_translatable:
            # Категория не переводится - показываем оригинал из правильного поля
            if self.original_language == 'ru':
                name = self.name_ru
            elif self.original_language == 'en':
                name = self.name_en
            else:
                # Fallback на старое поле name для обратной совместимости
                name = self.name.replace(self.icon, '').strip()
        else:
            # Для переводимых категорий выбираем нужный язык
            if language_code == 'ru':
                name = self.name_ru or self.name_en or self.name.replace(self.icon, '').strip()
            elif language_code == 'en':
                name = self.name_en or self.name_ru or self.name.replace(self.icon, '').strip()
            else:
                # Для других языков используем английский как fallback
                name = self.name_en or self.name_ru or self.name.replace(self.icon, '').strip()
        
        # Убираем эмодзи если он уже есть в названии, чтобы не дублировать
        if name and self.icon and name.startswith(self.icon):
            return name
        elif name and self.icon:
            return f"{self.icon} {name}"
        elif name:
            return name
        else:
            return "Прочие доходы"


class Income(models.Model):
    """Доходы пользователя"""
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='incomes')
    category = models.ForeignKey(
        IncomeCategory, 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True,
        related_name='incomes'
    )
    
    # Основная информация
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)])
    currency = models.CharField(max_length=3, default='RUB')  # Валюта дохода
    description = models.TextField(blank=True)
    
    # Дата и время
    income_date = models.DateField(default=date.today)
    income_time = models.TimeField(default=datetime.now)
    
    # Тип дохода
    income_type = models.CharField(
        max_length=20,
        default='other',
        choices=[
            ('salary', 'Зарплата'),
            ('bonus', 'Премия'),
            ('freelance', 'Фриланс'),
            ('investment', 'Инвестиции'),
            ('gift', 'Подарок'),
            ('refund', 'Возврат'),
            ('cashback', 'Кешбэк'),
            ('other', 'Прочее')
        ]
    )
    
    # Регулярность
    is_recurring = models.BooleanField(default=False)  # Регулярный доход
    recurrence_day = models.IntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        help_text='День месяца для регулярных доходов'
    )
    
    # AI категоризация
    ai_categorized = models.BooleanField(default=False)  # Категория определена AI
    ai_confidence = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)]
    )  # Уверенность AI в категории
    
    # Временные метки
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'incomes_income'
        verbose_name = 'Доход'
        verbose_name_plural = 'Доходы'
        ordering = ['-income_date', '-income_time']
        indexes = [
            models.Index(fields=['profile', '-income_date']),
            models.Index(fields=['profile', 'category', '-income_date']),
        ]
    
    def __str__(self):
        return f"+{self.amount} {self.currency} - {self.description[:30]}"


class IncomeCategoryKeyword(models.Model):
    """Ключевые слова для автоматического определения категорий доходов"""
    category = models.ForeignKey(IncomeCategory, on_delete=models.CASCADE, related_name='keywords')
    keyword = models.CharField(max_length=100, db_index=True)

    # Счетчик использования (для статистики)
    usage_count = models.IntegerField(default=0, verbose_name='Количество использований')

    # Временные метки
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    last_used = models.DateTimeField(auto_now=True, verbose_name='Последнее использование')

    class Meta:
        db_table = 'expenses_income_category_keyword'
        verbose_name = 'Ключевое слово категории дохода'
        verbose_name_plural = 'Ключевые слова категорий доходов'
        unique_together = ['category', 'keyword']
        indexes = [
            models.Index(fields=['keyword']),
            models.Index(fields=['category', 'usage_count']),
            models.Index(fields=['last_used']),  # Индекс для быстрой сортировки при очистке
        ]
    
    def __str__(self):
        return f"{self.keyword} -> {self.category.name}"


DEFAULT_CATEGORIES = [
    ('Продукты', '🛒'),
    ('Кафе и рестораны', '🍽️'),
    ('Транспорт', '🚕'),
    ('Автомобиль', '🚗'),
    ('Жилье', '🏠'),
    ('Аптеки', '💊'),
    ('Медицина', '🏥'),
    ('Красота', '💄'),
    ('Спорт и фитнес', '🏃'),
    ('Одежда и обувь', '👔'),
    ('Развлечения', '🎭'),
    ('Образование', '📚'),
    ('Подарки', '🎁'),
    ('Путешествия', '✈️'),
    ('Коммуналка и подписки', '📱'),
    ('Накопления', '💎'),
    ('Прочие расходы', '💰')
]


class Top5Snapshot(models.Model):
    """Снепшот топ-5 операций для пользователя"""
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name='top5_snapshot')
    window_start = models.DateField()
    window_end = models.DateField()
    items = models.JSONField(default=list)  # список элементов топ-5
    hash = models.CharField(max_length=64, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'top5_snapshots'
        verbose_name = 'Снепшот Топ‑5'
        verbose_name_plural = 'Снепшоты Топ‑5'


class Top5Pin(models.Model):
    """Данные о закрепленном сообщении Топ‑5 для пользователя"""
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name='top5_pin')
    chat_id = models.BigIntegerField()
    message_id = models.BigIntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'top5_pins'
        verbose_name = 'Закреп Топ‑5'
        verbose_name_plural = 'Закрепы Топ‑5'


# =============================================================================
# Модели для мониторинга и аналитики
# =============================================================================

class UserAnalytics(models.Model):
    """Ежедневная аналитика активности пользователя"""
    
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='analytics')
    date = models.DateField(auto_now_add=True)
    
    # Активность
    messages_sent = models.IntegerField(default=0)
    voice_messages = models.IntegerField(default=0)
    photos_sent = models.IntegerField(default=0)
    commands_used = models.JSONField(default=dict)  # {"command": count}
    
    # Использование функций
    expenses_added = models.IntegerField(default=0)
    incomes_added = models.IntegerField(default=0)
    categories_used = models.JSONField(default=dict)  # {"category_id": count}
    ai_categorizations = models.IntegerField(default=0)
    manual_categorizations = models.IntegerField(default=0)
    
    # Кешбэк
    cashback_calculated = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cashback_transactions = models.IntegerField(default=0)
    
    # Ошибки
    errors_encountered = models.IntegerField(default=0)
    error_types = models.JSONField(default=dict)  # {"error_type": count}
    
    # Время использования (в секундах)
    total_session_time = models.IntegerField(default=0)
    peak_hour = models.IntegerField(null=True)  # час максимальной активности (0-23)
    
    # Дополнительные метрики
    pdf_reports_generated = models.IntegerField(default=0)
    recurring_payments_processed = models.IntegerField(default=0)
    budget_checks = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_analytics'
        verbose_name = 'Аналитика пользователя'
        verbose_name_plural = 'Аналитика пользователей'
        unique_together = ['profile', 'date']
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['profile', 'date']),
            models.Index(fields=['-date']),  # для быстрой сортировки по убыванию
        ]
    
    def __str__(self):
        return f"Analytics for {self.profile.telegram_id} on {self.date}"


class AIServiceMetrics(models.Model):
    """Метрики работы AI сервисов"""
    
    SERVICE_CHOICES = (
        ('openai', 'OpenAI'),
        ('google', 'Google Gemini'),
        ('deepseek', 'DeepSeek'),
        ('qwen', 'Qwen'),
    )
    
    service = models.CharField(max_length=50, choices=SERVICE_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Производительность
    response_time = models.FloatField()  # в секундах
    tokens_used = models.IntegerField(null=True, blank=True)  # для OpenAI
    characters_processed = models.IntegerField(null=True, blank=True)  # для Google/Yandex
    
    # Результат
    success = models.BooleanField(default=True)
    error_type = models.CharField(max_length=100, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    
    # Контекст
    user_id = models.BigIntegerField(null=True)  # telegram_id пользователя
    operation_type = models.CharField(max_length=50)  # 'categorization', 'voice_recognition', etc.
    model_used = models.CharField(max_length=100, null=True, blank=True)  # название модели
    
    # Стоимость (в условных единицах, можно конвертировать в валюту)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    
    class Meta:
        db_table = 'ai_service_metrics'
        verbose_name = 'Метрика AI сервиса'
        verbose_name_plural = 'Метрики AI сервисов'
        indexes = [
            models.Index(fields=['service', 'timestamp']),
            models.Index(fields=['success']),
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user_id', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.service} - {self.timestamp} - {'✓' if self.success else '✗'}"


class SystemHealthCheck(models.Model):
    """История проверок здоровья системы"""
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Статус компонентов
    database_status = models.BooleanField(default=True)
    database_response_time = models.FloatField(null=True)  # в секундах
    
    redis_status = models.BooleanField(default=True)
    redis_response_time = models.FloatField(null=True)
    redis_memory_usage = models.BigIntegerField(null=True)  # в байтах
    
    telegram_api_status = models.BooleanField(default=True)
    telegram_api_response_time = models.FloatField(null=True)

    openai_api_status = models.BooleanField(default=True)
    openai_api_response_time = models.FloatField(null=True)
    
    google_ai_api_status = models.BooleanField(default=True)
    google_ai_api_response_time = models.FloatField(null=True)

    deepseek_api_status = models.BooleanField(default=True)
    deepseek_api_response_time = models.FloatField(null=True)

    qwen_api_status = models.BooleanField(default=True)
    qwen_api_response_time = models.FloatField(null=True)
    
    celery_status = models.BooleanField(default=True)
    celery_workers_count = models.IntegerField(null=True)
    celery_queue_size = models.IntegerField(null=True)
    
    # Системные метрики
    disk_free_gb = models.FloatField(null=True)
    memory_usage_percent = models.FloatField(null=True)
    cpu_usage_percent = models.FloatField(null=True)
    
    # Общий статус
    overall_status = models.CharField(max_length=20, default='healthy')  # healthy, degraded, unhealthy
    issues = models.JSONField(default=list)  # список проблем если есть
    
    class Meta:
        db_table = 'system_health_checks'
        verbose_name = 'Проверка здоровья системы'
        verbose_name_plural = 'Проверки здоровья системы'
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['overall_status']),
        ]
    
    def __str__(self):
        return f"Health Check - {self.timestamp} - {self.overall_status}"


DEFAULT_INCOME_CATEGORIES = [
    ('Зарплата', '💼'),
    ('Премии и бонусы', '🎁'),
    ('Фриланс', '💻'),
    ('Инвестиции', '📈'),
    ('Проценты по вкладам', '🏦'),
    ('Аренда недвижимости', '🏠'),
    ('Возвраты и компенсации', '💸'),
    ('Подарки', '🎉'),
    ('Прочие доходы', '💰')
]


# ============================================
# МОДЕЛИ ДЛЯ РЕФЕРАЛЬНОЙ ПРОГРАММЫ TELEGRAM STARS
# ============================================

class AffiliateProgram(models.Model):
    """Настройки реферальной программы Telegram Stars"""
    commission_permille = models.IntegerField(
        verbose_name='Комиссия в промилле',
        help_text='100 = 10%, 200 = 20%, максимум определяется Telegram'
    )
    duration_months = models.IntegerField(
        null=True, 
        blank=True,
        verbose_name='Срок действия (месяцы)',
        help_text='Оставьте пустым для бессрочной программы'
    )
    start_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата запуска'
    )
    end_date = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name='Дата окончания',
        help_text='Автоматически рассчитывается из duration_months'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активна'
    )
    telegram_program_id = models.CharField(
        max_length=255, 
        unique=True, 
        null=True, 
        blank=True,
        verbose_name='ID программы в Telegram'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'affiliate_program'
        verbose_name = 'Реферальная программа'
        verbose_name_plural = 'Реферальные программы'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Affiliate Program ({int(self.commission_permille/10)}%)"
    
    def get_commission_percent(self):
        """Получить комиссию в процентах"""
        return int(self.commission_permille / 10)
    
    def calculate_commission(self, amount):
        """Рассчитать комиссию от суммы"""
        return int(amount * self.commission_permille / 1000)


class AffiliateLink(models.Model):
    """Реферальные ссылки пользователей для Telegram Stars"""
    profile = models.OneToOneField(
        Profile, 
        on_delete=models.CASCADE,
        related_name='affiliate_link',
        verbose_name='Профиль'
    )
    affiliate_code = models.CharField(
        max_length=100, 
        unique=True, 
        db_index=True,
        verbose_name='Реферальный код'
    )
    telegram_link = models.URLField(
        verbose_name='Ссылка Telegram',
        help_text='Полная реферальная ссылка t.me/bot?start=ref_CODE'
    )
    
    # Статистика
    clicks = models.IntegerField(
        default=0,
        verbose_name='Количество переходов'
    )
    conversions = models.IntegerField(
        default=0,
        verbose_name='Количество конверсий'
    )
    total_earned = models.IntegerField(
        default=0,
        verbose_name='Всего заработано звёзд'
    )
    
    # Статус
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активна'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'affiliate_links'
        verbose_name = 'Реферальная ссылка'
        verbose_name_plural = 'Реферальные ссылки'
    
    def __str__(self):
        return f"{self.profile} - {self.affiliate_code}"
    
    def get_conversion_rate(self):
        """Получить конверсию в процентах"""
        if self.clicks == 0:
            return 0
        return round((self.conversions / self.clicks) * 100, 2)


class AffiliateReferral(models.Model):
    """Связь между рефереров и приглашённым пользователем"""
    referrer = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='referred_users',
        verbose_name='Реферер'
    )
    referred = models.OneToOneField(
        Profile,
        on_delete=models.CASCADE,
        related_name='referred_by',
        verbose_name='Приглашённый пользователь'
    )
    affiliate_link = models.ForeignKey(
        AffiliateLink,
        on_delete=models.CASCADE,
        related_name='referrals',
        verbose_name='Реферальная ссылка'
    )
    
    # Дополнительная информация
    joined_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата регистрации'
    )
    first_payment_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата первого платежа'
    )
    total_payments = models.IntegerField(
        default=0,
        verbose_name='Всего платежей'
    )
    total_spent = models.IntegerField(
        default=0,
        verbose_name='Всего потрачено звёзд'
    )

    reward_granted = models.BooleanField(
        default=False,
        verbose_name='Бонус выдан'
    )
    reward_granted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата выдачи бонуса'
    )
    reward_subscription = models.ForeignKey(
        'Subscription',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referral_rewards',
        verbose_name='Подписка-бонус'
    )
    reward_months = models.IntegerField(
        default=0,
        verbose_name='Количество месяцев в бонусе'
    )

    class Meta:
        db_table = 'affiliate_referrals'
        verbose_name = 'Реферальная связь'
        verbose_name_plural = 'Реферальные связи'
        unique_together = ['referred']  # Один пользователь может быть приглашён только одним рефеорером
    
    def __str__(self):
        return f"{self.referrer} → {self.referred}"


class AffiliateCommission(models.Model):
    """История начислений комиссий по реферальной программе"""
    COMMISSION_STATUS = [
        ('pending', 'Ожидает'),
        ('hold', 'На холде'),  # 21-дневный холд Telegram
        ('paid', 'Выплачено'),
        ('cancelled', 'Отменено'),
        ('refunded', 'Возвращено')
    ]
    
    referrer = models.ForeignKey(
        Profile, 
        on_delete=models.CASCADE, 
        related_name='commissions_earned',
        verbose_name='Реферер'
    )
    referred = models.ForeignKey(
        Profile, 
        on_delete=models.CASCADE, 
        related_name='commissions_generated',
        verbose_name='Приглашённый'
    )
    subscription = models.ForeignKey(
        Subscription, 
        on_delete=models.CASCADE,
        related_name='affiliate_commissions',
        verbose_name='Подписка'
    )
    referral = models.ForeignKey(
        AffiliateReferral,
        on_delete=models.CASCADE,
        related_name='commissions',
        verbose_name='Реферальная связь'
    )
    
    # Финансовая информация
    payment_amount = models.IntegerField(
        verbose_name='Сумма платежа (звёзды)'
    )
    commission_amount = models.IntegerField(
        verbose_name='Сумма комиссии (звёзды)'
    )
    commission_rate = models.IntegerField(
        verbose_name='Ставка комиссии (промилле)'
    )
    
    # Telegram данные
    telegram_transaction_id = models.CharField(
        max_length=255, 
        unique=True, 
        null=True,
        blank=True,
        verbose_name='ID транзакции Telegram'
    )
    telegram_payment_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='ID платежа в Telegram'
    )
    
    # Статус
    status = models.CharField(
        max_length=20, 
        choices=COMMISSION_STATUS,
        default='pending',
        verbose_name='Статус'
    )
    
    # Даты
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    hold_until = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Холд до',
        help_text='21 день с момента платежа'
    )
    paid_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name='Дата выплаты'
    )
    
    # Дополнительная информация
    notes = models.TextField(
        blank=True,
        verbose_name='Примечания'
    )
    
    class Meta:
        db_table = 'affiliate_commissions'
        verbose_name = 'Комиссия реферера'
        verbose_name_plural = 'Комиссии рефереров'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['referrer', 'status']),
            models.Index(fields=['telegram_transaction_id']),
            models.Index(fields=['telegram_payment_id']),  # Индекс для быстрого поиска по платежу
            models.Index(fields=['created_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['telegram_payment_id'], 
                name='unique_telegram_payment_id',
                condition=models.Q(telegram_payment_id__isnull=False)
            )
        ]
    
    def __str__(self):
        return f"{self.referrer} - {self.commission_amount} stars ({self.get_status_display()})"
    
    def get_commission_percent(self):
        """Получить процент комиссии"""
        return int(self.commission_rate / 10)  # промилле в проценты
    
    def calculate_hold_date(self):
        """Рассчитать дату окончания холда (21 день)"""
        from datetime import timedelta
        return self.created_at + timedelta(days=21)
from .models_campaigns import AdvertiserCampaign


class MonthlyInsight(models.Model):
    """AI-generated monthly insights about user's expenses"""
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='monthly_insights',
        verbose_name='Профиль'
    )

    # Period information
    year = models.IntegerField(
        verbose_name='Год',
        db_index=True
    )
    month = models.IntegerField(
        verbose_name='Месяц',
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        db_index=True
    )

    # Financial data for the period
    total_expenses = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Всего расходов'
    )
    total_incomes = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        verbose_name='Всего доходов'
    )
    expenses_count = models.IntegerField(
        default=0,
        verbose_name='Количество трат'
    )

    # Top categories data (JSON structure)
    top_categories = models.JSONField(
        default=list,
        verbose_name='Топ категорий',
        help_text='[{"category": "name", "amount": 1000, "percentage": 25}]'
    )

    # AI-generated insights
    ai_summary = models.TextField(
        verbose_name='AI резюме месяца',
        help_text='Краткое резюме трат за месяц от AI'
    )
    ai_analysis = models.TextField(
        verbose_name='AI анализ',
        help_text='Детальный анализ трат и паттернов'
    )
    ai_recommendations = models.TextField(
        verbose_name='AI рекомендации',
        help_text='Рекомендации по оптимизации бюджета'
    )

    # AI service info
    ai_model_used = models.CharField(
        max_length=100,
        verbose_name='Использованная AI модель'
    )
    ai_provider = models.CharField(
        max_length=50,
        choices=[
            ('openai', 'OpenAI'),
            ('google', 'Google AI'),
            ('deepseek', 'DeepSeek'),
            ('qwen', 'Qwen'),
        ],
        verbose_name='AI �஢�����'
    )

    # Generation metadata
    generated_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата генерации'
    )
    regeneration_count = models.IntegerField(
        default=0,
        verbose_name='Количество регенераций'
    )
    last_regenerated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Последняя регенерация'
    )

    # User interaction
    is_viewed = models.BooleanField(
        default=False,
        verbose_name='Просмотрено'
    )
    viewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата просмотра'
    )
    user_rating = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='Оценка пользователя'
    )

    class Meta:
        db_table = 'monthly_insights'
        verbose_name = 'Месячный инсайт'
        verbose_name_plural = 'Месячные инсайты'
        unique_together = ['profile', 'year', 'month']
        ordering = ['-year', '-month']
        indexes = [
            models.Index(fields=['profile', '-year', '-month']),
            models.Index(fields=['generated_at']),
        ]

    def __str__(self):
        return f"{self.profile} - {self.month:02d}.{self.year}"

    @property
    def period_display(self):
        """Display period in human-readable format"""
        months_ru = {
            1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
            5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
            9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
        }
        return f"{months_ru.get(self.month, self.month)} {self.year}"

    @property
    def balance(self):
        """Calculate balance for the period"""
        return self.total_incomes - self.total_expenses
