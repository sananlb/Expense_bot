from celery import shared_task
from datetime import datetime, date, timedelta
import asyncio
import logging
import re
from typing import List

from django.conf import settings
from django.db.models import Count, Sum
from aiogram import Bot

logger = logging.getLogger(__name__)



@shared_task
def send_weekly_reports():
    """Send weekly expense reports"""
    try:
        from expenses.models import Profile, UserSettings
        from bot.services.notifications import NotificationService
        
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        service = NotificationService(bot)
        
        current_weekday = datetime.now().weekday()
        current_time = datetime.now().time()
        
        # Get users with weekly reports enabled for current weekday and time
        profiles = Profile.objects.filter(
            settings__weekly_summary_enabled=True,
            settings__weekly_summary_day=current_weekday
        ).select_related('settings')
        
        logger.info(f"Sending weekly reports to {profiles.count()} users")
        
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        for profile in profiles:
            try:
                loop.run_until_complete(
                    service.send_weekly_report(profile.telegram_id, profile)
                )
            except Exception as e:
                logger.error(f"Error sending weekly report to user {profile.telegram_id}: {e}")
        
        loop.close()
        
    except Exception as e:
        logger.error(f"Error in send_weekly_reports task: {e}")


@shared_task
def send_monthly_reports():
    """Send monthly expense reports"""
    try:
        from expenses.models import Profile, UserSettings
        from bot.services.notifications import NotificationService
        from calendar import monthrange
        
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        service = NotificationService(bot)
        
        # Check if today is the last day of month
        today = datetime.now()
        last_day = monthrange(today.year, today.month)[1]
        
        if today.day != last_day:
            return
        
        current_time = today.time()
        
        # Get users with monthly reports enabled
        profiles = Profile.objects.filter(
            settings__monthly_summary_enabled=True
        ).select_related('settings')
        
        logger.info(f"Sending monthly reports to {profiles.count()} users")
        
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        for profile in profiles:
            try:
                loop.run_until_complete(
                    service.send_monthly_report(profile.telegram_id, profile)
                )
            except Exception as e:
                logger.error(f"Error sending monthly report to user {profile.telegram_id}: {e}")
        
        loop.close()
        
    except Exception as e:
        logger.error(f"Error in send_monthly_reports task: {e}")


@shared_task
def check_budget_limits():
    """Check budget limits and send warnings"""
    try:
        from profiles.models import Profile
        from expenses.models import Budget, Expense
        from bot.services.notifications import NotificationService
        from decimal import Decimal
        
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        service = NotificationService(bot)
        
        # Get all active budgets
        budgets = Budget.objects.filter(
            is_active=True
        ).select_related('profile', 'category')
        
        today = date.today()
        
        for budget in budgets:
            try:
                # Calculate spent amount based on period
                if budget.period == 'daily':
                    expenses = Expense.objects.filter(
                        profile=budget.profile,
                        date=today
                    )
                elif budget.period == 'weekly':
                    from datetime import timedelta
                    week_start = today - timedelta(days=today.weekday())
                    expenses = Expense.objects.filter(
                        profile=budget.profile,
                        date__gte=week_start,
                        date__lte=today
                    )
                elif budget.period == 'monthly':
                    month_start = today.replace(day=1)
                    expenses = Expense.objects.filter(
                        profile=budget.profile,
                        date__gte=month_start,
                        date__lte=today
                    )
                else:
                    continue
                
                # Filter by category if specified
                if budget.category:
                    expenses = expenses.filter(category=budget.category)
                
                # Calculate total spent
                spent = sum(e.amount for e in expenses)
                percent = (spent / budget.amount) * 100 if budget.amount > 0 else 0
                
                # Send warnings at 80%, 90%, and 100%
                if percent >= 80:
                    # Check if we should send notification
                    should_notify = False
                    
                    if percent >= 100 and not budget.notified_exceeded:
                        should_notify = True
                        budget.notified_exceeded = True
                    elif 90 <= percent < 100 and not budget.notified_90_percent:
                        should_notify = True
                        budget.notified_90_percent = True
                    elif 80 <= percent < 90 and not budget.notified_80_percent:
                        should_notify = True
                        budget.notified_80_percent = True
                    
                    if should_notify:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        loop.run_until_complete(
                            service.send_budget_warning(
                                budget.profile.telegram_id,
                                budget,
                                spent,
                                percent
                            )
                        )
                        
                        loop.close()
                        budget.save()
                
                # Reset notifications for new period
                elif percent < 80:
                    if budget.notified_80_percent or budget.notified_90_percent or budget.notified_exceeded:
                        budget.notified_80_percent = False
                        budget.notified_90_percent = False
                        budget.notified_exceeded = False
                        budget.save()
                
            except Exception as e:
                logger.error(f"Error checking budget {budget.id}: {e}")
        
    except Exception as e:
        logger.error(f"Error in check_budget_limits task: {e}")


@shared_task
def cleanup_old_expenses():
    """Clean up expenses older than retention period"""
    try:
        from expenses.models import Expense
        from datetime import timedelta
        
        # Keep expenses for 2 years by default
        retention_days = getattr(settings, 'EXPENSE_RETENTION_DAYS', 730)
        cutoff_date = date.today() - timedelta(days=retention_days)
        
        # Delete old expenses
        deleted_count, _ = Expense.objects.filter(
            created_at__lt=cutoff_date
        ).delete()
        
        logger.info(f"Deleted {deleted_count} expenses older than {cutoff_date}")
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_expenses task: {e}")


@shared_task
def send_daily_admin_report():
    """Отправка ежедневного отчета администратору"""
    try:
        from expenses.models import Profile, Expense, ExpenseCategory, Subscription
        from bot.services.admin_notifier import send_admin_alert
        from django.utils import timezone
        
        yesterday = timezone.now().date() - timedelta(days=1)
        today = timezone.now().date()
        
        # Собираем статистику по пользователям
        total_users = Profile.objects.count()
        active_users = Expense.objects.filter(
            expense_date=yesterday
        ).values('profile').distinct().count()
        
        new_users = Profile.objects.filter(
            created_at__date=yesterday
        ).count()
        
        # Статистика по расходам
        expenses_stats = Expense.objects.filter(
            expense_date=yesterday
        ).aggregate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        # Статистика по подпискам за вчера
        new_subscriptions = Subscription.objects.filter(
            created_at__date=yesterday,
            payment_method__in=['stars', 'referral', 'promo']
        ).values('type').annotate(
            count=Count('id')
        ).order_by('type')
        
        subscriptions_text = ""
        total_subs = 0
        for sub in new_subscriptions:
            sub_type = {
                'trial': 'Пробных',
                'month': 'Месячных', 
                'six_months': 'Полугодовых'
            }.get(sub['type'], sub['type'])
            subscriptions_text += f"  • {sub_type}: {sub['count']}\n"
            total_subs += sub['count']
        
        # Активные подписки на сегодня
        active_subscriptions = Subscription.objects.filter(
            is_active=True,
            end_date__gt=timezone.now()
        ).count()
        
        # Топ категорий
        top_categories = Expense.objects.filter(
            expense_date=yesterday
        ).values('category__name').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')[:5]
        
        categories_text = "\n".join([
            f"  • {cat['category__name'] or 'Без категории'}: "
            f"{cat['total']:,.0f} ₽ ({cat['count']} зап.)"
            for cat in top_categories
        ])
        
        # Формируем отчет
        report = (
            f"📊 *Ежедневный отчет ExpenseBot*\n"
            f"📅 За {yesterday.strftime('%d.%m.%Y')}\n\n"
            f"👥 *Пользователи:*\n"
            f"  • Всего: {total_users:,}\n"
            f"  • Активных вчера: {active_users}\n"
            f"  • Новых регистраций: {new_users}\n\n"
            f"💰 *Расходы за вчера:*\n"
            f"  • Записей: {expenses_stats['count'] or 0:,}\n"
            f"  • Общая сумма: {expenses_stats['total'] or 0:,.0f} ₽\n"
        )
        
        if expenses_stats['count'] and expenses_stats['count'] > 0:
            avg_expense = expenses_stats['total'] / expenses_stats['count']
            report += f"  • Средний чек: {avg_expense:,.0f} ₽\n"
        
        report += f"\n⭐ *Подписки:*\n"
        report += f"  • Активных всего: {active_subscriptions}\n"
        if total_subs > 0:
            report += f"  • Куплено вчера: {total_subs}\n"
            report += subscriptions_text
        else:
            report += f"  • Куплено вчера: 0\n"
        
        if categories_text:
            report += f"\n📂 *Топ-5 категорий вчера:*\n{categories_text}\n"
        
        report += f"\n⏰ Отчет сформирован: {datetime.now().strftime('%H:%M')}"
        
        # Отправляем отчет асинхронно
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(send_admin_alert(report, disable_notification=True))
        
        loop.close()
        
        logger.info(f"Ежедневный отчет за {yesterday} отправлен администратору")
        
    except Exception as e:
        logger.error(f"Ошибка отправки ежедневного отчета: {e}")


@shared_task
def process_recurring_payments():
    """Process recurring payments for today at 12:00"""
    try:
        from bot.services.recurring import process_recurring_payments_for_today
        from bot.utils.expense_messages import format_expense_added_message
        from aiogram import Bot
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Process recurring payments
        processed_count, processed_payments = loop.run_until_complete(
            process_recurring_payments_for_today()
        )
        
        # Отправляем уведомления пользователям о списанных ежемесячных платежах
        for payment_info in processed_payments:
            try:
                user_id = payment_info['user_id']
                expense = payment_info['expense']
                payment = payment_info['payment']
                
                # Для ежемесячных платежей не считаем кешбэк
                cashback_text = ""
                
                # Форматируем сообщение используя стандартную функцию
                text = loop.run_until_complete(
                    format_expense_added_message(
                        expense=expense,
                        category=expense.category,
                        cashback_text=cashback_text,
                        is_recurring=True  # Флаг для ежемесячного платежа
                    )
                )
                
                # Создаем клавиатуру с кнопками редактирования
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_expense_{expense.id}"),
                        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_expense_{expense.id}")
                    ]
                ])
                
                # Отправляем уведомление
                loop.run_until_complete(
                    bot.send_message(
                        chat_id=user_id,
                        text=text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                )
                
                logger.info(f"Sent notification to user {user_id} about recurring payment")
                
            except Exception as e:
                logger.error(f"Error sending notification to user {payment_info['user_id']}: {e}")
        
        loop.close()
        
        logger.info(f"Processed {processed_count} recurring payments")
        
    except Exception as e:
        logger.error(f"Error in process_recurring_payments task: {e}")


@shared_task
def update_keywords_weights(expense_id: int, old_category_id: int, new_category_id: int):
    """
    Обновление весов ключевых слов после изменения категории пользователем.
    Запускается в фоне после редактирования.
    """
    try:
        from expenses.models import Expense, ExpenseCategory, CategoryKeyword
        
        # Попробуем импортировать spellchecker, если не получится - используем без проверки
        try:
            from bot.utils.spellchecker import check_and_correct_text
        except ImportError:
            def check_and_correct_text(text):
                return text  # Возвращаем текст без изменений
        
        # Получаем объекты
        expense = Expense.objects.get(id=expense_id)
        new_category = ExpenseCategory.objects.get(id=new_category_id)
        old_category = ExpenseCategory.objects.get(id=old_category_id) if old_category_id else None
        
        # Извлекаем и очищаем слова из описания
        words = extract_words_from_description(expense.description)
        
        # Проверяем правописание
        corrected_words = []
        for word in words:
            corrected = check_and_correct_text(word)
            if corrected and len(corrected) >= 3:  # Минимум 3 буквы
                corrected_words.append(corrected.lower())
        
        words = corrected_words
        
        # Обновляем ключевые слова для НОВОЙ категории (пользователь исправил)
        for word in words:
            keyword, created = CategoryKeyword.objects.get_or_create(
                category=new_category,
                keyword=word,
                defaults={'normalized_weight': 1.0, 'usage_count': 0}
            )
            
            # Увеличиваем счетчик использований
            keyword.usage_count += 1
            keyword.save()
            
            logger.info(f"Updated keyword '{word}' for category '{new_category.name}' (user {expense.profile.telegram_id})")
        
        # Пересчитываем нормализованные веса для конфликтующих слов
        recalculate_normalized_weights(expense.profile.id, words)
        
        # Проверяем лимит 50 слов на категорию
        check_category_keywords_limit(new_category)
        if old_category:
            check_category_keywords_limit(old_category)
        
        logger.info(f"Successfully updated keywords weights for expense {expense_id}")
        
    except Exception as e:
        logger.error(f"Error in update_keywords_weights task: {e}")


def extract_words_from_description(description: str) -> List[str]:
    """Извлекает значимые слова из описания расхода"""
    # Удаляем числа, валюту, знаки препинания
    text = re.sub(r'\d+', '', description)
    text = re.sub(r'[₽$€£¥р\.,"\'!?;:\-\(\)]', ' ', text)
    
    # Разбиваем на слова
    words = text.lower().split()
    
    # Фильтруем стоп-слова
    stop_words = {
        'и', 'в', 'на', 'с', 'за', 'по', 'для', 'от', 'до', 'из',
        'или', 'но', 'а', 'к', 'у', 'о', 'об', 'под', 'над',
        'купил', 'купила', 'купили', 'взял', 'взяла', 'взяли',
        'потратил', 'потратила', 'потратили', 'оплатил', 'оплатила',
        'рубль', 'рубля', 'рублей', 'руб', 'р', 'тыс', 'тысяч'
    }
    
    # Фильтруем слова
    filtered_words = []
    for word in words:
        word = word.strip()
        if word and len(word) >= 3 and word not in stop_words:
            filtered_words.append(word)
    
    return filtered_words


def recalculate_normalized_weights(profile_id: int, words: List[str]):
    """Пересчитывает нормализованные веса для слов, встречающихся в нескольких категориях"""
    from expenses.models import CategoryKeyword
    from profiles.models import Profile
    
    try:
        profile = Profile.objects.get(id=profile_id)
        
        for word in words:
            # Находим все вхождения слова у данного пользователя
            keywords = CategoryKeyword.objects.filter(
                category__profile=profile,
                keyword=word
            )
            
            if keywords.count() > 1:
                # Слово встречается в нескольких категориях
                total_usage = sum(kw.usage_count for kw in keywords)
                
                if total_usage > 0:
                    for kw in keywords:
                        # Нормализуем вес от 0 до 1 на основе частоты использования
                        kw.normalized_weight = kw.usage_count / total_usage
                        kw.save()
                        
                    logger.info(f"Recalculated weights for word '{word}' across {keywords.count()} categories")
    
    except Exception as e:
        logger.error(f"Error recalculating weights: {e}")


def check_category_keywords_limit(category):
    """Проверяет и ограничивает количество ключевых слов в категории (максимум 50)"""
    from expenses.models import CategoryKeyword
    
    try:
        keywords = CategoryKeyword.objects.filter(category=category)
        
        if keywords.count() > 50:
            # Оставляем топ-50 по usage_count
            keywords_list = list(keywords)
            keywords_list.sort(key=lambda k: k.usage_count, reverse=True)
            
            # Удаляем слова с наименьшим использованием
            keywords_to_delete = keywords_list[50:]
            for kw in keywords_to_delete:
                logger.info(f"Deleting keyword '{kw.keyword}' from category '{category.name}' (low usage)")
                kw.delete()
            
            logger.info(f"Limited keywords for category '{category.name}' to 50 items")
    
    except Exception as e:
        logger.error(f"Error checking category keywords limit: {e}")