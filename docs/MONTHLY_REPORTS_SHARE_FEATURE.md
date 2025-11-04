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

**Важно**: Код практически идентичен существующим обработчикам, но:
1. Callback data: `monthly_report_*` вместо `export_month_*`
2. В caption добавляем рекламный текст

#### Пример для CSV:

```python
@router.callback_query(F.data.startswith("monthly_report_csv_"))
async def callback_monthly_report_csv(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Генерация CSV отчета из ежемесячного уведомления"""
    try:
        # ... (код идентичен callback_export_month_csv) ...

        # ========== ЕДИНСТВЕННОЕ ОТЛИЧИЕ ==========
        # Формируем caption с рекламным текстом
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
```

Аналогично для **XLSX** и **PDF** - просто копируем логику из `callback_export_month_excel` и `pdf_generate_current`, добавляя рекламный текст в caption.

---

## 🎯 Задача 3: Обновление существующих обработчиков экспорта

Опционально можно добавить рекламный текст и в существующие обработчики экспорта (когда пользователь сам выбирает экспорт из меню):

### Файл: `bot/routers/reports.py`

В функциях:
- `callback_export_month_csv` (строка ~920)
- `callback_export_month_excel` (строка ~1050)
- `callback_pdf_generate_current` (в `bot/routers/pdf_report.py`)

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

- [ ] Переименовать `send_monthly_report` → `send_monthly_report_notification` в `bot/services/notifications.py`
- [ ] Изменить тело функции: убрать генерацию PDF, добавить кнопки выбора формата
- [ ] Обновить вызов в `expense_bot/celery_tasks.py` (строка 73)
- [ ] Создать 3 callback обработчика в `bot/routers/reports.py`:
  - [ ] `callback_monthly_report_csv_*`
  - [ ] `callback_monthly_report_xlsx_*`
  - [ ] `callback_monthly_report_pdf_*`
- [ ] Добавить рекламный текст в caption всех трех обработчиков
- [ ] (Опционально) Добавить рекламный текст в существующие обработчики экспорта
- [ ] Протестировать весь флоу:
  - [ ] Автоматическая отправка уведомления 1 числа
  - [ ] Генерация PDF по кнопке
  - [ ] Генерация XLSX по кнопке
  - [ ] Генерация CSV по кнопке
  - [ ] Проверить caption с рекламным текстом
  - [ ] Проверить пересылку сообщения (Forward)

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
