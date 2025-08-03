"""
Service for generating PDF reports with charts
"""
import os
import io
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict, Optional
import logging

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import matplotlib
matplotlib.use('Agg')  # Используем backend без GUI
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Wedge
import numpy as np

from asgiref.sync import sync_to_async
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate

from expenses.models import Profile, Expense, ExpenseCategory
from bot.utils import get_text, format_amount, get_month_name

logger = logging.getLogger(__name__)

# Регистрируем шрифты для поддержки кириллицы
try:
    # Путь к шрифтам
    FONTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'fonts')
    if not os.path.exists(FONTS_DIR):
        os.makedirs(FONTS_DIR)
        
    # Можно использовать системные шрифты или добавить свои
    # Для Windows
    if os.path.exists('C:/Windows/Fonts/Arial.ttf'):
        pdfmetrics.registerFont(TTFont('Arial', 'C:/Windows/Fonts/Arial.ttf'))
        pdfmetrics.registerFont(TTFont('Arial-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
        DEFAULT_FONT = 'Arial'
    else:
        DEFAULT_FONT = 'Helvetica'
except Exception as e:
    logger.warning(f"Could not register custom fonts: {e}")
    DEFAULT_FONT = 'Helvetica'


class PDFReportGenerator:
    """Генератор PDF отчетов"""
    
    def __init__(self, profile: Profile, start_date: date, end_date: date, lang: str = 'ru'):
        self.profile = profile
        self.start_date = start_date
        self.end_date = end_date
        self.lang = lang
        self.currency = profile.currency or 'RUB'
        
        # Стили
        self.styles = getSampleStyleSheet()
        self._setup_styles()
        
    def _setup_styles(self):
        """Настройка стилей для PDF"""
        # Заголовок
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontName=f'{DEFAULT_FONT}-Bold' if DEFAULT_FONT != 'Helvetica' else 'Helvetica-Bold',
            fontSize=24,
            textColor=colors.HexColor('#2E86AB'),
            alignment=TA_CENTER,
            spaceAfter=30
        ))
        
        # Подзаголовок
        self.styles.add(ParagraphStyle(
            name='CustomHeading',
            parent=self.styles['Heading1'],
            fontName=f'{DEFAULT_FONT}-Bold' if DEFAULT_FONT != 'Helvetica' else 'Helvetica-Bold',
            fontSize=16,
            textColor=colors.HexColor('#2E86AB'),
            spaceBefore=20,
            spaceAfter=12
        ))
        
        # Обычный текст
        self.styles.add(ParagraphStyle(
            name='CustomNormal',
            parent=self.styles['Normal'],
            fontName=DEFAULT_FONT,
            fontSize=11,
            leading=14
        ))
        
    @sync_to_async
    def _get_expenses_data(self) -> Dict:
        """Получить данные о расходах за период"""
        expenses = Expense.objects.filter(
            profile=self.profile,
            date__gte=self.start_date,
            date__lte=self.end_date
        ).select_related('category')
        
        # Общая сумма
        total_amount = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # По категориям
        by_category = expenses.values(
            'category__name',
            'category__icon'
        ).annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')
        
        # По дням
        by_day = expenses.annotate(
            day=TruncDate('date')
        ).values('day').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('day')
        
        # Детальный список
        expense_list = list(expenses.order_by('-date', '-created_at')[:100])  # Максимум 100 записей
        
        return {
            'total_amount': total_amount,
            'by_category': list(by_category),
            'by_day': list(by_day),
            'expense_list': expense_list,
            'expense_count': expenses.count()
        }
        
    def _create_bar_chart(self, data: List[Dict]) -> io.BytesIO:
        """Создать столбчатую диаграмму по дням"""
        plt.style.use('seaborn-v0_8-darkgrid')
        fig, ax = plt.subplots(figsize=(10, 6))
        
        if not data:
            # Пустая диаграмма
            ax.text(0.5, 0.5, get_text('no_expenses_period', self.lang),
                   ha='center', va='center', fontsize=16)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
        else:
            # Подготовка данных
            dates = [item['day'] for item in data]
            amounts = [float(item['total']) for item in data]
            
            # Создаем график
            bars = ax.bar(dates, amounts, color='#2E86AB', alpha=0.8)
            
            # Добавляем значения на столбцы
            for bar, amount in zip(bars, amounts):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{amount:,.0f}',
                       ha='center', va='bottom', fontsize=9)
            
            # Настройка осей
            ax.set_xlabel(get_text('date', self.lang) if self.lang == 'ru' else 'Date', fontsize=12)
            ax.set_ylabel(get_text('amount', self.lang) if self.lang == 'ru' else 'Amount', fontsize=12)
            ax.set_title(get_text('expenses_by_day', self.lang) if self.lang == 'ru' else 'Expenses by Day', 
                        fontsize=16, pad=20)
            
            # Форматирование дат
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates)//10)))
            plt.xticks(rotation=45)
            
        plt.tight_layout()
        
        # Сохраняем в буфер
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close()
        
        return buffer
        
    def _create_pie_chart(self, data: List[Dict]) -> io.BytesIO:
        """Создать круговую диаграмму по категориям"""
        plt.style.use('seaborn-v0_8-darkgrid')
        fig, ax = plt.subplots(figsize=(10, 8))
        
        if not data:
            # Пустая диаграмма
            ax.text(0.5, 0.5, get_text('no_expenses_period', self.lang),
                   ha='center', va='center', fontsize=16)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
        else:
            # Подготовка данных - берем топ-7 категорий
            top_categories = data[:7]
            if len(data) > 7:
                # Объединяем остальные в "Прочее"
                other_total = sum(float(item['total']) for item in data[7:])
                top_categories.append({
                    'category__name': get_text('other', self.lang) if self.lang == 'ru' else 'Other',
                    'category__icon': '...',
                    'total': other_total
                })
            
            labels = [f"{item['category__icon']} {item['category__name']}" for item in top_categories]
            sizes = [float(item['total']) for item in top_categories]
            
            # Цветовая палитра
            colors_list = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#6A994E', '#BC4B51', '#5B8E7D', '#F4A259']
            
            # Создаем диаграмму
            wedges, texts, autotexts = ax.pie(
                sizes,
                labels=labels,
                colors=colors_list[:len(sizes)],
                autopct='%1.1f%%',
                startangle=90,
                pctdistance=0.85
            )
            
            # Настройка текста
            for text in texts:
                text.set_fontsize(11)
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontsize(10)
                autotext.set_weight('bold')
            
            # Заголовок
            ax.set_title(get_text('expenses_by_category', self.lang) if self.lang == 'ru' else 'Expenses by Category',
                        fontsize=16, pad=20)
            
        plt.tight_layout()
        
        # Сохраняем в буфер
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close()
        
        return buffer
        
    async def generate(self) -> io.BytesIO:
        """Генерировать PDF отчет"""
        # Получаем данные
        data = await self._get_expenses_data()
        
        # Создаем PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=20*mm,
            bottomMargin=20*mm
        )
        
        # Элементы документа
        story = []
        
        # Заголовок
        title = get_text('expense_report', self.lang) if self.lang == 'ru' else 'Expense Report'
        story.append(Paragraph(title, self.styles['CustomTitle']))
        
        # Информация о периоде
        period_text = f"{self.start_date.strftime('%d.%m.%Y')} - {self.end_date.strftime('%d.%m.%Y')}"
        story.append(Paragraph(period_text, self.styles['CustomNormal']))
        story.append(Spacer(1, 20))
        
        # Общая статистика
        stats_title = get_text('general_statistics', self.lang) if self.lang == 'ru' else 'General Statistics'
        story.append(Paragraph(stats_title, self.styles['CustomHeading']))
        
        # Таблица со статистикой
        stats_data = [
            [get_text('total_expenses', self.lang) if self.lang == 'ru' else 'Total Expenses:',
             format_amount(data['total_amount'], self.currency, self.lang)],
            [get_text('expense_count', self.lang) if self.lang == 'ru' else 'Number of Expenses:',
             str(data['expense_count'])],
            [get_text('average_expense', self.lang) if self.lang == 'ru' else 'Average Expense:',
             format_amount(data['total_amount'] / data['expense_count'] if data['expense_count'] > 0 else 0,
                          self.currency, self.lang)]
        ]
        
        stats_table = Table(stats_data, colWidths=[100*mm, 60*mm])
        stats_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), DEFAULT_FONT, 12),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#2E86AB')),
        ]))
        story.append(stats_table)
        story.append(Spacer(1, 30))
        
        # График по дням
        if data['by_day']:
            bar_chart = self._create_bar_chart(data['by_day'])
            img = Image(bar_chart, width=170*mm, height=100*mm)
            story.append(img)
            story.append(Spacer(1, 20))
        
        # Диаграмма по категориям
        if data['by_category']:
            story.append(PageBreak())
            pie_chart = self._create_pie_chart(data['by_category'])
            img = Image(pie_chart, width=170*mm, height=140*mm)
            story.append(img)
            story.append(Spacer(1, 20))
        
        # Таблица по категориям
        cat_title = get_text('by_categories', self.lang)
        story.append(Paragraph(cat_title, self.styles['CustomHeading']))
        
        cat_data = [[get_text('category', self.lang), get_text('amount', self.lang), get_text('percentage', self.lang)]]
        
        total = float(data['total_amount'])
        for item in data['by_category']:
            percentage = float(item['total']) / total * 100 if total > 0 else 0
            cat_data.append([
                f"{item['category__icon']} {item['category__name']}",
                format_amount(item['total'], self.currency, self.lang),
                f"{percentage:.1f}%"
            ])
            
        cat_table = Table(cat_data, colWidths=[80*mm, 50*mm, 30*mm])
        cat_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), DEFAULT_FONT, 11),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F0F0')]),
        ]))
        story.append(cat_table)
        
        # Детальный список расходов (на новой странице)
        if data['expense_list']:
            story.append(PageBreak())
            detail_title = get_text('expense_details', self.lang) if self.lang == 'ru' else 'Expense Details'
            story.append(Paragraph(detail_title, self.styles['CustomHeading']))
            
            detail_data = [[
                get_text('date', self.lang) if self.lang == 'ru' else 'Date',
                get_text('category', self.lang),
                get_text('description', self.lang),
                get_text('amount', self.lang)
            ]]
            
            for expense in data['expense_list']:
                detail_data.append([
                    expense.date.strftime('%d.%m.%Y'),
                    f"{expense.category.icon} {expense.category.name}" if expense.category else '-',
                    expense.description or '-',
                    format_amount(expense.amount, self.currency, self.lang)
                ])
                
            detail_table = Table(detail_data, colWidths=[30*mm, 50*mm, 60*mm, 30*mm])
            detail_table.setStyle(TableStyle([
                ('FONT', (0, 0), (-1, -1), DEFAULT_FONT, 9),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F8F8')]),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(detail_table)
        
        # Генерируем PDF
        doc.build(story)
        buffer.seek(0)
        
        return buffer


# Вспомогательные функции для роутера
@sync_to_async
def generate_pdf_report(telegram_id: int, start_date: date, end_date: date, lang: str = 'ru') -> Optional[io.BytesIO]:
    """
    Генерировать PDF отчет для пользователя
    
    Args:
        telegram_id: ID пользователя в Telegram
        start_date: Дата начала периода
        end_date: Дата конца периода
        lang: Язык отчета
        
    Returns:
        BytesIO с PDF файлом или None при ошибке
    """
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        generator = PDFReportGenerator(profile, start_date, end_date, lang)
        return generator.generate()
    except Profile.DoesNotExist:
        logger.error(f"Profile not found for user {telegram_id}")
        return None
    except Exception as e:
        logger.error(f"Error generating PDF report: {e}")
        return None