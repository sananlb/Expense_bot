# План интеграции автоматической конвертации валют

**Версия:** 2.1 (исправлена)
**Дата:** 2026-02-03

## Обзор

Добавление функционала автоматической конвертации валют при добавлении трат/доходов в другой валюте. Пользователь сможет выбрать в настройках, хочет ли он видеть траты в оригинальной валюте или автоматически конвертировать в валюту по умолчанию.

### Источники данных

| Источник | Назначение | Валюты |
|----------|------------|--------|
| **ЦБ РФ** (PRIMARY) | Официальный курс | 54 валюты (USD, EUR, CNY, GBP, etc.) |
| **Fawaz API** (FALLBACK) | Экзотические валюты + если ЦБ недоступен | ARS, COP, PEN, CLP, MXN |

**Архитектурное решение:** Используем существующий `currency_conversion.py` + Redis кеш. **БЕЗ** новых моделей Currency/ExchangeRate.

### Целевое поведение
```
Пользователь (валюта: RUB) добавляет трату "50 USD кофе"

├── auto_convert = OFF → Сохраняется: 50 USD
│                        Отображается: "☕ Кофе - 50 $"
│
└── auto_convert = ON
    ├── Курс получен    → Сохраняется: 4627 RUB (original: 50 USD)
    │                     Отображается: "☕ Кофе - 4627 ₽ <i>(~50 $)</i>"
    │
    └── Курс НЕ получен → Сохраняется: 50 USD (graceful degradation)
                          Отображается: "☕ Кофе - 50 $"
```

> **Примечание:** Telegram бот использует HTML разметку (`<i>`, `<b>`), НЕ Markdown.

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

## Этап 2: Исправить сервис конвертации валют

**Файл:** `bot/services/currency_conversion.py`

### 2.1 КРИТИЧНО: Исправить инверсию курса Fawaz API

**Проблема:** Fawaz API с `base=rub` возвращает `"usd": 0.013` (1 RUB = 0.013 USD).
Код интерпретирует как "1 USD = 0.013 RUB" — это **НЕПРАВИЛЬНО**!

**Исправление:**

```python
def _parse_fawaz_response(self, data: dict, base_currency: str) -> Dict[str, Dict]:
    """Parse Fawaz API response"""
    try:
        rates = {}
        currency_data = data.get(base_currency.lower(), {})

        for currency_code, rate_value in currency_data.items():
            if currency_code.upper() in self.SUPPORTED_CURRENCIES:
                currency_upper = currency_code.upper()

                # КРИТИЧНО: Fawaz возвращает "1 RUB = X валюта"
                # Нам нужно "1 валюта = X RUB", поэтому ИНВЕРТИРУЕМ
                if rate_value and rate_value > 0:
                    inverted_rate = Decimal('1') / Decimal(str(rate_value))
                else:
                    continue

                rates[currency_upper] = {
                    'value': inverted_rate,
                    'nominal': 1,
                    'name': self.SUPPORTED_CURRENCIES.get(currency_upper, currency_upper),
                    'unit_rate': inverted_rate  # 1 USD = ~76 RUB
                }

        return rates

    except Exception as e:
        logger.error(f"Error parsing Fawaz response: {e}")
        return {}
```

### 2.2 Раздельные кеши для CBRF и Fawaz

**Проблема:** Общий кеш — если первым запросом кешируется ЦБ, экзотика (ARS) не попадёт.

**Исправление:**

```python
class CurrencyConverter:
    # ... существующие константы ...

    # Валюты НЕ доступные через ЦБ РФ
    CBRF_UNAVAILABLE = {'ARS', 'COP', 'PEN', 'CLP', 'MXN'}

    def _get_cache_key(self, date_obj: Optional[date] = None, source: str = 'cbrf') -> str:
        """Generate cache key for rates WITH source prefix"""
        if not date_obj:
            date_obj = date.today()
        return f"{self._cache_prefix}:{source}:{date_obj.isoformat()}"

    async def fetch_daily_rates(self, date_obj: Optional[date] = None,
                                from_currency: Optional[str] = None,
                                to_currency: Optional[str] = None) -> Dict[str, Dict]:
        """
        Получает курсы валют с правильным выбором источника и кеша.

        ВАЖНО: Проверяем ОБЕ валюты (from и to) при выборе источника!
        Сценарий: from_currency=RUB, to_currency=ARS
        - RUB не экзотика, но ARS — экзотика, поэтому нужен Fawaz
        """
        await self._ensure_session()

        # Проверяем ОБЕ валюты на экзотику
        from_exotic = from_currency and from_currency.upper() in self.CBRF_UNAVAILABLE
        to_exotic = to_currency and to_currency.upper() in self.CBRF_UNAVAILABLE
        is_exotic = from_exotic or to_exotic

        if is_exotic:
            # Любая из валют экзотическая → Fawaz с отдельным кешем
            cache_key = self._get_cache_key(date_obj, source='fawaz')
            cached_rates = cache.get(cache_key)
            if cached_rates:
                return cached_rates

            rates = await self.fetch_fawaz_rates('rub')
            if rates:
                cache.set(cache_key, rates, self._cache_timeout)
                return rates
            return {}

        # Обычные валюты → ЦБ РФ
        cache_key = self._get_cache_key(date_obj, source='cbrf')
        cached_rates = cache.get(cache_key)
        if cached_rates:
            return cached_rates

        # PRIMARY: ЦБ РФ
        rates = await self.fetch_cbrf_rates(date_obj)
        if rates:
            logger.info(f"CBRF: Fetched {len(rates)} rates")
            cache.set(cache_key, rates, self._cache_timeout)
            return rates

        # FALLBACK: Fawaz (если ЦБ недоступен)
        logger.warning("CBRF unavailable, falling back to Fawaz API")
        fallback_key = self._get_cache_key(date_obj, source='fawaz')
        rates = await self.fetch_fawaz_rates('rub')
        if rates:
            cache.set(fallback_key, rates, self._cache_timeout)
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
        """
        if from_currency == to_currency:
            return amount, Decimal('1')

        if not conversion_date:
            conversion_date = date.today()

        # Получаем курсы с указанием ОБЕИХ валют (выберет правильный источник)
        rates = await self.fetch_daily_rates(
            conversion_date,
            from_currency=from_currency,
            to_currency=to_currency
        )
        if not rates:
            return None, None

        # Конвертация
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

## Этап 3: Централизованный helper с timezone профиля

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

import pytz
from django.utils import timezone

from .currency_conversion import currency_converter, CurrencyConverter

logger = logging.getLogger(__name__)


def get_user_local_date(profile) -> date:
    """
    Получает текущую дату в timezone пользователя.
    ВАЖНО: Использует timezone профиля, а не сервера!
    """
    try:
        user_tz = pytz.timezone(profile.timezone or 'UTC')
        return timezone.now().astimezone(user_tz).date()
    except Exception:
        return timezone.localdate()


async def maybe_convert_amount(
    amount: Decimal,
    input_currency: str,
    user_currency: str,
    auto_convert_enabled: bool,
    operation_date: Optional[date] = None,
    profile=None  # Для получения timezone
) -> Tuple[Decimal, str, Optional[Decimal], Optional[str], Optional[Decimal]]:
    """
    Конвертирует сумму если нужно.

    Args:
        amount: исходная сумма
        input_currency: валюта ввода
        user_currency: валюта пользователя по умолчанию
        auto_convert_enabled: включена ли автоконвертация
        operation_date: дата операции (для курса)
        profile: профиль пользователя (для timezone)

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

    # Определяем дату для курса
    if operation_date is None:
        if profile:
            operation_date = get_user_local_date(profile)
        else:
            operation_date = timezone.localdate()

    # Проверяем: экзотика + историческая дата = нет источника
    # ВАЖНО: Проверяем ОБЕ валюты (from и to)!
    is_from_exotic = input_currency in CurrencyConverter.CBRF_UNAVAILABLE
    is_to_exotic = user_currency in CurrencyConverter.CBRF_UNAVAILABLE
    is_exotic = is_from_exotic or is_to_exotic
    today = get_user_local_date(profile) if profile else timezone.localdate()
    is_historical = operation_date < today

    if is_exotic and is_historical:
        # Fawaz @latest не поддерживает исторические даты
        logger.warning(
            f"No historical rates for exotic currency {input_currency} "
            f"on {operation_date}, keeping original"
        )
        return amount, input_currency, None, None, None

    # Пытаемся конвертировать
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
                f"(rate: {rate}, date: {operation_date})"
            )
            return converted, user_currency, amount, input_currency, rate
        else:
            # Graceful degradation
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

# Существующая функция — добавить параметры
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
    # НОВЫЕ параметры для конвертации
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
        # НОВЫЕ поля
        original_amount=original_amount,
        original_currency=original_currency,
        exchange_rate_used=exchange_rate_used,
    )
    return expense


# НОВАЯ функция — обёртка с конвертацией
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
        lambda: UserSettings.objects.filter(profile=profile).first()
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
        operation_date=expense_date,
        profile=profile  # Для timezone
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


# ОБНОВИТЬ АЛИАС (строка ~177)
# Было: add_expense = create_expense
# Стало:
add_expense = create_expense  # Оставляем для обратной совместимости
add_expense_with_conversion = create_expense_with_conversion  # НОВЫЙ алиас
```

### 4.2 Аналогично для income.py

**Файл:** `bot/services/income.py`

```python
# Аналогичная структура:
# 1. Добавить параметры original_amount, original_currency, exchange_rate_used в create_income
# 2. Добавить create_income_with_conversion()
# 3. Добавить алиас: add_income_with_conversion = create_income_with_conversion
```

---

## Этап 5: Обновить ВСЕ точки вызова (WIRING)

### 5.1 Точки вызова add_expense в роутерах

**Файл:** `bot/routers/expense.py`

```python
# БЫЛО:
from ..services.expense import add_expense

expense = await add_expense(
    user_id=user_id,
    amount=amount,
    currency=currency,
    ...
)

# СТАЛО:
from ..services.expense import add_expense_with_conversion

expense = await add_expense_with_conversion(
    user_id=user_id,
    amount=amount,
    input_currency=currency,  # Переименован параметр!
    ...
)
```

### 5.2 Полный список файлов для обновления

| Файл | Что изменить |
|------|--------------|
| `bot/routers/expense.py` | `add_expense` → `add_expense_with_conversion` (3 места) |
| `bot/routers/income.py` | `add_income` → `add_income_with_conversion` |
| `bot/routers/voice.py` | Если есть вызовы — обновить |
| `bot/services/ai_parser.py` | Если создаёт траты — обновить |

### 5.3 Поиск всех точек вызова

```bash
# Выполнить перед реализацией:
grep -rn "add_expense\|create_expense" --include="*.py" bot/routers/
grep -rn "add_income\|create_income" --include="*.py" bot/routers/
```

---

## Этап 6: Изменить recurring.py

**Файл:** `bot/services/recurring.py`

**Проблема:** Функция напрямую вызывает `Expense.objects.create()` — обходит конвертацию.

```python
from .conversion_helper import maybe_convert_amount, get_user_local_date
from asgiref.sync import async_to_sync
from expenses.models import UserSettings

@sync_to_async
@transaction.atomic
def process_recurring_payments_for_today() -> tuple[int, list]:
    """Обработать регулярные платежи на сегодня"""
    # ... существующая логика получения платежей ...

    for payment in payments:
        profile = payment.profile
        today = get_user_local_date(profile)

        # Получаем настройки
        user_settings = UserSettings.objects.filter(profile=profile).first()
        auto_convert = user_settings.auto_convert_currency if user_settings else False

        # Конвертируем если нужно (sync wrapper для async функции)
        if auto_convert and payment.currency != profile.currency:
            convert_result = async_to_sync(maybe_convert_amount)(
                amount=payment.amount,
                input_currency=payment.currency,
                user_currency=profile.currency,
                auto_convert_enabled=True,
                operation_date=today,
                profile=profile
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
                # НОВЫЕ поля
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
                # НОВЫЕ поля
                original_amount=orig_amount,
                original_currency=orig_currency,
                exchange_rate_used=rate,
            )
```

---

## Этап 7: UI настроек

### 7.1 Добавить параметр в keyboards.py

**Файл:** `bot/keyboards.py`

```python
def settings_keyboard(
    lang: str = 'ru',
    cashback_enabled: bool = True,
    has_subscription: bool = False,
    view_scope: str = 'personal',
    auto_convert: bool = False  # НОВЫЙ параметр
) -> InlineKeyboardMarkup:
    """Меню настроек"""
    keyboard = InlineKeyboardBuilder()

    # ... существующие кнопки ...
    keyboard.button(text=get_text('change_language', lang), callback_data="change_language")
    keyboard.button(text=get_text('change_timezone', lang), callback_data="change_timezone")
    keyboard.button(text=get_text('change_currency', lang), callback_data="change_currency")

    # НОВАЯ кнопка автоконвертации
    auto_convert_icon = '✅' if auto_convert else '⬜'
    auto_convert_text = f"{auto_convert_icon} {get_text('auto_convert_currency', lang)}"
    keyboard.button(text=auto_convert_text, callback_data="toggle_auto_convert")

    # ... остальные кнопки ...
```

### 7.2 Обновить ВСЕ вызовы settings_keyboard()

**Файл:** `bot/routers/settings.py`

```python
# Строка ~89 и ~93 — обновить вызовы:

# БЫЛО:
reply_markup=settings_keyboard(lang, cashback_enabled, has_subscription, view_scope)

# СТАЛО:
# Сначала получаем настройку auto_convert
user_settings = await sync_to_async(
    lambda: UserSettings.objects.filter(profile=profile).first()
)()
auto_convert = user_settings.auto_convert_currency if user_settings else False

reply_markup=settings_keyboard(
    lang=lang,
    cashback_enabled=cashback_enabled,
    has_subscription=has_subscription,
    view_scope=view_scope,
    auto_convert=auto_convert  # НОВЫЙ параметр
)
```

### 7.3 Добавить обработчик toggle_auto_convert

**Файл:** `bot/routers/settings.py`

```python
@router.callback_query(F.data == "toggle_auto_convert")
async def toggle_auto_convert(callback: CallbackQuery):
    """Переключатель автоконвертации валют"""
    from expenses.models import UserSettings

    profile = await get_or_create_profile(callback.from_user.id)

    # Получаем или создаем настройки
    user_settings, created = await sync_to_async(
        lambda: UserSettings.objects.get_or_create(profile=profile)
    )()

    # Инвертируем значение
    user_settings.auto_convert_currency = not user_settings.auto_convert_currency
    await sync_to_async(user_settings.save)()

    lang = profile.language_code or 'ru'
    status = "enabled" if user_settings.auto_convert_currency else "disabled"

    await callback.answer(get_text(f'auto_convert_{status}', lang))

    # Получаем остальные параметры для клавиатуры
    from bot.services.subscription import check_subscription

    cashback_enabled = user_settings.cashback_enabled if user_settings else True
    has_subscription = await check_subscription(callback.from_user.id)
    view_scope = user_settings.view_scope if user_settings else 'personal'

    # Обновляем клавиатуру
    keyboard = settings_keyboard(
        lang=lang,
        cashback_enabled=cashback_enabled,
        has_subscription=has_subscription,
        view_scope=view_scope,
        auto_convert=user_settings.auto_convert_currency
    )
    await callback.message.edit_reply_markup(reply_markup=keyboard)
```

### 7.4 Добавить тексты

**Файл:** `bot/texts.py`

```python
# Добавить в словарь TEXTS:

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
```

---

## Этап 8: Форматирование с отображением оригинальной суммы

### 8.1 Изменить expense_formatter.py

**Файл:** `bot/utils/expense_formatter.py`

**ВАЖНО:** Форматтеры используют HTML (`<b>`, `<i>`), НЕ Markdown!

```python
from bot.utils import get_currency_symbol  # Реэкспортируется из bot/utils/__init__.py

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
        # ... существующий код получения amount_str ...

        currency = expense.currency or 'RUB'
        amount_str = format_amount(expense.amount, currency, lang)

        # ДОБАВИТЬ: оригинальная сумма если была конвертация
        if hasattr(expense, 'was_converted') and expense.was_converted:
            orig_symbol = get_currency_symbol(expense.original_currency)
            # HTML курсив для Telegram (НЕ Markdown!)
            amount_str += f" <i>(~{expense.original_amount:.0f} {orig_symbol})</i>"

        # ... формируем строку ...
```

### 8.2 Изменить income_formatter.py

**Файл:** `bot/utils/income_formatter.py`

**ВАЖНО:** Форматтеры используют HTML (`<b>`, `<i>`), НЕ Markdown!

```python
from bot.utils import get_currency_symbol  # Реэкспортируется из bot/utils/__init__.py

def format_incomes_diary_style(
    incomes: List[Any],
    today: date = None,
    max_incomes: int = 100,
    lang: str = 'ru'
) -> str:
    """Форматирует доходы в стиле дневника"""
    # ... существующая логика ...

    for income in incomes:
        # ИСПРАВИТЬ: использовать валюту дохода, НЕ хардкод RUB
        currency = income.currency or 'RUB'  # Было: currency = 'RUB'
        amount_str = format_amount(income.amount, currency, lang)

        # ДОБАВИТЬ: оригинальная сумма если была конвертация
        if hasattr(income, 'was_converted') and income.was_converted:
            orig_symbol = get_currency_symbol(income.original_currency)
            # HTML курсив для Telegram (НЕ Markdown!)
            amount_str += f" <i>(~{income.original_amount:.0f} {orig_symbol})</i>"

        # ... формируем строку ...
```

---

## Этап 9: Celery задача для предзагрузки курсов

### 9.1 Создать задачу

**Файл:** `expense_bot/celery_tasks.py` (добавить)

```python
@shared_task(name='prefetch_cbrf_rates')
def prefetch_cbrf_rates():
    """
    Предзагрузка курсов ЦБ РФ на завтра.
    Запускается в 23:30 МСК.

    ВАЖНО: Используем fetch_daily_rates() который:
    - Создаёт сессию (_ensure_session)
    - Кладёт результат в кеш
    """
    from bot.services.currency_conversion import currency_converter
    from asgiref.sync import async_to_sync

    async def _prefetch():
        # fetch_daily_rates() сам создаст сессию и закеширует результат
        rates = await currency_converter.fetch_daily_rates()
        if rates:
            logger.info(f"CBRF: Prefetched {len(rates)} rates for tomorrow")
            return len(rates)
        else:
            logger.error("CBRF: Failed to prefetch rates")
            return 0

    count = async_to_sync(_prefetch)()
    return f"Prefetched {count} CBRF rates"
```

### 9.2 Зарегистрировать в setup_periodic_tasks.py

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

### 9.3 Применить регистрацию

```bash
python manage.py setup_periodic_tasks
```

---

## Этап 10: Тестирование

### 10.1 Unit тесты

**Файл:** `tests/test_currency_conversion.py`

```python
import pytest
from decimal import Decimal
from unittest.mock import patch, AsyncMock, MagicMock
from bot.services.conversion_helper import maybe_convert_amount


def test_parse_fawaz_response_inversion():
    """
    Тест парсинга Fawaz API с инверсией курса.

    КРИТИЧНО: Fawaz возвращает "1 RUB = X валюта", нужна инверсия!
    """
    from bot.services.currency_conversion import CurrencyConverter
    from decimal import Decimal

    converter = CurrencyConverter()

    # Мок ответа Fawaz API: 1 RUB = 0.013 USD
    fawaz_response = {
        'date': '2026-02-03',
        'rub': {
            'usd': 0.013,    # 1 RUB = 0.013 USD
            'eur': 0.011,    # 1 RUB = 0.011 EUR
            'ars': 12.5,     # 1 RUB = 12.5 ARS (экзотика)
        }
    }

    rates = converter._parse_fawaz_response(fawaz_response, 'rub')

    # Проверяем что курсы ИНВЕРТИРОВАНЫ
    # 1 USD = 1/0.013 = 76.92 RUB
    assert 'USD' in rates
    usd_rate = rates['USD']['unit_rate']
    assert abs(float(usd_rate) - 76.92) < 0.1, f"USD rate should be ~76.92, got {usd_rate}"

    # 1 EUR = 1/0.011 = 90.91 RUB
    assert 'EUR' in rates
    eur_rate = rates['EUR']['unit_rate']
    assert abs(float(eur_rate) - 90.91) < 0.1, f"EUR rate should be ~90.91, got {eur_rate}"

    # 1 ARS = 1/12.5 = 0.08 RUB
    assert 'ARS' in rates
    ars_rate = rates['ARS']['unit_rate']
    assert abs(float(ars_rate) - 0.08) < 0.01, f"ARS rate should be ~0.08, got {ars_rate}"


@pytest.mark.asyncio
async def test_conversion_helper_with_fawaz():
    """Тест maybe_convert_amount с моком конвертера"""
    with patch('bot.services.currency_conversion.currency_converter') as mock:
        mock.convert_with_details = AsyncMock(
            return_value=(Decimal('7690'), Decimal('76.9'))
        )

        result = await maybe_convert_amount(
            amount=Decimal('100'),
            input_currency='USD',
            user_currency='RUB',
            auto_convert_enabled=True
        )

        assert result[0] == Decimal('7690')  # 100 * 76.9
        assert result[1] == 'RUB'


@pytest.mark.asyncio
async def test_exotic_to_currency_uses_fawaz():
    """
    Тест: если to_currency экзотическая, используется Fawaz.

    Сценарий: from_currency=RUB, to_currency=ARS
    RUB не экзотика, но ARS — экзотика, поэтому нужен Fawaz!
    """
    from datetime import date

    with patch('bot.services.currency_conversion.currency_converter') as mock:
        mock.convert_with_details = AsyncMock(
            return_value=(Decimal('1250'), Decimal('12.5'))
        )

        result = await maybe_convert_amount(
            amount=Decimal('100'),
            input_currency='RUB',      # НЕ экзотика
            user_currency='ARS',       # Экзотика!
            auto_convert_enabled=True,
            operation_date=date.today()
        )

        # Должна произойти конвертация через Fawaz
        assert result[0] == Decimal('1250')
        assert result[1] == 'ARS'
        assert result[2] == Decimal('100')  # original_amount
        assert result[3] == 'RUB'           # original_currency


@pytest.mark.asyncio
async def test_exotic_historical_no_conversion():
    """Тест: экзотика + прошлая дата = нет конвертации"""
    from datetime import date, timedelta

    mock_profile = MagicMock()
    mock_profile.timezone = 'Europe/Moscow'

    yesterday = date.today() - timedelta(days=1)

    result = await maybe_convert_amount(
        amount=Decimal('100'),
        input_currency='ARS',  # Экзотика
        user_currency='RUB',
        auto_convert_enabled=True,
        operation_date=yesterday,  # Вчера
        profile=mock_profile
    )

    # Должен сохранить оригинал без конвертации
    assert result[0] == Decimal('100')
    assert result[1] == 'ARS'
    assert result[2] is None  # no original_amount


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

## Этап 11: Деплой

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
│   │   ├── currency_conversion.py   # Исправить: инверсия Fawaz, раздельные кеши
│   │   ├── conversion_helper.py     # НОВЫЙ: maybe_convert_amount() + timezone
│   │   ├── expense.py               # + create_expense_with_conversion, обновить параметры
│   │   ├── income.py                # + create_income_with_conversion
│   │   └── recurring.py             # + конвертация в process_recurring_payments
│   ├── routers/
│   │   ├── settings.py              # + toggle_auto_convert, обновить вызовы settings_keyboard
│   │   └── expense.py               # add_expense → add_expense_with_conversion
│   ├── utils/
│   │   ├── expense_formatter.py     # + отображение оригинальной суммы (HTML!)
│   │   └── income_formatter.py      # + отображение + исправить хардкод RUB (HTML!)
│   ├── texts.py                     # + тексты auto_convert_*
│   ├── keyboards.py                 # + параметр auto_convert
│   └── management/commands/
│       └── setup_periodic_tasks.py  # + prefetch_cbrf_rates task
├── expense_bot/
│   └── celery_tasks.py              # + prefetch_cbrf_rates()
└── tests/
    └── test_currency_conversion.py  # НОВЫЙ: тесты с моками
```

---

## Чек-лист перед реализацией

- [ ] Проверить все точки вызова: `grep -rn "add_expense\|create_expense" bot/`
- [ ] Проверить все точки вызова: `grep -rn "add_income\|create_income" bot/`
- [ ] Проверить вызовы settings_keyboard: `grep -rn "settings_keyboard" bot/`
- [ ] Проверить формат Fawaz API ещё раз
- [ ] Написать тесты ДО реализации

---

## Обработка edge cases

| Ситуация | Решение |
|----------|---------|
| Курс не получен | Graceful degradation: сохраняем в оригинальной валюте |
| Выходной день | ЦБ вернёт курс пятницы |
| Экзотика (ARS, COP, PEN, CLP, MXN) сегодня | Fawaz API с инвертированным курсом |
| Экзотика + прошлая дата | Graceful degradation (Fawaz не поддерживает историю) |
| ЦБ РФ валюта + прошлая дата | ЦБ РФ с параметром `date_req` |
| Timezone на границе суток | `get_user_local_date(profile)` использует timezone профиля |
| Redis сброшен | On-demand запрос к API при первом обращении |

---

## Совместимость

- ✅ Существующие траты/доходы остаются без изменений (nullable поля)
- ✅ Автоконвертация по умолчанию ВЫКЛЮЧЕНА
- ✅ Graceful degradation при любых ошибках
- ✅ `add_expense` алиас сохранён для обратной совместимости
