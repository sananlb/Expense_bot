"""
Модели ExpenseBot согласно техническому заданию
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import date, datetime
from decimal import Decimal


class Profile(models.Model):
    """Профиль пользователя согласно ТЗ"""
    telegram_id = models.BigIntegerField(unique=True, db_index=True)
    username = models.CharField(max_length=255, null=True, blank=True)
    first_name = models.CharField(max_length=255, null=True, blank=True)
    last_name = models.CharField(max_length=255, null=True, blank=True)
    
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'users_profile'
        verbose_name = 'Профиль'
        verbose_name_plural = 'Профили'
        indexes = [
            models.Index(fields=['telegram_id']),
        ]
    
    def __str__(self):
        return f"{self.first_name} (@{self.username or 'no_username'})"


class UserSettings(models.Model):
    """Настройки пользователя согласно ТЗ"""
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name='settings')
    
    # Уведомления
    daily_reminder_enabled = models.BooleanField(default=True)
    daily_reminder_time = models.TimeField(default='20:00')
    weekly_summary_enabled = models.BooleanField(default=True)
    monthly_summary_enabled = models.BooleanField(default=True)
    budget_alerts_enabled = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'users_settings'
        verbose_name = 'Настройки'
        verbose_name_plural = 'Настройки'


class ExpenseCategory(models.Model):
    """Категории трат согласно ТЗ"""
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
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
        ]
        
    def __str__(self):
        return f"{self.icon} {self.name}"


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


class Cashback(models.Model):
    """Информация о кешбэках по категориям согласно ТЗ"""
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='cashbacks')
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE)
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
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'expenses_cashback'
        verbose_name = 'Кешбэк'
        verbose_name_plural = 'Кешбэки'
        unique_together = ['profile', 'category', 'bank_name', 'month']
        indexes = [
            models.Index(fields=['profile', 'month']),
            models.Index(fields=['profile', 'category']),
        ]
    
    def __str__(self):
        return f"{self.bank_name} - {self.category.name} - {self.cashback_percent}%"


# Базовые категории для новых пользователей
DEFAULT_CATEGORIES = [
    ('Супермаркеты', '🛒'),
    ('Другие продукты', '🫑'),
    ('Рестораны и кафе', '🍽️'),
    ('АЗС', '⛽'),
    ('Такси', '🚕'),
    ('Общественный транспорт', '🚌'),
    ('Автомобиль', '🚗'),
    ('Жилье', '🏠'),
    ('Аптеки', '💊'),
    ('Медицина', '🏥'),
    ('Спорт', '🏃'),
    ('Спортивные товары', '🏀'),
    ('Одежда и обувь', '👔'),
    ('Цветы', '🌹'),
    ('Развлечения', '🎭'),
    ('Образование', '📚'),
    ('Подарки', '🎁'),
    ('Путешествия', '✈️'),
    ('Связь и интернет', '📱'),
    ('Прочие расходы', '💰')
]