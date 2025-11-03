"""
Сервис для экспорта финансовых данных в CSV и XLSX форматы.
"""
import csv
import calendar
from io import StringIO, BytesIO
from datetime import datetime, date
from decimal import Decimal
from typing import List, Dict, Any
import logging

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import PieChart, BarChart, Reference
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.chart.layout import Layout, ManualLayout
from openpyxl.chart.label import DataLabel, DataLabelList
try:
    from openpyxl.chart.text import RichText, Paragraph
    from openpyxl.drawing.text import ParagraphProperties, CharacterProperties
except ImportError:
    RichText = Paragraph = ParagraphProperties = CharacterProperties = None

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

        # Функция для обрезания длинного текста с многоточием
        def truncate_text(text: str, max_length: int = 33) -> str:
            """Обрезает текст до max_length символов, добавляя многоточие если нужно
            max_length=33 соответствует длине "Коммунальные услуги и подписки"
            """
            if len(text) > max_length:
                return text[:max_length-1] + '…'
            return text

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

        # Стили для зебра-полосок и границ
        thin_border = Border(
            left=Side(style='thin', color='000000'),
            right=Side(style='thin', color='000000'),
            top=Side(style='thin', color='000000'),
            bottom=Side(style='thin', color='000000')
        )
        gray_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")

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
            cell.border = thin_border

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

            # Применяем границы и чередующуюся заливку к строке
            is_even_row = (current_row % 2 == 0)
            for col in range(1, 8):  # Колонки A-G
                cell = ws.cell(row=current_row, column=col)
                cell.border = thin_border
                if is_even_row:
                    cell.fill = gray_fill

            # Форматирование суммы
            amount_cell = ws.cell(row=current_row, column=3)
            if op['type'] == 'income':
                amount_cell.font = Font(color="008000", bold=True)
            else:
                amount_cell.font = Font(color="000000")  # Черный цвет для трат
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
            # Применяем границы к строке итогов
            for col in range(1, 8):
                ws.cell(row=current_row, column=col).border = thin_border
            ws.cell(row=current_row, column=3).font = Font(bold=True, color="000000")  # Черный цвет
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
            # Применяем границы к строке итогов
            for col in range(1, 8):
                ws.cell(row=current_row, column=col).border = thin_border
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
            # Применяем границы к строке итогов
            for col in range(1, 8):
                ws.cell(row=current_row, column=col).border = thin_border
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
            cell.border = thin_border

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

        sorted_categories = sorted(
            category_stats.items(), key=lambda x: x[1]['total'], reverse=True
        )
        total_expenses = sum(stats['total'] for _, stats in sorted_categories)
        pie_segment_ratios: List[float] = []

        # Заполнение Summary
        summary_row = 2
        for (category, currency), stats in sorted_categories:
            average = stats['total'] / stats['count'] if stats['count'] > 0 else 0

            # Кешбэк - СУММА по ВСЕМ category_id для этой категории (важно для household mode!)
            total_cashback = 0
            for category_id in stats.get('category_ids', set()):
                total_cashback += category_cashbacks.get(category_id, 0)
            cashback = total_cashback

            # Заполняем колонки I-N
            ws.cell(row=summary_row, column=9, value=truncate_text(category))
            ws.cell(row=summary_row, column=10, value=currency)
            ws.cell(row=summary_row, column=11, value=stats['total'])
            ws.cell(row=summary_row, column=12, value=stats['count'])
            ws.cell(row=summary_row, column=13, value=average)
            ws.cell(row=summary_row, column=14, value=cashback)

            # Применяем границы и чередующуюся заливку к строке Summary
            is_even_row = (summary_row % 2 == 0)
            for col in range(9, 15):  # Колонки I-N
                cell = ws.cell(row=summary_row, column=col)
                cell.border = thin_border
                if is_even_row:
                    cell.fill = gray_fill

            # Форматирование
            ws.cell(row=summary_row, column=11).number_format = '#,##0.00'
            ws.cell(row=summary_row, column=13).number_format = '#,##0.00'
            ws.cell(row=summary_row, column=14).number_format = '#,##0.00'

            # Кешбэк зеленым если > 0
            if cashback > 0:
                ws.cell(row=summary_row, column=14).font = Font(color="008000", bold=True)

            ratio = (stats['total'] / total_expenses) if total_expenses else 0
            pie_segment_ratios.append(ratio)

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

        total_expenses = sum(stats['total'] for _, stats in sorted_categories)
        pie_segment_ratios = []
        for (_, _), stats in sorted_categories:
            amount = stats['total']
            ratio = (amount / total_expenses) if total_expenses else 0
            pie_segment_ratios.append(ratio)
        # ==================== ГРАФИКИ ====================
        # Диаграммы размещаются ПОД таблицей Summary (вертикально)
        charts_start_row = summary_end_row + 2  # Начало диаграмм под таблицей
        pie_block_height = 11.5

        # КРУГОВАЯ ДИАГРАММА ПО КАТЕГОРИЯМ (под таблицей Summary)
        if summary_end_row > 1:
            from openpyxl.chart.legend import Legend

            pie = PieChart()
            pie.title = "Расходы по категориям" if lang == 'ru' else "Expenses by Category"
            pie.varyColors = True
            pie.width = 19.76  # Блок еще шире - диаграмма слева, легенда справа
            pie.height = 11.5488  # Блок выше для размещения заголовка
            pie.layout = Layout(
                manualLayout=ManualLayout(
                    xMode="edge",
                    yMode="factor",
                    wMode="factor",
                    hMode="factor",
                    x=0.115,  # Сдвинули на 5% правее (было 0.065)
                    y=0.05,
                    w=0.42,
                    h=0.8
                )
            )

            # Легенда внутри области диаграммы справа
            pie.legend = Legend()
            pie.legend.position = 'r'
            pie.legend.overlay = False  # Легенда не накладывается на диаграмму
            # Настройка позиции легенды - начало с 65%, увеличенная высота для одного столбца
            pie.legend.layout = Layout(
                manualLayout=ManualLayout(
                    xMode="edge",
                    yMode="edge",
                    x=0.65,  # Начало легенды на 65% ширины
                    y=0.02,  # Минимальный отступ сверху
                    w=0.32,  # Ширина 32% для длинных категорий
                    h=0.96  # Максимальная высота - принудительно вертикальное размещение
                )
            )

            # Данные: колонка I (категории) и K (всего)
            labels = Reference(ws, min_col=9, min_row=2, max_row=summary_end_row)
            data = Reference(ws, min_col=11, min_row=1, max_row=summary_end_row)
            pie.add_data(data, titles_from_data=True)
            pie.set_categories(labels)

            pie_block_height = pie.height

            # Применяем цвета из палитры к каждому сегменту круговой диаграммы
            from openpyxl.chart.series import DataPoint
            if pie.series:
                series = pie.series[0]
                series.tx = None  # убираем ссылку на заголовок серии, чтобы не выводился Total/Ряд

                data_labels = DataLabelList()
                data_labels.showPercent = False
                data_labels.showLeaderLines = False
                data_labels.showValue = False
                data_labels.showCatName = False
                data_labels.showLegendKey = False
                data_labels.showSerName = False
                data_labels.showBubbleSize = False
                data_labels.dLblPos = "outEnd"
                data_labels.numFmt = "0%"
                point_labels: List[DataLabel] = []
                if RichText and ParagraphProperties and CharacterProperties:
                    data_labels.txPr = RichText(p=[
                        Paragraph(
                            pPr=ParagraphProperties(
                                defRPr=CharacterProperties(sz=900, b=True, solidFill="FFFFFF")
                            )
                        )
                    ])
                series.dLbls = data_labels

                # Показываем подписи только для сегментов >= 3%
                for idx, ratio in enumerate(pie_segment_ratios):
                    if ratio >= 0.04:
                        point_labels.append(
                            DataLabel(
                                idx=idx,
                                showPercent=True,
                                showVal=False,
                                showCatName=False,
                                showSerName=False,
                                showLegendKey=False,
                                showLeaderLines=False
                            )
                        )
                if point_labels:
                    data_labels.dLbl = point_labels

                for idx in range(summary_end_row - 1):  # Количество категорий
                    color_idx = idx % len(ExportService.CATEGORY_COLORS)
                    color_hex = ExportService.CATEGORY_COLORS[color_idx].lstrip('#').upper()

                    # Создаем точку данных с цветом
                    pt = DataPoint(idx=idx)
                    pt.graphicalProperties = GraphicalProperties(solidFill=color_hex)
                    series.dPt.append(pt)

            # Размещение ПОД таблицей Summary, начиная с колонки I
            ws.add_chart(pie, f"I{charts_start_row}")

        # СТОЛБЧАТАЯ ДИАГРАММА ПО ДНЯМ И КАТЕГОРИЯМ
        # Подсчет расходов по дням и категориям для stacked bar chart
        last_day = calendar.monthrange(year, month)[1]

        daily_expenses = {}  # Общие расходы по дням (для обратной совместимости)
        daily_expenses_by_category = {}  # {category: {day: amount}}
        daily_cashback = {}  # Кешбек по дням

        # Получаем информацию о кешбеке для категорий (синхронно)
        category_cashbacks = {}
        cashbacks = Cashback.objects.filter(profile__telegram_id=user_id)
        for cb in cashbacks:
            if cb.category_id:
                category_cashbacks[cb.category_id] = float(cb.cashback_percent) / 100.0

        # Собираем все уникальные категории
        all_categories = set()
        category_to_id = {}  # Маппинг название категории -> id

        for op in operations:
            if op['type'] == 'expense':
                category = op['category'] or ('Без категории' if lang == 'ru' else 'No category')
                all_categories.add(category)
                category_to_id[category] = op.get('category_id')

                day = op['date'].day
                amount = abs(op['amount'])

                # Общие расходы по дням
                if day not in daily_expenses:
                    daily_expenses[day] = 0
                daily_expenses[day] += amount

                # Расходы по категориям и дням
                if category not in daily_expenses_by_category:
                    daily_expenses_by_category[category] = {}
                if day not in daily_expenses_by_category[category]:
                    daily_expenses_by_category[category][day] = 0
                daily_expenses_by_category[category][day] += amount

                # Кешбек по дням
                cat_id = op.get('category_id')
                if cat_id and cat_id in category_cashbacks:
                    cashback_rate = category_cashbacks[cat_id]
                    day_cashback = amount * cashback_rate
                    if day not in daily_cashback:
                        daily_cashback[day] = 0
                    daily_cashback[day] += day_cashback

        # Сортируем категории для стабильности отображения
        sorted_categories = sorted(all_categories)
        # ВАЖНО: sorted_days теперь включает ВСЕ дни месяца от 1 до last_day (как в PDF)
        sorted_days = list(range(1, last_day + 1))

        # СТОЛБЧАТАЯ ДИАГРАММА размещается СПРАВА от круговой
        bar_chart_row = charts_start_row  # Используем тот же ряд что и круговая диаграмма

        # Таблица данных для stacked bar chart размещается ПОД столбчатой диаграммой
        if sorted_categories and sorted_days:
            # Таблицу опускаем ниже диаграмм для наглядности
            table_start_row = bar_chart_row + int(pie_block_height + 12)
            # Размещаем в тех же колонках что и диаграммы (начиная с I = 9)
            chart_data_start_col = 9

            day_header = 'День' if lang == 'ru' else 'Day'
            day_cell = ws.cell(row=table_start_row, column=chart_data_start_col, value=day_header)
            day_cell.font = header_font
            day_cell.fill = header_fill
            day_cell.alignment = header_alignment
            day_cell.border = thin_border

            for idx, category in enumerate(sorted_categories):
                col = chart_data_start_col + 1 + idx
                cell = ws.cell(row=table_start_row, column=col, value=category)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment
                cell.border = thin_border

            # Заголовок для кешбека
            cashback_col = chart_data_start_col + 1 + len(sorted_categories)
            cashback_cell = ws.cell(row=table_start_row, column=cashback_col, value='Кешбек' if lang == 'ru' else 'Cashback')
            cashback_cell.font = header_font
            cashback_cell.fill = header_fill
            cashback_cell.alignment = header_alignment
            cashback_cell.border = thin_border

            for offset, day in enumerate(sorted_days, start=1):
                row_num = table_start_row + offset
                ws.cell(row=row_num, column=chart_data_start_col, value=day)
                ws.cell(row=row_num, column=chart_data_start_col).border = thin_border

                is_even_row = (row_num % 2 == 0)
                for idx, category in enumerate(sorted_categories):
                    col = chart_data_start_col + 1 + idx
                    amount = daily_expenses_by_category.get(category, {}).get(day, 0)
                    cell = ws.cell(row=row_num, column=col, value=amount if amount else None)
                    cell.number_format = '#,##0.00'
                    cell.border = thin_border
                    if is_even_row:
                        cell.fill = gray_fill

                # Данные кешбека
                cashback_amount = daily_cashback.get(day, 0)
                cashback_cell = ws.cell(row=row_num, column=cashback_col, value=cashback_amount if cashback_amount else None)
                cashback_cell.number_format = '#,##0.00'
                cashback_cell.border = thin_border
                if is_even_row:
                    cashback_cell.fill = gray_fill

                if is_even_row:
                    ws.cell(row=row_num, column=chart_data_start_col).fill = gray_fill

            days_start_row = table_start_row + 1
            days_end_row = table_start_row + len(sorted_days)
            categories_start_col = chart_data_start_col + 1
            categories_end_col = chart_data_start_col + len(sorted_categories)

            # СТОЛБЧАТАЯ ДИАГРАММА (STACKED - разные цвета по категориям)
            bar = BarChart()
            bar.type = "col"  # Вертикальные столбики
            bar.grouping = "stacked"  # Наложение категорий друг на друга
            bar.overlap = 100  # Полное наложение для stacked chart

            # Убираем весь текст - заголовок, подписи осей
            bar.title = None  # Убираем заголовок
            bar.x_axis.title = None  # Убираем подпись оси X
            bar.y_axis.title = None  # Убираем подпись оси Y
            bar.legend = None  # Убираем легенду

            bar.width = 16  # Чуть уже, сдвигаем ближе вправо
            bar.height = 11.6  # Делаем немного выше для лучшего баланса

            # Настраиваем ось X (дни) - показываем метки 5, 10, 15, 20, 25, 30
            # tickLblSkip определяет как часто показывать метки
            # Для показа 5, 10, 15, 20, 25, 30 нужно пропускать каждые 4 метки (показывать каждую 5-ю)
            bar.x_axis.tickLblSkip = 4  # Показываем каждую 5-ю метку
            bar.x_axis.tickMarkSkip = 4  # Также пропускаем метки делений
            bar.x_axis.delete = False  # Показываем ось X

            # Настраиваем ось Y (суммы)
            bar.y_axis.delete = False  # Показываем ось Y с числами

            # Серые горизонтальные линии сетки
            from openpyxl.chart.axis import ChartLines
            from openpyxl.drawing.line import LineProperties

            # Основные линии сетки Y (серые)
            bar.y_axis.majorGridlines = ChartLines()
            bar.y_axis.majorGridlines.spPr = GraphicalProperties(ln=LineProperties(solidFill="D0D0D0"))  # Серый цвет

            # Данные для столбцов: категории в столбцах, дни в строках
            days_labels = Reference(ws, min_col=chart_data_start_col, min_row=days_start_row, max_row=days_end_row)

            data = Reference(ws,
                             min_col=categories_start_col,
                             max_col=categories_end_col,
                             min_row=table_start_row,
                             max_row=days_end_row)
            bar.add_data(data, titles_from_data=True)
            bar.set_categories(days_labels)

            # Применяем цвета из палитры к каждой серии (категории)
            for idx, series in enumerate(bar.series):
                color_hex = ExportService.CATEGORY_COLORS[idx % len(ExportService.CATEGORY_COLORS)].lstrip('#').upper()
                series.graphicalProperties = GraphicalProperties(solidFill=color_hex)
                series.dLbls = None

            # Добавляем линию кешбека на вторую ось Y
            from openpyxl.chart import LineChart

            line = LineChart()
            line.title = None
            line.y_axis.axId = 200  # Вторая ось Y
            line.y_axis.delete = False
            line.y_axis.crosses = "max"  # Вторая ось справа
            # Убираем линии сетки со второй оси (черные линии)
            line.y_axis.majorGridlines = None

            # Данные для линии кешбека
            cashback_data = Reference(ws,
                                     min_col=cashback_col,
                                     min_row=table_start_row,
                                     max_row=days_end_row)
            line.add_data(cashback_data, titles_from_data=True)
            line.set_categories(days_labels)

            # Стиль линии кешбека (зеленая линия)
            if line.series:
                line.series[0].graphicalProperties = GraphicalProperties(
                    ln=LineProperties(solidFill="00AA00", w=25000)  # Зеленая линия, толщина 2.5pt
                )
                line.series[0].smooth = True  # Сглаженная линия

            # Объединяем столбчатую диаграмму и линию
            bar.y_axis.axId = 100
            bar.y_axis.crosses = "autoZero"
            bar += line  # Добавляем линию к столбчатой диаграмме

            # Размещение СПРАВА от круговой диаграммы (чуть правее для зазора)
            ws.add_chart(bar, f"Q{bar_chart_row}")

        # ==================== ДИАГРАММЫ ДОХОДОВ ====================
        # Подсчет статистики по категориям доходов
        income_category_stats = {}
        for op in operations:
            if op['type'] == 'income':
                category_name = op['category'] or ('Без категории' if lang == 'ru' else 'No category')
                currency = op['currency']
                amount = abs(op['amount'])

                key = (category_name, currency)
                if key not in income_category_stats:
                    income_category_stats[key] = {'total': 0, 'count': 0}

                income_category_stats[key]['total'] += amount
                income_category_stats[key]['count'] += 1

        # Если есть доходы, создаем диаграммы
        if income_category_stats:
            sorted_income_categories = sorted(
                income_category_stats.items(), key=lambda x: x[1]['total'], reverse=True
            )
            total_incomes = sum(stats['total'] for _, stats in sorted_income_categories)
            income_pie_segment_ratios: List[float] = []

            # ТАБЛИЦА SUMMARY ДЛЯ ДОХОДОВ (справа от диаграмм расходов)
            income_summary_start_col = 27  # Колонка AA (27)
            if lang == 'en':
                income_headers = ['Category', 'Currency', 'Total', 'Count', 'Average']
            else:
                income_headers = ['Категория', 'Валюта', 'Всего', 'Количество', 'Средний']

            # Заголовок секции доходов
            income_section_title = 'ДОХОДЫ' if lang == 'ru' else 'INCOME'
            title_cell = ws.cell(row=1, column=income_summary_start_col, value=income_section_title)
            title_cell.font = Font(bold=True, color="FFFFFF", size=12)
            title_cell.fill = PatternFill(start_color="4CAF50", end_color="4CAF50", fill_type="solid")
            title_cell.alignment = header_alignment
            title_cell.border = thin_border

            # Заголовки колонок для Summary доходов
            for idx, header in enumerate(income_headers):
                cell = ws.cell(row=2, column=income_summary_start_col + idx, value=header)
                cell.font = header_font
                cell.fill = PatternFill(start_color="66BB6A", end_color="66BB6A", fill_type="solid")
                cell.alignment = header_alignment
                cell.border = thin_border

            # Заполнение данных Summary для доходов
            income_summary_row = 3
            for (category, currency), stats in sorted_income_categories:
                average = stats['total'] / stats['count'] if stats['count'] > 0 else 0

                ws.cell(row=income_summary_row, column=income_summary_start_col, value=truncate_text(category))
                ws.cell(row=income_summary_row, column=income_summary_start_col + 1, value=currency)
                ws.cell(row=income_summary_row, column=income_summary_start_col + 2, value=stats['total'])
                ws.cell(row=income_summary_row, column=income_summary_start_col + 3, value=stats['count'])
                ws.cell(row=income_summary_row, column=income_summary_start_col + 4, value=average)

                # Применяем границы и чередующуюся заливку
                is_even_row = (income_summary_row % 2 == 0)
                for col in range(income_summary_start_col, income_summary_start_col + 5):
                    cell = ws.cell(row=income_summary_row, column=col)
                    cell.border = thin_border
                    if is_even_row:
                        cell.fill = gray_fill

                # Форматирование чисел
                ws.cell(row=income_summary_row, column=income_summary_start_col + 2).number_format = '#,##0.00'
                ws.cell(row=income_summary_row, column=income_summary_start_col + 4).number_format = '#,##0.00'

                ratio = (stats['total'] / total_incomes) if total_incomes else 0
                income_pie_segment_ratios.append(ratio)

                income_summary_row += 1

            income_summary_end_row = income_summary_row - 1

            # Автоширина для колонок доходов
            for col in range(income_summary_start_col, income_summary_start_col + 5):
                max_length = 0
                for row in range(1, income_summary_row):
                    cell = ws.cell(row=row, column=col)
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                ws.column_dimensions[get_column_letter(col)].width = min(max_length + 2, 40)

            # КРУГОВАЯ ДИАГРАММА ДОХОДОВ (справа от столбчатой расходов)
            income_pie = PieChart()
            income_pie.title = "Доходы по категориям" if lang == 'ru' else "Income by Category"
            income_pie.varyColors = True
            income_pie.width = 19.76
            income_pie.height = 11.5488
            income_pie.layout = Layout(
                manualLayout=ManualLayout(
                    xMode="edge",
                    yMode="factor",
                    wMode="factor",
                    hMode="factor",
                    x=0.115,  # Сдвинули на 5% правее (было 0.065)
                    y=0.05,
                    w=0.42,
                    h=0.8
                )
            )

            # Легенда внутри области диаграммы справа
            income_pie.legend = Legend()
            income_pie.legend.position = 'r'
            income_pie.legend.overlay = False  # Легенда не накладывается на диаграмму
            # Настройка позиции легенды - начало с 65%, увеличенная высота для одного столбца
            income_pie.legend.layout = Layout(
                manualLayout=ManualLayout(
                    xMode="edge",
                    yMode="edge",
                    x=0.65,  # Начало легенды на 65% ширины
                    y=0.02,  # Минимальный отступ сверху
                    w=0.32,  # Ширина 32% для длинных категорий
                    h=0.96  # Максимальная высота - принудительно вертикальное размещение
                )
            )

            # Данные для круговой диаграммы доходов
            income_labels = Reference(ws, min_col=income_summary_start_col, min_row=3, max_row=income_summary_end_row)
            income_data = Reference(ws, min_col=income_summary_start_col + 2, min_row=2, max_row=income_summary_end_row)
            income_pie.add_data(income_data, titles_from_data=True)
            income_pie.set_categories(income_labels)

            # Применяем цвета к сегментам круговой диаграммы доходов
            if income_pie.series:
                series = income_pie.series[0]
                series.tx = None

                data_labels = DataLabelList()
                data_labels.showPercent = False
                data_labels.showLeaderLines = False
                data_labels.showValue = False
                data_labels.showCatName = False
                data_labels.showLegendKey = False
                data_labels.showSerName = False
                data_labels.showBubbleSize = False
                data_labels.dLblPos = "outEnd"
                data_labels.numFmt = "0%"
                point_labels: List[DataLabel] = []
                if RichText and ParagraphProperties and CharacterProperties:
                    data_labels.txPr = RichText(p=[
                        Paragraph(
                            pPr=ParagraphProperties(
                                defRPr=CharacterProperties(sz=900, b=True, solidFill="FFFFFF")
                            )
                        )
                    ])
                series.dLbls = data_labels

                # Показываем подписи только для сегментов >= 4%
                for idx, ratio in enumerate(income_pie_segment_ratios):
                    if ratio >= 0.04:
                        point_labels.append(
                            DataLabel(
                                idx=idx,
                                showPercent=True,
                                showVal=False,
                                showCatName=False,
                                showSerName=False,
                                showLegendKey=False,
                                showLeaderLines=False
                            )
                        )
                if point_labels:
                    data_labels.dLbl = point_labels

                for idx in range(income_summary_end_row - 2):
                    color_idx = idx % len(ExportService.CATEGORY_COLORS)
                    color_hex = ExportService.CATEGORY_COLORS[color_idx].lstrip('#').upper()
                    pt = DataPoint(idx=idx)
                    pt.graphicalProperties = GraphicalProperties(solidFill=color_hex)
                    series.dPt.append(pt)

            # Размещение круговой диаграммы доходов (колонка AA)
            ws.add_chart(income_pie, f"AA{charts_start_row}")

            # СТОЛБЧАТАЯ ДИАГРАММА ДОХОДОВ ПО ДНЯМ
            # Подсчет доходов по дням и категориям
            daily_incomes_by_category = {}  # {category: {day: amount}}
            income_categories = set()

            for op in operations:
                if op['type'] == 'income':
                    category = op['category'] or ('Без категории' if lang == 'ru' else 'No category')
                    income_categories.add(category)

                    day = op['date'].day
                    amount = abs(op['amount'])

                    if category not in daily_incomes_by_category:
                        daily_incomes_by_category[category] = {}
                    if day not in daily_incomes_by_category[category]:
                        daily_incomes_by_category[category][day] = 0
                    daily_incomes_by_category[category][day] += amount

            sorted_income_categories_list = sorted(income_categories)

            if sorted_income_categories_list and sorted_days:
                # Таблица данных для столбчатой диаграммы доходов
                income_table_start_row = table_start_row  # Используем тот же ряд что и для расходов
                income_chart_data_start_col = income_summary_start_col  # Колонка AA

                day_header = 'День' if lang == 'ru' else 'Day'
                day_cell = ws.cell(row=income_table_start_row, column=income_chart_data_start_col, value=day_header)
                day_cell.font = header_font
                day_cell.fill = PatternFill(start_color="66BB6A", end_color="66BB6A", fill_type="solid")
                day_cell.alignment = header_alignment
                day_cell.border = thin_border

                for idx, category in enumerate(sorted_income_categories_list):
                    col = income_chart_data_start_col + 1 + idx
                    cell = ws.cell(row=income_table_start_row, column=col, value=category)
                    cell.font = header_font
                    cell.fill = PatternFill(start_color="66BB6A", end_color="66BB6A", fill_type="solid")
                    cell.alignment = header_alignment
                    cell.border = thin_border

                # Заполнение данных по дням
                for offset, day in enumerate(sorted_days, start=1):
                    row_num = income_table_start_row + offset
                    ws.cell(row=row_num, column=income_chart_data_start_col, value=day)
                    ws.cell(row=row_num, column=income_chart_data_start_col).border = thin_border

                    is_even_row = (row_num % 2 == 0)
                    for idx, category in enumerate(sorted_income_categories_list):
                        col = income_chart_data_start_col + 1 + idx
                        amount = daily_incomes_by_category.get(category, {}).get(day, 0)
                        cell = ws.cell(row=row_num, column=col, value=amount if amount else None)
                        cell.number_format = '#,##0.00'
                        cell.border = thin_border
                        if is_even_row:
                            cell.fill = gray_fill

                    if is_even_row:
                        ws.cell(row=row_num, column=income_chart_data_start_col).fill = gray_fill

                income_days_start_row = income_table_start_row + 1
                income_days_end_row = income_table_start_row + len(sorted_days)
                income_categories_start_col = income_chart_data_start_col + 1
                income_categories_end_col = income_chart_data_start_col + len(sorted_income_categories_list)

                # СТОЛБЧАТАЯ ДИАГРАММА ДОХОДОВ (STACKED)
                income_bar = BarChart()
                income_bar.type = "col"
                income_bar.grouping = "stacked"
                income_bar.overlap = 100

                income_bar.title = None
                income_bar.x_axis.title = None
                income_bar.y_axis.title = None
                income_bar.legend = None

                income_bar.width = 16
                income_bar.height = 11.6

                # Настройки оси
                income_bar.x_axis.tickLblSkip = 4
                income_bar.x_axis.tickMarkSkip = 4
                income_bar.x_axis.delete = False
                income_bar.y_axis.delete = False

                # Серые линии сетки
                income_bar.y_axis.majorGridlines = ChartLines()
                income_bar.y_axis.majorGridlines.spPr = GraphicalProperties(ln=LineProperties(solidFill="D0D0D0"))

                # Данные для столбцов
                income_days_labels = Reference(ws, min_col=income_chart_data_start_col, min_row=income_days_start_row, max_row=income_days_end_row)
                income_bar_data = Reference(ws,
                                          min_col=income_categories_start_col,
                                          max_col=income_categories_end_col,
                                          min_row=income_table_start_row,
                                          max_row=income_days_end_row)
                income_bar.add_data(income_bar_data, titles_from_data=True)
                income_bar.set_categories(income_days_labels)

                # Применяем цвета
                for idx, series in enumerate(income_bar.series):
                    color_hex = ExportService.CATEGORY_COLORS[idx % len(ExportService.CATEGORY_COLORS)].lstrip('#').upper()
                    series.graphicalProperties = GraphicalProperties(solidFill=color_hex)
                    series.dLbls = None

                # Размещение столбчатой диаграммы доходов (справа от круговой, немного правее)
                ws.add_chart(income_bar, f"AL{charts_start_row}")

        # Закрепить первую строку
        ws.freeze_panes = 'A2'

        # Сохранить в BytesIO
        output = BytesIO()
        wb.save(output)
        output.seek(0)

        return output
