"""
Простой сервис для генерации PDF отчетов без WeasyPrint
Использует reportlab для кроссплатформенной совместимости
"""
import io
import logging
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from django.db.models import Sum, Count
from expenses.models import Expense, Profile
from bot.utils.formatters import format_currency

logger = logging.getLogger(__name__)


class SimplePDFReportService:
    """Простой сервис для генерации PDF отчетов"""
    
    def __init__(self):
        # Регистрируем шрифты для поддержки кириллицы
        try:
            from reportlab.pdfbase.pdfmetrics import registerFont
            from reportlab.pdfbase.ttfonts import TTFont
            # Используем встроенные шрифты
        except Exception as e:
            logger.warning(f"Could not register fonts: {e}")
    
    async def generate_monthly_report(self, user_id: int, year: int, month: int) -> Optional[bytes]:
        """Генерация месячного отчета"""
        try:
            # Получаем данные
            profile = await Profile.objects.aget(telegram_id=user_id)
            
            # Получаем расходы за месяц
            expenses = await self._get_month_expenses(profile, year, month)
            if not expenses:
                return None
            
            # Группируем по валютам
            currency_totals = {}
            categories_by_currency = {}
            
            for expense in expenses:
                currency = expense.currency or 'RUB'
                
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
                        categories_by_currency[currency][cat_id] = {
                            'name': expense.category.name,
                            'icon': expense.category.icon,
                            'amount': Decimal('0')
                        }
                    categories_by_currency[currency][cat_id]['amount'] += expense.amount
            
            # Создаем PDF
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
            
            # Стили
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Title'],
                fontSize=24,
                textColor=colors.HexColor('#1f2937'),
                spaceAfter=30
            )
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=16,
                textColor=colors.HexColor('#374151'),
                spaceAfter=12
            )
            normal_style = styles['Normal']
            normal_style.fontSize = 12
            
            # Элементы документа
            elements = []
            
            # Заголовок
            month_names = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                          'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
            title = Paragraph(f"Отчет о расходах<br/>{month_names[month-1]} {year}", title_style)
            elements.append(title)
            elements.append(Spacer(1, 20))
            
            # Общая статистика
            elements.append(Paragraph("Общая статистика", heading_style))
            
            # Таблица с общими суммами по валютам
            totals_data = [["Валюта", "Сумма"]]
            for currency, amount in sorted(currency_totals.items()):
                totals_data.append([currency, format_currency(amount, currency)])
            
            totals_table = Table(totals_data, colWidths=[100, 150])
            totals_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(totals_table)
            elements.append(Spacer(1, 30))
            
            # Расходы по категориям для каждой валюты
            elements.append(Paragraph("Расходы по категориям", heading_style))
            
            for currency, categories in categories_by_currency.items():
                if categories:
                    elements.append(Spacer(1, 10))
                    elements.append(Paragraph(f"<b>{currency}</b>", normal_style))
                    
                    # Таблица категорий
                    cat_data = [["Категория", "Сумма", "Процент"]]
                    currency_total = currency_totals[currency]
                    
                    sorted_cats = sorted(categories.values(), key=lambda x: x['amount'], reverse=True)
                    for cat in sorted_cats:
                        percent = (cat['amount'] / currency_total * 100) if currency_total > 0 else 0
                        cat_data.append([
                            f"{cat['icon']} {cat['name']}",
                            format_currency(cat['amount'], currency),
                            f"{percent:.1f}%"
                        ])
                    
                    cat_table = Table(cat_data, colWidths=[200, 100, 50])
                    cat_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                        ('ALIGN', (2, 0), (2, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 11),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                        ('GRID', (0, 0), (-1, -1), 1, colors.grey)
                    ]))
                    elements.append(cat_table)
                    elements.append(Spacer(1, 15))
            
            # Генерируем PDF
            doc.build(elements)
            pdf_data = buffer.getvalue()
            buffer.close()
            
            return pdf_data
            
        except Exception as e:
            logger.error(f"Error generating PDF report: {e}")
            return None
    
    async def _get_month_expenses(self, profile: Profile, year: int, month: int) -> List[Expense]:
        """Получить расходы за месяц"""
        from asgiref.sync import sync_to_async
        
        expenses = await sync_to_async(list)(
            Expense.objects.filter(
                profile=profile,
                expense_date__year=year,
                expense_date__month=month
            ).select_related('category').order_by('-expense_date', '-created_at')
        )
        
        return expenses