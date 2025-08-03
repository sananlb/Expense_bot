"""
Админ панель для ExpenseBot согласно ТЗ
"""
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Count
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Profile, UserSettings, ExpenseCategory, Expense, Budget, Cashback


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['telegram_id', 'username', 'first_name', 'language_code', 'currency', 'is_active', 'created_at']
    list_filter = ['is_active', 'language_code', 'currency', 'created_at']
    search_fields = ['telegram_id', 'username', 'first_name', 'last_name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('telegram_id', 'username', 'first_name', 'last_name')
        }),
        ('Настройки', {
            'fields': ('language_code', 'timezone', 'currency')
        }),
        ('Статус', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            total_expenses=Sum('expenses__amount'),
            expenses_count=Count('expenses')
        )


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ['profile', 'daily_reminder_enabled', 'daily_reminder_time', 
                    'weekly_summary_enabled', 'monthly_summary_enabled']
    list_filter = ['daily_reminder_enabled', 'weekly_summary_enabled', 
                   'monthly_summary_enabled', 'budget_alerts_enabled']
    search_fields = ['profile__username', 'profile__first_name']
    
    fieldsets = (
        ('Профиль', {
            'fields': ('profile',)
        }),
        ('Уведомления', {
            'fields': ('daily_reminder_enabled', 'daily_reminder_time',
                      'weekly_summary_enabled', 'monthly_summary_enabled',
                      'budget_alerts_enabled')
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
        return f"{obj.icon} {obj.name}"
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
            return f"{obj.category.icon} {obj.category.name}"
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
        return f"{obj.category.icon} {obj.category.name}"
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


# Настройка админки
admin.site.site_header = "ExpenseBot Admin"
admin.site.site_title = "ExpenseBot"
admin.site.index_title = "Панель управления"