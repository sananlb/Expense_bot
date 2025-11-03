from django import forms
from django.utils import timezone
from datetime import datetime, timedelta
from .models import BroadcastMessage
from expenses.models import Profile


class BroadcastMessageForm(forms.ModelForm):
    """Форма для создания и редактирования рассылок"""
    
    # Дополнительные поля для удобства
    send_immediately = forms.BooleanField(
        label='Отправить сразу',
        required=False,
        initial=True,
        help_text='Снимите галочку, чтобы запланировать отправку'
    )
    
    scheduled_date = forms.DateField(
        label='Дата отправки',
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    
    scheduled_time = forms.TimeField(
        label='Время отправки',
        required=False,
        widget=forms.TimeInput(attrs={
            'type': 'time',
            'class': 'form-control'
        })
    )
    
    class Meta:
        model = BroadcastMessage
        fields = [
            'title',
            'message_text',
            'recipient_type',
            'language_filter',
            'include_inactive_days',
            'custom_recipients',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: Новогодняя акция'
            }),
            'message_text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 10,
                'placeholder': 'Введите текст сообщения...\n\nПоддерживается Markdown:\n*жирный* текст\n_курсив_\n[ссылка](https://example.com)'
            }),
            'recipient_type': forms.Select(attrs={
                'class': 'form-select',
                'id': 'recipient-type-select'
            }),
            'language_filter': forms.Select(attrs={
                'class': 'form-select',
            }),
            'include_inactive_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': '30'
            }),
            'custom_recipients': forms.SelectMultiple(attrs={
                'class': 'form-select',
                'size': 10
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Настройка поля custom_recipients
        self.fields['custom_recipients'].queryset = Profile.objects.filter(
            is_active=True
        ).order_by('language_code', '-last_activity')
        
        # Форматирование отображения пользователей
        self.fields['custom_recipients'].label_from_instance = self.label_from_instance
        
        # Если редактируем существующую рассылку
        if self.instance.pk:
            if self.instance.scheduled_at:
                self.fields['send_immediately'].initial = False
                self.fields['scheduled_date'].initial = self.instance.scheduled_at.date()
                self.fields['scheduled_time'].initial = self.instance.scheduled_at.time()
    
    def label_from_instance(self, obj):
        """Форматирование отображения пользователя в списке"""
        name = f"{obj.telegram_id} [{obj.language_code.upper()}]"
        # Проверяем наличие подписки
        if obj.subscriptions.filter(
            is_active=True,
            end_date__gt=timezone.now()
        ).exists():
            name += " ⭐"  # Подписчик
        if obj.is_beta_tester:
            name += " 🧪"  # Бета-тестер
        return name
    
    def clean(self):
        cleaned_data = super().clean()
        send_immediately = cleaned_data.get('send_immediately')
        scheduled_date = cleaned_data.get('scheduled_date')
        scheduled_time = cleaned_data.get('scheduled_time')
        recipient_type = cleaned_data.get('recipient_type')
        custom_recipients = cleaned_data.get('custom_recipients')
        include_inactive_days = cleaned_data.get('include_inactive_days')
        
        # Проверка планирования
        if not send_immediately:
            if not scheduled_date or not scheduled_time:
                raise forms.ValidationError(
                    'Укажите дату и время для запланированной отправки'
                )
            
            # Объединяем дату и время
            scheduled_at = timezone.make_aware(
                datetime.combine(scheduled_date, scheduled_time)
            )
            
            if scheduled_at <= timezone.now():
                raise forms.ValidationError(
                    'Время отправки должно быть в будущем'
                )
            
            cleaned_data['scheduled_at'] = scheduled_at
        else:
            cleaned_data['scheduled_at'] = None
        
        # Проверка получателей
        if recipient_type == 'custom' and not custom_recipients:
            raise forms.ValidationError(
                'Выберите хотя бы одного получателя для выборочной рассылки'
            )
        
        if recipient_type == 'inactive' and not include_inactive_days:
            raise forms.ValidationError(
                'Укажите количество дней неактивности'
            )
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Устанавливаем scheduled_at из cleaned_data
        if 'scheduled_at' in self.cleaned_data:
            instance.scheduled_at = self.cleaned_data['scheduled_at']
        
        # Устанавливаем статус
        if instance.scheduled_at:
            instance.status = 'scheduled'
        else:
            instance.status = 'draft'
        
        if commit:
            instance.save()
            self.save_m2m()
        
        return instance


class BroadcastFilterForm(forms.Form):
    """Форма фильтрации рассылок"""
    
    STATUS_CHOICES = [('', 'Все статусы')] + BroadcastMessage.STATUS_CHOICES
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm'
        })
    )
    
    date_from = forms.DateField(
        label='С',
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control form-control-sm'
        })
    )
    
    date_to = forms.DateField(
        label='По',
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control form-control-sm'
        })
    )
    
    search = forms.CharField(
        label='Поиск',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Название или текст...'
        })
    )
