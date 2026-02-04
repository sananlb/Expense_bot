"""
Сервис для генерации PDF отчетов из HTML шаблонов
Использует xhtml2pdf для конвертации HTML в PDF
"""
import io
import os
import base64
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
from decimal import Decimal
from xhtml2pdf import pisa
from jinja2 import Template
from django.db.models import Sum, Count
from expenses.models import Expense, Profile, Cashback
from bot.utils.formatters import format_currency
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

logger = logging.getLogger(__name__)


class HTMLPDFReportService:
    """Сервис для генерации PDF отчетов из HTML"""
    
    TEMPLATE_PATH = Path(__file__).parent.parent.parent / "reports" / "templates" / "report_variant_2_minimalist.html"
    LOGO_PATH = Path(__file__).parent.parent.parent / "reports" / "templates" / "logo.png"
    
    def __init__(self):
        self.template = self._load_template()
    
    def _load_template(self) -> Template:
        """Загрузить HTML шаблон"""
        with open(self.TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        return Template(content)
    
    async def generate_monthly_report(self, user_id: int, year: int, month: int) -> Optional[bytes]:
        """Генерация месячного отчета"""
        try:
            # Получаем данные
            profile = await Profile.objects.aget(telegram_id=user_id)
            expenses = await self._get_month_expenses(profile, year, month)
            
            if not expenses:
                return None
            
            # Подготавливаем данные для шаблона
            report_data = await self._prepare_report_data(profile, expenses, year, month)
            
            # Генерируем графики
            charts = await self._generate_charts(report_data)
            
            # Рендерим HTML
            html_content = self.template.render(
                **report_data,
                **charts,
                logo_path=str(self.LOGO_PATH) if self.LOGO_PATH.exists() else None
            )
            
            # Конвертируем в PDF
            pdf_buffer = io.BytesIO()
            pisa_status = pisa.CreatePDF(
                html_content,
                dest=pdf_buffer,
                encoding='utf-8'
            )
            
            if pisa_status.err:
                logger.error(f"Error generating PDF: {pisa_status.err}")
                return None
            
            pdf_data = pdf_buffer.getvalue()
            pdf_buffer.close()
            
            return pdf_data
            
        except Exception as e:
            logger.error(f"Error generating PDF report: {e}")
            return None
    
    async def _get_month_expenses(self, profile: Profile, year: int, month: int) -> List[Expense]:
        """Получить расходы за месяц"""
        from asgiref.sync import sync_to_async
        
        @sync_to_async
        def get_expenses():
            return list(
                Expense.objects.filter(
                    profile=profile,
                    expense_date__year=year,
                    expense_date__month=month
                ).select_related('category').order_by('-expense_date', '-created_at')
            )
        
        expenses = await get_expenses()
        
        return expenses
    
    async def _prepare_report_data(self, profile: Profile, expenses: List[Expense], year: int, month: int) -> Dict:
        """Подготовить данные для отчета"""
        # Группируем по валютам
        currency_totals = {}
        categories_by_currency = {}
        daily_expenses = {}
        
        for expense in expenses:
            currency = expense.currency or profile.currency or 'RUB'
            
            # Суммируем по валютам
            if currency not in currency_totals:
                currency_totals[currency] = Decimal('0')
            currency_totals[currency] += expense.amount
            
            # Группируем по категориям и валютам
            if expense.category:
                if currency not in categories_by_currency:
                    categories_by_currency[currency] = {}
                
                cat_id = expense.category.id
                if cat_id not in categories_by_currency[currency]:
                    # Получаем язык пользователя для правильного отображения
                    from bot.utils.language import get_user_language
                    from asgiref.sync import async_to_sync
                    user_lang = async_to_sync(get_user_language)(telegram_id)
                    
                    categories_by_currency[currency][cat_id] = {
                        'name': expense.category.get_display_name(user_lang),
                        'icon': expense.category.icon,
                        'amount': Decimal('0'),
                        'color': self._get_category_color(cat_id)
                    }
                categories_by_currency[currency][cat_id]['amount'] += expense.amount
            
            # Группируем по дням
            day_key = expense.expense_date.strftime('%Y-%m-%d')
            if day_key not in daily_expenses:
                daily_expenses[day_key] = {}
            if currency not in daily_expenses[day_key]:
                daily_expenses[day_key][currency] = Decimal('0')
            daily_expenses[day_key][currency] += expense.amount
        
        # Форматируем данные для шаблона
        month_names = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                      'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
        
        # Форматируем валюты
        formatted_totals = []
        for curr, amount in sorted(currency_totals.items()):
            formatted_totals.append({
                'currency': curr,
                'amount': format_currency(amount, curr),
                'raw_amount': float(amount)
            })
        
        # Форматируем категории
        formatted_categories = []
        for currency, cats in categories_by_currency.items():
            currency_total = currency_totals[currency]
            for cat_id, cat_data in cats.items():
                percent = (cat_data['amount'] / currency_total * 100) if currency_total > 0 else 0
                formatted_categories.append({
                    'name': f"{cat_data['icon']} {cat_data['name']}",
                    'amount': format_currency(cat_data['amount'], currency),
                    'percent': f"{percent:.1f}%",
                    'color': cat_data['color'],
                    'currency': currency
                })
        
        # Сортируем категории по сумме
        formatted_categories.sort(key=lambda x: x.get('raw_amount', 0), reverse=True)
        
        # Считаем потенциальный кешбэк
        cashback_total = await self._calculate_cashback(profile, expenses)
        
        return {
            'month_name': month_names[month - 1],
            'year': year,
            'expense_count': len(expenses),
            'currency_totals': formatted_totals,
            'categories': formatted_categories,
            'cashback_amount': format_currency(cashback_total, 'RUB'),
            'user_name': f"User {profile.telegram_id}",
            'report_date': datetime.now().strftime('%d.%m.%Y')
        }
    
    async def _generate_charts(self, report_data: Dict) -> Dict:
        """Генерация графиков"""
        charts = {}
        
        # График распределения по категориям
        if report_data['categories']:
            plt.figure(figsize=(8, 6))
            categories = [cat['name'] for cat in report_data['categories'][:5]]  # Топ 5
            amounts = [cat.get('raw_amount', 0) for cat in report_data['categories'][:5]]
            colors = [cat['color'] for cat in report_data['categories'][:5]]
            
            plt.pie(amounts, labels=categories, colors=colors, autopct='%1.1f%%')
            plt.title('Распределение расходов по категориям')
            
            # Сохраняем в base64
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', bbox_inches='tight', dpi=150)
            buffer.seek(0)
            charts['category_chart'] = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
        
        return charts
    
    def _get_category_color(self, category_id: int) -> str:
        """Получить цвет для категории"""
        colors = [
            '#FF6B6B', '#9B59B6', '#45B7D1', '#E74C3C', '#FECA57',
            '#FF9FF3', '#54A0FF', '#48DBFB', '#0ABDE3', '#EE5A6F'
        ]
        return colors[category_id % len(colors)]
    
    async def _calculate_cashback(self, profile: Profile, expenses: List[Expense]) -> Decimal:
        """Рассчитать потенциальный кешбэк"""
        from asgiref.sync import sync_to_async
        
        if not expenses:
            return Decimal('0')
        
        month = expenses[0].expense_date.month
        
        # Получаем кешбэки для месяца
        @sync_to_async
        def get_cashbacks():
            return list(
                Cashback.objects.filter(
                    profile=profile,
                    month=month
                ).select_related('category')
            )
        
        cashbacks = await get_cashbacks()
        
        # Считаем кешбэк
        total_cashback = Decimal('0')
        cashback_map = {cb.category_id: cb for cb in cashbacks}
        
        for expense in expenses:
            if expense.category_id in cashback_map:
                cb = cashback_map[expense.category_id]
                cashback_amount = expense.amount * cb.cashback_percent / 100
                
                if cb.limit_amount:
                    cashback_amount = min(cashback_amount, cb.limit_amount)
                
                total_cashback += cashback_amount
        
        return total_cashback
