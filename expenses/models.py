"""
Модели ExpenseBot согласно техническому заданию
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import date, datetime
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
    
    # Реферальная программа
    referrer = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referrals',
        verbose_name='Реферер',
        help_text='Кто привел этого пользователя'
    )
    referral_code = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Реферальный код',
        help_text='Уникальный реферальный код пользователя'
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
    
    def generate_referral_code(self):
        """Генерация уникального реферального кода"""
        if not self.referral_code:
            while True:
                code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                if not Profile.objects.filter(referral_code=code).exists():
                    self.referral_code = code
                    self.save()
                    break
        return self.referral_code
    
    @property
    def referrals_count(self):
        """Количество приглашенных пользователей"""
        return self.referrals.count()
    
    @property
    def active_referrals_count(self):
        """Количество активных рефералов с подпиской"""
        return self.referrals.filter(
            subscriptions__is_active=True,
            subscriptions__end_date__gt=timezone.now()
        ).distinct().count()


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


class CategoryKeyword(models.Model):
    """Ключевые слова для автоматического определения категорий"""
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE, related_name='keywords')
    keyword = models.CharField(max_length=100, db_index=True)
    
    # Счетчик использования (только ручные исправления)
    usage_count = models.IntegerField(default=0, verbose_name='Количество использований')
    
    # Нормализованный вес для конфликтующих слов
    normalized_weight = models.FloatField(default=1.0, verbose_name='Нормализованный вес')
    
    # Временная метка создания
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'expenses_category_keyword'
        verbose_name = 'Ключевое слово категории'
        verbose_name_plural = 'Ключевые слова категорий'
        unique_together = ['category', 'keyword']
        indexes = [
            models.Index(fields=['category', 'keyword']),
            models.Index(fields=['normalized_weight']),
        ]
    
    def __str__(self):
        return f"{self.keyword} -> {self.category.name} (вес: {self.normalized_weight:.2f})"


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


class RecurringPayment(models.Model):
    """Регулярные платежи пользователя"""
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='recurring_payments')
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE)
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
        verbose_name = 'Регулярный платеж'
        verbose_name_plural = 'Регулярные платежи'
        indexes = [
            models.Index(fields=['profile', 'is_active']),
            models.Index(fields=['day_of_month', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.description} - {self.amount} {self.currency} ({self.day_of_month} числа)"


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
        return f"{self.bank_name} - {self.category.name} - {self.cashback_percent}%"


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
            return base_price * (1 - self.discount_value / 100)
        elif self.discount_type == 'fixed':
            return max(0, base_price - self.discount_value)
        return base_price


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


class ReferralBonus(models.Model):
    """Реферальные бонусы"""
    referrer = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='referral_bonuses_given',
        verbose_name='Реферер'
    )
    referred = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='referral_bonuses_received',
        verbose_name='Приглашенный'
    )
    bonus_days = models.IntegerField(
        default=30,
        verbose_name='Бонусные дни'
    )
    subscription = models.ForeignKey(
        'Subscription',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Подписка',
        help_text='Подписка, за которую начислен бонус'
    )
    is_activated = models.BooleanField(
        default=False,
        verbose_name='Активирован'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'referral_bonuses'
        verbose_name = 'Реферальный бонус'
        verbose_name_plural = 'Реферальные бонусы'
    
    def __str__(self):
        return f"{self.referrer} -> {self.referred} ({self.bonus_days} дней)"


DEFAULT_CATEGORIES = [
    ('Продукты', '🛒'),
    ('Кафе и рестораны', '🍽️'),
    ('АЗС', '⛽'),
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
    ('Коммунальные услуги и подписки', '📱'),
    ('Прочие расходы', '💰')
]

CATEGORY_KEYWORDS = {
    'Продукты': [
        'магнит', 'пятерочка', 'перекресток', 'ашан', 'лента', 'дикси', 'вкусвилл',
        'metro', 'окей', 'азбука вкуса', 'продукты', 'супермаркет', 'гипермаркет',
        'овощи', 'фрукты', 'мясо', 'рыба', 'молоко', 'хлеб', 'grocery', 'market',
        'продуктовый', 'бакалея', 'сыр', 'колбаса', 'круглосуточный', '24 часа'
    ],
    'Кафе и рестораны': [
        'ресторан', 'кафе', 'бар', 'паб', 'кофейня', 'пиццерия', 'суши', 'фастфуд',
        'mcdonalds', 'kfc', 'burger king', 'subway', 'starbucks', 'coffee', 'обед',
        'ужин', 'завтрак', 'ланч', 'доставка еды', 'delivery club', 'яндекс еда',
        'шоколадница', 'теремок', 'крошка картошка', 'додо пицца', 'папа джонс',
        'кофе', 'капучино', 'латте', 'американо', 'эспрессо', 'чай', 'пицца', 
        'бургер', 'роллы', 'паста', 'салат', 'десерт', 'мороженое', 'торт'
    ],
    'АЗС': [
        'азс', 'заправка', 'бензин', 'топливо', 'газпром', 'лукойл', 'роснефть',
        'shell', 'bp', 'esso', 'татнефть', 'газпромнефть', 'дизель', 'газ', 'гсм',
        '92', '95', '98', 'аи-92', 'аи-95', 'аи-98', 'дт', 'автозаправка'
    ],
    'Транспорт': [
        'такси', 'uber', 'яндекс такси', 'ситимобил', 'gett', 'wheely', 'метро',
        'автобус', 'троллейбус', 'трамвай', 'маршрутка', 'электричка', 'проезд',
        'транспорт', 'тройка', 'единый', 'билет', 'подорожник', 'проездной'
    ],
    'Автомобиль': [
        'автомобиль', 'машина', 'авто', 'сто', 'автосервис', 'шиномонтаж', 'мойка',
        'парковка', 'штраф', 'гибдд', 'осаго', 'каско', 'техосмотр', 'ремонт',
        'запчасти', 'масло', 'антифриз', 'стеклоомыватель', 'автозапчасти'
    ],
    'Жилье': [
        'квартира', 'аренда', 'ипотека', 'жкх', 'коммуналка', 'квартплата',
        'управляющая компания', 'тсж', 'жск', 'капремонт', 'домофон', 'консьерж',
        'охрана', 'уборка', 'ремонт квартиры', 'сантехник', 'электрик'
    ],
    'Аптеки': [
        'аптека', 'ригла', 'асна', '36.6', 'горздрав', 'столички', 'фармация',
        'лекарства', 'медикаменты', 'таблетки', 'витамины', 'бад', 'pharmacy',
        'аптечный', 'рецепт', 'препарат', 'лекарственный', 'здравсити'
    ],
    'Медицина': [
        'клиника', 'больница', 'поликлиника', 'врач', 'доктор', 'медцентр',
        'стоматология', 'зубной', 'анализы', 'узи', 'мрт', 'кт', 'рентген',
        'осмотр', 'консультация', 'лечение', 'операция', 'медицинский', 'терапевт'
    ],
    'Красота': [
        'салон', 'парикмахерская', 'барбершоп', 'маникюр', 'педикюр', 'косметолог',
        'спа', 'spa', 'массаж', 'солярий', 'эпиляция', 'депиляция', 'стрижка',
        'окрашивание', 'укладка', 'косметика', 'beauty', 'красота', 'уход'
    ],
    'Спорт и фитнес': [
        'фитнес', 'спортзал', 'тренажерный', 'бассейн', 'йога', 'пилатес', 'танцы',
        'спорт', 'тренировка', 'абонемент', 'world class', 'fitness', 'x-fit',
        'спортмастер', 'декатлон', 'спортивный', 'тренер', 'секция', 'фитнес клуб'
    ],
    'Одежда и обувь': [
        'одежда', 'обувь', 'zara', 'h&m', 'uniqlo', 'mango', 'bershka', 'магазин одежды',
        'бутик', 'джинсы', 'платье', 'костюм', 'кроссовки', 'туфли', 'сапоги',
        'куртка', 'пальто', 'рубашка', 'юбка', 'брюки', 'белье', 'носки'
    ],
    'Развлечения': [
        'кино', 'театр', 'концерт', 'музей', 'выставка', 'клуб', 'караоке', 'боулинг',
        'бильярд', 'квест', 'развлечения', 'отдых', 'досуг', 'парк', 'аттракционы',
        'цирк', 'зоопарк', 'аквапарк', 'кинотеатр', 'синема', 'imax', 'билет'
    ],
    'Образование': [
        'курсы', 'обучение', 'школа', 'университет', 'институт', 'колледж', 'учеба',
        'образование', 'тренинг', 'семинар', 'вебинар', 'репетитор', 'учебник',
        'книги', 'канцелярия', 'тетради', 'ручки', 'учебный', 'экзамен', 'диплом'
    ],
    'Подарки': [
        'подарок', 'сувенир', 'цветы', 'букет', 'открытка', 'подарочный', 'презент',
        'поздравление', 'праздник', 'день рождения', 'юбилей', 'свадьба', 'gift',
        'флорист', 'цветочный', 'упаковка', 'лента', 'шары', 'декор'
    ],
    'Путешествия': [
        'авиабилет', 'билет', 'самолет', 'поезд', 'ржд', 'аэрофлот', 'победа',
        's7', 'utair', 'отель', 'гостиница', 'хостел', 'booking', 'airbnb',
        'путешествие', 'отпуск', 'туризм', 'экскурсия', 'гид', 'виза', 'паспорт'
    ],
    'Коммунальные услуги и подписки': [
        'интернет', 'мобильная связь', 'телефон', 'мтс', 'билайн', 'мегафон', 'теле2',
        'ростелеком', 'электричество', 'газ', 'вода', 'отопление', 'netflix', 'spotify',
        'youtube', 'подписка', 'apple', 'google', 'яндекс плюс', 'кинопоиск', 'иви',
        'окко', 'амедиатека', 'xbox', 'playstation', 'steam', 'коммунальные'
    ]
}