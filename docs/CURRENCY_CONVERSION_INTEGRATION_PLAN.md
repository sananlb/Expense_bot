# План интеграции автоматической конвертации валют

## Обзор

Добавление функционала автоматической конвертации валют при добавлении трат/доходов в другой валюте. Пользователь сможет выбрать в настройках, хочет ли он видеть траты в оригинальной валюте или автоматически конвертировать в валюту по умолчанию.

### Источники данных

| Источник | Назначение | Валюты |
|----------|------------|--------|
| **ЦБ РФ** (PRIMARY) | Официальный курс | 54 валюты (USD, EUR, CNY, GBP, etc.) |
| **Fawaz API** (FALLBACK) | Экзотические валюты + если ЦБ недоступен | ARS, COP, PEN, CLP, MXN |

**Архитектурное решение:** Используем существующий `currency_conversion.py` + Redis кеш. **БЕЗ** новых моделей Currency/ExchangeRate (упрощение).

### Целевое поведение
```
Пользователь (валюта: RUB) добавляет трату "50 USD кофе"

├── auto_convert = OFF → Сохраняется: 50 USD
│                        Отображается: "☕ Кофе - 50 $"
│
└── auto_convert = ON
    ├── Курс получен    → Сохраняется: 4627 RUB (original: 50 USD)
    │                     Отображается: "☕ Кофе - 4627 ₽ _(~50 $)_"
    │
    └── Курс НЕ получен → Сохраняется: 50 USD (graceful degradation)
                          Отображается: "☕ Кофе - 50 $"
```

---

## Этап 1: Модели данных (минимальные изменения)

### 1.1 Добавить поля для хранения оригинальной суммы

**Файл:** `expenses/models.py`

```python
class Expense(models.Model):
    # ... существующие поля ...

    # Новые поля для конвертации (nullable для обратной совместимости)
    original_amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        verbose_name="Оригинальная сумма"
    )
    original_currency = models.CharField(
        max_length=3,
        null=True, blank=True,
        verbose_name="Оригинальная валюта"
    )
    exchange_rate_used = models.DecimalField(
        max_digits=12, decimal_places=6,
        null=True, blank=True,
        verbose_name="Использованный курс"
    )

    @property
    def was_converted(self) -> bool:
        """Была ли трата сконвертирована"""
        return (
            self.original_currency is not None
            and self.original_currency != self.currency
        )


class Income(models.Model):
    # ... существующие поля ...

    # Аналогичные поля
    original_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    original_currency = models.CharField(max_length=3, null=True, blank=True)
    exchange_rate_used = models.DecimalField(
        max_digits=12, decimal_places=6, null=True, blank=True
    )

    @property
    def was_converted(self) -> bool:
        return (
            self.original_currency is not None
            and self.original_currency != self.currency
        )
```

### 1.2 Добавить настройку в UserSettings

**Файл:** `expenses/models.py` (класс UserSettings)

```python
class UserSettings(models.Model):
    # ... существующие поля ...

    auto_convert_currency = models.BooleanField(
        default=False,
        verbose_name="Автоконвертация валют"
    )
```

### 1.3 Миграция

```bash
python manage.py makemigrations expenses --name add_currency_conversion_fields
python manage.py migrate
```

---

## Этап 2: Изменить сервис конвертации валют

**Файл:** `bot/services/currency_conversion.py`

### 2.1 Добавить константу и изменить приоритет источников

```python
class CurrencyConverter:
    # ... существующие константы ...

    # Валюты НЕ доступные через ЦБ РФ
    CBRF_UNAVAILABLE = {'ARS', 'COP', 'PEN', 'CLP', 'MXN'}

    async def fetch_daily_rates(self, date_obj: Optional[date] = None,
                                currency_hint: Optional[str] = None) -> Dict[str, Dict]:
        """
        Получает курсы валют.

        Args:
            date_obj: дата курса
            currency_hint: подсказка какую валюту нужно (для выбора источника)
        """
        await self._ensure_session()

        # Проверяем кеш
        cache_key = self._get_cache_key(date_obj)
        cached_rates = cache.get(cache_key)
        if cached_rates:
            return cached_rates

        # Если нужна экзотическая валюта → сразу Fawaz
        if currency_hint and currency_hint.upper() in self.CBRF_UNAVAILABLE:
            rates = await self.fetch_fawaz_rates('rub')
            if rates:
                cache.set(cache_key, rates, self._cache_timeout)
                return rates

        # PRIMARY: ЦБ РФ (официальный курс)
        rates = await self.fetch_cbrf_rates(date_obj)
        if rates:
            logger.info(f"CBRF: Fetched {len(rates)} rates")
            cache.set(cache_key, rates, self._cache_timeout)
            return rates

        # FALLBACK: Fawaz (если ЦБ недоступен)
        logger.warning("CBRF unavailable, falling back to Fawaz API")
        rates = await self.fetch_fawaz_rates('rub')
        if rates:
            cache.set(cache_key, rates, self._cache_timeout)
        return rates


    async def convert_with_details(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str = 'RUB',
        conversion_date: Optional[date] = None
    ) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """
        Конвертирует сумму и возвращает использованный курс.

        Returns:
            Tuple[сконвертированная сумма, курс] или (None, None)
        """
        if from_currency == to_currency:
            return amount, Decimal('1')

        if not conversion_date:
            conversion_date = timezone.localdate()

        # Получаем курсы с подсказкой валюты
        rates = await self.fetch_daily_rates(conversion_date, currency_hint=from_currency)
        if not rates:
            return None, None

        # Конвертация через RUB
        if from_currency == 'RUB':
            if to_currency not in rates:
                return None, None
            rate = Decimal('1') / rates[to_currency]['unit_rate']
            return (amount * rate).quantize(Decimal('0.01')), rate

        if to_currency == 'RUB':
            if from_currency not in rates:
                return None, None
            rate = rates[from_currency]['unit_rate']
            return (amount * rate).quantize(Decimal('0.01')), rate

        # Кросс-курс через RUB
        if from_currency not in rates or to_currency not in rates:
            return None, None

        from_rate = rates[from_currency]['unit_rate']
        to_rate = rates[to_currency]['unit_rate']
        rate = from_rate / to_rate
        return (amount * rate).quantize(Decimal('0.01')), rate
```

---

## Этап 3: Централизованный helper для создания операций с конвертацией

**Файл:** `bot/services/conversion_helper.py` (НОВЫЙ)

```python
"""
Централизованный helper для автоконвертации валют при создании операций.
Используется в expense.py, income.py и recurring.py.
"""
import logging
from decimal import Decimal
from datetime import date
from typing import Optional, Tuple
from django.utils import timezone

from .currency_conversion import currency_converter

logger = logging.getLogger(__name__)


async def maybe_convert_amount(
    amount: Decimal,
    input_currency: str,
    user_currency: str,
    auto_convert_enabled: bool,
    operation_date: Optional[date] = None
) -> Tuple[Decimal, str, Optional[Decimal], Optional[str], Optional[Decimal]]:
    """
    Конвертирует сумму если нужно.

    Args:
        amount: исходная сумма
        input_currency: валюта ввода
        user_currency: валюта пользователя по умолчанию
        auto_convert_enabled: включена ли автоконвертация
        operation_date: дата операции (для курса)

    Returns:
        Tuple[
            final_amount,           # Итоговая сумма
            final_currency,         # Итоговая валюта
            original_amount,        # Оригинальная сумма (или None)
            original_currency,      # Оригинальная валюта (или None)
            exchange_rate_used      # Использованный курс (или None)
        ]
    """
    # Если валюты совпадают или автоконвертация выключена
    if input_currency == user_currency or not auto_convert_enabled:
        return amount, input_currency, None, None, None

    # Пытаемся конвертировать
    if operation_date is None:
        operation_date = timezone.localdate()

    try:
        converted, rate = await currency_converter.convert_with_details(
            amount=amount,
            from_currency=input_currency,
            to_currency=user_currency,
            conversion_date=operation_date
        )

        if converted is not None and rate is not None:
            logger.info(
                f"Converted {amount} {input_currency} -> {converted} {user_currency} "
                f"(rate: {rate})"
            )
            return converted, user_currency, amount, input_currency, rate
        else:
            # Graceful degradation: не удалось сконвертировать
            logger.warning(
                f"Failed to convert {amount} {input_currency} to {user_currency}, "
                f"keeping original"
            )
            return amount, input_currency, None, None, None

    except Exception as e:
        logger.error(f"Conversion error: {e}")
        return amount, input_currency, None, None, None
```

---

## Этап 4: Изменить сервисы создания операций

### 4.1 Изменить expense.py

**Файл:** `bot/services/expense.py`

```python
from .conversion_helper import maybe_convert_amount

@sync_to_async
def create_expense(
    user_id: int,
    amount: Decimal,
    category_id: Optional[int] = None,
    description: Optional[str] = None,
    expense_date: Optional[date] = None,
    ai_categorized: bool = False,
    ai_confidence: Optional[float] = None,
    currency: str = 'RUB',
    # Новые параметры для конвертации (передаются из async контекста)
    original_amount: Optional[Decimal] = None,
    original_currency: Optional[str] = None,
    exchange_rate_used: Optional[Decimal] = None,
) -> Optional[Expense]:
    """Создает трату с поддержкой конвертации"""
    # ... существующая логика получения профиля и категории ...

    expense = Expense.objects.create(
        profile=profile,
        amount=amount,
        currency=currency,
        category=category,
        description=description,
        expense_date=expense_date or date.today(),
        expense_time=datetime.now().time(),
        ai_categorized=ai_categorized,
        ai_confidence=ai_confidence,
        # Новые поля
        original_amount=original_amount,
        original_currency=original_currency,
        exchange_rate_used=exchange_rate_used,
    )
    return expense
```

### 4.2 Обертка для вызова с конвертацией

**Файл:** `bot/services/expense.py` (добавить)

```python
async def create_expense_with_conversion(
    user_id: int,
    amount: Decimal,
    input_currency: str,
    category_id: Optional[int] = None,
    description: Optional[str] = None,
    expense_date: Optional[date] = None,
    ai_categorized: bool = False,
    ai_confidence: Optional[float] = None,
) -> Optional[Expense]:
    """
    Создает трату с автоконвертацией валюты если включено в настройках.
    """
    from expenses.models import UserSettings
    from .conversion_helper import maybe_convert_amount

    # Получаем профиль и настройки
    profile = await sync_to_async(
        lambda: Profile.objects.filter(telegram_id=user_id).first()
    )()
    if not profile:
        return None

    user_settings = await sync_to_async(
        lambda: getattr(profile, 'settings', None)
    )()
    auto_convert = user_settings.auto_convert_currency if user_settings else False

    # Конвертируем если нужно
    (
        final_amount,
        final_currency,
        original_amount,
        original_currency,
        rate
    ) = await maybe_convert_amount(
        amount=amount,
        input_currency=input_currency,
        user_currency=profile.currency,
        auto_convert_enabled=auto_convert,
        operation_date=expense_date
    )

    # Создаем трату
    return await create_expense(
        user_id=user_id,
        amount=final_amount,
        currency=final_currency,
        category_id=category_id,
        description=description,
        expense_date=expense_date,
        ai_categorized=ai_categorized,
        ai_confidence=ai_confidence,
        original_amount=original_amount,
        original_currency=original_currency,
        exchange_rate_used=rate,
    )
```

### 4.3 Аналогично для income.py

**Файл:** `bot/services/income.py`

```python
# Аналогичная структура:
# 1. Добавить параметры original_amount, original_currency, exchange_rate_used в create_income
# 2. Добавить create_income_with_conversion()
```

---

## Этап 5: Изменить recurring.py

**Файл:** `bot/services/recurring.py`

### Проблема
Функция `process_recurring_payments_for_today()` напрямую вызывает `Expense.objects.create()` и `Income.objects.create()`, обходя конвертацию.

### Решение
Использовать helper внутри sync контекста:

```python
from .conversion_helper import maybe_convert_amount
from asgiref.sync import async_to_sync

@sync_to_async
@transaction.atomic
def process_recurring_payments_for_today() -> tuple[int, list]:
    """Обработать регулярные платежи на сегодня"""
    # ... существующая логика получения платежей ...

    for payment in payments:
        profile = payment.profile

        # Получаем настройки
        user_settings = getattr(profile, 'settings', None)
        auto_convert = user_settings.auto_convert_currency if user_settings else False

        # Конвертируем если нужно (sync wrapper для async функции)
        if auto_convert and payment.currency != profile.currency:
            convert_result = async_to_sync(maybe_convert_amount)(
                amount=payment.amount,
                input_currency=payment.currency,
                user_currency=profile.currency,
                auto_convert_enabled=True,
                operation_date=today
            )
            final_amount, final_currency, orig_amount, orig_currency, rate = convert_result
        else:
            final_amount = payment.amount
            final_currency = payment.currency
            orig_amount = orig_currency = rate = None

        if payment.operation_type == RecurringPayment.OPERATION_TYPE_INCOME:
            operation = Income.objects.create(
                profile=profile,
                category=payment.income_category,
                amount=final_amount,
                currency=final_currency,
                description=f"[Ежемесячный] {payment.description}",
                income_date=today,
                original_amount=orig_amount,
                original_currency=orig_currency,
                exchange_rate_used=rate,
            )
        else:
            operation = Expense.objects.create(
                profile=profile,
                category=payment.expense_category,
                amount=final_amount,
                currency=final_currency,
                description=f"[Ежемесячный] {payment.description}",
                expense_date=today,
                expense_time=datetime.now().time(),
                original_amount=orig_amount,
                original_currency=orig_currency,
                exchange_rate_used=rate,
            )
```

---

## Этап 6: UI настроек

### 6.1 Добавить кнопку в клавиатуру настроек

**Файл:** `bot/keyboards.py`

```python
def settings_keyboard(lang: str = 'ru', cashback_enabled: bool = True,
                     has_subscription: bool = False, view_scope: str = 'personal',
                     auto_convert: bool = False) -> InlineKeyboardMarkup:  # Новый параметр
    """Меню настроек"""
    keyboard = InlineKeyboardBuilder()

    # ... существующие кнопки ...
    keyboard.button(text=get_text('change_language', lang), callback_data="change_language")
    keyboard.button(text=get_text('change_timezone', lang), callback_data="change_timezone")
    keyboard.button(text=get_text('change_currency', lang), callback_data="change_currency")

    # Новая кнопка автоконвертации
    auto_convert_text = f"{'✅' if auto_convert else '⬜'} {get_text('auto_convert_currency', lang)}"
    keyboard.button(text=auto_convert_text, callback_data="toggle_auto_convert")

    # ... остальные кнопки ...
```

### 6.2 Добавить обработчик

**Файл:** `bot/routers/settings.py`

```python
@router.callback_query(F.data == "toggle_auto_convert")
async def toggle_auto_convert(callback: CallbackQuery):
    """Переключатель автоконвертации валют"""
    from expenses.models import UserSettings

    profile = await get_or_create_profile(callback.from_user.id)

    # Получаем или создаем настройки
    user_settings, _ = await sync_to_async(UserSettings.objects.get_or_create)(
        profile=profile
    )

    # Инвертируем значение
    user_settings.auto_convert_currency = not user_settings.auto_convert_currency
    await sync_to_async(user_settings.save)()

    lang = profile.language_code or 'ru'
    status = "enabled" if user_settings.auto_convert_currency else "disabled"

    await callback.answer(get_text(f'auto_convert_{status}', lang))

    # Обновляем клавиатуру
    keyboard = settings_keyboard(
        lang=lang,
        # ... другие параметры ...
        auto_convert=user_settings.auto_convert_currency
    )
    await callback.message.edit_reply_markup(reply_markup=keyboard)
```

### 6.3 Добавить тексты

**Файл:** `bot/utils/texts.py`

```python
TEXTS = {
    # ... существующие тексты ...

    'auto_convert_currency': {
        'ru': 'Автоконвертация валют',
        'en': 'Auto-convert currencies',
    },
    'auto_convert_enabled': {
        'ru': '✅ Автоконвертация включена',
        'en': '✅ Auto-conversion enabled',
    },
    'auto_convert_disabled': {
        'ru': '⬜ Автоконвертация выключена',
        'en': '⬜ Auto-conversion disabled',
    },
}
```

---

## Этап 7: Форматирование с отображением оригинальной суммы

### 7.1 Изменить expense_formatter.py

**Файл:** `bot/utils/expense_formatter.py`

```python
def format_expenses_diary_style(
    expenses: List[Any],
    today: date = None,
    max_expenses: int = 100,
    show_warning: bool = True,
    lang: str = 'ru'
) -> str:
    """Форматирует траты в стиле дневника"""
    # ... существующая логика ...

    for expense in expenses:
        # ... существующий код ...

        amount_str = format_amount(expense.amount, expense.currency, lang)

        # Добавляем оригинальную сумму если была конвертация
        if hasattr(expense, 'was_converted') and expense.was_converted:
            orig_symbol = get_currency_symbol(expense.original_currency)
            # Курсив в Telegram: _текст_
            amount_str += f" _(~{expense.original_amount:.0f} {orig_symbol})_"

        # ... формируем строку ...
```

### 7.2 Изменить income_formatter.py

**Файл:** `bot/utils/income_formatter.py`

```python
def format_incomes_diary_style(
    incomes: List[Any],
    today: date = None,
    max_incomes: int = 100,
    lang: str = 'ru'
) -> str:
    """Форматирует доходы в стиле дневника"""
    # ... существующая логика ...

    for income in incomes:
        # ИСПРАВЛЕНИЕ: использовать валюту дохода, а не хардкод RUB
        currency = income.currency or 'RUB'  # Было: currency = 'RUB'
        amount_str = format_amount(income.amount, currency, lang)

        # Добавляем оригинальную сумму если была конвертация
        if hasattr(income, 'was_converted') and income.was_converted:
            orig_symbol = get_currency_symbol(income.original_currency)
            amount_str += f" _(~{income.original_amount:.0f} {orig_symbol})_"

        # ... формируем строку ...
```

---

## Этап 8: Celery задача для предзагрузки курсов

### 8.1 Создать задачу

**Файл:** `expense_bot/celery_tasks.py` (добавить)

```python
@shared_task(name='prefetch_cbrf_rates')
def prefetch_cbrf_rates():
    """
    Предзагрузка курсов ЦБ РФ на завтра.
    Запускается в 23:30 МСК.
    """
    from bot.services.currency_conversion import currency_converter
    from asgiref.sync import async_to_sync

    async def _prefetch():
        rates = await currency_converter.fetch_cbrf_rates()
        if rates:
            logger.info(f"CBRF: Prefetched {len(rates)} rates")
            return len(rates)
        else:
            logger.error("CBRF: Failed to prefetch rates")
            return 0

    count = async_to_sync(_prefetch)()
    return f"Prefetched {count} CBRF rates"
```

### 8.2 Зарегистрировать в setup_periodic_tasks.py

**Файл:** `bot/management/commands/setup_periodic_tasks.py`

```python
def handle(self, *args, **options):
    # ... существующие задачи ...

    # Предзагрузка курсов ЦБ РФ
    schedule_prefetch_rates, _ = CrontabSchedule.objects.get_or_create(
        minute='30',
        hour='23',      # 23:30 МСК
        day_of_week='*',
        day_of_month='*',
        month_of_year='*',
        timezone=pytz.timezone('Europe/Moscow')
    )

    PeriodicTask.objects.update_or_create(
        name='Prefetch CBRF rates daily',
        defaults={
            'task': 'prefetch_cbrf_rates',
            'crontab': schedule_prefetch_rates,
            'enabled': True,
        }
    )

    self.stdout.write(self.style.SUCCESS('Created prefetch_cbrf_rates task'))
```

### 8.3 Применить регистрацию

```bash
python manage.py setup_periodic_tasks
```

---

## Этап 9: Тестирование

### 9.1 Unit тесты

**Файл:** `tests/test_currency_conversion.py`

```python
import pytest
from decimal import Decimal
from unittest.mock import patch, AsyncMock
from bot.services.conversion_helper import maybe_convert_amount


@pytest.mark.asyncio
async def test_convert_usd_to_rub():
    """Тест конвертации USD -> RUB"""
    with patch('bot.services.currency_conversion.currency_converter') as mock:
        mock.convert_with_details = AsyncMock(return_value=(Decimal('9250'), Decimal('92.5')))

        result = await maybe_convert_amount(
            amount=Decimal('100'),
            input_currency='USD',
            user_currency='RUB',
            auto_convert_enabled=True
        )

        assert result[0] == Decimal('9250')  # final_amount
        assert result[1] == 'RUB'            # final_currency
        assert result[2] == Decimal('100')   # original_amount
        assert result[3] == 'USD'            # original_currency


@pytest.mark.asyncio
async def test_no_conversion_when_disabled():
    """Тест: автоконвертация выключена"""
    result = await maybe_convert_amount(
        amount=Decimal('100'),
        input_currency='USD',
        user_currency='RUB',
        auto_convert_enabled=False
    )

    assert result[0] == Decimal('100')  # amount unchanged
    assert result[1] == 'USD'           # currency unchanged
    assert result[2] is None            # no original


@pytest.mark.asyncio
async def test_graceful_degradation():
    """Тест: graceful degradation при ошибке конвертации"""
    with patch('bot.services.currency_conversion.currency_converter') as mock:
        mock.convert_with_details = AsyncMock(return_value=(None, None))

        result = await maybe_convert_amount(
            amount=Decimal('100'),
            input_currency='USD',
            user_currency='RUB',
            auto_convert_enabled=True
        )

        # Должен сохранить оригинал
        assert result[0] == Decimal('100')
        assert result[1] == 'USD'
        assert result[2] is None
```

---

## Этап 10: Деплой

```bash
# 1. Применить миграции
python manage.py makemigrations expenses --name add_currency_conversion_fields
python manage.py migrate

# 2. Зарегистрировать Celery задачу
python manage.py setup_periodic_tasks

# 3. Перезапустить сервисы
docker-compose restart bot celery celery-beat
```

---

## Структура файлов (финальная)

```
expense_bot/
├── expenses/models.py               # + original_amount, original_currency, exchange_rate_used
│                                    # + UserSettings.auto_convert_currency
├── bot/
│   ├── services/
│   │   ├── currency_conversion.py   # Изменить: CBRF primary, добавить convert_with_details
│   │   ├── conversion_helper.py     # НОВЫЙ: maybe_convert_amount()
│   │   ├── expense.py               # Изменить: добавить create_expense_with_conversion
│   │   ├── income.py                # Изменить: добавить create_income_with_conversion
│   │   └── recurring.py             # Изменить: использовать конвертацию
│   ├── routers/
│   │   └── settings.py              # + toggle_auto_convert handler
│   ├── utils/
│   │   ├── expense_formatter.py     # + отображение оригинальной суммы
│   │   ├── income_formatter.py      # + отображение оригинальной суммы + исправить хардкод RUB
│   │   └── texts.py                 # + тексты для UI
│   ├── keyboards.py                 # + кнопка автоконвертации
│   └── management/commands/
│       └── setup_periodic_tasks.py  # + prefetch_cbrf_rates task
├── expense_bot/
│   └── celery_tasks.py              # + prefetch_cbrf_rates()
└── tests/
    └── test_currency_conversion.py  # НОВЫЙ: тесты
```

---

## Обработка edge cases

| Ситуация | Решение |
|----------|---------|
| Курс не получен | Graceful degradation: сохраняем в оригинальной валюте |
| Выходной день | ЦБ вернет курс пятницы |
| Экзотическая валюта (ARS, COP, PEN, CLP, MXN) | Сразу Fawaz API |
| Историческая дата (операция в прошлом) | ЦБ РФ поддерживает исторические курсы |
| Fawaz для историч. дат экзотич. валют | Используем @latest (только сегодня), предупреждаем пользователя |
| Timezone на границе суток | Используем `timezone.localdate()` с timezone профиля |

---

## Приоритет источников курсов

```
┌─────────────────────────────────────────────────────────────┐
│                   ВЫБОР ИСТОЧНИКА КУРСА                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Валюта в CBRF_UNAVAILABLE?                                 │
│  {'ARS', 'COP', 'PEN', 'CLP', 'MXN'}                        │
│                                                             │
│       ДА                              НЕТ                   │
│        │                               │                    │
│        ▼                               ▼                    │
│   Fawaz API                       ЦБ РФ (PRIMARY)           │
│   (экзотические)                       │                    │
│                                        │                    │
│                               ЦБ доступен?                  │
│                                   │                         │
│                          ДА       │       НЕТ               │
│                           │       │        │                │
│                           ▼       │        ▼                │
│                    Использовать   │   Fawaz API             │
│                    курс ЦБ РФ     │   (fallback)            │
│                                   │                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Совместимость

- ✅ Существующие траты/доходы остаются без изменений (nullable поля)
- ✅ Автоконвертация по умолчанию ВЫКЛЮЧЕНА
- ✅ Graceful degradation при любых ошибках
- ✅ Обратная совместимость с форматированием
