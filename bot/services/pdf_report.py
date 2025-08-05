"""
Сервис для генерации PDF отчетов
"""
import os
import base64
import logging
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
            
            # Получаем все кешбеки пользователя для этого месяца
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
                            category_cashback += cb_amount * (cb.cashback_percent / 100)
                    
                    top_categories.append({
                        'name': cat_stat['category__name'],
                        'icon': cat_stat['category__icon'] or '📊',
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
        html = self.template
        
        # Заменяем плейсхолдеры
        html = html.replace('Отчет за период: 1 - 31 октября 2024', f'Отчет за период: {report_data["period"]}')
        html = html.replace('45,320 ₽', f'{report_data["total_amount"]} ₽')
        html = html.replace('<p class="summary-value">127</p>', f'<p class="summary-value">{report_data["total_count"]}</p>')
        html = html.replace('2,420 ₽', f'{report_data["total_cashback"]} ₽')
        
        # Обновляем сравнение с предыдущим месяцем
        if report_data['change_direction']:
            trend_class = 'trend-up' if report_data['change_direction'] == '↑' else 'trend-down'
            trend_html = f'<p class="summary-trend {trend_class}">{report_data["change_direction"]} {report_data["change_percent"]}% к {report_data["prev_month_name"]}</p>'
            html = html.replace('<p class="summary-trend trend-up">↑ 12% к сентябрю</p>', trend_html)
        else:
            html = html.replace('<p class="summary-trend trend-up">↑ 12% к сентябрю</p>', '')
        
        # Заменяем src="logo.png" на base64
        if report_data.get('logo_base64'):
            html = html.replace(
                'src="logo.png"',
                f'src="data:image/png;base64,{report_data["logo_base64"]}"'
            )
        
        # Обновляем список категорий
        categories_html = ""
        for cat in report_data['categories']:
            categories_html += f"""
                    <div class="category-item">
                        <div class="category-info">
                            <div class="category-color" style="background: {cat['color']}"></div>
                            <span class="category-name">{cat['icon']} {cat['name']}</span>
                        </div>
                        <div class="category-right">
                            <div class="category-amount">{cat['amount']:,.0f} ₽</div>
                            <div class="category-cashback">+{cat['cashback']:,.0f} ₽ кешбек</div>
                        </div>
                    </div>"""
        
        # Находим и заменяем блок категорий
        start_marker = '<div class="categories-list">'
        end_marker = '</div>\n            </div>\n        </div>'
        start_idx = html.find(start_marker) + len(start_marker)
        end_idx = html.find(end_marker, start_idx)
        html = html[:start_idx] + categories_html + '\n                ' + html[end_idx:]
        
        # Обновляем JavaScript
        html = self._update_chart_data(html, report_data)
        
        return html
    
    def _update_chart_data(self, html: str, report_data: Dict) -> str:
        """Обновить данные для графиков в JavaScript"""
        # Подготавливаем данные
        categories_data = report_data['categories']
        pie_labels = [cat['name'] for cat in categories_data]
        pie_data = [cat['amount'] for cat in categories_data]
        pie_colors = [cat['color'] for cat in categories_data]
        
        days = list(range(1, report_data['days_in_month'] + 1))
        
        # Создаем данные для stacked bar chart
        category_datasets = []
        for cat in categories_data:
            cat_name = cat['name']
            cat_data = []
            
            for day in days:
                if day in report_data['daily_categories']:
                    amount = report_data['daily_categories'][day].get(cat_name, 0)
                    cat_data.append(amount)
                else:
                    cat_data.append(0)
            
            category_datasets.append({
                'label': cat_name,
                'data': cat_data,
                'backgroundColor': cat['color'],
                'borderWidth': 0
            })
        
        # Кешбек данные - считаем на основе категорий за день
        cashback_data = []
        for day in days:
            day_cashback = 0
            if day in report_data['daily_categories']:
                for cat_name, cat_amount in report_data['daily_categories'][day].items():
                    # Ищем категорию в списке top_categories чтобы получить её кешбек
                    for cat in categories_data:
                        if cat['name'] == cat_name and cat['cashback'] > 0:
                            # Пропорционально распределяем кешбек
                            if cat['amount'] > 0:
                                cashback_rate = cat['cashback'] / cat['amount']
                                day_cashback += cat_amount * cashback_rate
                            break
            cashback_data.append(round(-day_cashback, 2))  # Отрицательное значение для отображения вниз
        
        # Заменяем данные в JavaScript
        js_replacement = f"""
        // Pie Chart
        const pieCtx = document.getElementById('pieChart').getContext('2d');
        new Chart(pieCtx, {{
            type: 'doughnut',
            data: {{
                labels: {json.dumps(pie_labels, ensure_ascii=False)},
                datasets: [{{
                    data: {json.dumps(pie_data)},
                    backgroundColor: {json.dumps(pie_colors)},
                    borderWidth: 0
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'bottom',
                        labels: {{
                            padding: 10,
                            font: {{
                                size: 11
                            }},
                            boxWidth: 12,
                            usePointStyle: true
                        }},
                        fullSize: true,
                        maxHeight: 50
                    }}
                }}
            }}
        }});
        
        // Stacked Bar Chart with Cashback
        const barCtx = document.getElementById('barChart').getContext('2d');
        const categoryDatasets = {json.dumps(category_datasets, ensure_ascii=False)};
        const cashbackDataset = {{
            label: 'Кешбек',
            data: {json.dumps(cashback_data)},
            backgroundColor: '#10b981',
            borderWidth: 0
        }};
        
        new Chart(barCtx, {{
            type: 'bar',
            data: {{
                labels: {json.dumps(days)},
                datasets: [...categoryDatasets, cashbackDataset]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        display: false
                    }},
                    tooltip: {{
                        callbacks: {{
                            title: function(context) {{
                                return context[0].label + ' число';
                            }},
                            label: function(context) {{
                                const value = Math.abs(context.parsed.y);
                                return context.dataset.label + ': ' + value + ' ₽';
                            }}
                        }}
                    }}
                }},
                scales: {{
                    x: {{
                        stacked: true,
                        grid: {{
                            display: false
                        }},
                        ticks: {{
                            maxRotation: 0,
                            callback: function(value, index) {{
                                return (index + 1) % 5 === 0 ? index + 1 : '';
                            }}
                        }}
                    }},
                    y: {{
                        stacked: true,
                        beginAtZero: true,
                        ticks: {{
                            callback: function(value) {{
                                return Math.abs(value) + ' ₽';
                            }}
                        }}
                    }}
                }}
            }}
        }});
        """
        
        # Находим место для замены JavaScript
        script_start = html.find('<script>') + 8
        script_end = html.find('</script>')
        
        # Заменяем JavaScript
        html = html[:script_start] + js_replacement + html[script_end:]
        
        return html
    
    async def _html_to_pdf(self, html_content: str) -> bytes:
        """Конвертация HTML в PDF используя Playwright"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Загружаем HTML
            await page.set_content(html_content, wait_until='networkidle')
            
            # Ждем загрузки графиков
            await page.wait_for_timeout(2000)
            
            # Генерируем PDF
            pdf_bytes = await page.pdf(
                format='A4',
                print_background=True,
                margin={'top': '20px', 'bottom': '20px', 'left': '20px', 'right': '20px'}
            )
            
            await browser.close()
            
            return pdf_bytes