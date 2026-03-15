"""
Сервис для генерации PDF отчетов с использованием WeasyPrint
"""
import os
import base64
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import tempfile
import json
import io

import matplotlib
matplotlib.use('Agg')  # Используем backend без GUI
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import rcParams
import seaborn as sns
import weasyprint
from jinja2 import Template
from django.conf import settings
from django.db.models import Sum, Count, Q
from dateutil.relativedelta import relativedelta
from bot.utils.logging_safe import log_safe_id

from expenses.models import Expense, ExpenseCategory, Profile, Cashback

logger = logging.getLogger(__name__)

# Настройка шрифтов для русского языка
rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False


class PDFReportService:
    """Сервис для генерации PDF отчетов"""
    
    TEMPLATE_PATH = Path(__file__).parent.parent.parent / "reports" / "templates" / "report_variant_1_modern.html"
    LOGO_PATH = Path(__file__).parent.parent.parent / "reports" / "templates" / "logo.png"
    
    def __init__(self):
        self.template = self._load_template()
    
    def _load_template(self) -> str:
        """Загрузить HTML шаблон"""
        with open(self.TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    
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
                logger.warning(
                    "No data for report: %s period=%s/%s",
                    log_safe_id(user_id, "user"),
                    year,
                    month,
                )
                return None
            
            # Генерируем графики
            chart_images = await self._generate_chart_images(report_data)
            
            # Генерируем HTML
            html_content = await self._render_html(report_data, chart_images)
            
            # Конвертируем в PDF
            pdf_bytes = await self._html_to_pdf(html_content)
            
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"Error generating PDF report: {e}")
            return None
    
    async def _generate_chart_images(self, report_data: Dict) -> Dict[str, str]:
        """Генерация графиков с использованием matplotlib"""
        charts = {}
        currency_symbol = report_data.get('currency_symbol', '₽')
        
        # Настройка стиля
        plt.style.use('seaborn-v0_8-white')
        
        # 1. Круговая диаграмма категорий
        if report_data['categories']:
            fig, ax = plt.subplots(figsize=(8, 6))
            
            categories = report_data['categories']
            labels = [f"{cat['icon']} {cat['name']}" for cat in categories]
            sizes = [cat['amount'] for cat in categories]
            colors = [cat['color'] for cat in categories]
            
            # Создаем круговую диаграмму
            wedges, texts, autotexts = ax.pie(
                sizes, 
                labels=labels, 
                colors=colors,
                autopct='%1.1f%%',
                startangle=90,
                textprops={'fontsize': 10}
            )
            
            # Улучшаем внешний вид процентов
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_weight('bold')
                autotext.set_fontsize(9)
            
            ax.set_title('Распределение расходов по категориям', fontsize=14, pad=20)
            
            # Сохраняем в base64
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', bbox_inches='tight', dpi=150, transparent=True)
            buffer.seek(0)
            charts['pie_chart'] = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
        
        # 2. График расходов по дням
        if report_data['daily_expenses']:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]})
            
            days = list(range(1, report_data['days_in_month'] + 1))
            daily_amounts = [report_data['daily_expenses'].get(day, 0) for day in days]
            
            # Stacked bar chart для категорий
            bottom = [0] * len(days)
            
            for cat in report_data['categories']:
                cat_name = cat['name']
                cat_amounts = []
                
                for day in days:
                    if day in report_data['daily_categories']:
                        amount = report_data['daily_categories'][day].get(cat_name, 0)
                        cat_amounts.append(amount)
                    else:
                        cat_amounts.append(0)
                
                ax1.bar(days, cat_amounts, bottom=bottom, label=f"{cat['icon']} {cat_name}", 
                       color=cat['color'], width=0.8)
                bottom = [b + a for b, a in zip(bottom, cat_amounts)]
            
            ax1.set_xlabel('День месяца', fontsize=12)
            ax1.set_ylabel(f"Сумма расходов ({currency_symbol})", fontsize=12)
            ax1.set_title('Расходы по дням месяца', fontsize=14, pad=10)
            ax1.grid(axis='y', alpha=0.3)
            ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
            
            # График кешбека внизу
            cashback_data = []
            for day in days:
                day_cashback = 0
                if day in report_data['daily_categories']:
                    for cat_name, cat_amount in report_data['daily_categories'][day].items():
                        # Ищем категорию в списке top_categories чтобы получить её кешбек
                        for cat in report_data['categories']:
                            if cat['name'] == cat_name and cat['cashback'] > 0:
                                # Пропорционально распределяем кешбек
                                if cat['amount'] > 0:
                                    cashback_rate = cat['cashback'] / cat['amount']
                                    day_cashback += cat_amount * cashback_rate
                                break
                cashback_data.append(day_cashback)
            
            ax2.bar(days, cashback_data, color='#10b981', width=0.8, alpha=0.8)
            ax2.set_xlabel('День месяца', fontsize=12)
            ax2.set_ylabel(f"Кешбек ({currency_symbol})", fontsize=12)
            ax2.set_title('Потенциальный кешбек по дням', fontsize=12, pad=5)
            ax2.grid(axis='y', alpha=0.3)
            
            plt.tight_layout()
            
            # Сохраняем в base64
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', bbox_inches='tight', dpi=150, transparent=True)
            buffer.seek(0)
            charts['bar_chart'] = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
        
        return charts
    
    async def _render_html(self, report_data: Dict, chart_images: Dict[str, str]) -> str:
        """Рендеринг HTML из шаблона с данными"""
        # Создаем упрощенный HTML шаблон для WeasyPrint
        html_template = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <style>
        @page {
            size: A4;
            margin: 20mm;
        }
        
        body {
            font-family: 'DejaVu Sans', Arial, sans-serif;
            margin: 0;
            padding: 0;
            color: #333;
            line-height: 1.6;
        }
        
        .header {
            display: flex;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #e5e7eb;
        }
        
        .logo {
            width: 60px;
            height: 60px;
            margin-right: 20px;
        }
        
        .title {
            flex: 1;
        }
        
        .title h1 {
            margin: 0;
            font-size: 28px;
            color: #1f2937;
        }
        
        .title p {
            margin: 5px 0 0 0;
            font-size: 16px;
            color: #6b7280;
        }
        
        .summary {
            background: #f9fafb;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 30px;
        }
        
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
        }
        
        .summary-item {
            text-align: center;
        }
        
        .summary-label {
            font-size: 14px;
            color: #6b7280;
            margin-bottom: 5px;
        }
        
        .summary-value {
            font-size: 24px;
            font-weight: bold;
            color: #1f2937;
        }
        
        .summary-trend {
            font-size: 14px;
            margin-top: 5px;
        }
        
        .trend-up {
            color: #ef4444;
        }
        
        .trend-down {
            color: #10b981;
        }
        
        .section {
            margin-bottom: 40px;
        }
        
        .section-title {
            font-size: 20px;
            font-weight: bold;
            margin-bottom: 20px;
            color: #1f2937;
        }
        
        .categories-list {
            background: #f9fafb;
            border-radius: 12px;
            padding: 20px;
        }
        
        .category-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid #e5e7eb;
        }
        
        .category-item:last-child {
            border-bottom: none;
        }
        
        .category-info {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .category-color {
            width: 16px;
            height: 16px;
            border-radius: 4px;
        }
        
        .category-name {
            font-size: 16px;
            color: #1f2937;
        }
        
        .category-right {
            text-align: right;
        }
        
        .category-amount {
            font-size: 16px;
            font-weight: bold;
            color: #1f2937;
        }
        
        .category-cashback {
            font-size: 12px;
            color: #10b981;
            margin-top: 2px;
        }
        
        .chart-container {
            margin: 20px 0;
            text-align: center;
        }
        
        .chart-container img {
            max-width: 100%;
            height: auto;
        }
        
        .footer {
            margin-top: 50px;
            padding-top: 20px;
            border-top: 1px solid #e5e7eb;
            text-align: center;
            font-size: 12px;
            color: #6b7280;
        }
    </style>
</head>
<body>
    <div class="header">
        {% if logo_base64 %}
        <img src="data:image/png;base64,{{ logo_base64 }}" alt="Coins Logo" class="logo">
        {% endif %}
        <div class="title">
            <h1>Coins - Отчет о расходах</h1>
            <p>Отчет за период: {{ period }}</p>
        </div>
    </div>
    
    <div class="summary">
        <div class="summary-grid">
            <div class="summary-item">
                <p class="summary-label">Общая сумма</p>
                <p class="summary-value">{{ total_amount }} {{ currency_symbol }}</p>
                {% if change_direction %}
                <p class="summary-trend {% if change_direction == '↑' %}trend-up{% else %}trend-down{% endif %}">
                    {{ change_direction }} {{ change_percent }}% к {{ prev_month_name }}
                </p>
                {% endif %}
            </div>
            <div class="summary-item">
                <p class="summary-label">Количество трат</p>
                <p class="summary-value">{{ total_count }}</p>
            </div>
            <div class="summary-item">
                <p class="summary-label">Потенциальный кешбек</p>
                <p class="summary-value">{{ total_cashback }} {{ currency_symbol }}</p>
            </div>
        </div>
    </div>
    
    <div class="section">
        <h2 class="section-title">📊 Распределение по категориям</h2>
        <div class="categories-list">
            {% for cat in categories %}
            <div class="category-item">
                <div class="category-info">
                    <div class="category-color" style="background: {{ cat.color }}"></div>
                    <span class="category-name">{{ cat.icon }} {{ cat.name }}</span>
                </div>
                <div class="category-right">
                    <div class="category-amount">{{ "{:,.0f}".format(cat.amount) }} {{ currency_symbol }}</div>
                    <div class="category-cashback">+{{ "{:,.0f}".format(cat.cashback) }} {{ currency_symbol }} кешбек</div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
    
    {% if pie_chart %}
    <div class="section">
        <div class="chart-container">
            <img src="data:image/png;base64,{{ pie_chart }}" alt="Круговая диаграмма">
        </div>
    </div>
    {% endif %}
    
    {% if bar_chart %}
    <div class="section">
        <h2 class="section-title">📈 Динамика расходов</h2>
        <div class="chart-container">
            <img src="data:image/png;base64,{{ bar_chart }}" alt="График расходов">
        </div>
    </div>
    {% endif %}
    
    <div class="footer">
        <p>Отчет сгенерирован ботом Coins • {{ datetime.now().strftime('%d.%m.%Y %H:%M') }}</p>
    </div>
</body>
</html>
        """
        
        # Подготавливаем данные для шаблона
        template_data = {
            'logo_base64': report_data.get('logo_base64', ''),
            'period': report_data['period'],
            'total_amount': report_data['total_amount'],
            'total_count': report_data['total_count'],
            'total_cashback': report_data['total_cashback'],
            'currency_symbol': report_data.get('currency_symbol', '₽'),
            'change_percent': report_data.get('change_percent', 0),
            'change_direction': report_data.get('change_direction', ''),
            'prev_month_name': report_data.get('prev_month_name', ''),
            'categories': report_data['categories'],
            'pie_chart': chart_images.get('pie_chart', ''),
            'bar_chart': chart_images.get('bar_chart', ''),
            'datetime': datetime
        }
        
        # Рендерим шаблон
        template = Template(html_template)
        html = template.render(**template_data)
        
        return html
    
    async def _html_to_pdf(self, html_content: str) -> bytes:
        """Конвертация HTML в PDF используя WeasyPrint"""
        # Создаем PDF
        pdf_document = weasyprint.HTML(string=html_content).write_pdf()
        return pdf_document
    
    async def _prepare_report_data(self, user_id: int, year: int, month: int) -> Optional[Dict]:
        """Подготовить данные для отчета из БД"""
        try:
            # Получаем профиль пользователя
            profile = await Profile.objects.aget(telegram_id=user_id)
            
            # Определяем период
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
            
            # Получаем расходы за период
            expenses = Expense.objects.filter(
                profile=profile,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
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

            # Получаем весь кешбэк пользователя для этого месяца
            user_cashbacks = await Cashback.objects.filter(
                profile=profile,
                month=month
            ).select_related('category').aall()
            
            # Создаем словарь кешбеков по категориям
            cashback_by_category = {}
            for cb in user_cashbacks:
                if cb.category_id:
                    if cb.category_id not in cashback_by_category:
                        cashback_by_category[cb.category_id] = []
                    cashback_by_category[cb.category_id].append(cb)
            
            # Получаем топ-7 категорий
            categories_stats = expenses.values('category__id', 'category__name').annotate(
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
                            category_cashback += cb_amount * (cb.cashback_percent / 100)

                    top_categories.append({
                        'name': cat_stat['category__name'],
                        'icon': '📊',
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
                            other_cashback += cb_amount * (cb.cashback_percent / 100)
                
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
                day = expense.created_at.date().day
                
                if day not in daily_expenses:
                    daily_expenses[day] = 0
                    daily_categories[day] = {}
                
                daily_expenses[day] += float(expense.amount)
                
                cat_name = expense.category.name
                if cat_name not in daily_categories[day]:
                    daily_categories[day][cat_name] = 0
                daily_categories[day][cat_name] += float(expense.amount)
            
            # Общий кешбек
            total_cashback = sum(cat['cashback'] for cat in top_categories)
            
            # Сравнение с предыдущим месяцем
            prev_month = month - 1 if month > 1 else 12
            prev_year = year if month > 1 else year - 1
            
            prev_start = date(prev_year, prev_month, 1)
            if prev_month == 12:
                prev_end = date(prev_year + 1, 1, 1) - timedelta(days=1)
            else:
                prev_end = date(prev_year, prev_month + 1, 1) - timedelta(days=1)
            
            prev_total = await Expense.objects.filter(
                profile=profile,
                created_at__date__gte=prev_start,
                created_at__date__lte=prev_end
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
            
            from bot.utils import get_currency_symbol
            currency_symbol = get_currency_symbol(profile.currency or 'RUB')
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
                'logo_base64': await self._get_logo_base64(),
                'currency_symbol': currency_symbol,
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
            logger.debug("Failed to read WeasyPrint PDF logo from %s: %s", self.LOGO_PATH, logo_error)
            return ""
