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
    AffiliateProgram, AffiliateLink, AffiliateReferral, AffiliateCommission,
    AdvertiserCampaign
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
                    'is_beta_tester', 'referrals_count_display', 'payment_stats',
                    'language_code', 'currency', 'is_active', 'acquisition_source_display', 'created_at']
    list_filter = ['is_active', 'is_beta_tester', 'language_code', 'currency', 'acquisition_source', 'created_at']
    search_fields = ['telegram_id', 'beta_access_key', 'acquisition_campaign']
    readonly_fields = ['created_at', 'updated_at',
                       'referrals_count', 'active_referrals_count',
                       'total_payments_count', 'total_stars_paid',
                       'acquisition_date']
    inlines = [SubscriptionInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('telegram_id',)
        }),
        ('Настройки', {
            'fields': ('language_code', 'timezone', 'currency')
        }),
        ('Источник привлечения', {
            'fields': ('acquisition_source', 'acquisition_campaign', 'acquisition_date', 'acquisition_details'),
            'description': 'Данные об источнике привлечения пользователя (UTM-метки)'
        }),
        ('Статистика платежей', {
            'fields': ('total_payments_count', 'total_stars_paid'),
            'description': 'Общая статистика платежей пользователя через Telegram Stars'
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

    def payment_stats(self, obj):
        """Статистика платежей"""
        payments = obj.total_payments_count or 0
        stars = obj.total_stars_paid or 0

        if payments > 0:
            return format_html(
                '<span title="Всего {} платежей"><b>{}⭐</b> ({} пл.)</span>',
                payments, stars, payments
            )
        return format_html('<span style="color: gray;">—</span>')

    payment_stats.short_description = 'Платежи'

    def acquisition_source_display(self, obj):
        """Отображение источника привлечения с ссылкой для блогеров"""
        if obj.acquisition_source:
            source_labels = {
                'organic': '🌱',
                'blogger': '📹',
                'ads': '📢',
                'referral': '🤝',
                'social': '📱',
                'other': '📍'
            }
            icon = source_labels.get(obj.acquisition_source, '❓')

            # Для блогеров показываем имя и ссылку
            if obj.acquisition_source == 'blogger' and obj.acquisition_campaign:
                # Извлекаем имя блогера из кампании
                campaign_name = obj.acquisition_campaign.split('_')[0] if '_' in obj.acquisition_campaign else obj.acquisition_campaign

                # Формируем полную ссылку
                link = f"https://t.me/showmecoinbot?start=b_{obj.acquisition_campaign}"

                return format_html(
                    '{} <b>{}</b> <a href="{}" target="_blank" title="Персональная ссылка блогера">🔗</a>',
                    icon, campaign_name, link
                )
            elif obj.acquisition_campaign:
                return format_html(
                    '{} {}',
                    icon, obj.acquisition_campaign
                )
            else:
                return format_html('{} {}', icon, obj.get_acquisition_source_display())
        return format_html('<span style="color: gray;">—</span>')

    acquisition_source_display.short_description = 'Источник'
    payment_stats.admin_order_field = 'total_stars_paid'

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


# Функционал бюджетов отключен (30.10.2025)
# @admin.register(Budget)
# class BudgetAdmin(admin.ModelAdmin):
#     list_display = ['profile', 'category', 'amount', 'period_type', 'start_date',
#                     'end_date', 'is_active']
#     list_filter = ['period_type', 'is_active', 'start_date']
#     search_fields = ['profile__username', 'category__name']
#     date_hierarchy = 'start_date'
#
#     fieldsets = (
#         ('Основная информация', {
#             'fields': ('profile', 'category', 'amount', 'period_type')
#         }),
#         ('Период', {
#             'fields': ('start_date', 'end_date')
#         }),
#         ('Статус', {
#             'fields': ('is_active', 'created_at', 'updated_at')
#         }),
#     )
#     readonly_fields = ['created_at', 'updated_at']


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
                    'get_active_status', 'used_count', 'max_uses', 'valid_until', 'created_by']
    list_filter = ['is_active', 'discount_type', 'applicable_subscription_types',
                   'created_at', 'valid_until']
    search_fields = ['code', 'description']
    readonly_fields = ['used_count', 'created_at', 'updated_at', 'created_by']

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

    def get_changeform_initial_data(self, request):
        """Устанавливаем начальные значения для формы создания промокода"""
        initial = super().get_changeform_initial_data(request)
        # Не устанавливаем начальное значение для valid_until -
        # пусть пользователь сам выбирает дату и время
        return initial

    def get_active_status(self, obj):
        """Показать статус активности с учетом лимита использований"""
        from django.utils.html import format_html

        # Проверяем, достиг ли промокод лимита использований
        if obj.max_uses and obj.used_count >= obj.max_uses:
            return format_html('<span style="color: red;">✗</span>')
        elif obj.is_active:
            return format_html('<span style="color: green;">✓</span>')
        else:
            return format_html('<span style="color: red;">✗</span>')

    get_active_status.short_description = 'Активен'
    get_active_status.admin_order_field = 'is_active'

    def save_model(self, request, obj, form, change):
        """Автоматически заполняем created_by при создании промокода"""
        if not change:  # Только при создании нового промокода
            # Пытаемся найти профиль админа по telegram_id
            # Если у админа есть профиль в боте - используем его
            from expenses.models import Profile
            try:
                # Попробуем найти профиль по username админа
                admin_profile = Profile.objects.filter(username=request.user.username).first()
                if not admin_profile:
                    # Если нет - создаем профиль для админа или используем первый профиль админа
                    admin_profile = Profile.objects.filter(telegram_id=881292737).first()  # Ваш telegram_id
                obj.created_by = admin_profile
            except Exception:
                pass  # Если не удалось - оставляем пустым
        super().save_model(request, obj, form, change)

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


# ==============================
# Рекламные кампании
# ==============================

@admin.register(AdvertiserCampaign)
class AdvertiserCampaignAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'campaign', 'link_display', 'source_type', 'status',
        'users_count', 'paying_users_count', 'conversion_display',
        'total_revenue_display', 'roi_display', 'is_active', 'created_at'
    ]
    list_filter = ['source_type', 'status', 'is_active', 'created_at', 'start_date']
    search_fields = ['name', 'campaign', 'utm_code', 'contact_info']
    readonly_fields = ['utm_code', 'link_display_detail', 'created_at', 'updated_at', 'created_by']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('📊 Инструкция по просмотру статистики', {
            'description': (
                '<div style="background: #e8f4fd; padding: 15px; border-left: 4px solid #2196F3; margin-bottom: 20px; border-radius: 4px;">'
                '<h3 style="margin-top: 0; color: #1976D2;">Как посмотреть статистику кампании в боте:</h3>'
                '<p style="margin: 10px 0;"><strong>Используйте команду:</strong> <code style="background: #fff; padding: 4px 8px; border-radius: 3px;">/blogger_stats ИМЯ_БЛОГЕРА</code></p>'
                '<p style="margin: 10px 0;"><strong>Примеры:</strong></p>'
                '<ul style="margin: 5px 0;">'
                '<li><code style="background: #fff; padding: 2px 6px; border-radius: 3px;">/blogger_stats ivan</code> - статистика блогера ivan</li>'
                '<li><code style="background: #fff; padding: 2px 6px; border-radius: 3px;">/blogger_stats maria</code> - статистика блогера maria</li>'
                '</ul>'
                '<p style="margin: 10px 0 0 0;"><strong>Что покажет команда:</strong> количество пользователей, конверсии, активность, доход и рекомендации по оптимизации.</p>'
                '</div>'
            ),
            'fields': ()
        }),
        ('Основная информация', {
            'fields': ('name', 'campaign', 'utm_code', 'source_type')
        }),
        ('Статус и управление', {
            'fields': ('is_active', 'status')
        }),
        ('Планирование', {
            'fields': ('start_date', 'end_date', 'budget', 'target_users', 'target_conversion'),
            'classes': ('collapse',)
        }),
        ('Дополнительная информация', {
            'fields': ('description', 'contact_info'),
            'classes': ('collapse',)
        }),
        ('Системные', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['activate_campaigns', 'deactivate_campaigns', 'set_completed']

    def get_queryset(self, request):
        """Добавляем аннотации для статистики"""
        # Просто возвращаем queryset без аннотаций
        # Статистика будет считаться через методы модели
        return super().get_queryset(request)

    def link_display(self, obj):
        """Отображение полной ссылки"""
        link = obj.link
        # Копирование ссылки по клику
        return format_html(
            '<div style="display: flex; align-items: center; gap: 5px;">'
            '<code style="background: #f5f5f5; padding: 3px 6px; border-radius: 3px; font-size: 11px;">{}</code>'
            '<button onclick="navigator.clipboard.writeText(\'{}\'); this.textContent=\'✓\'; '
            'setTimeout(() => this.textContent=\'📋\', 2000); return false;" '
            'style="padding: 2px 6px; background: #4CAF50; color: white; border: none; '
            'border-radius: 3px; cursor: pointer; font-size: 11px;" '
            'title="Копировать ссылку">📋</button>'
            '</div>',
            link, link
        )
    link_display.short_description = 'Ссылка'
    link_display.allow_tags = True

    def link_display_detail(self, obj):
        """Отображение полной ссылки в детальном просмотре"""
        link = obj.link
        return format_html(
            '<div style="margin: 10px 0;">'
            '<input type="text" value="{}" readonly '
            'style="width: 400px; padding: 5px; font-family: monospace; background: #f5f5f5; border: 1px solid #ddd; border-radius: 3px;" '
            'onclick="this.select();" />'
            '<button onclick="navigator.clipboard.writeText(\'{}\'); this.textContent=\'✓ Скопировано\'; '
            'setTimeout(() => this.textContent=\'📋 Копировать\', 2000); return false;" '
            'style="margin-left: 10px; padding: 5px 15px; background: #4CAF50; color: white; border: none; '
            'border-radius: 3px; cursor: pointer;">'
            '📋 Копировать</button>'
            '<div style="margin-top: 5px; color: #666; font-size: 12px;">Полная ссылка для рекламопроизводителя</div>'
            '</div>',
            link, link
        )
    link_display_detail.short_description = 'Ссылка для кампании'

    def users_count(self, obj):
        """Количество привлеченных пользователей"""
        stats = obj.get_stats()
        return stats.get('total_users', 0)
    users_count.short_description = 'Пользователи'

    def paying_users_count(self, obj):
        """Количество платящих пользователей"""
        stats = obj.get_stats()
        return stats.get('paying_users', 0)
    paying_users_count.short_description = 'Платящих'

    def conversion_display(self, obj):
        """Конверсия в платящих"""
        stats = obj.get_stats()
        conversion = stats.get('conversion_to_paying', 0)

        if conversion >= 15:
            color = 'green'
            icon = '🔥'
        elif conversion >= 10:
            color = 'orange'
            icon = '✅'
        elif conversion >= 5:
            color = 'blue'
            icon = '📈'
        else:
            color = 'red'
            icon = '📊'

        return format_html(
            '<span style="color: {};">{} {}%</span>',
            color, icon, f"{conversion:.1f}"
        )
    conversion_display.short_description = 'Конверсия'

    def total_revenue_display(self, obj):
        """Общий доход"""
        stats = obj.get_stats()
        revenue_stars = stats.get('total_revenue', 0)
        revenue_rub = stats.get('total_revenue_rub', 0)

        if revenue_stars > 0:
            return format_html(
                '<span title="≈ {} ₽">{}⭐</span>',
                revenue_rub, revenue_stars
            )
        return format_html('<span style="color: gray;">—</span>')
    total_revenue_display.short_description = 'Доход'

    def roi_display(self, obj):
        """ROI кампании"""
        stats = obj.get_stats()
        roi = stats.get('roi', 0)

        if roi > 100:
            color = 'green'
            icon = '💰'
        elif roi > 0:
            color = 'orange'
            icon = '📈'
        elif roi == 0:
            return format_html('<span style="color: gray;">—</span>')
        else:
            color = 'red'
            icon = '📉'

        return format_html(
            '<span style="color: {};">{} {}%</span>',
            color, icon, f"{roi:.1f}"
        )
    roi_display.short_description = 'ROI'

    def save_model(self, request, obj, form, change):
        """Автоматически заполняем created_by при создании"""
        if not change and not obj.created_by:
            # Пытаемся найти профиль админа
            try:
                from expenses.models import Profile
                admin_profile = Profile.objects.filter(telegram_id=881292737).first()
                if admin_profile:
                    obj.created_by = request.user
            except Exception:
                pass
        super().save_model(request, obj, form, change)

    def activate_campaigns(self, request, queryset):
        """Активировать кампании"""
        updated = queryset.update(is_active=True, status='active')
        self.message_user(request, f'{updated} кампаний активировано.')
    activate_campaigns.short_description = 'Активировать кампании'

    def deactivate_campaigns(self, request, queryset):
        """Деактивировать кампании"""
        updated = queryset.update(is_active=False, status='paused')
        self.message_user(request, f'{updated} кампаний приостановлено.')
    deactivate_campaigns.short_description = 'Приостановить кампании'

    def set_completed(self, request, queryset):
        """Пометить как завершенные"""
        updated = queryset.update(status='completed')
        self.message_user(request, f'{updated} кампаний помечено как завершенные.')
    set_completed.short_description = 'Пометить как завершенные'
