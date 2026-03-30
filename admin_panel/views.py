from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Count, Sum, Q, F, Max
from django.db import transaction
from django.utils import timezone
from django.core.paginator import Paginator
from datetime import datetime, timedelta
import logging

from .decorators import admin_required
from .models import BroadcastMessage, BroadcastRecipient
from .forms import BroadcastMessageForm, BroadcastFilterForm
from expenses.models import (
    Profile, Expense, ExpenseCategory, Subscription, Income, RecurringPayment,
    AffiliateProgram, AffiliateLink, AffiliateReferral, AffiliateCommission
)
from bot.telegram_utils import send_telegram_message

logger = logging.getLogger(__name__)


def _claim_broadcast_for_sending(broadcast_id, *, total_recipients=None):
    update_kwargs = {
        'status': 'sending',
        'started_at': timezone.now(),
    }
    if total_recipients is not None:
        update_kwargs['total_recipients'] = total_recipients

    with transaction.atomic():
        return BroadcastMessage.objects.filter(
            pk=broadcast_id,
            status__in=('draft', 'scheduled'),
        ).update(**update_kwargs)


@login_required
@admin_required
def dashboard(request):
    """Главная страница админ панели с метриками"""
    now = timezone.now()
    today = now.date()
    yesterday = today - timedelta(days=1)
    week_ago_datetime = now - timedelta(days=7)
    week_ago_date = today - timedelta(days=7)
    month_ago_date = today - timedelta(days=30)
    
    # Основные метрики
    total_users = Profile.objects.count()
    active_today = Profile.objects.filter(last_activity__date=today).count()
    active_yesterday = Profile.objects.filter(last_activity__date=yesterday).count()
    active_week = Profile.objects.filter(last_activity__gte=week_ago_datetime).count()
    
    # Метрики по тратам
    expenses_today = Expense.objects.filter(expense_date=today).count()
    expenses_yesterday = Expense.objects.filter(expense_date=yesterday).count()
    expenses_week = Expense.objects.filter(expense_date__gte=week_ago_date).count()
    
    # Финансовые метрики
    total_expenses_today = Expense.objects.filter(
        expense_date=today
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    total_expenses_month = Expense.objects.filter(
        expense_date__gte=month_ago_date
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Метрики доходов
    total_income_month = Income.objects.filter(
        income_date__gte=month_ago_date
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Метрики подписок
    active_subscriptions_qs = Subscription.objects.filter(
        is_active=True,
        end_date__gt=now
    )
    active_subscriptions = active_subscriptions_qs.values('profile').distinct().count()
    trial_subscriptions = active_subscriptions_qs.filter(type='trial').values('profile').distinct().count()
    paid_subscriptions = active_subscriptions_qs.filter(payment_method='stars').values('profile').distinct().count()
    
    # Новые регистрации
    new_users_today = Profile.objects.filter(created_at__date=today).count()
    new_users_week = Profile.objects.filter(created_at__gte=week_ago_datetime).count()
    
    # Последние регистрации
    recent_registrations = Profile.objects.order_by('-created_at')[:10]
    
    # Последние траты
    recent_expenses = Expense.objects.select_related('profile', 'category').order_by('-created_at')[:10]
    
    # Топ активных пользователей за неделю
    top_active_users = Profile.objects.filter(
        expenses__expense_date__gte=week_ago_date
    ).annotate(
        expense_count=Count('expenses'),
        total_expenses=Sum('expenses__amount')
    ).order_by('-expense_count')[:10]
    
    # Топ категорий трат за месяц
    top_categories = ExpenseCategory.objects.filter(
        expenses__expense_date__gte=month_ago_date
    ).annotate(
        expense_count=Count('expenses'),
        total_amount=Sum('expenses__amount')
    ).order_by('-total_amount')[:10]
    
    # Статистика бета-тестеров
    beta_testers = Profile.objects.filter(is_beta_tester=True).count()
    active_beta_testers = Profile.objects.filter(
        is_beta_tester=True,
        last_activity__gte=week_ago_datetime
    ).count()
    
    # Статистика регулярных платежей
    recurring_payments = RecurringPayment.objects.filter(is_active=True).count()
    
    context = {
        'total_users': total_users,
        'active_today': active_today,
        'active_yesterday': active_yesterday,
        'active_week': active_week,
        'expenses_today': expenses_today,
        'expenses_yesterday': expenses_yesterday,
        'expenses_week': expenses_week,
        'total_expenses_today': total_expenses_today,
        'total_expenses_month': total_expenses_month,
        'total_income_month': total_income_month,
        'active_subscriptions': active_subscriptions,
        'trial_subscriptions': trial_subscriptions,
        'paid_subscriptions': paid_subscriptions,
        'new_users_today': new_users_today,
        'new_users_week': new_users_week,
        'recent_registrations': recent_registrations,
        'recent_expenses': recent_expenses,
        'top_active_users': top_active_users,
        'top_categories': top_categories,
        'beta_testers': beta_testers,
        'active_beta_testers': active_beta_testers,
        'recurring_payments': recurring_payments,
    }
    
    return render(request, 'admin_panel/dashboard.html', context)


@login_required
@admin_required
def users_list(request):
    """Список пользователей с фильтрами и поиском"""
    users = Profile.objects.all()
    
    # Поиск
    search_query = request.GET.get('search', '')
    if search_query:
        users = users.filter(
            Q(telegram_id__icontains=search_query)
        )
    
    # Фильтры
    date_filter = request.GET.get('date_filter', '')
    if date_filter:
        today = timezone.now().date()
        if date_filter == 'today':
            users = users.filter(created_at__date=today)
        elif date_filter == 'yesterday':
            users = users.filter(created_at__date=today - timedelta(days=1))
        elif date_filter == 'week':
            users = users.filter(created_at__gte=today - timedelta(days=7))
        elif date_filter == 'month':
            users = users.filter(created_at__gte=today - timedelta(days=30))
    
    activity_filter = request.GET.get('activity', '')
    if activity_filter == 'active':
        users = users.filter(last_activity__gte=timezone.now() - timedelta(days=7))
    elif activity_filter == 'inactive':
        users = users.filter(last_activity__lt=timezone.now() - timedelta(days=7))
    
    subscription_filter = request.GET.get('subscription', '')
    if subscription_filter == 'has':
        users = users.filter(
            subscriptions__is_active=True,
            subscriptions__end_date__gt=timezone.now()
        ).distinct()
    elif subscription_filter == 'expired':
        users = users.exclude(
            subscriptions__is_active=True,
            subscriptions__end_date__gt=timezone.now()
        )
    elif subscription_filter == 'trial':
        users = users.filter(
            subscriptions__type='trial',
            subscriptions__is_active=True,
            subscriptions__end_date__gt=timezone.now()
        ).distinct()
    
    beta_filter = request.GET.get('beta', '')
    if beta_filter == 'yes':
        users = users.filter(is_beta_tester=True)
    elif beta_filter == 'no':
        users = users.filter(is_beta_tester=False)
    
    # Аннотации для дополнительной информации
    users = users.annotate(
        expense_count=Count('expenses'),
        total_expenses=Sum('expenses__amount'),
        last_expense=Max('expenses__created_at')
    )
    
    # Сортировка
    sort_by = request.GET.get('sort', '-created_at')
    users = users.order_by(sort_by)
    
    # Пагинация
    paginator = Paginator(users, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'date_filter': date_filter,
        'activity_filter': activity_filter,
        'subscription_filter': subscription_filter,
        'beta_filter': beta_filter,
        'sort_by': sort_by,
    }
    
    return render(request, 'admin_panel/users_list.html', context)


@login_required
@admin_required
def user_detail(request, user_id):
    """Детальная страница пользователя"""
    user = get_object_or_404(Profile, id=user_id)
    
    # Последние траты
    recent_expenses = user.expenses.select_related('category').order_by('-expense_date', '-created_at')[:20]
    
    # Последние доходы
    recent_incomes = user.incomes.select_related('category').order_by('-income_date', '-created_at')[:10]
    
    # История подписок
    subscriptions = user.subscriptions.order_by('-end_date')
    
    # Статистика активности за 30 дней
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    # Траты по дням
    daily_expenses = user.expenses.filter(
        expense_date__gte=thirty_days_ago.date()
    ).values('expense_date').annotate(
        count=Count('id'),
        total=Sum('amount')
    ).order_by('expense_date')
    
    # Статистика по категориям
    category_stats = user.expenses.filter(
        expense_date__gte=thirty_days_ago.date()
    ).values('category__name', 'category__icon').annotate(
        count=Count('id'),
        total=Sum('amount')
    ).order_by('-total')[:10]
    
    # Регулярные платежи
    recurring_payments = user.recurring_payments.filter(is_active=True)
    
    # Общая статистика
    total_expenses = user.expenses.aggregate(
        total=Sum('amount'),
        count=Count('id')
    )
    
    total_incomes = user.incomes.aggregate(
        total=Sum('amount'),
        count=Count('id')
    )
    
    context = {
        'user': user,
        'recent_expenses': recent_expenses,
        'recent_incomes': recent_incomes,
        'subscriptions': subscriptions,
        'daily_expenses': daily_expenses,
        'category_stats': category_stats,
        'recurring_payments': recurring_payments,
        'total_expenses': total_expenses,
        'total_incomes': total_incomes,
    }
    
    return render(request, 'admin_panel/user_detail.html', context)


@login_required
@admin_required
def extend_subscription(request, user_id):
    """Продление подписки пользователя"""
    if request.method == 'POST':
        user = get_object_or_404(Profile, id=user_id)
        days = int(request.POST.get('days', 30))
        subscription_type = request.POST.get('type', 'month')
        
        # Находим последнюю активную подписку
        active_sub = user.subscriptions.filter(
            is_active=True,
            end_date__gt=timezone.now()
        ).order_by('-end_date').first()
        
        if active_sub:
            # Продлеваем существующую подписку
            active_sub.end_date = active_sub.end_date + timedelta(days=days)
            active_sub.save()
            end_date = active_sub.end_date
        else:
            # Создаем новую подписку только если нет активной
            start_date = timezone.now()
            end_date = start_date + timedelta(days=days)
            
            Subscription.objects.create(
                profile=user,
                type=subscription_type,
                payment_method='admin',
                amount=0,  # Бесплатно через админку
                start_date=start_date,
                end_date=end_date,
                is_active=True
            )
        
        # Отправка уведомления пользователю
        try:
            message = f"🎉 Ваша подписка продлена на {days} дней!\n"
            message += f"Новая дата окончания: {end_date.strftime('%d.%m.%Y')}"
            send_telegram_message(user.telegram_id, message)
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о продлении подписки: {e}")
        
        messages.success(request, f'Подписка продлена на {days} дней')
        return redirect('panel:user_detail', user_id=user_id)
    
    return redirect('panel:user_detail', user_id=user_id)


@login_required
@admin_required
def send_message(request, user_id):
    """Отправка сообщения пользователю"""
    if request.method == 'POST':
        user = get_object_or_404(Profile, id=user_id)
        message_text = request.POST.get('message', '')
        
        if message_text:
            try:
                send_telegram_message(user.telegram_id, message_text)
                messages.success(request, 'Сообщение отправлено')
            except Exception as e:
                messages.error(request, f'Ошибка отправки: {str(e)}')
        else:
            messages.error(request, 'Сообщение не может быть пустым')
    
    return redirect('panel:user_detail', user_id=user_id)


@login_required
@admin_required
def broadcast_list(request):
    """Список рассылок"""
    # Фильтрация
    filter_form = BroadcastFilterForm(request.GET)
    broadcasts = BroadcastMessage.objects.all().order_by('-created_at')
    
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('status'):
            broadcasts = broadcasts.filter(status=filter_form.cleaned_data['status'])
        
        if filter_form.cleaned_data.get('date_from'):
            broadcasts = broadcasts.filter(created_at__date__gte=filter_form.cleaned_data['date_from'])
        
        if filter_form.cleaned_data.get('date_to'):
            broadcasts = broadcasts.filter(created_at__date__lte=filter_form.cleaned_data['date_to'])
        
        if filter_form.cleaned_data.get('search'):
            search = filter_form.cleaned_data['search']
            broadcasts = broadcasts.filter(
                Q(title__icontains=search) |
                Q(message_text__icontains=search)
            )
    
    # Пагинация
    paginator = Paginator(broadcasts, 20)
    page = request.GET.get('page')
    broadcasts = paginator.get_page(page)
    
    context = {
        'broadcasts': broadcasts,
        'filter_form': filter_form,
    }
    
    return render(request, 'admin_panel/broadcast_list.html', context)


@login_required
@admin_required
def broadcast_create(request):
    """Создание новой рассылки"""
    from expenses.tasks import send_broadcast_message
    
    if request.method == 'POST':
        form = BroadcastMessageForm(request.POST)
        if form.is_valid():
            broadcast = form.save(commit=False)
            broadcast.created_by = request.user
            broadcast.save()
            form.save_m2m()
            
            # Подсчитываем количество получателей
            broadcast.total_recipients = broadcast.get_recipients_count()
            broadcast.save()
            
            # Если нужно отправить сразу
            if not broadcast.scheduled_at:
                claimed = _claim_broadcast_for_sending(
                    broadcast.id,
                    total_recipients=broadcast.total_recipients,
                )
                if claimed:
                    send_broadcast_message.delay(broadcast.id)
                    messages.success(
                        request,
                        f'Рассылка "{broadcast.title}" запущена. Будет отправлено {broadcast.total_recipients} сообщений.'
                    )
                else:
                    messages.warning(request, f'Рассылка "{broadcast.title}" уже была запущена.')
            else:
                messages.success(request, f'Рассылка "{broadcast.title}" запланирована на {broadcast.scheduled_at.strftime("%d.%m.%Y %H:%M")}')
            
            return redirect('panel:broadcast_detail', broadcast_id=broadcast.id)
    else:
        form = BroadcastMessageForm()
    
    # Статистика для подсказок
    stats = {
        'total_users': Profile.objects.filter(is_active=True).count(),
        'ru_users': Profile.objects.filter(is_active=True, language_code='ru').count(),
        'en_users': Profile.objects.filter(is_active=True, language_code='en').count(),
        'active_users': Profile.objects.filter(
            is_active=True,
            last_activity__gte=timezone.now() - timedelta(days=7)
        ).count(),
        'subscribers': Profile.objects.filter(
            is_active=True,
            subscriptions__is_active=True,
            subscriptions__end_date__gt=timezone.now()
        ).distinct().count(),
        'trial_users': Profile.objects.filter(
            is_active=True,
            subscriptions__type='trial',
            subscriptions__is_active=True,
            subscriptions__end_date__gt=timezone.now()
        ).distinct().count(),
        'beta_testers': Profile.objects.filter(
            is_active=True,
            is_beta_tester=True
        ).count(),
    }
    
    context = {
        'form': form,
        'stats': stats,
    }
    
    return render(request, 'admin_panel/broadcast_create.html', context)


@login_required
@admin_required
def broadcast_detail(request, broadcast_id):
    """Детали рассылки"""
    from expenses.tasks import send_broadcast_message
    
    broadcast = get_object_or_404(BroadcastMessage, id=broadcast_id)
    
    # Обработка действий
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'cancel' and broadcast.status in ['draft', 'scheduled', 'sending']:
            broadcast.status = 'cancelled'
            broadcast.save()
            messages.warning(request, 'Рассылка отменена')
            
        elif action == 'restart' and broadcast.status in ['failed', 'cancelled', 'completed']:
            # Сбрасываем статистику
            broadcast.status = 'draft'
            broadcast.sent_count = 0
            broadcast.failed_count = 0
            broadcast.started_at = None
            broadcast.completed_at = None
            broadcast.error_message = ''
            broadcast.save()
            
            # Сбрасываем статусы получателей
            BroadcastRecipient.objects.filter(broadcast=broadcast).update(
                status='pending',
                sent_at=None,
                error_message=''
            )
            
            # Запускаем заново
            if _claim_broadcast_for_sending(broadcast.id, total_recipients=broadcast.total_recipients):
                send_broadcast_message.delay(broadcast.id)
                messages.success(request, 'Рассылка перезапущена')
            else:
                messages.warning(request, 'Рассылка уже была запущена другим процессом')
            
        elif action == 'start_now' and broadcast.status == 'draft':
            total_recipients = broadcast.get_recipients_count()
            if total_recipients == 0:
                messages.warning(request, 'Нет получателей для отправки')
            elif _claim_broadcast_for_sending(broadcast.id, total_recipients=total_recipients):
                send_broadcast_message.delay(broadcast.id)
                messages.success(request, 'Рассылка запущена')
            else:
                messages.warning(request, 'Рассылка уже была запущена другим процессом')
        
        return redirect('panel:broadcast_detail', broadcast_id=broadcast.id)
    
    # Получаем статистику по получателям
    recipients_stats = {
        'total': broadcast.recipients.count(),
        'sent': broadcast.recipients.filter(status='sent').count(),
        'failed': broadcast.recipients.filter(status='failed').count(),
        'pending': broadcast.recipients.filter(status='pending').count(),
    }
    
    # Получаем последние ошибки
    failed_recipients = broadcast.recipients.filter(
        status='failed'
    ).select_related('profile').order_by('-id')[:10]
    
    context = {
        'broadcast': broadcast,
        'recipients_stats': recipients_stats,
        'failed_recipients': failed_recipients,
        'can_cancel': broadcast.status in ['draft', 'scheduled', 'sending'],
        'can_restart': broadcast.status in ['failed', 'cancelled', 'completed'],
        'can_start': broadcast.status == 'draft',
    }
    
    return render(request, 'admin_panel/broadcast_detail.html', context)


# API endpoints

@login_required
@admin_required
def api_stats(request):
    """API endpoint для получения статистики в реальном времени"""
    now = timezone.now()
    today = now.date()
    
    stats = {
        'active_now': Profile.objects.filter(
            last_activity__gte=now - timedelta(minutes=5)
        ).count(),
        'expenses_today': Expense.objects.filter(expense_date=today).count(),
        'new_users_today': Profile.objects.filter(created_at__date=today).count(),
    }
    
    return JsonResponse(stats)


@login_required
@admin_required
def api_users_search(request):
    """API endpoint для поиска пользователей"""
    query = request.GET.get('q', '')
    
    users = Profile.objects.filter(
        Q(telegram_id__icontains=query)
    )[:20]
    
    results = [{
        'id': user.id,
        'telegram_id': user.telegram_id,
        'is_beta': user.is_beta_tester,
        'has_subscription': user.subscriptions.filter(
            is_active=True,
            end_date__gt=timezone.now()
        ).exists()
    } for user in users]
    
    return JsonResponse({'results': results})


# ==============================
# Партнёрская программа (кастомная админка)
# ==============================

@login_required
@admin_required
def affiliate_dashboard(request):
    """Сводная страница партнёрской программы"""
    program = AffiliateProgram.objects.filter(is_active=True).first()

    # Агрегаты по ссылкам/рефералам/комиссиям
    total_links = AffiliateLink.objects.count()
    total_referrals = AffiliateReferral.objects.count()
    active_referrals = AffiliateReferral.objects.filter(total_payments__gt=0).count()

    commissions_qs = AffiliateCommission.objects.all()
    total_commissions = commissions_qs.count()
    paid_amount = commissions_qs.filter(status='paid').aggregate(total=Sum('commission_amount'))['total'] or 0
    hold_amount = commissions_qs.filter(status='hold').aggregate(total=Sum('commission_amount'))['total'] or 0
    pending_amount = commissions_qs.filter(status='pending').aggregate(total=Sum('commission_amount'))['total'] or 0

    recent_commissions = commissions_qs.select_related('referrer', 'referred').order_by('-created_at')[:10]

    context = {
        'program': program,
        'total_links': total_links,
        'total_referrals': total_referrals,
        'active_referrals': active_referrals,
        'total_commissions': total_commissions,
        'paid_amount': paid_amount,
        'hold_amount': hold_amount,
        'pending_amount': pending_amount,
        'recent_commissions': recent_commissions,
    }

    return render(request, 'admin_panel/affiliate_dashboard.html', context)


@login_required
@admin_required
def affiliate_links(request):
    """Список реферальных ссылок"""
    search = request.GET.get('q', '').strip()
    active = request.GET.get('active', '')  # '', '1', '0'

    links = AffiliateLink.objects.select_related('profile').all()
    if search:
        links = links.filter(
            Q(affiliate_code__icontains=search) |
            Q(profile__telegram_id__icontains=search)
        )
    if active == '1':
        links = links.filter(is_active=True)
    elif active == '0':
        links = links.filter(is_active=False)

    links = links.order_by('-created_at')

    paginator = Paginator(links, 50)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)

    context = {
        'page_obj': page_obj,
        'search': search,
        'active': active,
    }
    return render(request, 'admin_panel/affiliate_links.html', context)


@login_required
@admin_required
def affiliate_referrals(request):
    """Список рефералов"""
    search = request.GET.get('q', '').strip()

    referrals = AffiliateReferral.objects.select_related('referrer', 'referred').all()
    if search:
        referrals = referrals.filter(
            Q(referrer__telegram_id__icontains=search) |
            Q(referred__telegram_id__icontains=search)
        )

    referrals = referrals.order_by('-joined_at')
    paginator = Paginator(referrals, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'search': search,
    }
    return render(request, 'admin_panel/affiliate_referrals.html', context)


@login_required
@admin_required
def affiliate_commissions(request):
    """Список комиссий"""
    search = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')  # '', 'pending','hold','paid','cancelled','refunded'

    commissions = AffiliateCommission.objects.select_related('referrer', 'referred').all()
    if search:
        commissions = commissions.filter(
            Q(referrer__telegram_id__icontains=search) |
            Q(referred__telegram_id__icontains=search) |
            Q(telegram_payment_id__icontains=search) |
            Q(telegram_transaction_id__icontains=search)
        )
    if status in ['pending', 'hold', 'paid', 'cancelled', 'refunded']:
        commissions = commissions.filter(status=status)

    commissions = commissions.order_by('-created_at')

    agg = commissions.aggregate(
        total_amount=Sum('commission_amount'),
        count=Count('id')
    )

    paginator = Paginator(commissions, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'agg': agg,
    }
    return render(request, 'admin_panel/affiliate_commissions.html', context)
