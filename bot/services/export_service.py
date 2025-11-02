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
        Генерация XLSX файла с операциями, сводкой и графиками на одном листе.
        Структура: Траты слева (A-G), Summary справа (I-N), Графики правее (P+)

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
        category_cashbacks = ExportService.calculate_category_cashbacks(expenses, user_id, month, household_mode)
        wb = Workbook()
        ws = wb.active

        # ==================== НАЗВАНИЕ ЛИСТА В ФОРМАТЕ Oct-2025 ====================
        month_names_en = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        month_names_ru = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн',
                         'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']

        if lang == 'ru':
            ws.title = f"{month_names_ru[month-1]}-{year}"
        else:
            ws.title = f"{month_names_en[month-1]}-{year}"

        # Стили
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_alignment = Alignment(horizontal="center", vertical="center")

        # ==================== ЛЕВАЯ ЧАСТЬ: ТРАТЫ (Колонки A-G) ====================
        if lang == 'en':
            headers_left = ['Date', 'Time', 'Amount', 'Currency', 'Category', 'Description', 'Type']
        else:
            headers_left = ['Дата', 'Время', 'Сумма', 'Валюта', 'Категория', 'Описание', 'Тип']

        for idx, header in enumerate(headers_left, start=1):
            cell = ws.cell(row=1, column=idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment

        # Заполнение данных трат
        current_row = 2
        expenses_by_currency = {}
        incomes_by_currency = {}

        for op in operations:
            type_text = 'Доход' if op['type'] == 'income' else 'Трата'
            if lang == 'en':
                type_text = 'Income' if op['type'] == 'income' else 'Expense'

            # Санитизация
            description = str(op['description'] or '').replace('\n', ' ').replace('\r', ' ').strip()
            category = str(op['category'] or '').replace('\n', ' ').replace('\r', ' ').strip()

            # Заполняем колонки A-G
            ws.cell(row=current_row, column=1, value=op['date'].strftime('%d.%m.%Y'))
            ws.cell(row=current_row, column=2, value=op['time'].strftime('%H:%M'))
            ws.cell(row=current_row, column=3, value=op['amount'])
            ws.cell(row=current_row, column=4, value=op['currency'])
            ws.cell(row=current_row, column=5, value=category)
            ws.cell(row=current_row, column=6, value=description)
            ws.cell(row=current_row, column=7, value=type_text)

            # Форматирование
            amount_cell = ws.cell(row=current_row, column=3)
            if op['type'] == 'income':
                amount_cell.font = Font(color="008000", bold=True)
            else:
                amount_cell.font = Font(color="FF0000")
            amount_cell.number_format = '#,##0.00'

            # Подсчет по валютам
            currency = op['currency']
            if op['type'] == 'expense':
                if currency not in expenses_by_currency:
                    expenses_by_currency[currency] = 0
                expenses_by_currency[currency] += abs(op['amount'])
            else:
                if currency not in incomes_by_currency:
                    incomes_by_currency[currency] = 0
                incomes_by_currency[currency] += op['amount']

            current_row += 1

        expenses_data_end_row = current_row - 1

        # Итоги (Расходы, Доходы, Баланс)
        current_row += 1
        all_currencies = set(list(expenses_by_currency.keys()) + list(incomes_by_currency.keys()))

        for currency in sorted(all_currencies):
            expense_total = expenses_by_currency.get(currency, 0)
            income_total = incomes_by_currency.get(currency, 0)
            balance = income_total - expense_total

            # Расходы (ВСЕГДА показываем, даже если 0)
            label = 'Расходы:' if lang == 'ru' else 'Expenses:'
            ws.cell(row=current_row, column=1, value=label).font = Font(bold=True)
            ws.cell(row=current_row, column=2, value=None)
            ws.cell(row=current_row, column=3, value=-expense_total)
            ws.cell(row=current_row, column=4, value=currency)
            ws.cell(row=current_row, column=5, value=None)
            ws.cell(row=current_row, column=6, value=None)
            ws.cell(row=current_row, column=7, value=None)
            ws.cell(row=current_row, column=3).font = Font(bold=True, color="FF0000")
            ws.cell(row=current_row, column=3).number_format = '#,##0.00'
            current_row += 1

            # Доходы (ВСЕГДА показываем, даже если 0)
            label = 'Доходы:' if lang == 'ru' else 'Income:'
            ws.cell(row=current_row, column=1, value=label).font = Font(bold=True)
            ws.cell(row=current_row, column=2, value=None)
            ws.cell(row=current_row, column=3, value=income_total)
            ws.cell(row=current_row, column=4, value=currency)
            ws.cell(row=current_row, column=5, value=None)
            ws.cell(row=current_row, column=6, value=None)
            ws.cell(row=current_row, column=7, value=None)
            ws.cell(row=current_row, column=3).font = Font(bold=True, color="008000")
            ws.cell(row=current_row, column=3).number_format = '#,##0.00'
            current_row += 1

            # Баланс (ВСЕГДА показываем)
            label = 'Баланс:' if lang == 'ru' else 'Balance:'
            ws.cell(row=current_row, column=1, value=label).font = Font(bold=True)
            ws.cell(row=current_row, column=2, value=None)
            ws.cell(row=current_row, column=3, value=balance)
            ws.cell(row=current_row, column=4, value=currency)
            ws.cell(row=current_row, column=5, value=None)
            ws.cell(row=current_row, column=6, value=None)
            ws.cell(row=current_row, column=7, value=None)
            ws.cell(row=current_row, column=3).font = Font(bold=True, color="0000FF")
            ws.cell(row=current_row, column=3).number_format = '#,##0.00'
            current_row += 2

        # Автоширина для колонок A-G
        for col in range(1, 8):
            max_length = 0
            for row in range(1, current_row):
                cell = ws.cell(row=row, column=col)
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            ws.column_dimensions[get_column_letter(col)].width = min(max_length + 2, 50)

        # ==================== ПРАВАЯ ЧАСТЬ: SUMMARY (Колонки I-N) ====================
        # Заголовки Summary
        if lang == 'en':
            headers_right = ['Category', 'Currency', 'Total', 'Count', 'Average', 'Cashback']
        else:
            headers_right = ['Категория', 'Валюта', 'Всего', 'Количество', 'Средний чек', 'Кешбэк']

        summary_start_col = 9  # Колонка I
        for idx, header in enumerate(headers_right):
            cell = ws.cell(row=1, column=summary_start_col + idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment

        # Подсчет статистики по категориям
        category_stats = {}
        for op in operations:
            if op['type'] == 'expense':
                category_name = op['category'] or ('Без категории' if lang == 'ru' else 'No category')
                currency = op['currency']
                amount = abs(op['amount'])

                key = (category_name, currency)
                if key not in category_stats:
                    category_stats[key] = {'total': 0, 'count': 0, 'category_ids': set()}

                category_stats[key]['total'] += amount
                category_stats[key]['count'] += 1

                # Сохраняем ВСЕ category_id (в household mode может быть несколько для одного названия)
                if 'object' in op and hasattr(op['object'], 'category_id'):
                    category_stats[key]['category_ids'].add(op['object'].category_id)

        # Заполнение Summary
        summary_row = 2
        for (category, currency), stats in sorted(category_stats.items(), key=lambda x: x[1]['total'], reverse=True):
            average = stats['total'] / stats['count'] if stats['count'] > 0 else 0

            # Кешбэк - СУММА по ВСЕМ category_id для этой категории (важно для household mode!)
            total_cashback = 0
            for category_id in stats.get('category_ids', set()):
                total_cashback += category_cashbacks.get(category_id, 0)
            cashback = total_cashback

            # Заполняем колонки I-N
            ws.cell(row=summary_row, column=9, value=category)
            ws.cell(row=summary_row, column=10, value=currency)
            ws.cell(row=summary_row, column=11, value=stats['total'])
            ws.cell(row=summary_row, column=12, value=stats['count'])
            ws.cell(row=summary_row, column=13, value=average)
            ws.cell(row=summary_row, column=14, value=cashback)

            # Форматирование
            ws.cell(row=summary_row, column=11).number_format = '#,##0.00'
            ws.cell(row=summary_row, column=13).number_format = '#,##0.00'
            ws.cell(row=summary_row, column=14).number_format = '#,##0.00'

            # Кешбэк зеленым если > 0
            if cashback > 0:
                ws.cell(row=summary_row, column=14).font = Font(color="008000", bold=True)

            summary_row += 1

        summary_end_row = summary_row - 1

        # Автоширина для колонок I-N
        for col in range(9, 15):
            max_length = 0
            for row in range(1, summary_row):
                cell = ws.cell(row=row, column=col)
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            ws.column_dimensions[get_column_letter(col)].width = min(max_length + 2, 40)

        # ==================== ГРАФИКИ ====================

        # КРУГОВАЯ ДИАГРАММА ПО КАТЕГОРИЯМ (колонка P)
        if summary_end_row > 1:
            pie = PieChart()
            pie.title = "Расходы по категориям" if lang == 'ru' else "Expenses by Category"
            pie.width = 15
            pie.height = 12

            # Данные: колонка I (категории) и K (всего)
            labels = Reference(ws, min_col=9, min_row=2, max_row=summary_end_row)
            data = Reference(ws, min_col=11, min_row=1, max_row=summary_end_row)
            pie.add_data(data, titles_from_data=True)
            pie.set_categories(labels)

            # Размещение справа от summary (колонка P)
            ws.add_chart(pie, "P2")

        # СТОЛБЧАТАЯ ДИАГРАММА ПО ДНЯМ
        # Подсчет расходов по дням
        last_day = calendar.monthrange(year, month)[1]
        daily_expenses = {}

        for op in operations:
            if op['type'] == 'expense':
                day = op['date'].day
                amount = abs(op['amount'])
                if day not in daily_expenses:
                    daily_expenses[day] = 0
                daily_expenses[day] += amount

        # Данные по дням в колонках I-J (начиная после summary)
        days_start_row = summary_end_row + 3
        ws.cell(row=days_start_row - 1, column=9, value='День' if lang == 'ru' else 'Day')
        ws.cell(row=days_start_row - 1, column=10, value='Сумма' if lang == 'ru' else 'Amount')
        ws.cell(row=days_start_row - 1, column=9).font = header_font
        ws.cell(row=days_start_row - 1, column=9).fill = header_fill
        ws.cell(row=days_start_row - 1, column=10).font = header_font
        ws.cell(row=days_start_row - 1, column=10).fill = header_fill

        for day in range(1, last_day + 1):
            ws.cell(row=days_start_row + day - 1, column=9, value=day)
            ws.cell(row=days_start_row + day - 1, column=10, value=daily_expenses.get(day, 0))
            ws.cell(row=days_start_row + day - 1, column=10).number_format = '#,##0.00'

        days_end_row = days_start_row + last_day - 1

        # СТОЛБЧАТАЯ ДИАГРАММА
        if daily_expenses:
            bar = BarChart()
            bar.title = "Расходы по дням месяца" if lang == 'ru' else "Daily Expenses"
            bar.x_axis.title = 'День месяца' if lang == 'ru' else 'Day of month'
            bar.y_axis.title = 'Сумма' if lang == 'ru' else 'Amount'
            bar.width = 20
            bar.height = 10

            # Данные: колонка I (дни) и J (суммы)
            days_labels = Reference(ws, min_col=9, min_row=days_start_row, max_row=days_end_row)
            days_data = Reference(ws, min_col=10, min_row=days_start_row - 1, max_row=days_end_row)
            bar.add_data(days_data, titles_from_data=True)
            bar.set_categories(days_labels)

            # Размещение под круговой диаграммой
            ws.add_chart(bar, f"P{days_start_row}")

        # Закрепить первую строку
        ws.freeze_panes = 'A2'

        # Сохранить в BytesIO
        output = BytesIO()
        wb.save(output)
        output.seek(0)

        return output
