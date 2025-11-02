"""
Сервис для экспорта финансовых данных в CSV и XLSX форматы.
"""
import csv
from io import StringIO, BytesIO
from datetime import datetime, date
from decimal import Decimal
from typing import List, Dict, Any
import calendar
import logging

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import PieChart, BarChart, Reference

from expenses.models import Expense, Income, Cashback, Profile

logger = logging.getLogger(__name__)


class ExportService:
    """Сервис для экспорта данных о тратах и доходах"""

    # Цветовая палитра для категорий (как в PDF отчете)
    CATEGORY_COLORS = [
        '#4A90E2',  # мягкий синий
        '#FF6B35',  # кораллово-оранжевый
        '#7ED321',  # светло-зеленый
        '#8B5CF6',  # средний фиолетовый
        '#F5A623',  # золотой
        '#50C8E8',  # небесно-голубой
        '#BD5EFF',  # сливовый
        '#86D36B',  # бледно-зеленый
        '#E94B9A',  # светло-орхидный
        '#FF8C00',  # оранжевый
        '#5DADE2',  # светло-синий
        '#D4AC0D',  # пшеничный
        '#C39BD3',  # светло-фиолетовый
        '#17A2B8',  # светлый морской зеленый
        '#E91E63'   # ярко-розовый
    ]

    @staticmethod
    def calculate_category_cashbacks(expenses: List[Expense], user_id: int, month: int, household_mode: bool = False) -> Dict:
        """
        Рассчитать кешбеки по категориям.

        Args:
            expenses: Список трат
            user_id: ID пользователя
            month: Месяц для которого считаем кешбеки
            household_mode: Если True, учитываем кешбеки всех членов семьи

        Returns:
            Словарь {category_id: cashback_amount}
        """
        try:
            # Получаем профиль пользователя
            profile = Profile.objects.get(telegram_id=user_id)

            # Получаем все кешбеки (пользователя или всей семьи)
            if household_mode and profile.household:
                # В household mode берем кешбеки всех членов семьи
                user_cashbacks = list(Cashback.objects.filter(
                    profile__household=profile.household,
                    month=month
                ).select_related('category', 'profile'))
            else:
                # В личном режиме только кешбеки текущего пользователя
                user_cashbacks = list(Cashback.objects.filter(
                    profile=profile,
                    month=month
                ).select_related('category'))

            # Создаем словарь кешбеков по категориям
            cashback_by_category = {}
            for cb in user_cashbacks:
                if cb.category_id:
                    if cb.category_id not in cashback_by_category:
                        cashback_by_category[cb.category_id] = []
                    cashback_by_category[cb.category_id].append(cb)

            # Подсчитываем траты по категориям
            category_amounts = {}
            for expense in expenses:
                if expense.category_id:
                    if expense.category_id not in category_amounts:
                        category_amounts[expense.category_id] = 0
                    category_amounts[expense.category_id] += float(expense.amount)

            # Рассчитываем кешбек для каждой категории
            category_cashbacks = {}
            for category_id, amount in category_amounts.items():
                cashback = 0
                if category_id in cashback_by_category:
                    for cb in cashback_by_category[category_id]:
                        cb_amount = amount
                        if cb.limit_amount and cb.limit_amount > 0:
                            cb_amount = min(amount, float(cb.limit_amount))
                        cashback += cb_amount * (float(cb.cashback_percent) / 100)
                category_cashbacks[category_id] = cashback

            return category_cashbacks
        except Exception as e:
            logger.error(f"Error calculating cashbacks: {e}")
            return {}

    @staticmethod
    def prepare_operations_data(
        expenses: List[Expense],
        incomes: List[Income]
    ) -> List[Dict[str, Any]]:
        """
        Подготовить данные операций для экспорта.

        Args:
            expenses: Список трат
            incomes: Список доходов

        Returns:
            Список словарей с данными операций, отсортированный по дате (от новых к старым)
        """
        operations = []

        # Добавить траты
        for expense in expenses:
            operations.append({
                'date': expense.expense_date,
                'time': expense.expense_time or expense.created_at.time(),  # Fallback на время создания
                'type': 'expense',
                'amount': -float(expense.amount),  # Отрицательное для трат
                'currency': expense.currency,
                'category': expense.category.name if expense.category else '',
                'description': expense.description or '',
                'object': expense  # Сохраняем объект для доступа к category_id
            })

        # Добавить доходы
        for income in incomes:
            operations.append({
                'date': income.income_date,
                'time': income.income_time or income.created_at.time(),  # Fallback на время создания
                'type': 'income',
                'amount': float(income.amount),  # Положительное для доходов
                'currency': income.currency,
                'category': income.category.name if income.category else '',
                'description': income.description or '',
                'object': income  # Сохраняем объект для доступа к category_id
            })

        # Сортировать от новых к старым
        operations.sort(key=lambda x: (x['date'], x['time']), reverse=True)

        return operations

    @staticmethod
    def generate_csv(
        expenses: List[Expense],
        incomes: List[Income],
        year: int,
        month: int,
        lang: str = 'ru'
    ) -> bytes:
        """
        Генерация CSV файла с операциями за месяц.

        Args:
            expenses: Список трат
            incomes: Список доходов
            year: Год
            month: Месяц
            lang: Язык (ru/en)

        Returns:
            Байты CSV файла (UTF-8 с BOM для корректного открытия в Excel)
        """
        operations = ExportService.prepare_operations_data(expenses, incomes)

        output = StringIO()

        # Заголовки в зависимости от языка
        # ВАЖНО: Порядок колонок - Дата, Время, Сумма, Валюта, Категория, Описание, Тип
        if lang == 'en':
            headers = ['Date', 'Time', 'Amount', 'Currency', 'Category', 'Description', 'Type']
        else:
            headers = ['Дата', 'Время', 'Сумма', 'Валюта', 'Категория', 'Описание', 'Тип']

        writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
        writer.writerow(headers)

        # Данные
        for op in operations:
            type_text = 'Income' if op['type'] == 'income' else 'Expense'
            if lang == 'ru':
                type_text = 'Доход' if op['type'] == 'income' else 'Трата'

            # Санитизируем описание и категорию - убираем переносы строк и лишние пробелы
            description = str(op['description'] or '')
            description = description.replace('\n', ' ').replace('\r', ' ').strip()

            category = str(op['category'] or '')
            category = category.replace('\n', ' ').replace('\r', ' ').strip()

            writer.writerow([
                op['date'].strftime('%d.%m.%Y'),
                op['time'].strftime('%H:%M'),
                f"{op['amount']:.2f}",
                op['currency'],
                category,
                description,
                type_text
            ])

        # Вернуть байты с BOM (Byte Order Mark) для корректного открытия в Excel
        return '\ufeff'.encode('utf-8') + output.getvalue().encode('utf-8')

    @staticmethod
    def generate_xlsx_with_charts(
        expenses: List[Expense],
        incomes: List[Income],
        year: int,
        month: int,
        user_id: int,
        lang: str = 'ru',
        household_mode: bool = False
    ) -> BytesIO:
        """
        Генерация XLSX файла с операциями, сводкой и графиками.

        Args:
            expenses: Список трат
            incomes: Список доходов
            year: Год
            month: Месяц
            user_id: ID пользователя
            lang: Язык (ru/en)
            household_mode: Режим семейного бюджета

        Returns:
            BytesIO объект с XLSX файлом
        """
        operations = ExportService.prepare_operations_data(expenses, incomes)

        wb = Workbook()

        # ЛИСТ 1: Детализация
        ws_details = wb.active
        ws_details.title = 'Детализация' if lang == 'ru' else 'Details'

        # Заголовки
        if lang == 'en':
            headers = ['Date', 'Time', 'Amount', 'Currency', 'Category', 'Description', 'Type']
        else:
            headers = ['Дата', 'Время', 'Сумма', 'Валюта', 'Категория', 'Описание', 'Тип']

        ws_details.append(headers)

        # Стили для заголовков
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_alignment = Alignment(horizontal="center", vertical="center")

        for cell in ws_details[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment

        # Данные
        total_by_currency = {}

        for op in operations:
            type_text = 'Income' if op['type'] == 'income' else 'Expense'
            if lang == 'ru':
                type_text = 'Доход' if op['type'] == 'income' else 'Трата'

            # Sanitize description and category - remove line breaks
            description = str(op['description'] or '')
            description = description.replace('\n', ' ').replace('\r', ' ').strip()

            category = str(op['category'] or '')
            category = category.replace('\n', ' ').replace('\r', ' ').strip()

            row = [
                op['date'].strftime('%d.%m.%Y'),
                op['time'].strftime('%H:%M'),
                op['amount'],
                op['currency'],
                category,
                description,
                type_text
            ]
            ws_details.append(row)

            # Форматирование для доходов/расходов
            row_num = ws_details.max_row
            amount_cell = ws_details.cell(row=row_num, column=3)

            if op['type'] == 'income':
                amount_cell.font = Font(color="008000", bold=True)  # Зеленый для доходов
            else:
                amount_cell.font = Font(color="FF0000")  # Красный для трат

            # Форматирование суммы
            amount_cell.number_format = '#,##0.00'

            # Подсчет итогов по валютам
            currency = op['currency']
            if currency not in total_by_currency:
                total_by_currency[currency] = 0
            total_by_currency[currency] += op['amount']

        # Добавить итоговые строки (расходы, доходы, баланс отдельно)
        ws_details.append([])  # Пустая строка

        # Подсчет расходов и доходов отдельно по валютам
        expenses_by_currency = {}
        incomes_by_currency = {}

        for op in operations:
            currency = op['currency']
            amount = op['amount']

            if op['type'] == 'expense':
                if currency not in expenses_by_currency:
                    expenses_by_currency[currency] = 0
                expenses_by_currency[currency] += abs(amount)
            else:  # income
                if currency not in incomes_by_currency:
                    incomes_by_currency[currency] = 0
                incomes_by_currency[currency] += amount

        # Объединяем все валюты
        all_currencies = set(list(expenses_by_currency.keys()) + list(incomes_by_currency.keys()))

        for currency in sorted(all_currencies):
            expense_total = expenses_by_currency.get(currency, 0)
            income_total = incomes_by_currency.get(currency, 0)
            balance = income_total - expense_total

            # Сумма расходов
            if expense_total > 0:
                label_exp = 'Расходы:' if lang == 'ru' else 'Expenses:'
                ws_details.append([label_exp, '', -expense_total, currency, '', '', ''])
                row_num = ws_details.max_row
                ws_details.cell(row=row_num, column=1).font = Font(bold=True)
                total_cell = ws_details.cell(row=row_num, column=3)
                total_cell.font = Font(bold=True, color="FF0000")
                total_cell.number_format = '#,##0.00'

            # Сумма доходов
            if income_total > 0:
                label_inc = 'Доходы:' if lang == 'ru' else 'Income:'
                ws_details.append([label_inc, '', income_total, currency, '', '', ''])
                row_num = ws_details.max_row
                ws_details.cell(row=row_num, column=1).font = Font(bold=True)
                total_cell = ws_details.cell(row=row_num, column=3)
                total_cell.font = Font(bold=True, color="008000")
                total_cell.number_format = '#,##0.00'

            # Баланс
            label_bal = 'Баланс:' if lang == 'ru' else 'Balance:'
            ws_details.append([label_bal, '', balance, currency, '', '', ''])
            row_num = ws_details.max_row
            ws_details.cell(row=row_num, column=1).font = Font(bold=True)
            total_cell = ws_details.cell(row=row_num, column=3)
            total_cell.font = Font(bold=True, color="0000FF")
            total_cell.number_format = '#,##0.00'

            ws_details.append([])  # Пустая строка между валютами

        # Автоширина колонок
        for column in ws_details.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)

            for cell in column:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass

            adjusted_width = min(max_length + 2, 50)
            ws_details.column_dimensions[column_letter].width = adjusted_width

        # Закрепить первую строку (заголовки)
        ws_details.freeze_panes = 'A2'

        # ЛИСТ 2: Сводка + Графики
        ws_summary = wb.create_sheet(title='Сводка' if lang == 'ru' else 'Summary')

        # Рассчитываем кешбеки по категориям
        category_cashbacks = ExportService.calculate_category_cashbacks(expenses, user_id, month, household_mode)

        # Подсчитать статистику по категориям (только расходы для графиков)
        category_stats = {}

        for op in operations:
            if op['type'] == 'expense':  # Только расходы
                category_name = op['category'] or ('Без категории' if lang == 'ru' else 'No category')
                currency = op['currency']
                amount = abs(op['amount'])

                key = (category_name, currency)
                if key not in category_stats:
                    category_stats[key] = {'total': 0, 'count': 0, 'category_id': None}

                category_stats[key]['total'] += amount
                category_stats[key]['count'] += 1

                # Сохраняем category_id для расчета кешбека
                if 'object' in op and hasattr(op['object'], 'category_id'):
                    category_stats[key]['category_id'] = op['object'].category_id

        # Заголовки сводки с кешбэком
        if lang == 'en':
            summary_headers = ['Category', 'Currency', 'Total', 'Count', 'Average', 'Cashback']
        else:
            summary_headers = ['Категория', 'Валюта', 'Всего', 'Количество', 'Средний чек', 'Кешбэк']

        ws_summary.append(summary_headers)

        # Форматирование заголовков
        for cell in ws_summary[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment

        # Данные сводки (ПОКАЗЫВАЕМ ВСЕ КАТЕГОРИИ с кешбэком)
        total_cashback = 0
        for (category, currency), stats in sorted(category_stats.items(), key=lambda x: x[1]['total'], reverse=True):
            average = stats['total'] / stats['count'] if stats['count'] > 0 else 0

            # Получаем кешбэк для этой категории
            category_id = stats.get('category_id')
            cashback = category_cashbacks.get(category_id, 0) if category_id else 0
            total_cashback += cashback

            row = [
                category,
                currency,
                stats['total'],
                stats['count'],
                average,
                cashback
            ]
            ws_summary.append(row)

            # Форматирование чисел
            row_num = ws_summary.max_row
            ws_summary.cell(row=row_num, column=3).number_format = '#,##0.00'
            ws_summary.cell(row=row_num, column=5).number_format = '#,##0.00'
            ws_summary.cell(row=row_num, column=6).number_format = '#,##0.00'

            # Кешбэк зеленым если > 0
            if cashback > 0:
                ws_summary.cell(row=row_num, column=6).font = Font(color="008000", bold=True)

        summary_end_row = ws_summary.max_row

        # Автоширина для сводки
        for column in ws_summary.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)

            for cell in column:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass

            adjusted_width = min(max_length + 2, 40)
            ws_summary.column_dimensions[column_letter].width = adjusted_width

        # КРУГОВАЯ ДИАГРАММА ПО КАТЕГОРИЯМ (только если есть данные)
        if summary_end_row > 1:
            pie = PieChart()
            pie.title = "Расходы по категориям" if lang == 'ru' else "Expenses by Category"
            pie.width = 15
            pie.height = 12

            # Данные для диаграммы
            labels = Reference(ws_summary, min_col=1, min_row=2, max_row=summary_end_row)
            data = Reference(ws_summary, min_col=3, min_row=1, max_row=summary_end_row)
            pie.add_data(data, titles_from_data=True)
            pie.set_categories(labels)

            # Размещение диаграммы справа от таблицы
            ws_summary.add_chart(pie, "G2")

        # СТОЛБЧАТАЯ ДИАГРАММА ПО ДНЯМ
        # Подсчитать расходы по дням
        last_day = calendar.monthrange(year, month)[1]
        daily_expenses = {}

        for op in operations:
            if op['type'] == 'expense':
                day = op['date'].day
                amount = abs(op['amount'])

                if day not in daily_expenses:
                    daily_expenses[day] = 0
                daily_expenses[day] += amount

        # Создать таблицу дней (в колонке H-I)
        ws_summary.cell(row=summary_end_row + 3, column=8).value = 'День' if lang == 'ru' else 'Day'
        ws_summary.cell(row=summary_end_row + 3, column=9).value = 'Сумма' if lang == 'ru' else 'Amount'

        # Форматирование заголовков дней
        ws_summary.cell(row=summary_end_row + 3, column=8).font = header_font
        ws_summary.cell(row=summary_end_row + 3, column=8).fill = header_fill
        ws_summary.cell(row=summary_end_row + 3, column=9).font = header_font
        ws_summary.cell(row=summary_end_row + 3, column=9).fill = header_fill

        # Заполнить данные по дням
        days_start_row = summary_end_row + 4
        for day in range(1, last_day + 1):
            ws_summary.cell(row=days_start_row + day - 1, column=8).value = day
            ws_summary.cell(row=days_start_row + day - 1, column=9).value = daily_expenses.get(day, 0)
            ws_summary.cell(row=days_start_row + day - 1, column=9).number_format = '#,##0.00'

        days_end_row = days_start_row + last_day - 1

        # СТОЛБЧАТАЯ ДИАГРАММА ПО ДНЯМ (только если есть данные)
        if daily_expenses:
            bar = BarChart()
            bar.title = "Расходы по дням месяца" if lang == 'ru' else "Daily Expenses"
            bar.x_axis.title = 'День месяца' if lang == 'ru' else 'Day of month'
            bar.y_axis.title = 'Сумма' if lang == 'ru' else 'Amount'
            bar.width = 20
            bar.height = 10

            # Данные для диаграммы
            days_labels = Reference(ws_summary, min_col=8, min_row=days_start_row, max_row=days_end_row)
            days_data = Reference(ws_summary, min_col=9, min_row=summary_end_row + 3, max_row=days_end_row)
            bar.add_data(days_data, titles_from_data=True)
            bar.set_categories(days_labels)

            # Размещение диаграммы под круговой
            ws_summary.add_chart(bar, f"G{summary_end_row + 3}")

        # Закрепить первую строку
        ws_summary.freeze_panes = 'A2'

        # Сохранить в BytesIO
        output = BytesIO()
        wb.save(output)
        output.seek(0)

        return output
