"""
Админ панель для ExpenseBot согласно ТЗ
"""
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Count
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Profile, UserSettings, ExpenseCategory, Expense, Budget,
    Cashback, RecurringPayment, Subscription, PromoCode,
    PromoCodeUsage, Income, IncomeCategory,
    AffiliateProgram, AffiliateLink, AffiliateReferral, AffiliateCommission
)
from dateutil.relativedelta import relativedelta
from bot.utils.category_helpers import get_category_display_name


class SubscriptionInline(admin.TabularInline):
    """Inline редактор подписок в профиле"""
    model = Subscription
    extra = 0  # НЕ показывать пустые формы для новых подписок
    fields = ['type', 'payment_method', 'start_date', 'end_date', 'is_active', 'days_left']
    readonly_fields = ['days_left', 'type', 'payment_method', 'start_date']  # Делаем большинство полей readonly
    ordering = ['-end_date']
    can_delete = False  # Запрещаем удаление подписок через inline
    
    def days_left(self, obj):
        """Осталось дней"""
        from django.utils import timezone
        if obj and obj.end_date:
            if obj.is_active and obj.end_date > timezone.now():
                days = (obj.end_date - timezone.now()).days
                return f"{days} дней"
            return "Истекла"
        return "-"
    
    days_left.short_description = 'Осталось'
    
    def has_delete_permission(self, request, obj=None):
        return True
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        # Устанавливаем значения по умолчанию для новых подписок
        if obj:
            from django.utils import timezone
            formset.form.base_fields['end_date'].initial = timezone.now() + relativedelta(months=1)
            formset.form.base_fields['is_active'].initial = True
        return formset


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['telegram_id', 'subscription_status', 
                    'is_beta_tester', 'referrals_count_display', 'language_code', 
                    'currency', 'is_active', 'created_at']
    list_filter = ['is_active', 'is_beta_tester', 'language_code', 'currency', 'created_at']
    search_fields = ['telegram_id', 'beta_access_key']
    readonly_fields = ['created_at', 'updated_at',
                       'referrals_count', 'active_referrals_count']
    inlines = [SubscriptionInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('telegram_id',)
        }),
        ('Настройки', {
            'fields': ('language_code', 'timezone', 'currency')
        }),
        ('Бета-тестирование', {
            'fields': ('is_beta_tester', 'beta_access_key'),
            'classes': ('collapse',)
        }),
        ('Реферальная программа', {
            'fields': ('referrals_count', 'active_referrals_count'),
            'classes': ('collapse',)
        }),
        ('Статус', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            total_expenses=Sum('expenses__amount'),
            expenses_count=Count('expenses'),
            _referrals_count=Count('referred_users')
        )
    
    def subscription_status(self, obj):
        """Статус подписки (суммарно по всем активным)"""
        from django.utils import timezone
        from django.db.models import Max
        
        # Получаем все активные подписки
        active_subs = obj.subscriptions.filter(
            is_active=True,
            end_date__gt=timezone.now()
        )
        
        if active_subs.exists():
            # Берем максимальную дату окончания среди всех активных подписок
            max_end_date = active_subs.aggregate(Max('end_date'))['end_date__max']
            total_days = (max_end_date - timezone.now()).days
            
            # Считаем количество активных подписок
            sub_count = active_subs.count()
            
            # Определяем цвет
            if total_days > 30:
                color = 'green'
            elif total_days > 7:
                color = 'orange'
            else:
                color = 'red'
            
            # Если несколько подписок, показываем их количество
            if sub_count > 1:
                return format_html(
                    '<span style="color: {};">✅ {} дней ({} подп.)</span>',
                    color, total_days, sub_count
                )
            else:
                # Определяем тип подписки для единственной
                sub_type = active_subs.first().type
                type_label = {'trial': 'проб.', 'month': 'мес.', 'six_months': '6 мес.'}.get(sub_type, '')
                return format_html(
                    '<span style="color: {};">✅ {} дней {}</span>',
                    color, total_days, f'({type_label})' if type_label else ''
                )
        return format_html('<span style="color: red;">❌ Нет</span>')
    
    subscription_status.short_description = 'Подписка'
    
    def referrals_count_display(self, obj):
        """Количество рефералов"""
        total = getattr(obj, '_referrals_count', 0)
        active = obj.active_referrals_count
        
        if total > 0:
            return format_html('{} ({} акт.)', total, active)
        return '0'
    
    referrals_count_display.short_description = 'Рефералы'
    
    actions = ['make_beta_tester', 'remove_beta_tester',
               'add_month_subscription', 'add_six_months_subscription']
    
    def make_beta_tester(self, request, queryset):
        """Сделать бета-тестерами"""
        updated = queryset.update(is_beta_tester=True)
        self.message_user(request, f'{updated} пользователей стали бета-тестерами.')
    
    make_beta_tester.short_description = 'Сделать бета-тестерами'
    
    def remove_beta_tester(self, request, queryset):
        """Убрать из бета-тестеров"""
        updated = queryset.update(is_beta_tester=False)
        self.message_user(request, f'{updated} пользователей удалены из бета-тестеров.')
    
    remove_beta_tester.short_description = 'Убрать из бета-тестеров'
    
    # generate_referral_codes удален - используется новая система Telegram Stars
    # Реферальные ссылки создаются автоматически при первом обращении
    
    def add_month_subscription(self, request, queryset):
        """Добавить месячную подписку"""
        from django.utils import timezone
        count = 0
        for profile in queryset:
            # Ищем активную подписку
            active_sub = profile.subscriptions.filter(
                is_active=True,
                end_date__gt=timezone.now()
            ).order_by('-end_date').first()
            
            if active_sub:
                # Продлеваем существующую подписку
                active_sub.end_date = active_sub.end_date + relativedelta(months=1)
                active_sub.save()
            else:
                # Создаем новую подписку только если нет активной
                Subscription.objects.create(
                    profile=profile,
                    type='month',
                    payment_method='stars',
                    amount=0,  # Бесплатно через админку
                    start_date=timezone.now(),
                    end_date=timezone.now() + relativedelta(months=1),
                    is_active=True
                )
            count += 1
        
        self.message_user(request, f'Продлено {count} месячных подписок.')
    
    add_month_subscription.short_description = 'Добавить месячную подписку'
    
    def add_six_months_subscription(self, request, queryset):
        """Добавить полугодовую подписку"""
        from django.utils import timezone
        count = 0
        for profile in queryset:
            # Ищем активную подписку
            active_sub = profile.subscriptions.filter(
                is_active=True,
                end_date__gt=timezone.now()
            ).order_by('-end_date').first()
            
            if active_sub:
                # Продлеваем существующую подписку
                active_sub.end_date = active_sub.end_date + relativedelta(months=6)
                active_sub.save()
            else:
                # Создаем новую подписку только если нет активной
                Subscription.objects.create(
                    profile=profile,
                    type='six_months',
                    payment_method='stars',
                    amount=0,  # Бесплатно через админку
                    start_date=timezone.now(),
                    end_date=timezone.now() + relativedelta(months=6),
                    is_active=True
                )
            count += 1
        
        self.message_user(request, f'Продлено {count} полугодовых подписок.')
    
    add_six_months_subscription.short_description = 'Добавить полугодовую подписку'


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ['profile', 'budget_alerts_enabled']
    list_filter = ['budget_alerts_enabled']
    search_fields = ['profile__telegram_id']
    
    fieldsets = (
        ('Профиль', {
            'fields': ('profile',)
        }),
        ('Уведомления', {
            'fields': ('budget_alerts_enabled',)
        }),
        ('Системные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ['display_category', 'profile', 'name', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'profile__username']
    list_per_page = 50
    
    def display_category(self, obj):
        # Используем язык администратора для отображения
        return get_category_display_name(obj, 'ru')  # Админка всегда на русском
    display_category.short_description = 'Категория'
    
    fieldsets = (
        (None, {
            'fields': ('profile', 'name', 'icon', 'is_active')
        }),
        ('Системные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['profile', 'amount', 'display_category', 'expense_date', 
                    'ai_categorized', 'created_at']
    list_filter = ['expense_date', 'ai_categorized', 'category', 'created_at']
    search_fields = ['description', 'profile__username', 'category__name']
    date_hierarchy = 'expense_date'
    list_per_page = 100
    
    def display_category(self, obj):
        if obj.category:
            # Используем язык администратора для отображения
            return get_category_display_name(obj.category, 'ru')  # Админка всегда на русском
        return "—"
    display_category.short_description = 'Категория'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('profile', 'amount', 'category', 'description')
        }),
        ('Дата и время', {
            'fields': ('expense_date', 'expense_time')
        }),
        ('AI обработка', {
            'fields': ('ai_categorized', 'ai_confidence'),
            'classes': ('collapse',)
        }),
        ('Дополнительно', {
            'fields': ('receipt_photo',),
            'classes': ('collapse',)
        }),
        ('Системные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('profile', 'category')


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['profile', 'category', 'amount', 'period_type', 'start_date', 
                    'end_date', 'is_active']
    list_filter = ['period_type', 'is_active', 'start_date']
    search_fields = ['profile__username', 'category__name']
    date_hierarchy = 'start_date'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('profile', 'category', 'amount', 'period_type')
        }),
        ('Период', {
            'fields': ('start_date', 'end_date')
        }),
        ('Статус', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
    )
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Cashback)
class CashbackAdmin(admin.ModelAdmin):
    list_display = ['profile', 'display_category', 'bank_name', 'cashback_percent', 
                    'month', 'limit_amount', 'created_at']
    list_filter = ['bank_name', 'month', 'created_at']
    search_fields = ['profile__username', 'category__name', 'bank_name']
    list_per_page = 50
    
    def display_category(self, obj):
        # Используем язык администратора для отображения
        return get_category_display_name(obj.category, 'ru')  # Админка всегда на русском
    display_category.short_description = 'Категория'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('profile', 'category', 'bank_name')
        }),
        ('Кешбэк', {
            'fields': ('cashback_percent', 'month', 'limit_amount')
        }),
        ('Системные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('profile', 'category')


@admin.register(RecurringPayment)
class RecurringPaymentAdmin(admin.ModelAdmin):
    list_display = ['description', 'profile_link', 'category', 'amount',
                    'currency', 'day_of_month', 'is_active', 'last_processed']
    list_filter = ['is_active', 'currency', 'day_of_month', 'created_at']
    search_fields = ['description', 'profile__username', 'profile__telegram_id',
                     'category__name']
    
    def profile_link(self, obj):
        """Ссылка на профиль"""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:expenses_profile_change', args=[obj.profile.id]),
            obj.profile
        )
    
    profile_link.short_description = 'Профиль'


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['profile_link', 'type', 'payment_method', 'amount',
                    'start_date', 'end_date', 'is_active', 'days_left']
    list_filter = ['type', 'payment_method', 'is_active', 'notification_sent',
                   'created_at']
    search_fields = ['profile__telegram_id', 'profile__username',
                     'telegram_payment_charge_id']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'end_date'
    
    def profile_link(self, obj):
        """Ссылка на профиль"""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:expenses_profile_change', args=[obj.profile.id]),
            obj.profile
        )
    
    profile_link.short_description = 'Профиль'
    
    def days_left(self, obj):
        """Осталось дней"""
        from django.utils import timezone
        if obj.is_active and obj.end_date > timezone.now():
            days = (obj.end_date - timezone.now()).days
            color = 'green' if days > 7 else 'orange' if days > 0 else 'red'
            return format_html(
                '<span style="color: {};">{} дней</span>',
                color, days
            )
        return format_html('<span style="color: gray;">Истекла</span>')
    
    days_left.short_description = 'Осталось'
    
    actions = ['extend_30_days', 'send_expiry_notifications']
    
    def extend_30_days(self, request, queryset):
        """Продлить на 30 дней"""
        from dateutil.relativedelta import relativedelta
        count = 0
        for sub in queryset:
            sub.end_date = sub.end_date + relativedelta(months=1)
            sub.save()
            count += 1
        self.message_user(request, f'Продлено {count} подписок на 30 дней.')
    
    extend_30_days.short_description = 'Продлить на 30 дней'


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'get_discount_display', 'applicable_subscription_types',
                    'is_active', 'used_count', 'max_uses', 'valid_until', 'created_by']
    list_filter = ['is_active', 'discount_type', 'applicable_subscription_types',
                   'created_at', 'valid_until']
    search_fields = ['code', 'description']
    readonly_fields = ['used_count', 'created_at', 'updated_at']

    fieldsets = (
        ('Основная информация', {
            'fields': ('code', 'description', 'is_active')
        }),
        ('Скидка', {
            'fields': ('discount_type', 'discount_value', 'applicable_subscription_types')
        }),
        ('Ограничения', {
            'fields': ('max_uses', 'used_count', 'valid_from', 'valid_until')
        }),
        ('Метаданные', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['activate_codes', 'deactivate_codes']
    
    def activate_codes(self, request, queryset):
        """Активировать промокоды"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} промокодов активировано.')
    
    activate_codes.short_description = 'Активировать'
    
    def deactivate_codes(self, request, queryset):
        """Деактивировать промокоды"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} промокодов деактивировано.')
    
    deactivate_codes.short_description = 'Деактивировать'


@admin.register(PromoCodeUsage)
class PromoCodeUsageAdmin(admin.ModelAdmin):
    list_display = ['promocode', 'profile', 'subscription', 'used_at']
    list_filter = ['used_at', 'promocode']
    search_fields = ['promocode__code', 'profile__username',
                     'profile__telegram_id']
    readonly_fields = ['promocode', 'profile', 'subscription', 'used_at']
    
    def has_add_permission(self, request):
        return False


# ReferralBonusAdmin удален - используется новая система Telegram Stars
# См. AffiliateProgram, AffiliateLink, AffiliateReferral, AffiliateCommission


@admin.register(IncomeCategory)
class IncomeCategoryAdmin(admin.ModelAdmin):
    list_display = ['display_category', 'profile', 'name', 'is_active', 'is_default', 'created_at']
    list_filter = ['is_active', 'is_default', 'created_at']
    search_fields = ['name', 'profile__telegram_id']
    list_per_page = 50
    
    def display_category(self, obj):
        # Используем язык администратора для отображения
        return get_category_display_name(obj, 'ru')  # Админка всегда на русском
    display_category.short_description = 'Категория дохода'
    
    fieldsets = (
        (None, {
            'fields': ('profile', 'name', 'icon', 'is_active', 'is_default')
        }),
        ('Системные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('profile')


@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ['profile', 'display_amount', 'display_category', 'income_type', 
                    'income_date', 'is_recurring', 'ai_categorized', 'created_at']
    list_filter = ['income_date', 'income_type', 'is_recurring', 'ai_categorized', 
                   'category', 'created_at']
    search_fields = ['description', 'profile__telegram_id', 'category__name']
    date_hierarchy = 'income_date'
    list_per_page = 100
    
    def display_amount(self, obj):
        return format_html('<span style="color: green; font-weight: bold;">+{} {}</span>', 
                          obj.amount, obj.currency)
    display_amount.short_description = 'Сумма'
    display_amount.admin_order_field = 'amount'
    
    def display_category(self, obj):
        if obj.category:
            # Используем язык администратора для отображения
            return get_category_display_name(obj.category, 'ru')  # Админка всегда на русском
        return "—"
    display_category.short_description = 'Категория'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('profile', 'amount', 'currency', 'category', 'description')
        }),
        ('Тип дохода', {
            'fields': ('income_type',)
        }),
        ('Дата и время', {
            'fields': ('income_date', 'income_time')
        }),
        ('Регулярность', {
            'fields': ('is_recurring', 'recurrence_day'),
            'description': 'Для регулярных доходов (например, зарплата каждый месяц)'
        }),
        ('AI обработка', {
            'fields': ('ai_categorized', 'ai_confidence'),
            'classes': ('collapse',)
        }),
        ('Системные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('profile', 'category')


# Настройка админки
admin.site.site_header = "ExpenseBot Admin"
admin.site.site_title = "ExpenseBot"
admin.site.index_title = "Панель управления"


# ==============================
# Партнёрская программа (просмотр)
# ==============================

@admin.register(AffiliateProgram)
class AffiliateProgramAdmin(admin.ModelAdmin):
    list_display = [
        'commission_percent', 'commission_permille', 'is_active',
        'duration_months', 'start_date', 'end_date', 'telegram_program_id',
        'created_at'
    ]
    list_filter = ['is_active', 'duration_months', 'start_date', 'created_at']
    search_fields = ['telegram_program_id']
    readonly_fields = ['start_date', 'end_date', 'created_at', 'updated_at', 'telegram_program_id']
    fieldsets = (
        ('Общие', {
            'fields': ('is_active', 'commission_permille', 'duration_months')
        }),
        ('Telegram', {
            'fields': ('telegram_program_id',),
            'classes': ('collapse',)
        }),
        ('Системные', {
            'fields': ('start_date', 'end_date', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def commission_percent(self, obj):
        return f"{obj.get_commission_percent()}%"
    commission_percent.short_description = 'Комиссия'


@admin.register(AffiliateLink)
class AffiliateLinkAdmin(admin.ModelAdmin):
    list_display = [
        'profile_link', 'affiliate_code', 'clicks', 'conversions',
        'conversion_rate_display', 'total_earned', 'is_active', 'created_at'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['affiliate_code', 'profile__telegram_id']
    readonly_fields = [
        'profile', 'affiliate_code', 'telegram_link', 'clicks', 'conversions',
        'total_earned', 'created_at', 'updated_at'
    ]
    fieldsets = (
        (None, {
            'fields': ('profile', 'affiliate_code', 'telegram_link', 'is_active')
        }),
        ('Статистика', {
            'fields': ('clicks', 'conversions', 'total_earned')
        }),
        ('Системные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    list_per_page = 50

    def profile_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:expenses_profile_change', args=[obj.profile.id]),
            obj.profile.telegram_id
        )
    profile_link.short_description = 'Профиль'

    def conversion_rate_display(self, obj):
        return f"{obj.get_conversion_rate()}%"
    conversion_rate_display.short_description = 'Конверсия'


@admin.register(AffiliateReferral)
class AffiliateReferralAdmin(admin.ModelAdmin):
    list_display = [
        'referrer_link', 'referred_link', 'joined_at', 'first_payment_at',
        'total_payments', 'total_spent'
    ]
    list_filter = ['joined_at', 'first_payment_at']
    search_fields = ['referrer__telegram_id', 'referred__telegram_id']
    readonly_fields = [
        'referrer', 'referred', 'affiliate_link', 'joined_at', 'first_payment_at',
        'total_payments', 'total_spent'
    ]
    fieldsets = (
        (None, {
            'fields': ('referrer', 'referred', 'affiliate_link')
        }),
        ('Статистика', {
            'fields': ('joined_at', 'first_payment_at', 'total_payments', 'total_spent')
        }),
    )

    def referrer_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:expenses_profile_change', args=[obj.referrer.id]),
            obj.referrer.telegram_id
        )
    referrer_link.short_description = 'Реферер'

    def referred_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:expenses_profile_change', args=[obj.referred.id]),
            obj.referred.telegram_id
        )
    referred_link.short_description = 'Реферал'


@admin.register(AffiliateCommission)
class AffiliateCommissionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'referrer_link', 'referred_link', 'payment_amount',
        'commission_amount', 'commission_rate_display', 'status',
        'created_at', 'hold_until', 'paid_at'
    ]
    list_filter = ['status', 'created_at', 'hold_until', 'paid_at']
    search_fields = [
        'referrer__telegram_id', 'referred__telegram_id',
        'telegram_payment_id', 'telegram_transaction_id'
    ]
    readonly_fields = [
        'referrer', 'referred', 'subscription', 'referral', 'payment_amount',
        'commission_amount', 'commission_rate', 'telegram_transaction_id',
        'telegram_payment_id', 'status', 'created_at', 'hold_until', 'paid_at',
        'notes'
    ]
    fieldsets = (
        ('Связи', {
            'fields': ('referrer', 'referred', 'subscription', 'referral')
        }),
        ('Финансы', {
            'fields': ('payment_amount', 'commission_amount', 'commission_rate')
        }),
        ('Telegram', {
            'fields': ('telegram_payment_id', 'telegram_transaction_id'),
            'classes': ('collapse',)
        }),
        ('Статус и даты', {
            'fields': ('status', 'created_at', 'hold_until', 'paid_at')
        }),
        ('Примечания', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    list_per_page = 100

    def referrer_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:expenses_profile_change', args=[obj.referrer.id]),
            obj.referrer.telegram_id
        )
    referrer_link.short_description = 'Реферер'

    def referred_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:expenses_profile_change', args=[obj.referred.id]),
            obj.referred.telegram_id
        )
    referred_link.short_description = 'Реферал'

    def commission_rate_display(self, obj):
        return f"{obj.get_commission_percent()}%"
    commission_rate_display.short_description = 'Ставка'
