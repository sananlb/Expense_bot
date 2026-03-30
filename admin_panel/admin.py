from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.contrib import messages
from django.db import transaction

from admin_panel.models import BroadcastMessage, BroadcastRecipient
from admin_panel.forms import BroadcastMessageForm


class BroadcastRecipientInline(admin.TabularInline):
    model = BroadcastRecipient
    extra = 0
    can_delete = False
    fields = ['profile_link', 'status', 'sent_at', 'error_message']
    readonly_fields = ['profile_link', 'status', 'sent_at', 'error_message']
    ordering = ['status', '-sent_at']
    max_num = 0
    show_change_link = False

    def profile_link(self, obj):
        from django.urls import reverse
        url = reverse('admin:expenses_profile_change', args=[obj.profile_id])
        return format_html('<a href="{}">{}</a>', url, obj.profile.telegram_id)

    profile_link.short_description = 'Telegram ID'

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(BroadcastMessage)
class BroadcastMessageAdmin(admin.ModelAdmin):
    form = BroadcastMessageForm

    list_display = [
        'title', 'status_badge', 'recipient_type', 'language_filter',
        'progress_display', 'scheduled_at', 'created_at',
    ]
    list_filter = ['status', 'recipient_type', 'language_filter', 'created_at']
    search_fields = ['title', 'message_text']
    readonly_fields = [
        'status', 'total_recipients', 'sent_count', 'failed_count',
        'created_by', 'created_at', 'updated_at', 'started_at', 'completed_at',
        'error_message', 'recipients_preview',
    ]
    filter_horizontal = ['custom_recipients']
    actions = ['action_send_now', 'action_cancel']

    fieldsets = (
        ('Основное', {
            'fields': ('title', 'message_text'),
        }),
        ('Получатели', {
            'fields': (
                'recipient_type', 'language_filter',
                'include_inactive_days', 'custom_recipients',
                'recipients_preview',
            ),
        }),
        ('Планирование', {
            'description': (
                'Оставьте "Отправить сразу" для немедленной отправки '
                'или снимите галочку и укажите дату/время.'
            ),
            'fields': ('send_immediately', 'scheduled_date', 'scheduled_time'),
        }),
        ('Статус и статистика', {
            'fields': (
                'status', 'total_recipients', 'sent_count', 'failed_count',
                'error_message', 'created_by', 'created_at', 'updated_at',
                'started_at', 'completed_at',
            ),
            'classes': ('collapse',),
        }),
    )

    def get_inlines(self, request, obj):
        if obj and obj.pk and obj.status != 'draft':
            return [BroadcastRecipientInline]
        return []

    def recipients_preview(self, obj):
        if not obj or not obj.pk:
            return '—'
        count = obj.get_recipients_count()
        return format_html(
            '<strong style="font-size:1.1em">{}</strong> получателей',
            count
        )

    recipients_preview.short_description = 'Предварительный подсчёт'

    def status_badge(self, obj):
        colors = {
            'draft': '#6c757d',
            'scheduled': '#0d6efd',
            'sending': '#fd7e14',
            'completed': '#198754',
            'cancelled': '#6c757d',
            'failed': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:0.85em">{}</span>',
            color, obj.get_status_display()
        )

    status_badge.short_description = 'Статус'

    def progress_display(self, obj):
        if obj.status == 'draft':
            return '—'
        processed = obj.sent_count + obj.failed_count
        total = obj.total_recipients
        if total > 0:
            pct = int(processed / total * 100)
            pct_str = f' из {total} ({pct}%)'
        else:
            pct_str = ''
        return format_html(
            '<span style="color:#198754">✓ {}</span> '
            '/ <span style="color:#dc3545">✗ {}</span>{}',
            obj.sent_count, obj.failed_count, pct_str
        )

    progress_display.short_description = 'Прогресс (отпр / ошибок)'

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        # scheduled_at и status уже выставлены в form.save()
        super().save_model(request, obj, form, change)

    @admin.action(description='▶ Отправить сейчас')
    def action_send_now(self, request, queryset):
        from expenses.tasks import send_broadcast_message

        sent = 0
        for broadcast in queryset:
            if broadcast.status not in ('draft', 'scheduled'):
                self.message_user(
                    request,
                    f'«{broadcast.title}» — статус "{broadcast.get_status_display()}", пропущена.',
                    messages.WARNING,
                )
                continue

            count = broadcast.get_recipients_count()
            if count == 0:
                self.message_user(
                    request,
                    f'«{broadcast.title}» — нет получателей, пропущена.',
                    messages.WARNING,
                )
                continue

            # Атомарно переводим в sending, чтобы исключить дубли
            with transaction.atomic():
                updated = BroadcastMessage.objects.filter(
                    pk=broadcast.pk,
                    status__in=('draft', 'scheduled'),
                ).update(
                    status='sending',
                    total_recipients=count,
                    started_at=timezone.now(),
                )
            if not updated:
                self.message_user(
                    request,
                    f'«{broadcast.title}» — уже запущена другим процессом, пропущена.',
                    messages.WARNING,
                )
                continue

            send_broadcast_message.delay(broadcast.pk)
            sent += 1

        if sent:
            self.message_user(
                request,
                f'Запущено рассылок: {sent}.',
                messages.SUCCESS,
            )

    @admin.action(description='✕ Отменить рассылку')
    def action_cancel(self, request, queryset):
        updated = queryset.filter(
            status__in=('draft', 'scheduled', 'sending')
        ).update(status='cancelled')
        self.message_user(request, f'Отменено рассылок: {updated}.', messages.SUCCESS)
