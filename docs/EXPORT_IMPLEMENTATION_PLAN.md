# 📊 План реализации экспорта отчетов в CSV и XLSX

> **Дата создания:** 02.11.2025
> **Дата обновления:** 02.11.2025
> **Статус:** В разработке
> **Версия:** 1.1

## ✅ Исправления в версии 1.1

Все критические ошибки из версии 1.0 исправлены:

1. ✅ **Импорт моделей** - исправлено на `from expenses.models import Expense, Income, Profile`
2. ✅ **Отношения моделей** - используется `profile.household` и `profile__household` для фильтрации
3. ✅ **view_scope из UserSettings** - получаем через `get_user_settings.__wrapped__()`
4. ✅ **Timezone пользователя** - используем `profile.timezone` для корректного определения месяца
5. ✅ **Fallback для времени** - добавлен `expense_time or created_at.time()`
6. ✅ **Структура TEXTS** - тексты добавляются в существующий `TEXTS['ru']` / `TEXTS['en']`
7. ✅ **get_subscription_button()** - вызывается без параметров (уже возвращает локализованную кнопку)
8. ✅ **Troubleshooting** - исправлено на `household.profiles.all()` (не `household.members`)

---

## 🎯 Цель проекта

Добавить возможность экспорта финансовых данных (трат и доходов) в форматы CSV и XLSX с графиками и диаграммами для пользователей с Premium подпиской.

---

## 📋 Требования

### Функциональные требования:

1. **Экспортируемые данные:**
   - Все операции за текущий месяц (от 1-го числа до последнего дня месяца)
   - Включает траты и доходы
   - Поддерживает личный и семейный режимы просмотра

2. **Форматы экспорта:**
   - **CSV** - для импорта в другие системы (1С, CRM, Excel)
   - **XLSX** - красивый отчет с форматированием и графиками

3. **Премиум функция:**
   - Доступна только пользователям с активной подпиской
   - Показывает сообщение о необходимости подписки для бесплатных пользователей

4. **Расположение:**
   - Кнопки экспорта в дневнике трат
   - В один ряд: [📄 CSV] [📊 Excel]

### Технические требования:

1. **CSV:**
   - Кодировка: UTF-8 с BOM (для корректного открытия в Excel)
   - Разделитель: запятая (,)
   - Заголовки на выбранном языке (RU/EN)
   - Экранирование специальных символов

2. **XLSX:**
   - 2 листа: "Детализация" и "Сводка"
   - Форматирование (цвета, жирный текст, границы)
   - 2 графика:
     - Круговая диаграмма расходов по категориям
     - Столбчатая диаграмма расходов по дням месяца
   - Показывать ВСЕ категории (без ограничений)
   - Автоширина колонок
   - Закрепленные заголовки

3. **Производительность:**
   - Генерация CSV: < 1 сек
   - Генерация XLSX: < 3 сек
   - Максимальный размер файла: < 5 MB

---

## 📁 Структура файлов

### Новые файлы:

```
bot/services/export_service.py    # Сервис для генерации CSV/XLSX
docs/EXPORT_IMPLEMENTATION_PLAN.md # Этот файл - план реализации
```

### Изменяемые файлы:

```
requirements.txt                   # Добавить openpyxl
bot/texts.py                       # Тексты кнопок и сообщений
bot/routers/reports.py             # Кнопки и обработчики экспорта
```

---

## 🔨 Этапы реализации

### Этап 1: Подготовка зависимостей

**Файл:** `requirements.txt`

**Действие:** Добавить библиотеку для работы с Excel файлами

```txt
# Для генерации Excel файлов с графиками и диаграммами
openpyxl==3.1.5
```

**Установка локально:**

```bash
pip install openpyxl==3.1.5
```

**Проверка:**

```bash
python -c "import openpyxl; print(openpyxl.__version__)"
# Должно вывести: 3.1.5
```

---

### Этап 2: Создание сервиса экспорта

**Файл:** `bot/services/export_service.py` (новый)

#### 2.1 Структура класса ExportService

```python
"""
Сервис для экспорта финансовых данных в CSV и XLSX форматы.
"""
import csv
from io import StringIO, BytesIO
from datetime import datetime, date
from decimal import Decimal
from typing import List, Dict, Any, Tuple
import calendar

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import PieChart, BarChart, Reference

from expenses.models import Expense, Income


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

        writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(headers)

        # Данные
        for op in operations:
            type_text = 'Income' if op['type'] == 'income' else 'Expense'
            if lang == 'ru':
                type_text = 'Доход' if op['type'] == 'income' else 'Трата'

            writer.writerow([
                op['date'].strftime('%d.%m.%Y'),
                op['time'].strftime('%H:%M'),
                f"{op['amount']:.2f}",
                op['currency'],
                op['category'],
                op['description'],
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
        lang: str = 'ru'
    ) -> BytesIO:
        """
        Генерация XLSX файла с операциями, сводкой и графиками.

        Args:
            expenses: Список трат
            incomes: Список доходов
            year: Год
            month: Месяц
            lang: Язык (ru/en)

        Returns:
            BytesIO объект с XLSX файлом
        """
        # ... (полная реализация ниже)
```

#### 2.2 Генерация CSV - детали реализации

**Особенности:**

1. **UTF-8 с BOM** - для корректного открытия в Excel на Windows
2. **Порядок колонок:** Дата, Время, Сумма, Валюта, Категория, Описание, Тип
3. **Экранирование:** Автоматическое для запятых и кавычек
4. **Формат даты:** DD.MM.YYYY (российский стандарт)
5. **Формат времени:** HH:MM (24-часовой формат)

**Пример вывода:**

```csv
Дата,Время,Сумма,Валюта,Категория,Описание,Тип
02.11.2025,14:30,-500.00,RUB,🍔 Продукты,Пятерочка,Трата
02.11.2025,09:00,50000.00,RUB,💰 Доход,Зарплата,Доход
01.11.2025,18:45,-1200.00,RUB,🏠 Дом и ремонт,Ikea столик,Трата
```

#### 2.3 Генерация XLSX - детали реализации

**Лист 1: "Детализация"**

```python
def _create_details_sheet(wb, operations, lang):
    """Создать лист с детализацией операций"""
    ws = wb.active
    ws.title = 'Детализация' if lang == 'ru' else 'Details'

    # Заголовки
    if lang == 'en':
        headers = ['Date', 'Time', 'Amount', 'Currency', 'Category', 'Description', 'Type']
    else:
        headers = ['Дата', 'Время', 'Сумма', 'Валюта', 'Категория', 'Описание', 'Тип']

    ws.append(headers)

    # Стили для заголовков
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center")

    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment

    # Данные
    total_by_currency = {}

    for op in operations:
        type_text = 'Income' if op['type'] == 'income' else 'Expense'
        if lang == 'ru':
            type_text = 'Доход' if op['type'] == 'income' else 'Трата'

        row = [
            op['date'].strftime('%d.%m.%Y'),
            op['time'].strftime('%H:%M'),
            op['amount'],
            op['currency'],
            op['category'],
            op['description'],
            type_text
        ]
        ws.append(row)

        # Форматирование для доходов/расходов
        row_num = ws.max_row
        amount_cell = ws.cell(row=row_num, column=3)

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

    # Добавить итоговые строки
    ws.append([])  # Пустая строка

    total_label = 'ИТОГО:' if lang == 'ru' else 'TOTAL:'
    for currency, total in total_by_currency.items():
        ws.append([total_label, '', total, currency, '', '', ''])
        row_num = ws.max_row

        # Форматирование итоговой строки
        ws.cell(row=row_num, column=1).font = Font(bold=True)
        total_cell = ws.cell(row=row_num, column=3)
        total_cell.font = Font(bold=True, color="0000FF")
        total_cell.number_format = '#,##0.00'

    # Автоширина колонок
    for column in ws.columns:
        max_length = 0
        column_letter = get_column_letter(column[0].column)

        for cell in column:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass

        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width

    # Закрепить первую строку (заголовки)
    ws.freeze_panes = 'A2'

    return ws
```

**Лист 2: "Сводка" + Графики**

```python
def _create_summary_sheet(wb, operations, year, month, lang):
    """Создать лист со сводкой и графиками"""
    ws = wb.create_sheet(title='Сводка' if lang == 'ru' else 'Summary')

    # 1. ТАБЛИЦА СВОДКИ ПО КАТЕГОРИЯМ
    # Подсчитать статистику по категориям
    category_stats = {}
    for op in operations:
        if op['type'] == 'expense':  # Только расходы
            category = op['category'] or ('Без категории' if lang == 'ru' else 'No category')
            currency = op['currency']
            amount = abs(op['amount'])

            key = (category, currency)
            if key not in category_stats:
                category_stats[key] = {'total': 0, 'count': 0, 'amounts': []}

            category_stats[key]['total'] += amount
            category_stats[key]['count'] += 1
            category_stats[key]['amounts'].append(amount)

    # Заголовки сводки
    if lang == 'en':
        summary_headers = ['Category', 'Currency', 'Total', 'Count', 'Average']
    else:
        summary_headers = ['Категория', 'Валюта', 'Всего', 'Количество', 'Средний чек']

    ws.append(summary_headers)

    # Форматирование заголовков
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")

    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Данные сводки (ПОКАЗЫВАЕМ ВСЕ КАТЕГОРИИ БЕЗ ОГРАНИЧЕНИЙ)
    category_rows = []
    for (category, currency), stats in sorted(category_stats.items(), key=lambda x: x[1]['total'], reverse=True):
        average = stats['total'] / stats['count'] if stats['count'] > 0 else 0

        row = [
            category,
            currency,
            stats['total'],
            stats['count'],
            average
        ]
        ws.append(row)
        category_rows.append((category, stats['total']))

        # Форматирование чисел
        row_num = ws.max_row
        ws.cell(row=row_num, column=3).number_format = '#,##0.00'
        ws.cell(row=row_num, column=5).number_format = '#,##0.00'

    summary_end_row = ws.max_row

    # Автоширина для сводки
    for column in ws.columns:
        max_length = 0
        column_letter = get_column_letter(column[0].column)

        for cell in column:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass

        adjusted_width = min(max_length + 2, 40)
        ws.column_dimensions[column_letter].width = adjusted_width

    # 2. КРУГОВАЯ ДИАГРАММА ПО КАТЕГОРИЯМ
    pie = PieChart()
    pie.title = "Расходы по категориям" if lang == 'ru' else "Expenses by Category"
    pie.width = 15
    pie.height = 12

    # Данные для диаграммы
    labels = Reference(ws, min_col=1, min_row=2, max_row=summary_end_row)
    data = Reference(ws, min_col=3, min_row=1, max_row=summary_end_row)
    pie.add_data(data, titles_from_data=True)
    pie.set_categories(labels)

    # Размещение диаграммы справа от таблицы
    ws.add_chart(pie, "G2")

    # 3. ТАБЛИЦА ПО ДНЯМ ДЛЯ СТОЛБЧАТОЙ ДИАГРАММЫ
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
    ws.cell(row=summary_end_row + 3, column=8).value = 'День' if lang == 'ru' else 'Day'
    ws.cell(row=summary_end_row + 3, column=9).value = 'Сумма' if lang == 'ru' else 'Amount'

    # Форматирование заголовков дней
    ws.cell(row=summary_end_row + 3, column=8).font = header_font
    ws.cell(row=summary_end_row + 3, column=8).fill = header_fill
    ws.cell(row=summary_end_row + 3, column=9).font = header_font
    ws.cell(row=summary_end_row + 3, column=9).fill = header_fill

    # Заполнить данные по дням
    days_start_row = summary_end_row + 4
    for day in range(1, last_day + 1):
        ws.cell(row=days_start_row + day - 1, column=8).value = day
        ws.cell(row=days_start_row + day - 1, column=9).value = daily_expenses.get(day, 0)
        ws.cell(row=days_start_row + day - 1, column=9).number_format = '#,##0.00'

    days_end_row = days_start_row + last_day - 1

    # 4. СТОЛБЧАТАЯ ДИАГРАММА ПО ДНЯМ
    bar = BarChart()
    bar.title = "Расходы по дням месяца" if lang == 'ru' else "Daily Expenses"
    bar.x_axis.title = 'День месяца' if lang == 'ru' else 'Day of month'
    bar.y_axis.title = 'Сумма' if lang == 'ru' else 'Amount'
    bar.width = 20
    bar.height = 10

    # Данные для диаграммы
    days_labels = Reference(ws, min_col=8, min_row=days_start_row, max_row=days_end_row)
    days_data = Reference(ws, min_col=9, min_row=summary_end_row + 3, max_row=days_end_row)
    bar.add_data(days_data, titles_from_data=True)
    bar.set_categories(days_labels)

    # Размещение диаграммы под круговой
    ws.add_chart(bar, f"G{summary_end_row + 3}")

    # Закрепить первую строку
    ws.freeze_panes = 'A2'

    return ws
```

**Полная функция генерации XLSX:**

```python
@staticmethod
def generate_xlsx_with_charts(
    expenses: List[Expense],
    incomes: List[Income],
    year: int,
    month: int,
    lang: str = 'ru'
) -> BytesIO:
    """
    Генерация XLSX файла с операциями, сводкой и графиками.
    """
    operations = ExportService.prepare_operations_data(expenses, incomes)

    wb = Workbook()

    # Лист 1: Детализация
    ExportService._create_details_sheet(wb, operations, lang)

    # Лист 2: Сводка + Графики
    ExportService._create_summary_sheet(wb, operations, year, month, lang)

    # Сохранить в BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return output
```

---

### Этап 3: Добавление текстов

**Файл:** `bot/texts.py`

**Найти:** Секции с русскими и английскими текстами

**Добавить в существующий словарь TEXTS['ru']:**

```python
# В файле bot/texts.py найти TEXTS = {'ru': { ... }, 'en': { ... }}
# Добавить в секцию 'ru':

TEXTS = {
    'ru': {
        # ... существующие тексты ...

        # Экспорт отчетов (Premium функция)
        'export_csv_button': '📄 CSV',
        'export_excel_button': '📊 Excel',
        'export_premium_required': (
            '⭐ <b>Экспорт отчетов</b> доступен только в Premium подписке\n\n'
            'С Premium вы получаете:\n'
            '• 📊 Экспорт в Excel с графиками\n'
            '• 📄 Экспорт в CSV для импорта\n'
            '• 📑 PDF отчеты без ограничений\n'
            '• 🎯 Приоритетная поддержка'
        ),
        'export_success': '✅ Отчет за <b>{month}</b> успешно сгенерирован!',
        'export_error': '❌ Произошла ошибка при генерации отчета. Попробуйте позже.',
        'export_empty': '📭 Нет данных за текущий месяц для экспорта',
        'export_generating': '⏳ Генерируем отчет, пожалуйста подождите...',
    },
    'en': {
        # ... существующие тексты ...

        # Export reports (Premium feature)
        'export_csv_button': '📄 CSV',
        'export_excel_button': '📊 Excel',
        'export_premium_required': (
            '⭐ <b>Report export</b> is only available with Premium subscription\n\n'
            'With Premium you get:\n'
            '• 📊 Excel export with charts\n'
            '• 📄 CSV export for import\n'
            '• 📑 Unlimited PDF reports\n'
            '• 🎯 Priority support'
        ),
        'export_success': '✅ Report for <b>{month}</b> generated successfully!',
        'export_error': '❌ An error occurred while generating the report. Please try again later.',
        'export_empty': '📭 No data for current month to export',
        'export_generating': '⏳ Generating report, please wait...',
    }
}
```

---

### Этап 4: Добавление кнопок в дневник трат

**Файл:** `bot/routers/reports.py`

**Найти:** Функцию `callback_show_diary` (строка ~779)

**Найти секцию создания кнопок:**

```python
# Кнопка переключения режима (личный/семейный) - если есть семья
if has_household:
    scope_btn_text = (
        get_text('household_budget_button', lang)
        if current_scope == 'household'
        else get_text('my_budget_button', lang)
    )
    keyboard_buttons.append([InlineKeyboardButton(text=scope_btn_text, callback_data="toggle_view_scope_diary")])

# Кнопки Назад и Закрыть
keyboard_buttons.append([InlineKeyboardButton(text=get_text('back_button', lang), callback_data="expenses_today")])
keyboard_buttons.append([InlineKeyboardButton(text=get_text('close', lang), callback_data="close")])
```

**Изменить на:**

```python
# Кнопка переключения режима (личный/семейный) - если есть семья
if has_household:
    scope_btn_text = (
        get_text('household_budget_button', lang)
        if current_scope == 'household'
        else get_text('my_budget_button', lang)
    )
    keyboard_buttons.append([InlineKeyboardButton(text=scope_btn_text, callback_data="toggle_view_scope_diary")])

# НОВОЕ: Кнопки экспорта в один ряд (CSV и Excel) - ПРЕМИУМ ФУНКЦИЯ
keyboard_buttons.append([
    InlineKeyboardButton(
        text=get_text('export_csv_button', lang),
        callback_data="export_month_csv"
    ),
    InlineKeyboardButton(
        text=get_text('export_excel_button', lang),
        callback_data="export_month_excel"
    )
])

# Кнопки Назад и Закрыть
keyboard_buttons.append([InlineKeyboardButton(text=get_text('back_button', lang), callback_data="expenses_today")])
keyboard_buttons.append([InlineKeyboardButton(text=get_text('close', lang), callback_data="close")])
```

---

### Этап 5: Создание обработчиков экспорта

**Файл:** `bot/routers/reports.py`

#### 5.1 Добавить импорты в начало файла:

```python
from aiogram.types import BufferedInputFile
from asgiref.sync import sync_to_async
from bot.services.export_service import ExportService
from bot.services.subscription import check_subscription, get_subscription_button
from bot.services.profile import get_user_settings
from expenses.models import Expense, Income, Profile
from datetime import datetime, date
import calendar
import pytz
```

#### 5.2 Добавить обработчик для CSV экспорта:

```python
@router.callback_query(F.data == "export_month_csv")
async def callback_export_month_csv(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """
    Обработчик экспорта текущего месяца в формате CSV.
    ПРЕМИУМ ФУНКЦИЯ - требуется активная подписка.
    """
    await callback.answer()

    # 1. ПРОВЕРКА ПРЕМИУМ ПОДПИСКИ
    has_subscription = await check_subscription(callback.from_user.id)
    if not has_subscription:
        await callback.message.answer(
            get_text('export_premium_required', lang),
            reply_markup=get_subscription_button(),
            parse_mode="HTML"
        )
        logger.info(f"User {callback.from_user.id} tried to export CSV without premium")
        return

    try:
        # 2. ПОЛУЧЕНИЕ ПРОФИЛЯ ПОЛЬЗОВАТЕЛЯ
        user = callback.from_user
        profile = await sync_to_async(Profile.objects.get)(telegram_id=user.id)

        # 3. ОПРЕДЕЛЕНИЕ РЕЖИМА (ЛИЧНЫЙ/СЕМЕЙНЫЙ) ИЗ UserSettings
        settings = await sync_to_async(get_user_settings.__wrapped__)(user.id)
        household_mode = bool(profile.household) and getattr(settings, 'view_scope', 'personal') == 'household'

        # 4. ПОКАЗАТЬ СООБЩЕНИЕ О ГЕНЕРАЦИИ
        progress_msg = await callback.message.edit_text(
            get_text('export_generating', lang)
        )

        # 5. ОПРЕДЕЛИТЬ ТЕКУЩИЙ МЕСЯЦ С УЧЕТОМ TIMEZONE ПОЛЬЗОВАТЕЛЯ
        user_tz = pytz.timezone(profile.timezone if profile.timezone else 'UTC')
        now_user_tz = datetime.now(user_tz)
        today = now_user_tz.date()
        year = today.year
        month = today.month
        start_date = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = date(year, month, last_day)

        # 6. ПОЛУЧИТЬ ВСЕ ОПЕРАЦИИ ЗА ТЕКУЩИЙ МЕСЯЦ
        if household_mode:
            # Семейный режим - все участники домохозяйства
            expenses = await sync_to_async(list)(
                Expense.objects.filter(
                    profile__household=profile.household,
                    expense_date__gte=start_date,
                    expense_date__lte=end_date
                ).select_related('category', 'profile').order_by('-expense_date', '-expense_time')
            )
            incomes = await sync_to_async(list)(
                Income.objects.filter(
                    profile__household=profile.household,
                    income_date__gte=start_date,
                    income_date__lte=end_date
                ).select_related('category', 'profile').order_by('-income_date', '-income_time')
            )
        else:
            # Личный режим
            expenses = await sync_to_async(list)(
                Expense.objects.filter(
                    profile=profile,
                    expense_date__gte=start_date,
                    expense_date__lte=end_date
                ).select_related('category').order_by('-expense_date', '-expense_time')
            )
            incomes = await sync_to_async(list)(
                Income.objects.filter(
                    profile=profile,
                    income_date__gte=start_date,
                    income_date__lte=end_date
                ).select_related('category').order_by('-income_date', '-income_time')
            )

        # 8. ПРОВЕРИТЬ ЧТО ЕСТЬ ДАННЫЕ
        if not expenses and not incomes:
            await progress_msg.edit_text(get_text('export_empty', lang))
            logger.info(f"User {user.id} tried to export empty month {year}-{month}")
            return

        # 9. ГЕНЕРАЦИЯ CSV ФАЙЛА
        export_service = ExportService()
        csv_bytes = await sync_to_async(export_service.generate_csv)(
            expenses, incomes, year, month, lang
        )

        # 10. ФОРМИРОВАНИЕ ИМЕНИ ФАЙЛА
        if lang == 'en':
            months = ['january', 'february', 'march', 'april', 'may', 'june',
                      'july', 'august', 'september', 'october', 'november', 'december']
            filename = f"Coins_Report_{months[month-1]}_{year}.csv"
            month_name = months[month-1].title()
        else:
            months = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
                      'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
            filename = f"Coins_Отчет_{months[month-1]}_{year}.csv"
            month_name = months[month-1]

        # 11. ОТПРАВКА ФАЙЛА ПОЛЬЗОВАТЕЛЮ
        file = BufferedInputFile(csv_bytes, filename=filename)
        await callback.message.answer_document(
            document=file,
            caption=get_text('export_success', lang).format(month=month_name)
        )

        # 12. УДАЛЕНИЕ СООБЩЕНИЯ О ПРОГРЕССЕ
        await progress_msg.delete()

        # 13. ЛОГИРОВАНИЕ
        logger.info(f"User {user.id} exported CSV for {year}-{month} ({len(expenses)} expenses, {len(incomes)} incomes)")

    except Profile.DoesNotExist:
        logger.error(f"Profile not found for user {callback.from_user.id}")
        await callback.message.answer(get_text('export_error', lang))
    except Exception as e:
        logger.error(f"Error exporting month to CSV for user {callback.from_user.id}: {e}", exc_info=True)
        try:
            await progress_msg.edit_text(get_text('export_error', lang))
        except:
            await callback.message.answer(get_text('export_error', lang))
```

#### 5.3 Добавить обработчик для XLSX экспорта:

```python
@router.callback_query(F.data == "export_month_excel")
async def callback_export_month_excel(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """
    Обработчик экспорта текущего месяца в формате XLSX с графиками.
    ПРЕМИУМ ФУНКЦИЯ - требуется активная подписка.
    """
    await callback.answer()

    # 1. ПРОВЕРКА ПРЕМИУМ ПОДПИСКИ
    has_subscription = await check_subscription(callback.from_user.id)
    if not has_subscription:
        await callback.message.answer(
            get_text('export_premium_required', lang),
            reply_markup=get_subscription_button(),
            parse_mode="HTML"
        )
        logger.info(f"User {callback.from_user.id} tried to export XLSX without premium")
        return

    try:
        # 2. ПОЛУЧЕНИЕ ПРОФИЛЯ ПОЛЬЗОВАТЕЛЯ
        user = callback.from_user
        profile = await sync_to_async(Profile.objects.get)(telegram_id=user.id)

        # 3. ОПРЕДЕЛЕНИЕ РЕЖИМА (ЛИЧНЫЙ/СЕМЕЙНЫЙ) ИЗ UserSettings
        settings = await sync_to_async(get_user_settings.__wrapped__)(user.id)
        household_mode = bool(profile.household) and getattr(settings, 'view_scope', 'personal') == 'household'

        # 4. ПОКАЗАТЬ СООБЩЕНИЕ О ГЕНЕРАЦИИ
        progress_msg = await callback.message.edit_text(
            get_text('export_generating', lang)
        )

        # 5. ОПРЕДЕЛИТЬ ТЕКУЩИЙ МЕСЯЦ С УЧЕТОМ TIMEZONE ПОЛЬЗОВАТЕЛЯ
        user_tz = pytz.timezone(profile.timezone if profile.timezone else 'UTC')
        now_user_tz = datetime.now(user_tz)
        today = now_user_tz.date()
        year = today.year
        month = today.month
        start_date = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = date(year, month, last_day)

        # 6. ПОЛУЧИТЬ ВСЕ ОПЕРАЦИИ ЗА ТЕКУЩИЙ МЕСЯЦ
        if household_mode:
            # Семейный режим - все участники домохозяйства
            expenses = await sync_to_async(list)(
                Expense.objects.filter(
                    profile__household=profile.household,
                    expense_date__gte=start_date,
                    expense_date__lte=end_date
                ).select_related('category', 'profile').order_by('-expense_date', '-expense_time')
            )
            incomes = await sync_to_async(list)(
                Income.objects.filter(
                    profile__household=profile.household,
                    income_date__gte=start_date,
                    income_date__lte=end_date
                ).select_related('category', 'profile').order_by('-income_date', '-income_time')
            )
        else:
            # Личный режим
            expenses = await sync_to_async(list)(
                Expense.objects.filter(
                    profile=profile,
                    expense_date__gte=start_date,
                    expense_date__lte=end_date
                ).select_related('category').order_by('-expense_date', '-expense_time')
            )
            incomes = await sync_to_async(list)(
                Income.objects.filter(
                    profile=profile,
                    income_date__gte=start_date,
                    income_date__lte=end_date
                ).select_related('category').order_by('-income_date', '-income_time')
            )

        if not expenses and not incomes:
            await progress_msg.edit_text(get_text('export_empty', lang))
            logger.info(f"User {user.id} tried to export empty month {year}-{month}")
            return

        # 9. ГЕНЕРАЦИЯ XLSX ФАЙЛА С ГРАФИКАМИ
        export_service = ExportService()
        xlsx_file = await sync_to_async(export_service.generate_xlsx_with_charts)(
            expenses, incomes, year, month, lang
        )

        # 10. ФОРМИРОВАНИЕ ИМЕНИ ФАЙЛА
        if lang == 'en':
            months = ['january', 'february', 'march', 'april', 'may', 'june',
                      'july', 'august', 'september', 'october', 'november', 'december']
            filename = f"Coins_Report_{months[month-1]}_{year}.xlsx"
            month_name = months[month-1].title()
        else:
            months = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
                      'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
            filename = f"Coins_Отчет_{months[month-1]}_{year}.xlsx"
            month_name = months[month-1]

        # 11. ОТПРАВКА ФАЙЛА
        file = BufferedInputFile(xlsx_file.read(), filename=filename)
        await callback.message.answer_document(
            document=file,
            caption=get_text('export_success', lang).format(month=month_name)
        )

        # 12. УДАЛЕНИЕ СООБЩЕНИЯ О ПРОГРЕССЕ
        await progress_msg.delete()

        # 13. ЛОГИРОВАНИЕ
        logger.info(f"User {user.id} exported XLSX for {year}-{month} ({len(expenses)} expenses, {len(incomes)} incomes)")

    except Profile.DoesNotExist:
        logger.error(f"Profile not found for user {callback.from_user.id}")
        await callback.message.answer(get_text('export_error', lang))
    except Exception as e:
        logger.error(f"Error exporting month to XLSX for user {callback.from_user.id}: {e}", exc_info=True)
        try:
            await progress_msg.edit_text(get_text('export_error', lang))
        except:
            await callback.message.answer(get_text('export_error', lang))
```

---

### Этап 6: Тестирование

#### 6.1 Локальное тестирование

**Подготовка:**

```bash
# 1. Установить зависимости
pip install openpyxl==3.1.5

# 2. Запустить бота локально
python manage.py runbot
```

**Тестовые сценарии:**

##### Сценарий 1: Проверка без подписки

1. Открыть бота
2. Перейти в "💸 Траты сегодня"
3. Нажать "📔 Дневник трат"
4. Нажать "📄 CSV" или "📊 Excel"
5. **Ожидаемый результат:** Сообщение о необходимости Premium подписки

##### Сценарий 2: Экспорт CSV с подпиской

1. Активировать Premium подписку (в админке или через промокод)
2. Открыть дневник трат
3. Нажать "📄 CSV"
4. **Ожидаемый результат:**
   - Сообщение "⏳ Генерируем отчет..."
   - Получен файл `Coins_Отчет_ноябрь_2025.csv`
   - Файл открывается в Excel без кракозябр
   - Данные корректные (даты, суммы, категории)
   - Порядок колонок: Дата, Время, Сумма, Валюта, Категория, Описание, Тип

##### Сценарий 3: Экспорт XLSX с подпиской

1. С активной подпиской открыть дневник трат
2. Нажать "📊 Excel"
3. **Ожидаемый результат:**
   - Сообщение "⏳ Генерируем отчет..."
   - Получен файл `Coins_Отчет_ноябрь_2025.xlsx`
   - Файл открывается в Excel
   - **Лист "Детализация":**
     - Все операции за месяц
     - Доходы зеленым, расходы красным
     - Итоговые строки по валютам
     - Автоширина колонок
   - **Лист "Сводка":**
     - Таблица по категориям (ВСЕ категории показаны)
     - Круговая диаграмма расходов по категориям
     - Столбчатая диаграмма расходов по дням
     - Графики корректно отображаются

##### Сценарий 4: Режимы просмотра

1. **Личный режим:**
   - Экспортировать CSV/XLSX
   - Проверить что показаны только личные операции

2. **Семейный режим:**
   - Переключиться на семейный бюджет
   - Экспортировать CSV/XLSX
   - Проверить что показаны операции всех членов семьи

##### Сценарий 5: Граничные случаи

1. **Пустой месяц:**
   - Удалить все операции за текущий месяц
   - Попытаться экспортировать
   - **Ожидаемый результат:** "📭 Нет данных за текущий месяц"

2. **Много операций (100+):**
   - Создать 100+ операций за месяц
   - Экспортировать XLSX
   - Проверить что все операции на месте
   - Проверить что графики корректны

3. **Разные валюты:**
   - Создать операции в RUB, USD, EUR
   - Экспортировать
   - Проверить что итоги подсчитаны отдельно по валютам

4. **Emoji в категориях:**
   - Проверить что emoji корректно отображаются
   - В CSV и XLSX

#### 6.2 Проверка производительности

```python
# Замерить время генерации
import time

# CSV
start = time.time()
csv_bytes = export_service.generate_csv(expenses, incomes, 2025, 11, 'ru')
csv_time = time.time() - start
print(f"CSV generation: {csv_time:.2f} sec")
# Ожидается: < 1 сек

# XLSX
start = time.time()
xlsx_file = export_service.generate_xlsx_with_charts(expenses, incomes, 2025, 11, 'ru')
xlsx_time = time.time() - start
print(f"XLSX generation: {xlsx_time:.2f} sec")
# Ожидается: < 3 сек
```

#### 6.3 Проверка размера файлов

```python
import sys

# CSV
csv_size = sys.getsizeof(csv_bytes) / 1024  # KB
print(f"CSV size: {csv_size:.2f} KB")

# XLSX
xlsx_file.seek(0, 2)  # Конец файла
xlsx_size = xlsx_file.tell() / 1024  # KB
print(f"XLSX size: {xlsx_size:.2f} KB")
```

---

### Этап 7: Развертывание на сервере

**Последовательность действий:**

#### 7.1 Локальный коммит

```bash
# 1. Проверить изменения
git status

# 2. Добавить все файлы
git add requirements.txt
git add bot/services/export_service.py
git add bot/texts.py
git add bot/routers/reports.py
git add docs/EXPORT_IMPLEMENTATION_PLAN.md

# 3. Проверить что все файлы добавлены
git status

# 4. Создать коммит
git commit -m "$(cat <<'EOF'
Добавлен экспорт отчетов в CSV и XLSX форматы (Premium функция)

Изменения:
- Добавлен сервис export_service.py для генерации CSV и XLSX
- XLSX с графиками: круговая диаграмма по категориям, столбчатая по дням
- Показываются ВСЕ категории без ограничений
- Экспорт доступен только пользователям с Premium подпиской
- Кнопки экспорта в дневнике трат в один ряд
- Экспортируется весь текущий месяц
- Поддержка личного и семейного режимов
- Добавлена документация: docs/EXPORT_IMPLEMENTATION_PLAN.md

Технические детали:
- Библиотека openpyxl==3.1.5 для работы с Excel
- CSV с UTF-8 BOM для корректного открытия в Excel
- Порядок колонок: Дата, Время, Сумма, Валюта, Категория, Описание, Тип
- Форматирование XLSX: цвета, шрифты, автоширина
- Обработка ошибок и логирование

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"

# 5. Push на сервер
git push origin master
```

#### 7.2 Обновление на сервере

**ВАЖНО:** Команды выполняет пользователь на сервере!

```bash
# Подключиться к серверу
ssh batman@94.198.220.155

# Перейти в папку проекта
cd /home/batman/expense_bot

# Обновить код
git pull origin master

# Активировать виртуальное окружение (если используется)
source venv/bin/activate

# Установить новые зависимости
pip install -r requirements.txt

# Проверить что openpyxl установлен
python -c "import openpyxl; print(openpyxl.__version__)"

# Перезапустить бота в Docker
docker-compose restart bot

# Проверить логи
docker-compose logs --tail=50 bot

# Проверить что бот запустился без ошибок
docker-compose ps
```

#### 7.3 Проверка на сервере

```bash
# Посмотреть логи в реальном времени
docker logs -f expense_bot_app

# Проверить обработку экспорта (после тестового экспорта)
docker logs expense_bot_app | grep "exported"
```

---

## 📊 Структура сгенерированных файлов

### CSV файл (Coins_Отчет_ноябрь_2025.csv)

```csv
Дата,Время,Сумма,Валюта,Категория,Описание,Тип
02.11.2025,14:30,-500.00,RUB,🍔 Продукты,Пятерочка,Трата
02.11.2025,09:00,50000.00,RUB,💰 Доход,Зарплата,Доход
01.11.2025,18:45,-1200.00,RUB,🏠 Дом и ремонт,Ikea столик,Трата
01.11.2025,12:30,-350.00,RUB,🍔 Продукты,Магнит,Трата
```

**Особенности:**
- UTF-8 с BOM - открывается в Excel без проблем с кириллицей
- Суммы с 2 знаками после запятой
- Отрицательные для расходов, положительные для доходов
- Даты в формате DD.MM.YYYY
- Время в формате HH:MM

### XLSX файл (Coins_Отчет_ноябрь_2025.xlsx)

#### Лист 1: "Детализация"

```
┌──────────────┬────────┬──────────┬─────────┬────────────────┬──────────────────┬─────────┐
│ Дата         │ Время  │ Сумма    │ Валюта  │ Категория      │ Описание         │ Тип     │
├──────────────┼────────┼──────────┼─────────┼────────────────┼──────────────────┼─────────┤
│ 02.11.2025   │ 14:30  │ -500.00  │ RUB     │ 🍔 Продукты    │ Пятерочка        │ Трата   │
│ 02.11.2025   │ 09:00  │ 50000.00 │ RUB     │ 💰 Доход       │ Зарплата         │ Доход   │
│ 01.11.2025   │ 18:45  │ -1200.00 │ RUB     │ 🏠 Дом и ремонт│ Ikea столик      │ Трата   │
├──────────────┼────────┼──────────┼─────────┼────────────────┼──────────────────┼─────────┤
│ ИТОГО:       │        │ -25340   │ RUB     │                │                  │         │
│ ИТОГО:       │        │ 150000   │ RUB     │                │                  │         │
└──────────────┴────────┴──────────┴─────────┴────────────────┴──────────────────┴─────────┘
```

**Форматирование:**
- Заголовки: синий фон (#4472C4), белый текст, жирный
- Доходы: зеленый текст (#008000), жирный
- Расходы: красный текст (#FF0000)
- Итоги: синий текст (#0000FF), жирный
- Числа: формат #,##0.00 (тысячи с пробелом)
- Автоширина колонок
- Первая строка закреплена

#### Лист 2: "Сводка"

**Таблица по категориям:**

```
┌────────────────┬─────────┬──────────┬────────────┬──────────────┐
│ Категория      │ Валюта  │ Всего    │ Количество │ Средний чек  │
├────────────────┼─────────┼──────────┼────────────┼──────────────┤
│ 🍔 Продукты    │ RUB     │ 25340.50 │ 45         │ 563.12       │
│ 🚗 Транспорт   │ RUB     │ 15000.00 │ 23         │ 652.17       │
│ 🏠 Дом и ремонт│ RUB     │ 8900.00  │ 12         │ 741.67       │
│ 🎬 Развлечения │ RUB     │ 7200.00  │ 8          │ 900.00       │
│ ...            │ ...     │ ...      │ ...        │ ...          │
└────────────────┴─────────┴──────────┴────────────┴──────────────┘
```

**ВАЖНО:** Показываются ВСЕ категории без ограничений!

**Графики:**

1. **Круговая диаграмма расходов по категориям:**
   - Справа от таблицы (колонка G, строка 2)
   - Размер: 15x12
   - Цветовая палитра как в PDF отчете
   - Легенда с названиями категорий
   - Подписи с процентами

2. **Столбчатая диаграмма расходов по дням:**
   - Справа от таблицы (колонка G, ниже круговой)
   - Размер: 20x10
   - Ось X: дни месяца (1-30/31)
   - Ось Y: сумма расходов
   - Показывает динамику трат по дням

**Таблица по дням (для графика):**

```
┌──────┬──────────┐
│ День │ Сумма    │
├──────┼──────────┤
│ 1    │ 1500.00  │
│ 2    │ 2300.50  │
│ 3    │ 850.00   │
│ ...  │ ...      │
│ 30   │ 1200.00  │
└──────┴──────────┘
```

Эта таблица создается в колонках H-I для построения столбчатой диаграммы.

---

## 🎯 Итоговая структура интерфейса

### Кнопки в дневнике трат:

```
📔 Дневник трат за ноябрь 2025
┌─────────────────────────────────────────────┐
│ 02.11.2025 (сегодня)                        │
│ 14:30  Пятерочка            -500.00 RUB     │
│ 09:00  Зарплата          +50000.00 RUB      │
│                                             │
│ 01.11.2025                                  │
│ 18:45  Ikea столик         -1200.00 RUB     │
│ 12:30  Магнит               -350.00 RUB     │
│                                             │
│ Всего трат: -25,340 RUB                     │
│ Всего доходов: +150,000 RUB                 │
└─────────────────────────────────────────────┘

[🏠 Семейный бюджет]         ← если есть семья
[📄 CSV] [📊 Excel]          ← НОВОЕ! В один ряд
[← Назад]
[❌ Закрыть]
```

### Поведение кнопок:

**Без Premium подписки:**
- Нажатие на любую кнопку экспорта → Сообщение о Premium + кнопка подписки

**С Premium подпиской:**
- Нажатие на [📄 CSV] → Генерация и отправка CSV файла
- Нажатие на [📊 Excel] → Генерация и отправка XLSX файла с графиками

---

## 📝 Чеклист реализации

### Этап 1: Зависимости
- [ ] Добавлен openpyxl==3.1.5 в requirements.txt
- [ ] Установлен локально: `pip install openpyxl==3.1.5`
- [ ] Проверка импорта: `import openpyxl`

### Этап 2: Сервис экспорта
- [ ] Создан файл bot/services/export_service.py
- [ ] Реализован класс ExportService
- [ ] Реализован метод prepare_operations_data()
- [ ] Реализован метод generate_csv() с UTF-8 BOM
- [ ] Реализован метод generate_xlsx_with_charts()
- [ ] Реализован метод _create_details_sheet()
- [ ] Реализован метод _create_summary_sheet()
- [ ] Добавлена круговая диаграмма по категориям
- [ ] Добавлена столбчатая диаграмма по дням
- [ ] Проверено: показываются ВСЕ категории

### Этап 3: Тексты
- [ ] Добавлены русские тексты в bot/texts.py
- [ ] Добавлены английские тексты в bot/texts.py
- [ ] Проверены переводы

### Этап 4: Кнопки
- [ ] Найдена функция callback_show_diary в bot/routers/reports.py
- [ ] Добавлены кнопки экспорта в один ряд
- [ ] Проверено расположение кнопок

### Этап 5: Обработчики
- [ ] Добавлены импорты в bot/routers/reports.py
- [ ] Создан обработчик callback_export_month_csv
- [ ] Создан обработчик callback_export_month_excel
- [ ] Добавлена проверка премиум подписки
- [ ] Добавлена поддержка личного/семейного режима
- [ ] Добавлено логирование
- [ ] Добавлена обработка ошибок

### Этап 6: Тестирование
- [ ] Локальное тестирование без подписки
- [ ] Локальное тестирование CSV экспорта с подпиской
- [ ] Локальное тестирование XLSX экспорта с подпиской
- [ ] Проверка личного режима
- [ ] Проверка семейного режима
- [ ] Проверка пустого месяца
- [ ] Проверка с большим количеством операций (100+)
- [ ] Проверка с разными валютами
- [ ] Проверка emoji в категориях
- [ ] Замер производительности (CSV < 1 сек, XLSX < 3 сек)
- [ ] Проверка размера файлов

### Этап 7: Развертывание
- [ ] Коммит всех изменений
- [ ] Push на GitHub
- [ ] Обновление на сервере: `git pull`
- [ ] Установка зависимостей: `pip install -r requirements.txt`
- [ ] Перезапуск бота: `docker-compose restart bot`
- [ ] Проверка логов на сервере
- [ ] Тестирование на production

---

## 🚀 Критерии успеха

### Функциональные:
✅ Кнопки экспорта отображаются в дневнике трат
✅ Без Premium показывается сообщение о подписке
✅ С Premium генерируются файлы CSV и XLSX
✅ CSV открывается в Excel без кракозябр
✅ XLSX содержит 2 листа с форматированием
✅ XLSX содержит графики (круговой и столбчатый)
✅ Показываются ВСЕ категории без ограничений
✅ Экспортируется весь текущий месяц
✅ Поддерживаются личный и семейный режимы
✅ Порядок колонок: Дата, Время, Сумма, Валюта, Категория, Описание, Тип

### Технические:
✅ Генерация CSV < 1 сек
✅ Генерация XLSX < 3 сек
✅ Размер файлов < 5 MB
✅ Нет ошибок в логах
✅ Корректная обработка исключений
✅ Логирование всех операций

### UX:
✅ Понятные сообщения пользователю
✅ Сообщение о процессе генерации
✅ Красивое форматирование XLSX
✅ Интуитивные названия файлов
✅ Файлы открываются без проблем

---

## 📊 Метрики для отслеживания

После запуска функционала рекомендуется отслеживать:

1. **Использование функции:**
   - Количество экспортов CSV в день
   - Количество экспортов XLSX в день
   - Процент пользователей, использующих экспорт

2. **Конверсия в Premium:**
   - Сколько бесплатных пользователей пытаются экспортировать
   - Сколько из них покупают Premium после этого

3. **Производительность:**
   - Среднее время генерации CSV
   - Среднее время генерации XLSX
   - Пиковая нагрузка

4. **Ошибки:**
   - Количество ошибок при экспорте
   - Типы ошибок
   - Проблемные сценарии

---

## 🔧 Возможные проблемы и решения

### Проблема 1: Кракозябры в CSV при открытии в Excel

**Причина:** Отсутствие BOM в UTF-8

**Решение:**
```python
return '\ufeff'.encode('utf-8') + output.getvalue().encode('utf-8')
```

### Проблема 2: Графики не отображаются в XLSX

**Причина:** Неправильные Reference или координаты

**Решение:** Проверить `min_row`, `max_row`, `min_col`, `max_col` в Reference

### Проблема 3: Медленная генерация XLSX

**Причина:** Много категорий или операций

**Решение:** Оптимизация запросов с `select_related()`, кеширование данных

### Проблема 4: Файл не отправляется через Telegram

**Причина:** Превышен лимит 50 MB

**Решение:** Ограничить период экспорта или сжать данные

### Проблема 5: Ошибка при экспорте семейного бюджета

**Причина:** Неправильная выборка участников домохозяйства

**Решение:**
- Использовать `household.profiles.all()` для получения всех участников
- Или фильтры `profile__household=profile.household` в QuerySet
- Помнить: Profile имеет FK к Household, обратная связь - `profiles` (не `members`)

---

## 🎓 Дальнейшее развитие

### Возможные улучшения в будущем:

1. **Выбор периода экспорта:**
   - Не только текущий месяц
   - За прошлый месяц
   - За квартал
   - За год
   - Кастомный период (даты с-по)

2. **Дополнительные графики в XLSX:**
   - График доходов по дням
   - Сравнение расходов/доходов
   - Динамика баланса
   - Топ-5 категорий с трендом

3. **Настройки экспорта:**
   - Выбор валюты для отображения
   - Фильтр по категориям
   - Группировка по неделям/месяцам

4. **Автоматический экспорт:**
   - Ежемесячная отправка отчета на email
   - Интеграция с Google Drive
   - Интеграция с Dropbox

5. **Расширенная аналитика в XLSX:**
   - Прогноз расходов на следующий месяц
   - Сравнение с прошлым месяцем
   - Рекомендации по оптимизации

---

## 📚 Полезные ссылки

- [openpyxl документация](https://openpyxl.readthedocs.io/)
- [openpyxl charts](https://openpyxl.readthedocs.io/en/stable/charts/introduction.html)
- [CSV спецификация](https://tools.ietf.org/html/rfc4180)
- [Telegram Bot API - sendDocument](https://core.telegram.org/bots/api#senddocument)

---

**Документ подготовлен:** 02.11.2025
**Версия плана:** 1.0
**Статус:** Готов к реализации
