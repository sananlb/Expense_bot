"""
Сервис для работы с доходами
"""
import logging
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any

from asgiref.sync import sync_to_async
from django.db.models import Q, Sum, Count
from django.utils import timezone

from expenses.models import Income, IncomeCategory, Profile
from bot.utils.db_utils import get_or_create_user_profile_sync
from bot.utils.category_helpers import get_category_display_name, get_category_name_without_emoji
from bot.utils.language import get_text
from bot.utils.emoji_utils import EMOJI_PREFIX_RE
from bot.utils.input_sanitizer import InputSanitizer

# Предзагрузка Celery задач для устранения "холодного старта"
# Импортируем заранее, чтобы при первом вызове не было задержки 6+ секунд
try:
    from expense_bot.celery_tasks import learn_income_keywords_on_create, update_income_keywords
except ImportError:
    # На случай если Celery не установлен (например, в тестах)
    learn_income_keywords_on_create = None
    update_income_keywords = None

logger = logging.getLogger(__name__)


@sync_to_async
def create_income(
    user_id: int,
    amount: Decimal,
    category_id: int = None,
    description: str = None,
    income_date: date = None,
    ai_categorized: bool = False,
    ai_confidence: float = None,
    currency: str = 'RUB'
) -> Optional[Income]:
    """
    Создать новый доход

    Args:
        user_id: ID пользователя в Telegram
        amount: Сумма дохода
        category_id: ID категории дохода
        description: Описание дохода
        income_date: Дата дохода (если None - текущая дата)
        ai_categorized: Был ли доход категоризирован AI
        ai_confidence: Уверенность AI в категоризации
        currency: Валюта дохода

    Returns:
        Income объект или None при ошибке
    """
    try:
        # Получаем или создаем профиль пользователя
        profile = get_or_create_user_profile_sync(user_id)
        
        # Обрабатываем дату
        if income_date is None:
            income_date = date.today()
        
        # Проверка 1: Не вносить доходы в будущем
        if income_date > date.today():
            logger.warning(f"User {user_id} tried to add income in future: {income_date}")
            raise ValueError("Нельзя вносить доходы в будущем")
        
        # Проверка 2: Не вносить доходы старше 1 года
        one_year_ago = date.today() - timedelta(days=365)
        if income_date < one_year_ago:
            logger.warning(f"User {user_id} tried to add income older than 1 year: {income_date}")
            raise ValueError("Нельзя вносить доходы старше 1 года")
        
        # Проверка 3: Не вносить доходы до даты регистрации пользователя
        profile_created_date = profile.created_at.date() if profile.created_at else date.today()
        if income_date < profile_created_date:
            logger.warning(f"User {user_id} tried to add income before registration: {income_date}, registered: {profile_created_date}")
            raise ValueError(f"Нельзя вносить доходы до даты регистрации ({profile_created_date.strftime('%d.%m.%Y')})")
        
        # Проверяем общий лимит операций (доходы + расходы) в 100 записей в день
        today_incomes_count = Income.objects.filter(
            profile=profile,
            income_date=income_date
        ).count()
        
        # Также проверяем количество расходов
        from expenses.models import Expense
        today_expenses_count = Expense.objects.filter(
            profile=profile,
            expense_date=income_date
        ).count()
        
        total_operations = today_incomes_count + today_expenses_count
        
        if total_operations >= 100:
            logger.warning(f"User {user_id} reached daily operations limit (100)")
            raise ValueError("Достигнут лимит записей в день (максимум 100). Попробуйте завтра.")
        
        # Проверяем длину описания
        if description and len(description) > 500:
            description = description[:500]

        # Проверка максимальной суммы (лимит БД: NUMERIC(12,2))
        MAX_AMOUNT = Decimal('9999999999.99')
        if amount > MAX_AMOUNT:
            logger.warning(f"User {user_id} tried to add income with amount too large: {amount}")
            raise ValueError("⚠️ Сумма слишком велика")

        # Определяем время для дохода
        if income_date == date.today():
            income_time = datetime.now().time()
        else:
            # Для прошлых дат используем 12:00
            income_time = time(12, 0)
        
        # Получаем категорию с валидацией household (аналогично expense.py)
        category = None
        if category_id:
            try:
                category = IncomeCategory.objects.select_related('profile').get(
                    id=category_id,
                    is_active=True
                )

                # Проверяем что категория принадлежит пользователю или члену его семьи
                is_valid_category = False

                # Случай 1: Категория принадлежит самому пользователю
                if category.profile_id == profile.id:
                    is_valid_category = True
                # Случай 2: Семейный бюджет - категория от члена семьи
                elif profile.household_id is not None:
                    if category.profile.household_id == profile.household_id:
                        is_valid_category = True
                        logger.debug(f"Income category {category_id} belongs to household member, allowed")

                if not is_valid_category:
                    logger.warning(
                        f"User {user_id} (profile {profile.id}) tried to use income category {category_id} "
                        f"belonging to another user (profile {category.profile_id})"
                    )
                    raise ValueError("Нельзя использовать категорию другого пользователя")

            except IncomeCategory.DoesNotExist:
                logger.warning(f"Income category {category_id} not found for user {user_id}")
                raise ValueError(f"Категория дохода с ID {category_id} не существует")
        
        # Создаем доход
        income = Income.objects.create(
            profile=profile,
            amount=amount,
            category=category,
            description=description or '',
            income_date=income_date,
            income_time=income_time,
            ai_categorized=ai_categorized,
            ai_confidence=ai_confidence,
            currency=currency.upper()
        )

        # Если была AI-категоризация, обучаем систему
        if ai_categorized and category and learn_income_keywords_on_create:
            try:
                # Запускаем обучение в фоне через Celery (не блокирует пользователя!)
                learn_income_keywords_on_create.apply_async(
                    args=(income.id,),
                    countdown=0
                )
                logger.info(
                    f"Scheduled background keyword learning for AI-categorized income "
                    f"{income.id} (category: {category.name})"
                )
            except Exception as e:
                logger.warning(f"Could not schedule income keyword learning task: {e}")

        # Сбрасываем флаг напоминания о внесении операций
        from expenses.tasks import clear_expense_reminder
        clear_expense_reminder(user_id)

        logger.info(f"Created income {income.id} for user {user_id}: {amount} {currency}")
        return income
        
    except ValueError:
        raise  # Пробрасываем ValueError дальше для обработки в роутере
    except Exception as e:
        logger.error(f"Error creating income for user {user_id}: {e}")
        return None


# Алиас для обратной совместимости
add_income = create_income


@sync_to_async
def get_user_incomes(
    user_id: int,
    start_date: date = None,
    end_date: date = None,
    category_id: int = None,
    limit: int = 200
) -> List[Income]:
    """
    Получить доходы пользователя
    
    Args:
        user_id: ID пользователя в Telegram
        start_date: Начальная дата периода
        end_date: Конечная дата периода
        category_id: ID категории для фильтрации
        limit: Максимальное количество записей
        
    Returns:
        Список объектов Income
    """
    try:
        profile = get_or_create_user_profile_sync(user_id)
        
        # Базовый запрос
        query = Income.objects.filter(profile=profile)
        
        # Фильтрация по датам
        if start_date:
            query = query.filter(income_date__gte=start_date)
        if end_date:
            query = query.filter(income_date__lte=end_date)
            
        # Фильтрация по категории
        if category_id:
            query = query.filter(category_id=category_id)
        
        # Сортировка и лимит
        incomes = query.select_related('category').order_by(
            '-income_date', '-income_time'
        )[:limit]
        
        return list(incomes)
        
    except Exception as e:
        logger.error(f"Error getting incomes for user {user_id}: {e}")
        return []


@sync_to_async
def get_incomes_summary(
    user_id: int,
    start_date: date,
    end_date: date
) -> Dict:
    """
    Получить сводку по доходам за период
    
    Args:
        user_id: ID пользователя в Telegram
        start_date: Начальная дата периода
        end_date: Конечная дата периода
        
    Returns:
        Словарь с суммарными данными
    """
    try:
        profile = get_or_create_user_profile_sync(user_id)
        
        # Получаем доходы за период
        incomes = Income.objects.filter(
            profile=profile,
            income_date__gte=start_date,
            income_date__lte=end_date
        ).select_related('category')
        
        # Если нет доходов
        if not incomes.exists():
            return {
                'total': 0,
                'count': 0,
                'by_category': [],
                'currency': profile.currency
            }

        # Общая сумма и количество
        total_amount = incomes.aggregate(total=Sum('amount'))['total'] or 0
        total_count = incomes.count()

        # Группировка по категориям
        category_stats = {}

        # Определяем язык пользователя
        user_lang = profile.language_code or 'ru'

        for income in incomes:
            # По категориям
            category_name = get_category_display_name(income.category, user_lang) if income.category else f"❓ {get_text('no_category', user_lang)}"
            if category_name not in category_stats:
                category_stats[category_name] = {'amount': 0, 'count': 0}
            category_stats[category_name]['amount'] += float(income.amount)
            category_stats[category_name]['count'] += 1
        
        # Сортируем категории по сумме (убывание)
        by_category = [
            {
                'name': name,
                'amount': stats['amount'],
                'count': stats['count'],
                'percentage': round(stats['amount'] / float(total_amount) * 100, 1)
            }
            for name, stats in sorted(
                category_stats.items(),
                key=lambda x: x[1]['amount'],
                reverse=True
            )
        ]

        return {
            'total': float(total_amount),
            'count': total_count,
            'by_category': by_category,
            'currency': profile.currency
        }
        
    except Exception as e:
        logger.error(f"Error getting incomes summary for user {user_id}: {e}")
        return {
            'total': 0,
            'count': 0,
            'by_category': [],
            'currency': 'RUB'
        }


async def get_today_income_summary(user_id: int) -> Dict:
    """
    Получить сводку по доходам за сегодня (async версия как у расходов)

    Args:
        user_id: ID пользователя в Telegram

    Returns:
        Словарь с суммами по валютам
    """
    from expenses.models import Profile

    try:
        profile = await Profile.objects.aget(telegram_id=user_id)
        today = date.today()

        @sync_to_async
        def get_today_incomes():
            return list(
                Income.objects.filter(
                    profile=profile,
                    income_date=today
                ).select_related('category')
            )

        incomes = await get_today_incomes()

        # Группируем по валютам
        currency_totals = {}
        for income in incomes:
            currency = income.currency or 'RUB'
            if currency not in currency_totals:
                currency_totals[currency] = 0.0
            currency_totals[currency] += float(income.amount)

        return {
            'currency_totals': currency_totals,
            'count': len(incomes)
        }

    except Profile.DoesNotExist:
        return {'currency_totals': {}, 'count': 0}
    except Exception as e:
        logger.error(f"Error getting today income summary for user {user_id}: {e}")
        return {'currency_totals': {}, 'count': 0}


async def get_date_income_summary(user_id: int, target_date: date) -> Dict:
    """
    Получить сводку по доходам за конкретную дату (async версия)

    Args:
        user_id: ID пользователя в Telegram
        target_date: Дата для получения сводки

    Returns:
        Словарь с суммами по валютам
    """
    from expenses.models import Profile

    try:
        profile = await Profile.objects.aget(telegram_id=user_id)

        @sync_to_async
        def get_incomes_for_date():
            return list(
                Income.objects.filter(
                    profile=profile,
                    income_date=target_date
                ).select_related('category')
            )

        incomes = await get_incomes_for_date()

        # Группируем по валютам
        currency_totals = {}
        for income in incomes:
            currency = income.currency or 'RUB'
            if currency not in currency_totals:
                currency_totals[currency] = 0.0
            currency_totals[currency] += float(income.amount)

        return {
            'currency_totals': currency_totals,
            'count': len(incomes)
        }

    except Profile.DoesNotExist:
        return {'currency_totals': {}, 'count': 0}
    except Exception as e:
        logger.error(f"Error getting income summary for user {user_id} on {target_date}: {e}")
        return {'currency_totals': {}, 'count': 0}


@sync_to_async
def get_incomes_by_period(
    user_id: int,
    period: str = 'month'
) -> Dict:
    """
    Получить доходы за стандартный период
    
    Args:
        user_id: ID пользователя в Telegram
        period: Период ('today', 'week', 'month', 'year')
        
    Returns:
        Словарь с суммарными данными
    """
    try:
        today = timezone.now().date()
        
        if period == 'today':
            start_date = today
            end_date = today
        elif period == 'week':
            start_date = today - timedelta(days=today.weekday())
            end_date = today
        elif period == 'month':
            start_date = today.replace(day=1)
            end_date = today
        elif period == 'year':
            start_date = today.replace(month=1, day=1)
            end_date = today
        else:
            # По умолчанию - текущий месяц
            start_date = today.replace(day=1)
            end_date = today
            
        # Вызываем синхронно, так как мы в синхронной функции
        profile = Profile.objects.get(telegram_id=user_id)
        incomes = Income.objects.filter(
            profile=profile,
            income_date__gte=start_date,
            income_date__lte=end_date
        )
        
        # Общая сумма и количество
        total_amount = 0
        for income in incomes:
            total_amount += float(income.amount)
            
        # По категориям
        user_lang = profile.language_code or 'ru'
        by_category = {}
        for income in incomes:
            cat_name = get_category_display_name(income.category, user_lang) if income.category else get_text('no_category', user_lang)
            if cat_name not in by_category:
                by_category[cat_name] = 0
            by_category[cat_name] += float(income.amount)
            
        return {
            'total': total_amount,
            'count': incomes.count(),
            'by_category': [{'name': k, 'total': v} for k, v in by_category.items()],
            'currency': profile.currency
        }
        
    except Exception as e:
        logger.error(f"Error getting incomes by period for user {user_id}: {e}")
        return {
            'total': 0,
            'count': 0,
            'by_category': [],
            'currency': 'RUB'
        }


@sync_to_async
def update_income(
    user_id: int,
    income_id: int,
    **kwargs
) -> bool:
    """
    Обновить доход
    
    Args:
        user_id: ID пользователя в Telegram
        income_id: ID дохода
        **kwargs: Поля для обновления
        
    Returns:
        True при успешном обновлении, False при ошибке
    """
    try:
        profile = get_or_create_user_profile_sync(user_id)
        
        # Получаем доход
        income = Income.objects.get(
            id=income_id,
            profile=profile
        )
        
        # Сохраняем старую категорию для обучения
        old_category = income.category if hasattr(income, 'category') else None
        old_category_id = old_category.id if old_category else None

        # Обновляем поля
        for field, value in kwargs.items():
            if hasattr(income, field):
                # Для category_id получаем объект категории
                if field == 'category_id' and value:
                    try:
                        category_obj = IncomeCategory.objects.get(
                            id=value,
                            profile=profile,
                            is_active=True
                        )
                        setattr(income, 'category', category_obj)
                    except IncomeCategory.DoesNotExist:
                        logger.warning(f"Income category {value} not found for user {user_id}")
                        continue
                else:
                    setattr(income, field, value)

        # Сохраняем изменения ПЕРЕД запуском Celery задачи
        income.save()

        # Если изменилась категория, обучаем систему В ФОНЕ через Celery
        # ВАЖНО: Проверяем category_id (приходит из роутера), а не category!
        if 'category_id' in kwargs and old_category_id != income.category_id and update_income_keywords:
            try:
                # Запускаем обучение в фоне (не блокирует пользователя!)
                update_income_keywords.apply_async(
                    kwargs={
                        'income_id': income.id,
                        'old_category_id': old_category_id,
                        'new_category_id': income.category_id
                    },
                    countdown=0
                )

                logger.info(
                    f"Scheduled background learning for income category change: "
                    f"{old_category} -> {income.category} (income {income_id})"
                )
            except Exception as e:
                logger.warning(f"Could not schedule income keyword learning task: {e}")
        
        logger.info(f"Updated income {income_id} for user {user_id}")
        return True
        
    except Income.DoesNotExist:
        logger.warning(f"Income {income_id} not found for user {user_id}")
        return False
    except Exception as e:
        logger.error(f"Error updating income {income_id} for user {user_id}: {e}")
        return False


@sync_to_async
def get_income_by_id(
    income_id: int,
    telegram_id: int
) -> Optional[Income]:
    """
    Получить доход по ID
    
    Args:
        income_id: ID дохода
        telegram_id: ID пользователя в Telegram
        
    Returns:
        Объект Income или None
    """
    try:
        profile = get_or_create_user_profile_sync(telegram_id)
        
        income = Income.objects.filter(
            id=income_id,
            profile=profile
        ).select_related('category').first()
        
        return income
        
    except Exception as e:
        logger.error(f"Error getting income {income_id} for user {telegram_id}: {e}")
        return None


@sync_to_async
def delete_income(
    telegram_id: int,
    income_id: int
) -> bool:
    """
    Удалить доход
    
    Args:
        telegram_id: ID пользователя в Telegram
        income_id: ID дохода
        
    Returns:
        True при успешном удалении, False при ошибке
    """
    try:
        profile = get_or_create_user_profile_sync(telegram_id)
        
        # Удаляем доход
        deleted_count, _ = Income.objects.filter(
            id=income_id,
            profile=profile
        ).delete()
        
        if deleted_count > 0:
            logger.info(f"Deleted income {income_id} for user {telegram_id}")
            return True
        else:
            logger.warning(f"Income {income_id} not found for user {telegram_id}")
            return False
            
    except Exception as e:
        logger.error(f"Error deleting income {income_id} for user {telegram_id}: {e}")
        return False


@sync_to_async
def get_last_income(telegram_id: int) -> Optional[Income]:
    """
    Получить последний доход пользователя
    
    Args:
        telegram_id: ID пользователя в Telegram
        
    Returns:
        Последний доход или None
    """
    try:
        profile = get_or_create_user_profile_sync(telegram_id)
        
        income = Income.objects.filter(
            profile=profile
        ).select_related('category').order_by(
            '-income_date', '-income_time'
        ).first()
        
        return income
        
    except Exception as e:
        logger.error(f"Error getting last income for user {telegram_id}: {e}")
        return None


@sync_to_async
def get_last_income_by_description(telegram_id: int, description: str) -> Optional[Income]:
    """
    Найти последний доход пользователя по описанию
    
    Args:
        telegram_id: ID пользователя
        description: Описание для поиска
        
    Returns:
        Последний доход с похожим описанием или None
    """
    try:
        profile = get_or_create_user_profile_sync(telegram_id)
        
        # Нормализуем описание для поиска - убираем пробелы и приводим к нижнему регистру
        search_desc = description.strip().lower()
        
        # Получаем все доходы пользователя
        incomes = Income.objects.filter(
            profile=profile
        ).select_related('category').order_by('-income_date', '-created_at')
        
        # Ищем доход с похожим описанием (регистронезависимый поиск)
        for income in incomes:
            if income.description:
                income_desc = income.description.strip().lower()
                # Проверяем точное совпадение или вхождение
                if income_desc == search_desc or search_desc in income_desc or income_desc in search_desc:
                    logger.info(f"Found similar income: '{income.description}' for search: '{description}'")
                    return income
        
        logger.debug(f"No similar income found for: '{description}'")
        return None
    except Exception as e:
        logger.error(f"Error finding income by description: {e}")
        return None


@sync_to_async
def get_today_incomes_summary(user_id: int) -> Dict:
    """
    Получить сводку по доходам за сегодня
    
    Args:
        user_id: ID пользователя в Telegram
        
    Returns:
        Словарь с данными о доходах за сегодня
    """
    try:
        profile = get_or_create_user_profile_sync(user_id)
        today = timezone.now().date()
        
        # Получаем доходы за сегодня
        incomes = Income.objects.filter(
            profile=profile,
            income_date=today
        ).select_related('category')
        
        # Если нет доходов
        if not incomes.exists():
            return {
                'totals': {},
                'categories': [],
                'count': 0,
                'incomes': []
            }
        
        # Группируем по валютам
        user_lang = profile.language_code or 'ru'
        currency_totals = {}
        categories = {}

        for income in incomes:
            currency = income.currency

            # Суммируем по валютам
            if currency not in currency_totals:
                currency_totals[currency] = 0
            currency_totals[currency] += float(income.amount)

            # Суммируем по категориям
            cat_name = get_category_display_name(income.category, user_lang) if income.category else f"❓ {get_text('no_category', user_lang)}"
            if cat_name not in categories:
                categories[cat_name] = 0
            categories[cat_name] += float(income.amount)

        # Сортируем категории по сумме
        sorted_categories = [
            {'name': name, 'amount': amount}
            for name, amount in sorted(
                categories.items(),
                key=lambda x: x[1],
                reverse=True
            )
        ]

        # Последние доходы
        last_incomes = [
            {
                'id': inc.id,
                'amount': float(inc.amount),
                'currency': inc.currency,
                'category': get_category_display_name(inc.category, user_lang) if inc.category else f"❓ {get_text('no_category', user_lang)}",
                'description': inc.description,
                'time': inc.income_time.strftime('%H:%M')
            }
            for inc in incomes.order_by('-income_time')[:5]
        ]
        
        return {
            'totals': currency_totals,
            'categories': sorted_categories,
            'count': incomes.count(),
            'incomes': last_incomes
        }
        
    except Exception as e:
        logger.error(f"Error getting today incomes summary for user {user_id}: {e}")
        return {
            'totals': {},
            'categories': [],
            'count': 0,
            'incomes': []
        }


@sync_to_async
def get_month_incomes_summary(
    user_id: int,
    month: int = None,
    year: int = None
) -> Dict:
    """
    Получить сводку по доходам за месяц
    
    Args:
        user_id: ID пользователя в Telegram
        month: Месяц (если None - текущий)
        year: Год (если None - текущий)
        
    Returns:
        Словарь с данными о доходах за месяц
    """
    try:
        profile = get_or_create_user_profile_sync(user_id)
        
        # Определяем месяц и год
        today = timezone.now().date()
        if month is None:
            month = today.month
        if year is None:
            year = today.year
            
        # Определяем границы месяца
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        
        # Получаем доходы за месяц
        incomes = Income.objects.filter(
            profile=profile,
            income_date__gte=start_date,
            income_date__lte=end_date
        ).select_related('category')
        
        # Если нет доходов
        if not incomes.exists():
            return {
                'totals': {},
                'categories': [],
                'count': 0,
                'month': month,
                'year': year
            }

        # Группируем по валютам
        user_lang = profile.language_code or 'ru'
        currency_totals = {}
        categories = {}

        for income in incomes:
            currency = income.currency

            # Суммируем по валютам
            if currency not in currency_totals:
                currency_totals[currency] = 0
            currency_totals[currency] += float(income.amount)

            # Суммируем по категориям
            cat_name = get_category_display_name(income.category, user_lang) if income.category else f"❓ {get_text('no_category', user_lang)}"
            if cat_name not in categories:
                categories[cat_name] = 0
            categories[cat_name] += float(income.amount)

        # Сортируем категории по сумме
        sorted_categories = [
            {'name': name, 'amount': amount}
            for name, amount in sorted(
                categories.items(),
                key=lambda x: x[1],
                reverse=True
            )
        ]

        return {
            'totals': currency_totals,
            'categories': sorted_categories,
            'count': incomes.count(),
            'month': month,
            'year': year
        }
        
    except Exception as e:
        logger.error(f"Error getting month incomes summary for user {user_id}: {e}")
        return {
            'totals': {},
            'categories': [],
            'count': 0,
            'month': month,
            'year': year
        }


@sync_to_async
def get_last_incomes(
    telegram_id: int,
    limit: int = 30
) -> List[Income]:
    """
    Получить последние доходы пользователя
    
    Args:
        telegram_id: ID пользователя в Telegram
        limit: Максимальное количество записей
        
    Returns:
        Список последних доходов
    """
    try:
        profile = get_or_create_user_profile_sync(telegram_id)
        
        incomes = Income.objects.filter(
            profile=profile
        ).select_related('category').order_by(
            '-income_date', '-income_time'
        )[:limit]
        
        return list(incomes)
        
    except Exception as e:
        logger.error(f"Error getting last incomes for user {telegram_id}: {e}")
        return []


@sync_to_async
def find_similar_incomes(
    telegram_id: int,
    description: str,
    days_back: int = 365
) -> List[Dict]:
    """
    Найти похожие доходы по описанию
    
    Args:
        telegram_id: ID пользователя в Telegram
        description: Описание для поиска
        days_back: Количество дней назад для поиска
        
    Returns:
        Список похожих доходов с уникальными суммами
    """
    try:
        profile = get_or_create_user_profile_sync(telegram_id)
        
        # Определяем период поиска
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        # Поиск похожих доходов
        similar_incomes = Income.objects.filter(
            profile=profile,
            income_date__gte=start_date,
            income_date__lte=end_date
        )
        
        # Фильтруем по описанию
        if description:
            words = description.lower().split()
            q_filter = Q()
            for word in words:
                if len(word) >= 3:  # Игнорируем короткие слова
                    q_filter |= Q(description__icontains=word)
            
            if q_filter:
                similar_incomes = similar_incomes.filter(q_filter)
        
        # Группируем по уникальным суммам
        user_lang = profile.language_code or 'ru'
        unique_amounts = {}
        for income in similar_incomes.select_related('category'):
            amount_key = f"{income.amount}_{income.currency}"
            if amount_key not in unique_amounts:
                unique_amounts[amount_key] = {
                    'amount': float(income.amount),
                    'currency': income.currency,
                    'category': get_category_display_name(income.category, user_lang) if income.category else None,
                    'description': income.description,
                    'count': 1,
                    'last_date': income.income_date
                }
            else:
                unique_amounts[amount_key]['count'] += 1
                if income.income_date > unique_amounts[amount_key]['last_date']:
                    unique_amounts[amount_key]['last_date'] = income.income_date
                    unique_amounts[amount_key]['description'] = income.description
        
        # Сортируем по дате последнего использования (последний доход первым)
        sorted_amounts = sorted(
            unique_amounts.values(),
            key=lambda x: x['last_date'],
            reverse=True
        )[:5]
        
        return sorted_amounts
        
    except Exception as e:
        logger.error(f"Error finding similar incomes for user {telegram_id}: {e}")
        return []


@sync_to_async
def get_recurring_incomes(telegram_id: int) -> List[Income]:
    """
    Получить регулярные доходы пользователя
    
    Args:
        telegram_id: ID пользователя в Telegram
        
    Returns:
        Список регулярных доходов
    """
    try:
        profile = get_or_create_user_profile_sync(telegram_id)
        
        incomes = Income.objects.filter(
            profile=profile,
            is_recurring=True
        ).select_related('category').order_by('recurrence_day')
        
        return list(incomes)
        
    except Exception as e:
        logger.error(f"Error getting recurring incomes for user {telegram_id}: {e}")
        return []


@sync_to_async
def get_user_income_categories(telegram_id: int) -> List[IncomeCategory]:
    """
    Получить категории доходов пользователя
    
    Args:
        telegram_id: ID пользователя в Telegram
        
    Returns:
        Список категорий доходов
    """
    try:
        profile = get_or_create_user_profile_sync(telegram_id)
        
        # Получаем все категории доходов пользователя
        categories = IncomeCategory.objects.filter(
            profile=profile,
            is_active=True
        )

        # Сортируем по алфавиту по отображаемому названию без эмодзи, с учетом языка профиля
        user_lang = profile.language_code or 'ru'
        categories_list = list(categories)
        try:
            categories_list.sort(key=lambda c: (get_category_name_without_emoji(c, user_lang) or '').lower())
        except Exception:
            categories_list.sort(key=lambda c: (c.name or '').lower())

        return categories_list
        
    except Exception as e:
        logger.error(f"Error getting income categories for user {telegram_id}: {e}")
        return []


def create_income_category(
    telegram_id: int,
    name: str,
    icon: Optional[str] = None
) -> IncomeCategory:
    """
    Создать новую категорию доходов
    
    Args:
        telegram_id: ID пользователя в Telegram
        name: Название категории
        icon: Иконка категории (эмодзи)
        
    Returns:
        Созданная категория
        
    Raises:
        ValueError: Если категория с таким названием уже существует
    """
    try:
        profile = get_or_create_user_profile_sync(telegram_id)
        
        # Разбираем имя и иконку используя централизованный паттерн (включает ZWJ/VS-16)
        match = EMOJI_PREFIX_RE.match(name)
        parsed_icon = ''
        text = name
        if match:
            parsed_icon = match.group().strip()
            text = name[len(match.group()):].strip()
        if icon and not parsed_icon:
            parsed_icon = icon

        if len(text) > InputSanitizer.MAX_CATEGORY_LENGTH:
            raise ValueError(f"Название категории слишком длинное (максимум {InputSanitizer.MAX_CATEGORY_LENGTH} символов)")

        text_sanitized = InputSanitizer.sanitize_category_name(text).strip()
        if not text_sanitized:
            raise ValueError("Название категории не может быть пустым")

        text = text_sanitized

        display_name = f"{parsed_icon} {text}".strip() if parsed_icon else text
        existing = IncomeCategory.objects.filter(
            profile=profile,
            name__iexact=display_name,
            is_active=True
        ).exists()
        if existing:
            raise ValueError("Категория с таким названием уже существует")

        # Определяем язык текста
        has_cyrillic = bool(re.search(r'[а-яА-ЯёЁ]', text))
        has_latin = bool(re.search(r'[a-zA-Z]', text))
        if has_cyrillic and not has_latin:
            original_language = 'ru'
        elif has_latin and not has_cyrillic:
            original_language = 'en'
        else:
            # По умолчанию язык профиля
            original_language = profile.language_code or 'ru'

        # Создаём как непереводимую пользовательскую категорию
        kwargs = dict(
            profile=profile,
            icon=parsed_icon or '',
            is_active=True,
            is_translatable=False,
            original_language=original_language,
        )
        if original_language == 'ru':
            kwargs['name_ru'] = text
        else:
            kwargs['name_en'] = text

        category = IncomeCategory.objects.create(**kwargs)

        # Генерируем ключевые слова для новой категории (пропускаем в тестах)
        import sys
        if 'pytest' not in sys.modules:
            try:
                from bot.services.income_categorization import generate_keywords_for_income_category
                import asyncio

                # Запускаем асинхронную функцию в синхронном контексте
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                keywords = loop.run_until_complete(
                    generate_keywords_for_income_category(category, name)
                )
                loop.close()

                logger.info(f"Generated {len(keywords)} keywords for income category '{display_name}'")
            except Exception as e:
                logger.warning(f"Could not generate keywords for income category: {e}")
        
        logger.info(f"Created income category '{category.name}' for user {telegram_id}")
        return category
        
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error creating income category for user {telegram_id}: {e}")
        raise ValueError("Ошибка при создании категории")


def update_income_category(
    telegram_id: int,
    category_id: int,
    new_name: Optional[str] = None,
    new_icon: Optional[str] = None
) -> IncomeCategory:
    """
    Обновить категорию доходов
    
    Args:
        telegram_id: ID пользователя в Telegram
        category_id: ID категории
        new_name: Новое название категории
        new_icon: Новая иконка категории
        
    Returns:
        Обновленная категория
        
    Raises:
        ValueError: Если категория не найдена или название уже существует
    """
    try:
        profile = get_or_create_user_profile_sync(telegram_id)
        
        category = IncomeCategory.objects.filter(
            id=category_id,
            profile=profile,
            is_active=True
        ).first()
        
        if not category:
            raise ValueError("Категория не найдена")
            
        if new_name:
            # Разбираем эмодзи и текст используя централизованный паттерн (включает ZWJ/VS-16)
            match = EMOJI_PREFIX_RE.match(new_name)
            parsed_icon = None
            text = new_name
            if match:
                parsed_icon = match.group().strip()
                text = new_name[len(match.group()):].strip()

            if len(text) > InputSanitizer.MAX_CATEGORY_LENGTH:
                raise ValueError(f"Название категории слишком длинное (максимум {InputSanitizer.MAX_CATEGORY_LENGTH} символов)")

            text_sanitized = InputSanitizer.sanitize_category_name(text).strip()
            if not text_sanitized:
                raise ValueError("Название категории не может быть пустым")

            text = text_sanitized

            # Проверяем уникальность по собранному отображаемому имени
            display_name = f"{parsed_icon} {text}".strip() if parsed_icon else text
            existing = IncomeCategory.objects.filter(
                profile=profile,
                name__iexact=display_name,
                is_active=True
            ).exclude(id=category_id).exists()
            if existing:
                raise ValueError("Категория с таким названием уже существует")

            # Определяем язык текста
            has_cyrillic = bool(re.search(r'[а-яА-ЯёЁ]', text))
            has_latin = bool(re.search(r'[a-zA-Z]', text))
            if has_cyrillic and not has_latin:
                lang = 'ru'
                category.name_ru = text
                category.name_en = category.name_en or text
            elif has_latin and not has_cyrillic:
                lang = 'en'
                category.name_en = text
                category.name_ru = category.name_ru or text
            else:
                # Смешанный/другой — фиксируем как язык профиля
                lang = profile.language_code or 'ru'
                if lang == 'ru':
                    category.name_ru = text
                else:
                    category.name_en = text

            # Обновляем иконку
            if parsed_icon is not None:
                category.icon = parsed_icon
            elif new_icon is not None:
                category.icon = new_icon

            # Пользовательское редактирование — делаем непереводимым и фиксируем исходный язык
            category.original_language = lang
            category.is_translatable = False

        elif new_icon is not None:
            # Только обновляем иконку
            category.icon = new_icon
            
        category.save()
        
        logger.info(f"Updated income category {category_id} for user {telegram_id}")
        return category
        
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error updating income category {category_id} for user {telegram_id}: {e}")
        raise ValueError("Ошибка при обновлении категории")


@sync_to_async
def delete_income_category(telegram_id: int, category_id: int) -> bool:
    """
    Удалить категорию доходов (мягкое удаление)
    
    Args:
        telegram_id: ID пользователя в Telegram
        category_id: ID категории
        
    Returns:
        True если успешно удалено
        
    Raises:
        ValueError: Если категория не найдена
    """
    try:
        profile = get_or_create_user_profile_sync(telegram_id)
        
        category = IncomeCategory.objects.filter(
            id=category_id,
            profile=profile,
            is_active=True
        ).first()
        
        if not category:
            raise ValueError("Категория не найдена")
            
        # Проверяем, есть ли доходы с этой категорией
        has_incomes = Income.objects.filter(category=category).exists()
        
        if has_incomes:
            # Мягкое удаление - просто деактивируем
            category.is_active = False
            category.save()
            
            # Убираем категорию у всех связанных доходов
            Income.objects.filter(category=category).update(category=None)
        else:
            # Если нет связанных доходов, удаляем полностью
            category.delete()
            
        logger.info(f"Deleted income category {category_id} for user {telegram_id}")
        return True
        
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error deleting income category {category_id} for user {telegram_id}: {e}")
        raise ValueError("Ошибка при удалении категории")
