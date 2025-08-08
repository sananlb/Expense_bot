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
        """Подготовить данные для отчета за произвольный период"""
        try:
            # Получаем профиль пользователя
            try:
                profile = await Profile.objects.select_related('settings').aget(telegram_id=user_id)
            except Profile.DoesNotExist:
                logger.warning(f"Profile not found for user {user_id}")
                return None
            
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
                logger.warning(f"No expenses found for user {user_id} in period {start_date} to {end_date}")
                return None
            
            # Статистика по категориям
            categories_stats = []
            async for stat in expenses.values('category').annotate(
                total=Sum('amount'),
                count=Count('id')
            ).order_by('-total').aiterator():
                categories_stats.append(stat)
            
            # Получаем информацию о категориях и кешбэках
            categories_data = []
            colors = ['#8B4513', '#4682B4', '#9370DB', '#20B2AA', '#FFD700', 
                      '#FF6347', '#32CD32', '#FF69B4', '#87CEEB']
            
            # Группируем категории: топ-8 + остальные в "Другие"
            other_amount = 0
            other_cashback = 0
            
            for i, stat in enumerate(categories_stats):
                if i < 8:  # Топ-8 категорий
                    if stat['category']:
                        category = await ExpenseCategory.objects.aget(id=stat['category'])
                        name = category.name
                        icon = category.icon or '💰'
                    else:
                        name = 'Без категории'
                        icon = '💰'
                    
                    # Считаем кешбэк
                    cashback = 0
                    if stat['category']:
                        try:
                            cashback_obj = await Cashback.objects.aget(
                                profile=profile,
                                category_id=stat['category']
                            )
                            cashback = float(stat['total']) * float(cashback_obj.percent) / 100
                        except Cashback.DoesNotExist:
                            pass
                    
                    categories_data.append({
                        'name': name,
                        'icon': icon,
                        'amount': float(stat['total']),
                        'amount_formatted': f"{float(stat['total']):,.0f}",
                        'percent': (float(stat['total']) / total_amount * 100) if total_amount > 0 else 0,
                        'cashback': cashback,
                        'cashback_formatted': f"{cashback:,.0f}",
                        'color': colors[i]
                    })
                else:  # Остальные категории объединяем в "Другие"
                    other_amount += float(stat['total'])
                    
                    # Считаем кешбэк для "Других"
                    if stat['category']:
                        try:
                            category = await ExpenseCategory.objects.aget(id=stat['category'])
                            cashback_obj = await Cashback.objects.aget(
                                profile=profile,
                                category=category
                            )
                            other_cashback += float(stat['total']) * float(cashback_obj.percent) / 100
                        except (Cashback.DoesNotExist, ExpenseCategory.DoesNotExist):
                            pass
            
            # Добавляем категорию "Остальные расходы" если есть остальные траты
            if other_amount > 0:
                categories_data.append({
                    'name': 'Остальные расходы',
                    'icon': '📊',
                    'amount': other_amount,
                    'amount_formatted': f"{other_amount:,.0f}",
                    'percent': (other_amount / total_amount * 100) if total_amount > 0 else 0,
                    'cashback': other_cashback,
                    'cashback_formatted': f"{other_cashback:,.0f}",
                    'color': colors[8]
                })
            
            # Статистика по дням
            days_in_period = (end_date - start_date).days + 1
            daily_expenses = [0] * days_in_period
            daily_cashback = [0] * days_in_period
            
            # Получаем все расходы в список
            expenses_list = []
            async for expense in expenses.select_related('category').aiterator():
                expenses_list.append(expense)
            
            # Обрабатываем расходы
            for expense in expenses_list:
                day_index = (expense.expense_date - start_date).days
                if 0 <= day_index < days_in_period:
                    daily_expenses[day_index] += float(expense.amount)
            
            # Формируем заголовок периода
            if title:
                period_text = title
            elif (end_date - start_date).days == 6:
                # Недельный отчет
                period_text = f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
            else:
                period_text = f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
            
            # Подготавливаем данные для шаблона
            return {
                'period': period_text,
                'total_amount': f"{total_amount:,.0f}",
                'total_count': total_count,
                'total_cashback': f"{sum(cat['cashback'] for cat in categories_data):,.0f}",
                'categories': categories_data,
                'categories_json': json.dumps(categories_data, ensure_ascii=False),
                'daily_json': json.dumps({
                    'days': list(range(1, days_in_period + 1)),
                    'expenses': daily_expenses,
                    'cashback': daily_cashback
                }, ensure_ascii=False),
                'change_direction': '',
                'change_percent': 0,
                'prev_month_name': '',
                'logo_base64': await self._get_logo_base64()
            }
            
        except Exception as e:
            logger.error(f"Error preparing period report data: {e}")
            return None
            
            # Генерируем HTML
            html_content = await self._render_html(report_data)
            
            # Конвертируем в PDF
            pdf_bytes = await self._html_to_pdf(html_content)
            
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"Error generating PDF report: {e}")
            return None
        """Подготовить данные для отчета за произвольный период"""
        try:
            # Получаем профиль пользователя
            try:
                profile = await Profile.objects.select_related('settings').aget(telegram_id=user_id)
            except Profile.DoesNotExist:
                logger.warning(f"Profile not found for user {user_id}")
                return None
            
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
                logger.warning(f"No expenses found for user {user_id} in period {start_date} to {end_date}")
                return None
            
            # Статистика по категориям
            categories_stats = []
            async for stat in expenses.values('category').annotate(
                total=Sum('amount'),
                count=Count('id')
            ).order_by('-total').aiterator():
                categories_stats.append(stat)
            
            # Получаем информацию о категориях и кешбэках
            categories_data = []
            colors = ['#8B4513', '#4682B4', '#9370DB', '#20B2AA', '#FFD700', 
                      '#FF6347', '#32CD32', '#FF69B4', '#87CEEB']
            
            # Группируем категории: топ-8 + остальные в "Другие"
            other_amount = 0
            other_cashback = 0
            
            for i, stat in enumerate(categories_stats):
                if i < 8:  # Топ-8 категорий
                    if stat['category']:
                        category = await ExpenseCategory.objects.aget(id=stat['category'])
                        name = category.name
                        icon = category.icon or '💰'
                    else:
                        name = 'Без категории'
                        icon = '💰'
                    
                    # Считаем кешбэк
                    cashback = 0
                    if stat['category']:
                        try:
                            cashback_obj = await Cashback.objects.aget(
                                profile=profile,
                                category_id=stat['category']
                            )
                            cashback = float(stat['total']) * float(cashback_obj.percent) / 100
                        except Cashback.DoesNotExist:
                            pass
                    
                    categories_data.append({
                        'name': name,
                        'icon': icon,
                        'amount': float(stat['total']),
                        'amount_formatted': f"{float(stat['total']):,.0f}",
                        'percent': (float(stat['total']) / total_amount * 100) if total_amount > 0 else 0,
                        'cashback': cashback,
                        'cashback_formatted': f"{cashback:,.0f}",
                        'color': colors[i]
                    })
                else:  # Остальные категории объединяем в "Другие"
                    other_amount += float(stat['total'])
                    
                    # Считаем кешбэк для "Других"
                    if stat['category']:
                        try:
                            category = await ExpenseCategory.objects.aget(id=stat['category'])
                            cashback_obj = await Cashback.objects.aget(
                                profile=profile,
                                category=category
                            )
                            other_cashback += float(stat['total']) * float(cashback_obj.percent) / 100
                        except (Cashback.DoesNotExist, ExpenseCategory.DoesNotExist):
                            pass
            
            # Добавляем категорию "Остальные расходы" если есть остальные траты
            if other_amount > 0:
                categories_data.append({
                    'name': 'Остальные расходы',
                    'icon': '📊',
                    'amount': other_amount,
                    'amount_formatted': f"{other_amount:,.0f}",
                    'percent': (other_amount / total_amount * 100) if total_amount > 0 else 0,
                    'cashback': other_cashback,
                    'cashback_formatted': f"{other_cashback:,.0f}",
                    'color': colors[8]
                })
            
            # Статистика по дням
            days_in_period = (end_date - start_date).days + 1
            daily_expenses = [0] * days_in_period
            daily_cashback = [0] * days_in_period
            
            # Получаем все расходы в список
            expenses_list = []
            async for expense in expenses.select_related('category').aiterator():
                expenses_list.append(expense)
            
            # Обрабатываем расходы
            for expense in expenses_list:
                day_index = (expense.expense_date - start_date).days
                if 0 <= day_index < days_in_period:
                    daily_expenses[day_index] += float(expense.amount)
            
            # Формируем заголовок периода
            if title:
                period_text = title
            elif (end_date - start_date).days == 6:
                # Недельный отчет
                period_text = f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
            else:
                period_text = f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
            
            # Подготавливаем данные для шаблона
            return {
                'period': period_text,
                'total_amount': f"{total_amount:,.0f}",
                'total_count': total_count,
                'total_cashback': f"{sum(cat['cashback'] for cat in categories_data):,.0f}",
                'categories': categories_data,
                'categories_json': json.dumps(categories_data, ensure_ascii=False),
                'daily_json': json.dumps({
                    'days': list(range(1, days_in_period + 1)),
                    'expenses': daily_expenses,
                    'cashback': daily_cashback
                }, ensure_ascii=False),
                'change_direction': '',
                'change_percent': 0,
                'prev_month_name': '',
                'logo_base64': await self._get_logo_base64()
            }
            
        except Exception as e:
            logger.error(f"Error preparing period report data: {e}")
            return None
    
    async def _prepare_report_data(self, user_id: int, year: int, month: int) -> Optional[Dict]:
        """Подготовить данные для отчета из БД"""
        try:
            # Получаем профиль пользователя
            try:
                profile = await Profile.objects.select_related('settings').aget(telegram_id=user_id)
            except Profile.DoesNotExist:
                logger.warning(f"Profile not found for user {user_id}")
                return None
            
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
                logger.warning(f"No expenses found for user {user_id} in period {start_date} to {end_date}")
                return None
            
            # Статистика по категориям
            categories_stats = []
            async for stat in expenses.values('category').annotate(
                total=Sum('amount'),
                count=Count('id')
            ).order_by('-total').aiterator():
                categories_stats.append(stat)
            
            # Получаем информацию о категориях и кешбэках
            categories_data = []
            colors = ['#8B4513', '#4682B4', '#9370DB', '#20B2AA', '#FFD700', 
                      '#FF6347', '#32CD32', '#FF69B4', '#87CEEB']
            
            # Группируем категории: топ-8 + остальные в "Другие"
            other_amount = 0
            other_cashback = 0
            
            for i, stat in enumerate(categories_stats):
                if i < 8:  # Топ-8 категорий
                    if stat['category']:
                        category = await ExpenseCategory.objects.aget(id=stat['category'])
                        name = category.name
                        icon = category.icon or '💰'
                    else:
                        name = 'Без категории'
                        icon = '💰'
                    
                    # Считаем кешбэк
                    cashback = 0
                    if stat['category']:
                        try:
                            cashback_obj = await Cashback.objects.aget(
                                profile=profile,
                                category_id=stat['category']
                            )
                            cashback = float(stat['total']) * float(cashback_obj.percent) / 100
                        except Cashback.DoesNotExist:
                            pass
                    
                    categories_data.append({
                        'name': name,
                        'icon': icon,
                        'amount': float(stat['total']),
                        'amount_formatted': f"{float(stat['total']):,.0f}",
                        'percent': (float(stat['total']) / total_amount * 100) if total_amount > 0 else 0,
                        'cashback': cashback,
                        'cashback_formatted': f"{cashback:,.0f}",
                        'color': colors[i]
                    })
                else:  # Остальные категории объединяем в "Другие"
                    other_amount += float(stat['total'])
                    
                    # Считаем кешбэк для "Других"
                    if stat['category']:
                        try:
                            category = await ExpenseCategory.objects.aget(id=stat['category'])
                            cashback_obj = await Cashback.objects.aget(
                                profile=profile,
                                category=category
                            )
                            other_cashback += float(stat['total']) * float(cashback_obj.percent) / 100
                        except (Cashback.DoesNotExist, ExpenseCategory.DoesNotExist):
                            pass
            
            # Добавляем категорию "Остальные расходы" если есть остальные траты
            if other_amount > 0:
                categories_data.append({
                    'name': 'Остальные расходы',
                    'icon': '📊',
                    'amount': other_amount,
                    'amount_formatted': f"{other_amount:,.0f}",
                    'percent': (other_amount / total_amount * 100) if total_amount > 0 else 0,
                    'cashback': other_cashback,
                    'cashback_formatted': f"{other_cashback:,.0f}",
                    'color': colors[8]
                })
            
            # Статистика по дням
            days_in_period = (end_date - start_date).days + 1
            daily_expenses = [0] * days_in_period
            daily_cashback = [0] * days_in_period
            
            # Получаем все расходы в список
            expenses_list = []
            async for expense in expenses.select_related('category').aiterator():
                expenses_list.append(expense)
            
            # Обрабатываем расходы
            for expense in expenses_list:
                day_index = (expense.expense_date - start_date).days
                if 0 <= day_index < days_in_period:
                    daily_expenses[day_index] += float(expense.amount)
            
            # Формируем заголовок периода
            if title:
                period_text = title
            elif (end_date - start_date).days == 6:
                # Недельный отчет
                period_text = f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
            else:
                period_text = f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
            
            # Подготавливаем данные для шаблона
            return {
                'period': period_text,
                'total_amount': f"{total_amount:,.0f}",
                'total_count': total_count,
                'total_cashback': f"{sum(cat['cashback'] for cat in categories_data):,.0f}",
                'categories': categories_data,
                'categories_json': json.dumps(categories_data, ensure_ascii=False),
                'daily_json': json.dumps({
                    'days': list(range(1, days_in_period + 1)),
                    'expenses': daily_expenses,
                    'cashback': daily_cashback
                }, ensure_ascii=False),
                'change_direction': '',
                'change_percent': 0,
                'prev_month_name': '',
                'logo_base64': await self._get_logo_base64()
            }
            
        except Exception as e:
            logger.error(f"Error preparing period report data: {e}")
            return None
            
            # Генерируем HTML
            html_content = await self._render_html(report_data)
            
            # Конвертируем в PDF
            pdf_bytes = await self._html_to_pdf(html_content)
            
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"Error generating period PDF report: {e}")
            return None
        """Подготовить данные для отчета за произвольный период"""
        try:
            # Получаем профиль пользователя
            try:
                profile = await Profile.objects.select_related('settings').aget(telegram_id=user_id)
            except Profile.DoesNotExist:
                logger.warning(f"Profile not found for user {user_id}")
                return None
            
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
                logger.warning(f"No expenses found for user {user_id} in period {start_date} to {end_date}")
                return None
            
            # Статистика по категориям
            categories_stats = []
            async for stat in expenses.values('category').annotate(
                total=Sum('amount'),
                count=Count('id')
            ).order_by('-total').aiterator():
                categories_stats.append(stat)
            
            # Получаем информацию о категориях и кешбэках
            categories_data = []
            colors = ['#8B4513', '#4682B4', '#9370DB', '#20B2AA', '#FFD700', 
                      '#FF6347', '#32CD32', '#FF69B4', '#87CEEB']
            
            # Группируем категории: топ-8 + остальные в "Другие"
            other_amount = 0
            other_cashback = 0
            
            for i, stat in enumerate(categories_stats):
                if i < 8:  # Топ-8 категорий
                    if stat['category']:
                        category = await ExpenseCategory.objects.aget(id=stat['category'])
                        name = category.name
                        icon = category.icon or '💰'
                    else:
                        name = 'Без категории'
                        icon = '💰'
                    
                    # Считаем кешбэк
                    cashback = 0
                    if stat['category']:
                        try:
                            cashback_obj = await Cashback.objects.aget(
                                profile=profile,
                                category_id=stat['category']
                            )
                            cashback = float(stat['total']) * float(cashback_obj.percent) / 100
                        except Cashback.DoesNotExist:
                            pass
                    
                    categories_data.append({
                        'name': name,
                        'icon': icon,
                        'amount': float(stat['total']),
                        'amount_formatted': f"{float(stat['total']):,.0f}",
                        'percent': (float(stat['total']) / total_amount * 100) if total_amount > 0 else 0,
                        'cashback': cashback,
                        'cashback_formatted': f"{cashback:,.0f}",
                        'color': colors[i]
                    })
                else:  # Остальные категории объединяем в "Другие"
                    other_amount += float(stat['total'])
                    
                    # Считаем кешбэк для "Других"
                    if stat['category']:
                        try:
                            category = await ExpenseCategory.objects.aget(id=stat['category'])
                            cashback_obj = await Cashback.objects.aget(
                                profile=profile,
                                category=category
                            )
                            other_cashback += float(stat['total']) * float(cashback_obj.percent) / 100
                        except (Cashback.DoesNotExist, ExpenseCategory.DoesNotExist):
                            pass
            
            # Добавляем категорию "Остальные расходы" если есть остальные траты
            if other_amount > 0:
                categories_data.append({
                    'name': 'Остальные расходы',
                    'icon': '📊',
                    'amount': other_amount,
                    'amount_formatted': f"{other_amount:,.0f}",
                    'percent': (other_amount / total_amount * 100) if total_amount > 0 else 0,
                    'cashback': other_cashback,
                    'cashback_formatted': f"{other_cashback:,.0f}",
                    'color': colors[8]
                })
            
            # Статистика по дням
            days_in_period = (end_date - start_date).days + 1
            daily_expenses = [0] * days_in_period
            daily_cashback = [0] * days_in_period
            
            # Получаем все расходы в список
            expenses_list = []
            async for expense in expenses.select_related('category').aiterator():
                expenses_list.append(expense)
            
            # Обрабатываем расходы
            for expense in expenses_list:
                day_index = (expense.expense_date - start_date).days
                if 0 <= day_index < days_in_period:
                    daily_expenses[day_index] += float(expense.amount)
            
            # Формируем заголовок периода
            if title:
                period_text = title
            elif (end_date - start_date).days == 6:
                # Недельный отчет
                period_text = f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
            else:
                period_text = f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
            
            # Подготавливаем данные для шаблона
            return {
                'period': period_text,
                'total_amount': f"{total_amount:,.0f}",
                'total_count': total_count,
                'total_cashback': f"{sum(cat['cashback'] for cat in categories_data):,.0f}",
                'categories': categories_data,
                'categories_json': json.dumps(categories_data, ensure_ascii=False),
                'daily_json': json.dumps({
                    'days': list(range(1, days_in_period + 1)),
                    'expenses': daily_expenses,
                    'cashback': daily_cashback
                }, ensure_ascii=False),
                'change_direction': '',
                'change_percent': 0,
                'prev_month_name': '',
                'logo_base64': await self._get_logo_base64()
            }
            
        except Exception as e:
            logger.error(f"Error preparing period report data: {e}")
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
        # Подготавливаем данные для графиков в формате JSON
        categories_json = json.dumps(report_data['categories'], ensure_ascii=False)
        
        # Подготавливаем данные для ежедневного графика
        daily_json = {
            'days': list(range(1, report_data['days_in_month'] + 1)),
            'expenses': report_data['daily_expenses'],
            'cashback': []
        }
        
        # Считаем кешбек для каждого дня
        for day in daily_json['days']:
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
            daily_json['cashback'].append(round(day_cashback, 2))
        
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
            daily_json=json.dumps(daily_json, ensure_ascii=False)
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
                scale=0.95  # Немного увеличиваем масштаб для лучшего использования пространства
            )
            
            await browser.close()
            
            return pdf_bytes