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

from expenses.models import Expense, ExpenseCategory, Profile, Cashback

logger = logging.getLogger(__name__)


class PDFReportService:
    """Сервис для генерации PDF отчетов"""
    
    TEMPLATE_PATH = Path(__file__).parent.parent.parent / "reports" / "templates" / "report_modern.html"
    LOGO_PATH = Path(__file__).parent.parent.parent / "reports" / "templates" / "logo.png"
    
    def __init__(self):
        self.template = self._load_template()
    
    def _load_template(self) -> Template:
        """Загрузить HTML шаблон"""
        with open(self.TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        return Template(content)
    
    async def generate_monthly_report(self, user_id: int, year: int, month: int) -> Optional[bytes]:
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
            report_data = await self._prepare_report_data(user_id, year, month)
            if not report_data:
                logger.warning(f"No data for report: user_id={user_id}, year={year}, month={month}")
                return None
            
            # Генерируем HTML
            html_content = await self._render_html(report_data)
            
            # Конвертируем в PDF
            pdf_bytes = await self._html_to_pdf(html_content)
            
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"Error generating PDF report: {e}")
            return None
    
    async def _prepare_report_data(self, user_id: int, year: int, month: int) -> Optional[Dict]:
        """Подготовить данные для отчета из БД"""
        try:
            # Получаем профиль пользователя
            profile = await Profile.objects.aget(telegram_id=user_id)
            
            # Определяем период
            start_date = date(year, month, 1)
            last_day = calendar.monthrange(year, month)[1]
            end_date = date(year, month, last_day)
            
            # Получаем расходы за период
            expenses = Expense.objects.filter(
                profile=profile,
                expense_date__gte=start_date,
                expense_date__lte=end_date
            )
            
            # Общая статистика
            total_stats = await expenses.aaggregate(
                total_amount=Sum('amount'),
                total_count=Count('id')
            )
            
            total_amount = float(total_stats['total_amount'] or 0)
            total_count = total_stats['total_count'] or 0
            
            if total_count == 0:
                return None
            
            # Статистика по категориям
            category_colors = [
                '#8B4513',  # коричневый
                '#4682B4',  # стальной синий
                '#9370DB',  # средний фиолетовый
                '#20B2AA',  # светлый морской
                '#F4A460',  # песочный
                '#708090',  # серо-синий
                '#DDA0DD',  # сливовый
                '#B0C4DE'   # светло-стальной синий
            ]
            
            # Получаем все кешбеки пользователя для этого месяца
            user_cashbacks = []
            async for cb in Cashback.objects.filter(
                profile=profile,
                month=month
            ).select_related('category'):
                user_cashbacks.append(cb)
            
            # Создаем словарь кешбеков по категориям
            cashback_by_category = {}
            for cb in user_cashbacks:
                if cb.category_id:
                    if cb.category_id not in cashback_by_category:
                        cashback_by_category[cb.category_id] = []
                    cashback_by_category[cb.category_id].append(cb)
            
            # Получаем топ-7 категорий
            categories_stats = expenses.values('category__id', 'category__name', 'category__icon').annotate(
                amount=Sum('amount')
            ).order_by('-amount')
            
            top_categories = []
            other_amount = 0
            other_cashback = 0
            
            idx = 0
            async for cat_stat in categories_stats:
                if idx < 7:
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
                    
                    top_categories.append({
                        'name': cat_stat['category__name'],
                        'icon': cat_stat['category__icon'] or '',
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
            
            # Добавляем "Другое" если есть
            if other_amount > 0:
                top_categories.append({
                    'name': 'Другое',
                    'icon': '🔍',
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
                
                cat_name = expense.category.name if expense.category else 'Без категории'
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
                profile=profile,
                expense_date__gte=prev_start,
                expense_date__lte=prev_end
            ).aaggregate(total=Sum('amount'))
            
            prev_amount = float(prev_total['total'] or 0)
            
            if prev_amount > 0:
                change_percent = round((total_amount - prev_amount) / prev_amount * 100, 1)
                change_direction = "↑" if change_percent > 0 else "↓"
            else:
                change_percent = 0
                change_direction = ""
            
            # Форматируем данные для шаблона
            months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                      'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
            
            prev_months = ['январю', 'февралю', 'марту', 'апрелю', 'маю', 'июню',
                           'июлю', 'августу', 'сентябрю', 'октябрю', 'ноябрю', 'декабрю']
            
            report_data = {
                'period': f"1 - {end_date.day} {months[month-1]} {year}",
                'total_amount': f"{total_amount:,.0f}",
                'total_count': total_count,
                'total_cashback': f"{total_cashback:,.0f}",
                'change_percent': abs(change_percent),
                'change_direction': change_direction,
                'prev_month_name': prev_months[prev_month-1],
                'categories': top_categories,
                'daily_expenses': daily_expenses,
                'daily_categories': daily_categories,
                'days_in_month': end_date.day,
                'logo_base64': await self._get_logo_base64()
            }
            
            return report_data
            
        except Profile.DoesNotExist:
            logger.error(f"Profile not found for user_id: {user_id}")
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
        except:
            return ""
    
    async def _render_html(self, report_data: Dict) -> str:
        """Рендеринг HTML из шаблона с данными"""
        # Вычисляем общую сумму для процентов
        total_raw = 0
        for cat in report_data['categories']:
            total_raw += cat['amount']
        
        # Подготавливаем данные для категорий с процентами
        for cat in report_data['categories']:
            cat['percent'] = round((cat['amount'] / total_raw * 100) if total_raw > 0 else 0, 1)
            cat['amount_formatted'] = f"{cat['amount']:,.0f}"
            cat['cashback_formatted'] = f"{cat['cashback']:,.0f}"
        
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
            daily_json=daily_json
        )
        
        return html
    
    
    async def _html_to_pdf(self, html_content: str) -> bytes:
        """Конвертация HTML в PDF используя Playwright"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            # Создаем страницу с высоким разрешением для лучшей четкости
            page = await browser.new_page(
                viewport={'width': 1920, 'height': 1080},
                device_scale_factor=2  # Удваиваем разрешение для четкости
            )
            
            # Загружаем HTML
            await page.set_content(html_content, wait_until='networkidle')
            
            # Ждем загрузки графиков
            await page.wait_for_timeout(2000)
            
            # Генерируем PDF с оптимизацией для одной страницы
            pdf_bytes = await page.pdf(
                format='A4',
                print_background=True,
                margin={'top': '10px', 'bottom': '10px', 'left': '15px', 'right': '15px'},
                scale=0.95  # Немного уменьшаем масштаб для лучшего размещения на странице
            )
            
            await browser.close()
            
            return pdf_bytes