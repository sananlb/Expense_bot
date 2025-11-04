# План реализации: Выбор формата отчета и расшаривание

## 📋 Обзор изменений

### Текущее поведение
1 числа каждого месяца в 10:00 всем пользователям с Premium подпиской автоматически отправляется PDF отчет за предыдущий месяц с AI инсайтами.

### Новое поведение
1. **1 числа месяца**: Отправляется сообщение с AI инсайтами + 3 кнопки для выбора формата
2. **После генерации отчета**: Под каждым отчетом кнопка "Поделиться отчетом"
3. **При расшаривании**: Получатель получает отчет + приветственное сообщение

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

Добавить три новых обработчика после существующих `callback_export_month_csv`, `callback_export_month_excel`:

```python
@router.callback_query(F.data.startswith("monthly_report_csv_"))
async def callback_monthly_report_csv(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Генерация CSV отчета из ежемесячного уведомления"""
    try:
        from expenses.models import Expense, Income, Profile
        from bot.services.export_service import ExportService
        from bot.services.profile import get_user_settings
        from asgiref.sync import sync_to_async

        user_id = callback.from_user.id

        # Извлекаем год и месяц из callback_data
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

        # Показываем уведомление о генерации
        await callback.answer(get_text('export_generating', lang), show_alert=False)

        # Получаем данные пользователя и операции (аналогично callback_export_month_csv)
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

        # Создаем клавиатуру с кнопкой "Поделиться отчетом"
        share_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📤 Поделиться отчетом" if lang == 'ru' else "📤 Share report",
                callback_data=f"share_report_{year}_{month}_csv"
            )]
        ])

        # Отправляем файл с кнопкой
        await callback.message.answer_document(
            document,
            caption=get_text('export_success', lang).format(month=f"{month_name} {year}"),
            parse_mode="HTML",
            reply_markup=share_keyboard
        )

    except Exception as e:
        logger.error(f"Error generating monthly CSV report: {e}", exc_info=True)
        await callback.message.answer(
            get_text('export_error', lang),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("monthly_report_xlsx_"))
async def callback_monthly_report_xlsx(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Генерация XLSX отчета из ежемесячного уведомления"""
    # Аналогично CSV, но вызываем generate_xlsx_with_charts
    # ... (код идентичен CSV, только меняется генерация и filename на .xlsx)
    pass


@router.callback_query(F.data.startswith("monthly_report_pdf_"))
async def callback_monthly_report_pdf(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Генерация PDF отчета из ежемесячного уведомления"""
    try:
        from bot.services.pdf_report import PDFReportService
        from aiogram.types import BufferedInputFile

        user_id = callback.from_user.id

        # Извлекаем год и месяц
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

        await callback.answer(get_text('generating_report', lang), show_alert=False)

        # Генерируем PDF
        pdf_service = PDFReportService()
        pdf_bytes = await pdf_service.generate_monthly_report(
            user_id=user_id,
            year=year,
            month=month,
            lang=lang
        )

        if not pdf_bytes:
            await callback.message.answer(
                get_text('no_data_for_report', lang),
                parse_mode="HTML"
            )
            return

        # Формируем имя файла
        month_names_ru = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
                         'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
        month_names_en = ['January', 'February', 'March', 'April', 'May', 'June',
                         'July', 'August', 'September', 'October', 'November', 'December']
        month_name = month_names_ru[month - 1] if lang == 'ru' else month_names_en[month - 1]

        filename = f"Report_Coins_{month_name}_{year}.pdf"
        pdf_file = BufferedInputFile(pdf_bytes, filename=filename)

        # Создаем клавиатуру с кнопкой "Поделиться отчетом"
        share_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📤 Поделиться отчетом" if lang == 'ru' else "📤 Share report",
                callback_data=f"share_report_{year}_{month}_pdf"
            )]
        ])

        # Отправляем PDF с кнопкой
        await callback.message.answer_document(
            document=pdf_file,
            caption=get_text('export_success', lang).format(month=f"{month_name} {year}"),
            parse_mode="HTML",
            reply_markup=share_keyboard
        )

    except Exception as e:
        logger.error(f"Error generating monthly PDF report: {e}", exc_info=True)
        await callback.message.answer(
            get_text('export_error', lang),
            parse_mode="HTML"
        )
```

---

## 🎯 Задача 3: Кнопка "Поделиться отчетом"

### Подход: Deep-link (аналогично приглашению в семью)

Создаем модель для хранения временных токенов расшаривания отчетов.

### Файл: `expenses/models.py`

```python
class ReportShareToken(models.Model):
    """Токен для расшаривания отчета"""
    token = models.CharField(max_length=32, unique=True, db_index=True)
    sender = models.ForeignKey('Profile', on_delete=models.CASCADE, related_name='shared_reports')
    year = models.IntegerField()
    month = models.IntegerField()
    format = models.CharField(max_length=10, choices=[('pdf', 'PDF'), ('xlsx', 'XLSX'), ('csv', 'CSV')])
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_name = 'expenses_reportsharetok'
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['sender', 'created_at']),
        ]

    def is_valid(self):
        """Проверка валидности токена"""
        from django.utils import timezone
        return timezone.now() < self.expires_at

    def __str__(self):
        return f"Share token for {self.sender.telegram_id} - {self.year}/{self.month} ({self.format})"
```

### Файл: `bot/services/report_share.py` (новый)

```python
import secrets
import logging
from datetime import timedelta
from django.utils import timezone
from expenses.models import ReportShareToken, Profile

logger = logging.getLogger(__name__)


class ReportShareService:
    """Сервис для расшаривания отчетов"""

    @staticmethod
    def generate_share_link(sender_profile: Profile, year: int, month: int, format: str, bot_username: str) -> tuple[bool, str]:
        """
        Генерирует ссылку для расшаривания отчета

        Returns:
            (success: bool, result: str) - где result это либо ссылка, либо сообщение об ошибке
        """
        try:
            # Генерируем уникальный токен
            token = secrets.token_urlsafe(16)

            # Создаем запись в БД (срок действия 7 дней)
            expires_at = timezone.now() + timedelta(days=7)

            ReportShareToken.objects.create(
                token=token,
                sender=sender_profile,
                year=year,
                month=month,
                format=format,
                expires_at=expires_at
            )

            # Формируем deep-link
            share_link = f"https://t.me/{bot_username}?start=report_{token}"

            logger.info(f"Generated share link for user {sender_profile.telegram_id}: {token}")

            return True, share_link

        except Exception as e:
            logger.error(f"Error generating share link: {e}")
            return False, "Ошибка при генерации ссылки"

    @staticmethod
    def get_report_by_token(token: str) -> tuple[bool, object]:
        """
        Получает данные отчета по токену

        Returns:
            (success: bool, data: ReportShareToken or str) - данные отчета или сообщение об ошибке
        """
        try:
            share_token = ReportShareToken.objects.filter(token=token).first()

            if not share_token:
                return False, "Ссылка недействительна"

            if not share_token.is_valid():
                return False, "Срок действия ссылки истек"

            return True, share_token

        except Exception as e:
            logger.error(f"Error retrieving report by token: {e}")
            return False, "Ошибка при получении отчета"
```

### Файл: `bot/routers/reports.py` - добавляем обработчик расшаривания

```python
@router.callback_query(F.data.startswith("share_report_"))
async def callback_share_report(callback: CallbackQuery, lang: str = 'ru'):
    """Генерация ссылки для расшаривания отчета"""
    try:
        from bot.services.report_share import ReportShareService
        from expenses.models import Profile
        from asgiref.sync import sync_to_async

        await callback.answer()

        # Извлекаем данные из callback_data: share_report_YEAR_MONTH_FORMAT
        parts = callback.data.split('_')
        year = int(parts[2])
        month = int(parts[3])
        format = parts[4]  # pdf, xlsx, csv

        user_id = callback.from_user.id

        # Получаем профиль и bot_username
        profile = await sync_to_async(Profile.objects.get)(telegram_id=user_id)
        bot_info = await callback.bot.get_me()

        # Генерируем ссылку
        success, result = await sync_to_async(ReportShareService.generate_share_link)(
            sender_profile=profile,
            year=year,
            month=month,
            format=format,
            bot_username=bot_info.username
        )

        if success:
            month_names_ru = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
                             'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
            month_name = month_names_ru[month - 1]

            # Отправляем ссылку для расшаривания
            await callback.message.answer(
                f"🔗 <b>Ссылка для расшаривания отчета</b>\n\n"
                f"Отчет: {month_name} {year} ({format.upper()})\n\n"
                f"Отправьте эту ссылку другу:\n"
                f"<code>{result}</code>\n\n"
                f"<i>Ссылка действительна 7 дней</i>",
                parse_mode="HTML"
            )
        else:
            await callback.message.answer(
                f"❌ {result}",
                parse_mode="HTML"
            )

    except Exception as e:
        logger.error(f"Error sharing report: {e}", exc_info=True)
        await callback.message.answer(
            get_text('error_occurred', lang),
            parse_mode="HTML"
        )
```

---

## 🎯 Задача 4: Обработка расшаренной ссылки

### Файл: `bot/routers/start.py`

Добавить обработку deep-link с префиксом `report_`:

```python
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    """Обработчик команды /start с поддержкой deep-links"""

    # ... существующий код ...

    # Проверяем наличие параметра (deep-link)
    if command.args:
        args = command.args

        # ... существующие проверки (family_inv_, referral_, etc.) ...

        # Новая проверка: расшаривание отчета
        if args.startswith('report_'):
            token = args[7:]  # Убираем префикс 'report_'
            await process_shared_report(message, token)
            return

    # ... остальной код /start ...


async def process_shared_report(message: Message, token: str):
    """
    Обработка расшаренного отчета
    Вызывается из start.py при обработке deep-link report_*
    """
    from bot.services.report_share import ReportShareService
    from bot.services.pdf_report import PDFReportService
    from bot.services.export_service import ExportService
    from expenses.models import Expense, Income
    from aiogram.types import BufferedInputFile
    from asgiref.sync import sync_to_async

    user_id = message.from_user.id
    profile = await get_or_create_profile(user_id)
    lang = await sync_to_async(lambda: profile.language_code or 'ru')()

    # Получаем данные отчета по токену
    success, result = await sync_to_async(ReportShareService.get_report_by_token)(token)

    if not success:
        await message.answer(
            f"❌ {result}",
            parse_mode="HTML"
        )
        return

    share_token = result

    # Получаем информацию об отправителе
    try:
        sender_chat = await message.bot.get_chat(share_token.sender.telegram_id)
        sender_name = sender_chat.first_name or "Пользователь"
        if sender_chat.username:
            sender_display = f"<a href='https://t.me/{sender_chat.username}'>{sender_name}</a>"
        else:
            sender_display = sender_name
    except Exception:
        sender_display = "Пользователь"

    month_names_ru = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
                     'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
    month_name = month_names_ru[share_token.month - 1]

    # Отправляем приветственное сообщение
    greeting = (
        f"👋 Привет! {sender_display} поделился с тобой своим отчетом!\n\n"
        f"📊 Отчет за {month_name} {share_token.year} ({share_token.format.upper()})\n\n"
        f"🤖 Сгенерировано ботом Coins @showmecoinbot\n\n"
        f"⏳ Генерирую отчет..."
    )

    sent_message = await message.answer(greeting, parse_mode="HTML")

    try:
        # Генерируем отчет в нужном формате
        sender_id = share_token.sender.telegram_id
        year = share_token.year
        month = share_token.month
        format = share_token.format

        if format == 'pdf':
            # Генерируем PDF
            pdf_service = PDFReportService()
            file_bytes = await pdf_service.generate_monthly_report(
                user_id=sender_id,
                year=year,
                month=month,
                lang='ru'
            )
            filename = f"Report_Coins_{month_name}_{year}.pdf"

        elif format == 'xlsx':
            # Получаем данные отправителя
            @sync_to_async
            def get_sender_data():
                from bot.services.profile import get_user_settings
                sender_profile = share_token.sender
                settings = get_user_settings.__wrapped__(sender_id)
                household_mode = bool(sender_profile.household) and getattr(settings, 'view_scope', 'personal') == 'household'

                if household_mode:
                    expenses = list(Expense.objects.filter(
                        profile__household=sender_profile.household,
                        expense_date__year=year,
                        expense_date__month=month
                    ).select_related('category').order_by('-expense_date', '-expense_time'))

                    incomes = list(Income.objects.filter(
                        profile__household=sender_profile.household,
                        income_date__year=year,
                        income_date__month=month
                    ).select_related('category').order_by('-income_date', '-income_time'))
                else:
                    expenses = list(Expense.objects.filter(
                        profile__telegram_id=sender_id,
                        expense_date__year=year,
                        expense_date__month=month
                    ).select_related('category').order_by('-expense_date', '-expense_time'))

                    incomes = list(Income.objects.filter(
                        profile__telegram_id=sender_id,
                        income_date__year=year,
                        income_date__month=month
                    ).select_related('category').order_by('-income_date', '-income_time'))

                return expenses, incomes, household_mode

            expenses, incomes, household_mode = await get_sender_data()

            @sync_to_async
            def generate_xlsx():
                xlsx_buffer = ExportService.generate_xlsx_with_charts(
                    expenses, incomes, year, month, sender_id, 'ru', household_mode
                )
                return xlsx_buffer.read()

            file_bytes = await generate_xlsx()
            filename = f"expenses_{month_name}_{year}.xlsx"

        elif format == 'csv':
            # Аналогично XLSX
            @sync_to_async
            def get_sender_data():
                from bot.services.profile import get_user_settings
                sender_profile = share_token.sender
                settings = get_user_settings.__wrapped__(sender_id)
                household_mode = bool(sender_profile.household) and getattr(settings, 'view_scope', 'personal') == 'household'

                if household_mode:
                    expenses = list(Expense.objects.filter(
                        profile__household=sender_profile.household,
                        expense_date__year=year,
                        expense_date__month=month
                    ).select_related('category').order_by('-expense_date', '-expense_time'))

                    incomes = list(Income.objects.filter(
                        profile__household=sender_profile.household,
                        income_date__year=year,
                        income_date__month=month
                    ).select_related('category').order_by('-income_date', '-income_time'))
                else:
                    expenses = list(Expense.objects.filter(
                        profile__telegram_id=sender_id,
                        expense_date__year=year,
                        expense_date__month=month
                    ).select_related('category').order_by('-expense_date', '-expense_time'))

                    incomes = list(Income.objects.filter(
                        profile__telegram_id=sender_id,
                        income_date__year=year,
                        income_date__month=month
                    ).select_related('category').order_by('-income_date', '-income_time'))

                return expenses, incomes, household_mode

            expenses, incomes, household_mode = await get_sender_data()

            @sync_to_async
            def generate_csv():
                return ExportService.generate_csv(
                    expenses, incomes, year, month, 'ru', sender_id, household_mode
                )

            file_bytes = await generate_csv()
            filename = f"expenses_{month_name}_{year}.csv"

        if file_bytes:
            document = BufferedInputFile(file_bytes, filename=filename)

            # Отправляем документ
            await message.answer_document(
                document,
                caption=f"✅ Вот отчет от {sender_display}!",
                parse_mode="HTML"
            )

            # Удаляем сообщение "Генерирую отчет..."
            await sent_message.delete()
        else:
            await sent_message.edit_text(
                "❌ Не удалось сгенерировать отчет (нет данных)",
                parse_mode="HTML"
            )

    except Exception as e:
        logger.error(f"Error processing shared report: {e}", exc_info=True)
        await sent_message.edit_text(
            "❌ Произошла ошибка при генерации отчета",
            parse_mode="HTML"
        )
```

---

## 🗄️ Миграция базы данных

Создать новую миграцию для модели `ReportShareToken`:

```bash
python manage.py makemigrations expenses --name add_report_share_token
python manage.py migrate
```

---

## 🌐 Добавление текстов

### Файл: `bot/texts.py`

Добавить новые ключи:

```python
TEXTS = {
    'ru': {
        # ... существующие тексты ...
        'monthly_report_ready': '📊 Ваш отчет за {month} {year} готов!',
        'select_report_format': '💡 Выберите формат для скачивания:',
        'share_report_button': '📤 Поделиться отчетом',
        'share_report_title': '🔗 Ссылка для расшаривания отчета',
        'share_report_link_desc': 'Отчет: {month} {year} ({format})\n\nОтправьте эту ссылку другу:',
        'share_report_valid': 'Ссылка действительна 7 дней',
        'shared_report_greeting': '👋 Привет! {sender} поделился с тобой своим отчетом!',
        'shared_report_info': '📊 Отчет за {month} {year} ({format})',
        'shared_report_generated_by': '🤖 Сгенерировано ботом Coins @showmecoinbot',
        'shared_report_generating': '⏳ Генерирую отчет...',
        'shared_report_success': '✅ Вот отчет от {sender}!',
        'shared_report_link_invalid': '❌ Ссылка недействительна',
        'shared_report_link_expired': '❌ Срок действия ссылки истек',
    },
    'en': {
        # ... аналогично на английском ...
    }
}
```

---

## ✅ Чек-лист реализации

- [ ] Изменить `send_monthly_report` → `send_monthly_report_notification` в `bot/services/notifications.py`
- [ ] Обновить вызов в `expense_bot/celery_tasks.py`
- [ ] Создать 3 callback обработчика в `bot/routers/reports.py`: `monthly_report_csv_*`, `monthly_report_xlsx_*`, `monthly_report_pdf_*`
- [ ] Создать модель `ReportShareToken` в `expenses/models.py`
- [ ] Создать `bot/services/report_share.py` с сервисом расшаривания
- [ ] Добавить обработчик `callback_share_report_*` в `bot/routers/reports.py`
- [ ] Добавить обработку deep-link `report_*` в `bot/routers/start.py`
- [ ] Создать функцию `process_shared_report` в `bot/routers/start.py`
- [ ] Создать миграцию для `ReportShareToken`
- [ ] Добавить новые тексты в `bot/texts.py`
- [ ] Протестировать весь флоу:
  - [ ] Автоматическая отправка уведомления 1 числа
  - [ ] Генерация PDF/XLSX/CSV по кнопке
  - [ ] Расшаривание отчета (генерация ссылки)
  - [ ] Получение расшаренного отчета по ссылке

---

## 🎨 Визуальный дизайн кнопок

### Уведомление 1 числа:
```
📊 Ваш отчет за октябрь 2025 готов!

[AI инсайты...]

💡 Выберите формат для скачивания:

[📋 CSV] [📊 Excel] [📄 PDF]
```

### После генерации отчета:
```
✅ Отчет успешно сгенерирован!

[Файл: expenses_october_2025.xlsx]

[📤 Поделиться отчетом]
```

### Расшаренный отчет для получателя:
```
👋 Привет! Иван Иванов поделился с тобой своим отчетом!

📊 Отчет за октябрь 2025 (XLSX)

🤖 Сгенерировано ботом Coins @showmecoinbot

⏳ Генерирую отчет...
```

---

## 📝 Примечания

1. **Безопасность**: Токены действительны 7 дней и одноразовые (можно сделать)
2. **Производительность**: Отчеты генерируются на лету при расшаривании (нет кеширования)
3. **Приватность**: Получатель видит ВСЕ операции отправителя за месяц (включая семейные если включен household_mode)
4. **Масштабирование**: Можно добавить ограничение на количество расшариваний в день
5. **Аналитика**: Можно добавить счетчик использования токенов для статистики

---

## 🚀 Последовательность внедрения

1. **Этап 1**: Создать модель и миграцию
2. **Этап 2**: Реализовать сервис расшаривания
3. **Этап 3**: Изменить уведомление 1 числа
4. **Этап 4**: Создать callback обработчики для форматов
5. **Этап 5**: Добавить кнопку "Поделиться"
6. **Этап 6**: Реализовать обработку deep-link
7. **Этап 7**: Тестирование на всех форматах

---

## 🔄 Обратная совместимость

Старые PDF отчеты, сгенерированные вручную через меню, продолжат работать как раньше.
Изменяется только автоматическая отправка 1 числа месяца.
