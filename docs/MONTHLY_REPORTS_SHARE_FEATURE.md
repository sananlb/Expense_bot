# План реализации: Выбор формата ежемесячного отчета

## 📋 Обзор изменений

### Текущее поведение
1 числа каждого месяца в 10:00 всем пользователям с Premium подпиской автоматически отправляется PDF отчет за предыдущий месяц с AI инсайтами.

### Новое поведение
1. **1 числа месяца**: Отправляется сообщение с AI инсайтами + 3 кнопки для выбора формата (CSV/Excel/PDF)
2. **После генерации отчета**: В caption добавляется рекламный текст "🤖 Сгенерировано в Coins @showmecoinbot"
3. **Пересылка отчета**: Пользователь использует встроенную функцию Telegram (Forward)

---

## 🎯 Задача 1: Изменение автоматической отправки отчетов

### Файл: `bot/services/notifications.py`

#### Текущий код (строки 22-107):
```python
async def send_monthly_report(self, user_id: int, profile: Profile, year: int = None, month: int = None):
    """Send monthly expense report for specified year/month (defaults to current month)"""
    # ... генерирует PDF и отправляет с AI инсайтами
```

#### Новый код:
```python
async def send_monthly_report_notification(self, user_id: int, profile: Profile, year: int = None, month: int = None):
    """Send monthly report notification with format selection buttons"""
    try:
        from ..services.monthly_insights import MonthlyInsightsService
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        today = date.today()

        # Если год/месяц не указаны - используем предыдущий месяц
        if year is None or month is None:
            if today.month == 1:
                report_month = 12
                report_year = today.year - 1
            else:
                report_month = today.month - 1
                report_year = today.year
        else:
            report_year = year
            report_month = month

        month_name = get_month_name(report_month, 'ru')

        # Генерируем AI инсайты
        caption = f"📊 Ваш отчет за {month_name} {report_year} готов!"

        try:
            insights_service = MonthlyInsightsService()
            insight = await insights_service.get_insight(profile, report_year, report_month)

            if not insight:
                insight = await insights_service.generate_insight(
                    profile=profile,
                    year=report_year,
                    month=report_month,
                    provider='google',
                    force_regenerate=False
                )

            if insight:
                insight_text = self._format_insight_text(insight, report_month, report_year)
                full_caption = f"{caption}\n\n{insight_text}\n\n💡 Выберите формат для скачивания:"

                if len(full_caption) <= 4000:
                    caption = full_caption
                else:
                    max_insight_length = 4000 - len(caption) - 50
                    if max_insight_length > 100:
                        truncated_insight = insight_text[:max_insight_length] + "..."
                        caption = f"{caption}\n\n{truncated_insight}\n\n💡 Выберите формат для скачивания:"

        except Exception as e:
            logger.error(f"Error generating insights for user {user_id}: {e}")
            caption += "\n\n💡 Выберите формат для скачивания:"

        # Создаем клавиатуру с кнопками форматов (в один ряд, как в expenses_summary_keyboard)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 CSV", callback_data=f"monthly_report_csv_{report_year}_{report_month}"),
                InlineKeyboardButton(text="📊 Excel", callback_data=f"monthly_report_xlsx_{report_year}_{report_month}"),
                InlineKeyboardButton(text="📄 PDF", callback_data=f"monthly_report_pdf_{report_year}_{report_month}")
            ]
        ])

        # Отправляем сообщение с кнопками
        await self.bot.send_message(
            chat_id=user_id,
            text=caption,
            reply_markup=keyboard,
            parse_mode='HTML'
        )

        logger.info(f"Monthly report notification sent to user {user_id} for {report_year}-{report_month:02d}")

    except Exception as e:
        logger.error(f"Error sending monthly report notification to user {user_id}: {e}")
```

#### Изменения в `expense_bot/celery_tasks.py` (строка 73):
```python
# Было:
loop.run_until_complete(
    service.send_monthly_report(profile.telegram_id, profile)
)

# Стало:
loop.run_until_complete(
    service.send_monthly_report_notification(profile.telegram_id, profile)
)
```

---

## 🎯 Задача 2: Создание callback обработчиков

### Файл: `bot/routers/reports.py`

Добавить три новых обработчика после существующих `callback_export_month_csv`, `callback_export_month_excel`.

**⚠️ ВАЖНО**: Код НЕ идентичен существующим обработчикам!

**Ключевое отличие**: Существующие обработчики (`callback_export_month_csv`, `callback_export_month_excel`) берут период из **FSM state** (`report_start_date`/`report_end_date`), который заполняется при навигации по меню.

Новые обработчики вызываются из push-уведомления 1 числа, где state НЕ заполнен. Поэтому нужно:
1. **Парсить год и месяц из `callback_data`** (формат: `monthly_report_csv_YEAR_MONTH`)
2. **Запрашивать операции напрямую** по году/месяцу (не из state)

#### Пример для CSV:

```python
@router.callback_query(F.data.startswith("monthly_report_csv_"))
async def callback_monthly_report_csv(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Генерация CSV отчета из ежемесячного уведомления"""
    try:
        from expenses.models import Expense, Income, Profile
        from bot.services.export_service import ExportService
        from bot.services.profile import get_user_settings
        from asgiref.sync import sync_to_async
        from aiogram.types import BufferedInputFile

        user_id = callback.from_user.id

        # ========== ОТЛИЧИЕ 1: Парсим callback_data ==========
        # Формат: monthly_report_csv_2025_10
        parts = callback.data.split('_')
        year = int(parts[3])
        month = int(parts[4])

        # Проверка Premium подписки
        if not await check_subscription(user_id):
            await callback.answer()
            await callback.message.answer(
                get_text('export_premium_required', lang),
                reply_markup=get_subscription_button(),
                parse_mode="HTML"
            )
            return

        await callback.answer(get_text('export_generating', lang), show_alert=False)

        # ========== ОТЛИЧИЕ 2: Запрашиваем данные по year/month ==========
        @sync_to_async
        def get_user_data():
            profile = Profile.objects.get(telegram_id=user_id)
            settings = get_user_settings.__wrapped__(user_id)
            household_mode = bool(profile.household) and getattr(settings, 'view_scope', 'personal') == 'household'

            if household_mode:
                expenses = list(
                    Expense.objects.filter(
                        profile__household=profile.household,
                        expense_date__year=year,
                        expense_date__month=month
                    ).select_related('category').order_by('-expense_date', '-expense_time')
                )
                incomes = list(
                    Income.objects.filter(
                        profile__household=profile.household,
                        income_date__year=year,
                        income_date__month=month
                    ).select_related('category').order_by('-income_date', '-income_time')
                )
            else:
                expenses = list(
                    Expense.objects.filter(
                        profile__telegram_id=user_id,
                        expense_date__year=year,
                        expense_date__month=month
                    ).select_related('category').order_by('-expense_date', '-expense_time')
                )
                incomes = list(
                    Income.objects.filter(
                        profile__telegram_id=user_id,
                        income_date__year=year,
                        income_date__month=month
                    ).select_related('category').order_by('-income_date', '-income_time')
                )

            return expenses, incomes, household_mode

        expenses, incomes, household_mode = await get_user_data()

        # Проверка на пустоту
        if not expenses and not incomes:
            await callback.message.answer(
                get_text('export_empty', lang),
                parse_mode="HTML"
            )
            return

        # Генерация CSV
        @sync_to_async
        def generate_csv_file():
            return ExportService.generate_csv(expenses, incomes, year, month, lang, user_id, household_mode)

        csv_bytes = await generate_csv_file()

        # Формируем имя файла
        month_names_ru = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
                         'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
        month_names_en = ['January', 'February', 'March', 'April', 'May', 'June',
                         'July', 'August', 'September', 'October', 'November', 'December']
        month_name = month_names_ru[month - 1] if lang == 'ru' else month_names_en[month - 1]

        filename = f"expenses_{month_name}_{year}.csv"
        document = BufferedInputFile(csv_bytes, filename=filename)

        # ========== ОТЛИЧИЕ 3: Добавляем рекламный текст ==========
        caption = (
            f"{get_text('export_success', lang).format(month=f'{month_name} {year}')}\n\n"
            f"🤖 Сгенерировано в Coins @showmecoinbot"
        )

        # Отправляем файл
        await callback.message.answer_document(
            document,
            caption=caption,
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error generating monthly CSV report: {e}", exc_info=True)
        await callback.message.answer(
            get_text('export_error', lang),
            parse_mode="HTML"
        )
```

Аналогично для **XLSX** и **PDF** - копируем эту же логику:
1. Парсим `callback_data` для получения year/month
2. Запрашиваем данные по этим параметрам (не из state)
3. Добавляем рекламный текст в caption

---

## 🎯 Задача 3: Обновление существующих обработчиков экспорта

Опционально можно добавить рекламный текст и в существующие обработчики экспорта (когда пользователь сам выбирает экспорт из меню):

### Файлы для изменения:

**1. `bot/routers/reports.py`:**
- `callback_export_month_csv` (строка ~920)
- `callback_export_month_excel` (строка ~1050)

**2. `bot/routers/expense.py`:**
- `callback_pdf_generate_current` (строка 442)

Добавить рекламный текст в caption:

```python
# Было:
caption = get_text('export_success', lang).format(month=f"{month_name} {year}")

# Стало:
caption = (
    f"{get_text('export_success', lang).format(month=f'{month_name} {year}')}\n\n"
    f"🤖 Сгенерировано в Coins @showmecoinbot"
)
```

---

## 🌐 Добавление текстов

### Файл: `bot/texts.py`

Не требуется - используем существующие тексты + добавляем рекламный текст напрямую в код.

---

## ✅ Чек-лист реализации

### Этап 1: Изменение уведомления
- [ ] Переименовать `send_monthly_report` → `send_monthly_report_notification` в `bot/services/notifications.py`
- [ ] Изменить тело функции: убрать генерацию PDF, добавить кнопки выбора формата
- [ ] Обновить вызов в `expense_bot/celery_tasks.py` (строка 73)

### Этап 2: Создание обработчиков (в `bot/routers/reports.py`)
- [ ] `callback_monthly_report_csv_*`:
  - [ ] Парсить year/month из callback_data (формат: `monthly_report_csv_YEAR_MONTH`)
  - [ ] Запросить expenses/incomes по year/month (НЕ из state!)
  - [ ] Генерировать CSV
  - [ ] Добавить рекламный текст в caption
- [ ] `callback_monthly_report_xlsx_*`:
  - [ ] Парсить year/month из callback_data
  - [ ] Запросить expenses/incomes по year/month
  - [ ] Генерировать XLSX
  - [ ] Добавить рекламный текст в caption
- [ ] `callback_monthly_report_pdf_*`:
  - [ ] Парсить year/month из callback_data
  - [ ] Вызвать PDFReportService с year/month
  - [ ] Добавить рекламный текст в caption

### Этап 3 (опционально): Обновление существующих обработчиков
- [ ] `callback_export_month_csv` в `bot/routers/reports.py:920`
- [ ] `callback_export_month_excel` в `bot/routers/reports.py:1050`
- [ ] `callback_pdf_generate_current` в `bot/routers/expense.py:442`

### Этап 4: Тестирование
- [ ] Автоматическая отправка уведомления 1 числа (можно эмулировать)
- [ ] Генерация PDF по кнопке из уведомления
- [ ] Генерация XLSX по кнопке из уведомления
- [ ] Генерация CSV по кнопке из уведомления
- [ ] Проверить caption с рекламным текстом на всех форматах
- [ ] Проверить пересылку сообщения (Forward) - рекламный текст должен сохраняться

---

## 🎨 Визуальный дизайн

### Уведомление 1 числа:
```
📊 Ваш отчет за октябрь 2025 готов!

💰 Расходы: 45 230 ₽
📊 Количество трат: 87

🏆 Топ категорий:
1. Супермаркеты: 12 450₽ (28%)
2. Рестораны: 8 900₽ (20%)
3. АЗС: 7 650₽ (17%)

📝 За октябрь вы стали чаще питаться вне дома...

💡 Выберите формат для скачивания:

[📋 CSV] [📊 Excel] [📄 PDF]
```

### После генерации отчета:
```
✅ Отчет за октябрь 2025 успешно сгенерирован!

🤖 Сгенерировано в Coins @showmecoinbot

[Файл: expenses_october_2025.xlsx]
```

Пользователь может нажать встроенную кнопку "Forward" → выбрать контакт → отправить.

---

## 📝 Примечания

1. **Простота**: Никаких токенов, БД, миграций
2. **Реклама**: При пересылке получатель видит "🤖 Сгенерировано в Coins @showmecoinbot"
3. **Гибкость**: Пользователь сам выбирает формат (PDF/XLSX/CSV)
4. **UX**: Используется встроенный механизм пересылки Telegram
5. **⚠️ Важно**: Новые обработчики НЕ используют FSM state - парсят данные из callback_data
6. **Расположение файлов**:
   - CSV/XLSX обработчики → `bot/routers/reports.py`
   - PDF обработчик существует в → `bot/routers/expense.py:442` (не pdf_report.py!)

---

## 🚀 Последовательность внедрения

1. **Этап 1**: Изменить уведомление 1 числа (убрать прямую генерацию PDF, добавить кнопки)
2. **Этап 2**: Создать 3 callback обработчика для форматов
3. **Этап 3**: Добавить рекламный текст в caption
4. **Этап 4**: Тестирование всего флоу
5. **Этап 5** (опционально): Добавить рекламный текст в существующие обработчики экспорта

---

## 🔄 Обратная совместимость

- Старые PDF отчеты, сгенерированные вручную через меню, продолжат работать
- Изменяется только автоматическая отправка 1 числа месяца
- Все существующие функции экспорта остаются без изменений
