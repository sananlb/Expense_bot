"""
Сервис для генерации PDF отчетов
"""
import os
import base64
import logging
import calendar
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import tempfile
import asyncio
import json

from playwright.async_api import async_playwright
from jinja2 import Template
from django.conf import settings
from django.db.models import Sum, Count, Q
from dateutil.relativedelta import relativedelta
from bot.utils.formatters import truncate_text
from bot.utils.language import get_text
from bot.utils.logging_safe import log_safe_id

from expenses.models import Expense, ExpenseCategory, Profile, Cashback, Income, IncomeCategory, UserSettings

logger = logging.getLogger(__name__)


class PDFReportService:
    """Сервис для генерации PDF отчетов"""

    TEMPLATE_PATH = Path(__file__).parent.parent.parent / "reports" / "templates" / "report_modern.html"
    LOGO_PATH = Path(__file__).parent.parent.parent / "reports" / "templates" / "logo.png"
    CHARTJS_PATH = Path(__file__).parent.parent.parent / "reports" / "templates" / "static" / "chart.min.js"

    def __init__(self):
        self.template = self._load_template()
        self.chart_js_code = self._load_chartjs()

    def _load_template(self) -> Template:
        """Загрузить HTML шаблон"""
        with open(self.TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        return Template(content)

    def _load_chartjs(self) -> str:
        """
        Загрузить Chart.js код из локального файла.

        Raises:
            FileNotFoundError: Если файл Chart.js не найден
            RuntimeError: Если произошла ошибка при чтении файла

        Returns:
            str: Код Chart.js библиотеки
        """
        try:
            with open(self.CHARTJS_PATH, 'r', encoding='utf-8') as f:
                chart_code = f.read()
                if not chart_code:
                    raise ValueError("Chart.js file is empty")
                return chart_code
        except FileNotFoundError:
            logger.error(f"Chart.js file not found at {self.CHARTJS_PATH}")
            raise FileNotFoundError(
                f"Chart.js library not found at {self.CHARTJS_PATH}. "
                "Cannot generate PDF with charts."
            )
        except Exception as e:
            logger.error(f"Error loading Chart.js: {e}")
            raise RuntimeError(f"Failed to load Chart.js library: {e}")
    
    async def generate_monthly_report(self, user_id: int, year: int, month: int, lang: str = 'ru') -> Optional[bytes]:
        """
        Генерация месячного отчета для пользователя
        
        Args:
            user_id: ID пользователя в Telegram
            year: Год отчета
            month: Месяц отчета (1-12)
            
        Returns:
            PDF файл в виде байтов или None при ошибке
        """
        try:
            # Получаем данные из БД
            report_data = await self._prepare_report_data(user_id, year, month, lang)
            if not report_data:
                logger.warning(
                    "No data for report: %s period=%s/%s",
                    log_safe_id(user_id, "user"),
                    year,
                    month,
                )
                return None
            
            # Генерируем HTML
            html_content = await self._render_html(report_data, lang)
            
            # Конвертируем в PDF
            pdf_bytes = await self._html_to_pdf(html_content)
            
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"Error generating PDF report: {e}")
            return None
    
    async def _prepare_report_data(self, user_id: int, year: int, month: int, lang: str = 'ru') -> Optional[Dict]:
        """Подготовить данные для отчета из БД"""
        try:
            # Получаем профиль пользователя
            profile = await Profile.objects.select_related('household').aget(telegram_id=user_id)

            # Определяем период
            start_date = date(year, month, 1)
            last_day = calendar.monthrange(year, month)[1]
            end_date = date(year, month, last_day)

            # Статистика по категориям (нежная палитра с чуть более темными оттенками)
            # Определяем цвета здесь, чтобы они были доступны для всех разделов отчета
            category_colors = [
                '#4A90E2',  # мягкий синий (темнее)
                '#FF6B35',  # кораллово-оранжевый (темнее)
                '#7ED321',  # светло-зеленый (темнее)
                '#8B5CF6',  # средний фиолетовый (темнее)
                '#F5A623',  # золотой (темнее)
                '#50C8E8',  # небесно-голубой (темнее)
                '#BD5EFF',  # сливовый (темнее)
                '#86D36B',  # бледно-зеленый (темнее)
                '#E94B9A',  # светло-орхидный (темнее)
                '#FF8C00',  # оранжевый (темнее)
                '#5DADE2',  # светло-синий (темнее)
                '#D4AC0D',  # пшеничный (темнее)
                '#C39BD3',  # светло-фиолетовый (темнее)
                '#17A2B8',  # светлый морской зеленый (темнее)
                '#E91E63'   # ярко-розовый (темнее)
            ]

            # Определяем режим отображения (личный/семейный) и имя семьи
            try:
                settings_obj = await UserSettings.objects.aget(profile=profile)
            except UserSettings.DoesNotExist:
                settings_obj = None

            household_mode = bool(getattr(profile, 'household_id', None)) and settings_obj and getattr(settings_obj, 'view_scope', 'personal') == 'household'
            household_name = None
            if household_mode and getattr(profile, 'household', None) and getattr(profile.household, 'name', None):
                household_name = profile.household.name

            primary_currency = getattr(profile, 'currency', None) or 'RUB'

            def build_filters(prefix: str, start: date, end: date) -> Dict[str, object]:
                """������������ ������ ��� ��������/������� � ������ ������ ��������� � �������� ������."""
                filters: Dict[str, object] = {
                    f"{prefix}_date__gte": start,
                    f"{prefix}_date__lte": end,
                    "currency": primary_currency,
                }
                if household_mode and getattr(profile, 'household', None):
                    filters['profile__household'] = profile.household
                else:
                    filters['profile'] = profile
                return filters

            def build_cashback_filters() -> Dict[str, object]:
                filters: Dict[str, object] = {'month': month}
                if household_mode and getattr(profile, 'household', None):
                    filters['profile__household'] = profile.household
                else:
                    filters['profile'] = profile
                return filters

            # Получаем расходы за период
            expenses = Expense.objects.filter(**build_filters('expense', start_date, end_date))

            # Общая статистика
            total_stats = await expenses.aaggregate(
                total_amount=Sum('amount'),
                total_count=Count('id')
            )

            total_amount = float(total_stats['total_amount'] or 0)
            total_count = total_stats['total_count'] or 0

            # Инициализируем переменные по умолчанию
            top_categories = []
            total_cashback = 0
            change_percent = 0
            change_direction = ""
            prev_summaries = []
            daily_expenses = {}
            daily_categories = {}
            income_categories = []
            daily_incomes = {}

            # Обрабатываем расходы только если они есть
            if total_count > 0:
                # Получаем весь кешбэк пользователя для этого месяца
                user_cashbacks = []
                async for cb in Cashback.objects.filter(
                    **build_cashback_filters()
                ).select_related('category'):
                    user_cashbacks.append(cb)

                # Создаем словарь кешбеков по категориям
                cashback_by_category = {}
                for cb in user_cashbacks:
                    if cb.category_id:
                        if cb.category_id not in cashback_by_category:
                            cashback_by_category[cb.category_id] = []
                        cashback_by_category[cb.category_id].append(cb)

                # Получаем все категории для определения мультиязычности
                categories_with_multilang = {}
                async for exp in expenses.select_related('category'):
                    if exp.category and exp.category.id not in categories_with_multilang:
                        cat = exp.category
                        # Используем стандартный метод для получения отображаемого имени
                        display_name = cat.get_display_name(lang)
                        categories_with_multilang[cat.id] = display_name
            
                # Получаем категории с учетом мультиязычности
                categories_stats = expenses.values('category__id', 'category__name').annotate(
                    amount=Sum('amount')
                ).order_by('-amount')
            
                # Определяем количество категорий для логики отображения
                total_categories_count = await categories_stats.acount()

                # Единое поведение: всегда показываем топ-9 + "Остальные покупки"
                max_display_categories = 9
            
                top_categories = []
                other_amount = 0
                other_cashback = 0
            
                idx = 0
                async for cat_stat in categories_stats:
                    if idx < max_display_categories:
                        amount = float(cat_stat['amount'])
                        category_id = cat_stat['category__id']
                    
                        # Рассчитываем кешбек для категории
                        category_cashback = 0
                        if category_id in cashback_by_category:
                            for cb in cashback_by_category[category_id]:
                                cb_amount = amount
                                if cb.limit_amount and cb.limit_amount > 0:
                                    cb_amount = min(amount, float(cb.limit_amount))
                                category_cashback += cb_amount * (float(cb.cashback_percent) / 100)
                    
                        # Используем мультиязычное имя если доступно
                        cat_name = categories_with_multilang.get(category_id, cat_stat['category__name'])

                        # Обрезаем длинные названия категорий для корректного отображения в PDF
                        if cat_name:
                            cat_name_truncated = truncate_text(cat_name, max_length=25, suffix="...")
                        else:
                            cat_name_truncated = get_text('no_category', lang)

                        top_categories.append({
                            'name': cat_name_truncated,
                            'icon': '',  # Пустое, т.к. get_display_name() уже включает эмодзи
                            'amount': amount,
                            'cashback': category_cashback,
                            'color': category_colors[idx] if idx < len(category_colors) else '#95a5a6'
                        })
                    else:
                        amount = float(cat_stat['amount'])
                        category_id = cat_stat['category__id']
                        other_amount += amount
                    
                        # Рассчитываем кешбек для "Другое"
                        if category_id in cashback_by_category:
                            for cb in cashback_by_category[category_id]:
                                cb_amount = amount
                                if cb.limit_amount and cb.limit_amount > 0:
                                    cb_amount = min(amount, float(cb.limit_amount))
                                other_cashback += cb_amount * (float(cb.cashback_percent) / 100)
                
                    idx += 1
            
                # Добавляем единый блок "Остальные покупки"
                if other_amount > 0:
                    other_name = 'Остальные покупки'
                    other_icon = ''
                    top_categories.append({
                        'name': other_name,
                        'icon': other_icon,
                        'amount': other_amount,
                        'cashback': other_cashback,
                        'color': '#95a5a6'
                    })
            
                # Расходы по дням
                daily_expenses = {}
                daily_categories = {}
            
                # Получаем все расходы с категориями
                expenses_list = expenses.select_related('category')
                async for expense in expenses_list:
                    day = expense.expense_date.day
                
                    if day not in daily_expenses:
                        daily_expenses[day] = 0
                        daily_categories[day] = {}
                
                    daily_expenses[day] += float(expense.amount)
                
                    # Используем мультиязычное имя категории
                    if expense.category:
                        cat_name = categories_with_multilang.get(expense.category.id, expense.category.name)
                    else:
                        from bot.utils.language import get_text
                        cat_name = get_text('no_category', lang)
                    
                    if cat_name not in daily_categories[day]:
                        daily_categories[day][cat_name] = 0
                    daily_categories[day][cat_name] += float(expense.amount)
            
                # Общий кешбек
                total_cashback = sum(cat['cashback'] for cat in top_categories)
            
                # Сравнение с предыдущим месяцем
                prev_month = month - 1 if month > 1 else 12
                prev_year = year if month > 1 else year - 1
            
                prev_start = date(prev_year, prev_month, 1)
                prev_last_day = calendar.monthrange(prev_year, prev_month)[1]
                prev_end = date(prev_year, prev_month, prev_last_day)
            
                prev_total = await Expense.objects.filter(
                    **build_filters('expense', prev_start, prev_end)
                ).aaggregate(total=Sum('amount'))
            
                prev_amount = float(prev_total['total'] or 0)
            
                if prev_amount > 0:
                    change_percent = round((total_amount - prev_amount) / prev_amount * 100, 1)
                    change_direction = "↑" if change_percent > 0 else "↓"
                else:
                    change_percent = 0
                    change_direction = ""
            
                # Статистика по месяцам (последние 6 месяцев, от новых к старым)
                # Оптимизация: собираем данные за все 6 месяцев одним запросом
                prev_summaries = []

                # Определяем границы периода для запроса (6 месяцев назад)
                six_months_ago = date(year, month, 1) - relativedelta(months=5)
                six_months_start = date(six_months_ago.year, six_months_ago.month, 1)

                # Получаем все расходы за 6 месяцев одним запросом
                all_expenses_6m = []
                async for item in Expense.objects.filter(
                    **build_filters('expense', six_months_start, end_date)
                ).values('expense_date__year', 'expense_date__month', 'currency').annotate(
                    total=Sum('amount'),
                    count=Count('id')
                ):
                    all_expenses_6m.append(item)

                # Получаем все доходы за 6 месяцев одним запросом
                all_incomes_6m = []
                async for item in Income.objects.filter(
                    **build_filters('income', six_months_start, end_date)
                ).values('income_date__year', 'income_date__month', 'currency').annotate(
                    total=Sum('amount'),
                    count=Count('id')
                ):
                    all_incomes_6m.append(item)

                # Группируем данные по месяцам
                expenses_by_month = {}
                for expense in all_expenses_6m:
                    key = (expense['expense_date__year'], expense['expense_date__month'])
                    if key not in expenses_by_month:
                        expenses_by_month[key] = {}
                    curr = expense['currency'] or primary_currency
                    if curr not in expenses_by_month[key]:
                        expenses_by_month[key][curr] = {'total': 0, 'count': 0}
                    expenses_by_month[key][curr]['total'] = float(expense['total'])
                    expenses_by_month[key][curr]['count'] = expense['count']

                incomes_by_month = {}
                for income in all_incomes_6m:
                    key = (income['income_date__year'], income['income_date__month'])
                    if key not in incomes_by_month:
                        incomes_by_month[key] = {}
                    curr = income['currency'] or primary_currency
                    if curr not in incomes_by_month[key]:
                        incomes_by_month[key][curr] = {'total': 0, 'count': 0}
                    incomes_by_month[key][curr]['total'] = float(income['total'])
                    incomes_by_month[key][curr]['count'] = income['count']

                # Теперь формируем данные для каждого месяца
                for i in range(0, 6):
                    stats_date = date(year, month, 1) - relativedelta(months=i)
                    month_key = (stats_date.year, stats_date.month)

                    # Используем уже полученные данные вместо новых запросов
                    currency_operations = {}

                    # Обрабатываем расходы из кеша
                    if month_key in expenses_by_month:
                        for curr, data in expenses_by_month[month_key].items():
                            if curr not in currency_operations:
                                currency_operations[curr] = {'expense': 0, 'income': 0, 'count': 0}
                            currency_operations[curr]['expense'] = data['total']
                            currency_operations[curr]['count'] += data['count']

                    # Обрабатываем доходы из кеша
                    if month_key in incomes_by_month:
                        for curr, data in incomes_by_month[month_key].items():
                            if curr not in currency_operations:
                                currency_operations[curr] = {'expense': 0, 'income': 0, 'count': 0}
                            currency_operations[curr]['income'] = data['total']
                            currency_operations[curr]['count'] += data['count']
                
                    # Сортируем валюты по количеству операций и берем топ-2
                    sorted_currencies = sorted(currency_operations.items(), key=lambda x: x[1]['count'], reverse=True)[:2]
                
                    # Форматируем данные для отображения
                    expenses_str = ''
                    incomes_str = ''
                    balance_str = ''
                
                    currency_symbols = {
                        'RUB': '₽',
                        'USD': '$',
                        'EUR': '€',
                        'GBP': '£',
                        'CNY': '¥',
                        'TRY': '₺',
                        'UAH': '₴',
                        'KZT': '₸',
                        'BYN': 'Br',
                        'GEL': '₾',
                        'AMD': '֏',
                        'AZN': '₼'
                    }
                
                    # Сначала собираем все части для каждого типа данных
                    expenses_parts = []
                    incomes_parts = []
                    balance_parts = []
                
                    for idx, (curr, data) in enumerate(sorted_currencies):
                        symbol = currency_symbols.get(curr, curr)
                    
                        expense_amount = data['expense']
                        income_amount = data['income']
                        balance = income_amount - expense_amount
                    
                        # Пропускаем валюты где все суммы нулевые
                        if expense_amount == 0 and income_amount == 0:
                            continue
                    
                        # Добавляем части только если они не нулевые
                        if expense_amount > 0:
                            expenses_parts.append(f"{round(expense_amount):,.0f}{symbol}")
                        
                        if income_amount > 0:
                            incomes_parts.append(f"{round(income_amount):,.0f}{symbol}")
                    
                        if balance != 0:
                            balance_parts.append(f"{round(balance):+,.0f}{symbol}")
                
                    # Формируем финальные строки только из непустых частей
                    expenses_str = ' / '.join(expenses_parts) if expenses_parts else ''
                    incomes_str = ' / '.join(incomes_parts) if incomes_parts else ''
                    balance_str = ' / '.join(balance_parts) if balance_parts else ''
                
                    # Если совсем нет данных, показываем прочерки
                    if not expenses_str:
                        expenses_str = '-'
                        incomes_str = '-'
                        balance_str = '-'
                
                    month_names = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн',
                                   'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']
                
                    prev_summaries.append({
                        'label': f"{month_names[stats_date.month - 1]} {stats_date.year}",
                        'expenses': expenses_str,
                        'incomes': incomes_str,
                        'balance': balance_str,
                        'is_current': stats_date.month == month and stats_date.year == year
                    })
            
            # Получаем доходы за период
            incomes = Income.objects.filter(
                **build_filters('income', start_date, end_date)
            ).select_related('category')
            
            # Статистика по доходам
            income_stats = await incomes.aaggregate(
                total_amount=Sum('amount'),
                total_count=Count('id')
            )
            
            income_total_amount = float(income_stats['total_amount'] or 0)
            income_total_count = income_stats['total_count'] or 0

            # Проверяем есть ли данные для отчета (расходы или доходы)
            if total_count == 0 and income_total_count == 0:
                return None

            # Получаем все категории доходов для определения мультиязычности
            income_categories_with_multilang = {}
            async for income in incomes.select_related('category'):
                if income.category and income.category.id not in income_categories_with_multilang:
                    cat = income.category
                    # Используем стандартный метод для получения отображаемого имени
                    display_name = cat.get_display_name(lang)
                    income_categories_with_multilang[cat.id] = display_name

            # Доходы по категориям
            income_category_stats = incomes.values('category__id', 'category__name').annotate(
                amount=Sum('amount')
            ).order_by('-amount')
            
            income_categories = []
            async for cat_stat in income_category_stats:
                # Используем переведенное название если есть, иначе fallback
                if cat_stat['category__id'] and cat_stat['category__id'] in income_categories_with_multilang:
                    category_name = income_categories_with_multilang[cat_stat['category__id']]
                else:
                    category_name = cat_stat['category__name'] if cat_stat['category__name'] else (
                        '💵 Other income' if lang == 'en' else '💵 Прочие доходы'
                    )

                # Обрезаем длинные названия категорий для корректного отображения в PDF
                if category_name:
                    category_name_truncated = truncate_text(category_name, max_length=25, suffix="...")
                else:
                    category_name_truncated = '💵 Доходы' if lang == 'ru' else '💵 Income'


                income_categories.append({
                    'name': category_name_truncated,
                    'icon': '',  # Пустое, т.к. get_display_name() уже включает эмодзи
                    'amount': float(cat_stat['amount']),
                    'color': category_colors[len(income_categories) % len(category_colors)] if category_colors else '#95a5a6'
                })
            
            # Доходы по дням
            daily_incomes = {}
            async for income in incomes:
                day = income.income_date.day
                if day not in daily_incomes:
                    daily_incomes[day] = 0
                daily_incomes[day] += float(income.amount)
            
            # Баланс
            net_balance = income_total_amount - total_amount
            
            # Форматируем данные для шаблона
            if lang == 'en':
                months = ['January', 'February', 'March', 'April', 'May', 'June',
                          'July', 'August', 'September', 'October', 'November', 'December']
                prev_months = ['January', 'February', 'March', 'April', 'May', 'June',
                               'July', 'August', 'September', 'October', 'November', 'December']
            else:
                months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                          'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
                prev_months = ['январю', 'февралю', 'марту', 'апрелю', 'маю', 'июню',
                               'июлю', 'августу', 'сентябрю', 'октябрю', 'ноябрю', 'декабрю']
            
            report_data = {
                'period': f"1 - {end_date.day} {months[month-1]} {year}",
                'total_amount': f"{round(total_amount):,.0f}",
                'total_count': total_count,
                'total_cashback': f"{round(total_cashback):,.0f}",
                'change_percent': abs(change_percent),
                'change_direction': change_direction,
                'prev_month_name': prev_months[prev_month-1],
                'categories': top_categories,
                'daily_expenses': daily_expenses,
                'daily_categories': daily_categories,
                'days_in_month': end_date.day,
                'logo_base64': await self._get_logo_base64(),
                # Режим отчёта
                'household_mode': household_mode,
                'household_name': household_name,
                # Новые поля для доходов
                'income_total_amount': f"{round(income_total_amount):,.0f}",
                'income_total_count': income_total_count,
                'income_categories': income_categories,
                'daily_incomes': daily_incomes,
                'net_balance': f"{round(net_balance):,.0f}",
                'has_incomes': income_total_count > 0,
                'prev_summaries': prev_summaries
            }
            
            return report_data
            
        except Profile.DoesNotExist:
            logger.error("Profile not found for %s", log_safe_id(user_id, "user"))
            return None
        except Exception as e:
            logger.error(f"Error preparing report data: {e}")
            return None
    
    async def _get_logo_base64(self) -> str:
        """Получить логотип в base64"""
        try:
            with open(self.LOGO_PATH, 'rb') as f:
                logo_bytes = f.read()
            return base64.b64encode(logo_bytes).decode('utf-8')
        except OSError as logo_error:
            logger.debug("Failed to read PDF logo from %s: %s", self.LOGO_PATH, logo_error)
            return ""
    
    async def _render_html(self, report_data: Dict, lang: str = 'ru') -> str:
        """Рендеринг HTML из шаблона с данными"""
        # Безопасно извлекаем флаги режима отчёта (личный/семейный)
        household_mode = report_data.get('household_mode', False)
        household_name = report_data.get('household_name')
        # Вычисляем общую сумму для процентов
        total_raw = 0
        for cat in report_data['categories']:
            total_raw += cat['amount']
        
        # Подготавливаем данные для категорий с процентами
        for cat in report_data['categories']:
            cat['percent'] = round((cat['amount'] / total_raw * 100) if total_raw > 0 else 0, 1)
            cat['amount_formatted'] = f"{round(cat['amount']):,.0f}"
            cat['cashback_formatted'] = f"{round(cat['cashback']):,.0f}"
        
        # Подготавливаем данные для графиков
        categories_json = json.dumps([{
            'name': cat['name'],
            'amount': cat['amount'],
            'color': cat['color'],
            'icon': cat['icon']
        } for cat in report_data['categories']], ensure_ascii=False)
        
        # Подготавливаем данные для ежедневного графика с разбивкой по категориям
        daily_data = []
        for day in range(1, report_data['days_in_month'] + 1):
            daily_data.append(report_data['daily_expenses'].get(day, 0))
        
        # Подготавливаем разбивку по категориям для каждого дня
        category_breakdown = {}
        for cat in report_data['categories']:
            cat_name = cat['name']
            category_breakdown[cat_name] = []
            for day in range(1, report_data['days_in_month'] + 1):
                if day in report_data.get('daily_categories', {}):
                    amount = report_data['daily_categories'][day].get(cat_name, 0)
                    category_breakdown[cat_name].append(amount)
                else:
                    category_breakdown[cat_name].append(0)
        
        # Подготавливаем данные о кешбеке для каждого дня
        cashback_data = []
        for day in range(1, report_data['days_in_month'] + 1):
            day_cashback = 0
            if day in report_data.get('daily_categories', {}):
                for cat_name, cat_amount in report_data['daily_categories'][day].items():
                    # Находим категорию и её кешбек
                    for cat in report_data['categories']:
                        if cat['name'] == cat_name and cat['cashback'] > 0:
                            if cat['amount'] > 0:
                                cashback_rate = cat['cashback'] / cat['amount']
                                day_cashback += cat_amount * cashback_rate
                            break
            cashback_data.append(round(day_cashback, 2))
        
        daily_json = json.dumps({
            'days': list(range(1, report_data['days_in_month'] + 1)),
            'expenses': daily_data,
            'categoryBreakdown': category_breakdown,
            'cashback': cashback_data
        }, ensure_ascii=False)
        
        # Подготавливаем данные по доходам
        income_total_raw = 0
        for cat in report_data.get('income_categories', []):
            income_total_raw += cat['amount']
            
        # Добавляем проценты и форматирование для категорий доходов
        for cat in report_data.get('income_categories', []):
            cat['percent'] = round((cat['amount'] / income_total_raw * 100) if income_total_raw > 0 else 0, 1)
            cat['amount_formatted'] = f"{round(cat['amount']):,.0f}"
        
        # JSON для категорий доходов
        income_categories_json = json.dumps([{
            'name': cat['name'],
            'amount': cat['amount'],
            'color': cat['color'],
            'icon': cat['icon']
        } for cat in report_data.get('income_categories', [])], ensure_ascii=False)
        
        # Подготавливаем данные для ежедневного графика доходов
        daily_incomes_list = []
        for day in range(1, report_data['days_in_month'] + 1):
            daily_incomes_list.append(report_data.get('daily_incomes', {}).get(day, 0))
        
        daily_incomes_json = json.dumps(daily_incomes_list, ensure_ascii=False)
        
        # Подготавливаем переводы для шаблона
        if lang == 'en':
            translations = {
                'report_title': 'Coins - Expense Report',
                'report_for_period': 'Report for period:',
                'total_spent': 'Total Spent',
                'total_income': 'Total Income', 
                'balance': 'Balance',
                'expense_count': 'Number of Expenses',
                'monthly_cashback': 'Monthly Cashback',
                'expenses_by_category': 'Expenses by Category',
                'daily_expenses': 'Daily Expense Dynamics',
                'income_by_category': 'Income by Category', 
                'daily_income': 'Daily Income Dynamics',
                'monthly_statistics': 'Monthly Statistics',
                'month': 'Month',
                'expenses': 'Expenses',
                'income': 'Income',
                'generated_by': 'Generated by Coins bot • @showmecoinbot',
                'to_prev_month': f'vs {report_data.get("prev_month_name", "")}'
            }
        else:
            translations = {
                'report_title': 'Coins - Отчет о расходах',
                'report_for_period': 'Отчет за период:',
                'total_spent': 'Всего потрачено',
                'total_income': 'Всего доходов',
                'balance': 'Баланс месяца',
                'expense_count': 'Количество трат',
                'monthly_cashback': 'Кешбэк за месяц',
                'expenses_by_category': 'Расходы по категориям',
                'daily_expenses': 'Динамика расходов по дням',
                'income_by_category': 'Доходы по категориям',
                'daily_income': 'Динамика доходов по дням',
                'monthly_statistics': 'Статистика по месяцам',
                'month': 'Месяц',
                'expenses': 'Расходы',
                'income': 'Доходы',
                'generated_by': 'Сгенерировано ботом Coins • @showmecoinbot',
                'to_prev_month': f'к {report_data.get("prev_month_name", "")}'
            }

        # Рендерим шаблон с данными
        html = self.template.render(
            period=report_data['period'],
            total_amount=report_data['total_amount'],
            total_count=report_data['total_count'],
            total_cashback=report_data['total_cashback'],
            change_direction=report_data.get('change_direction', ''),
            change_percent=report_data.get('change_percent', 0),
            prev_month_name=report_data.get('prev_month_name', ''),
            categories=report_data['categories'],
            logo_base64=report_data.get('logo_base64', ''),
            categories_json=categories_json,
            daily_json=daily_json,
            # Новые поля для доходов
            income_total_amount=report_data.get('income_total_amount', '0'),
            income_total_count=report_data.get('income_total_count', 0),
            income_categories=report_data.get('income_categories', []),
            income_categories_json=income_categories_json,
            daily_incomes_json=daily_incomes_json,
            net_balance=report_data.get('net_balance', '0'),
            has_incomes=report_data.get('has_incomes', False),
            # Режим отчета
            household_mode=household_mode,
            household_name=household_name,
            # Chart.js код для встраивания
            chart_js_code=self.chart_js_code,
            # Переводы
            **translations,
            prev_summaries=report_data.get('prev_summaries', [])
        )
        
        return html
    
    
    async def _html_to_pdf(self, html_content: str) -> bytes:
        """
        Конвертация HTML в PDF используя Playwright.

        Chart.js встроен локально, нет зависимости от CDN:
        - try/finally для гарантированного закрытия браузера
        - set_default_timeout на странице
        - domcontentloaded для быстрой загрузки (Chart.js уже в HTML)
        - Явный timeout на все операции
        """
        async with async_playwright() as p:
            browser = None
            try:
                browser = await p.chromium.launch(headless=True)

                # Создаем страницу с высоким разрешением для лучшей четкости
                page = await browser.new_page(
                    viewport={'width': 1920, 'height': 1080},
                    device_scale_factor=2  # Удваиваем разрешение для четкости
                )

                # Устанавливаем глобальный таймаут для всех операций страницы
                page.set_default_timeout(15000)  # 15 секунд максимум

                # Загружаем HTML (Chart.js уже встроен в HTML, не ждем внешние ресурсы)
                await page.set_content(
                    html_content,
                    wait_until='domcontentloaded',
                    timeout=10000  # Явный timeout 10 секунд
                )

                # Проверяем что Chart.js загружен (должен быть мгновенно, т.к. inline)
                await page.wait_for_function(
                    "typeof Chart !== 'undefined'",
                    timeout=2000  # 2 секунды достаточно для inline скрипта
                )
                logger.debug("Chart.js loaded successfully from inline code")

                # Ждем отрисовки графиков
                await page.wait_for_timeout(2000)

                # Генерируем PDF (timeout контролируется через set_default_timeout выше)
                pdf_bytes = await page.pdf(
                    format='A4',
                    print_background=True,
                    margin={'top': '10px', 'bottom': '10px', 'left': '15px', 'right': '15px'},
                    scale=0.95
                )

                return pdf_bytes

            finally:
                # КРИТИЧНО: Всегда закрываем браузер, даже при ошибке
                if browser:
                    try:
                        await browser.close()
                        logger.debug("Browser closed successfully")
                    except Exception as e:
                        logger.error(f"Error closing browser: {e}")
