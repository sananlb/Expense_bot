# План реализации AI месячных инсайтов для ExpenseBot

**Дата создания:** 2025-10-09
**Автор:** Claude Code
**Цель:** Добавить AI-генерируемый текстовый анализ финансов в месячные отчеты

---

## 📋 Оглавление

1. [Общее описание](#общее-описание)
2. [Архитектура решения](#архитектура-решения)
3. [Структура файлов](#структура-файлов)
4. [Переменные окружения](#переменные-окружения)
5. [Подробное описание компонентов](#подробное-описание-компонентов)
6. [Схема работы](#схема-работы)
7. [Обработка ошибок и Fallback](#обработка-ошибок-и-fallback)
8. [Уведомления админу](#уведомления-админу)
9. [Тестирование](#тестирование)
10. [Этапы реализации](#этапы-реализации)

---

## Общее описание

### Что делаем:
Добавляем умный AI-анализ месячных финансов пользователя, который отправляется **ВМЕСТЕ с PDF отчетом** в caption сообщения.

### Что получит пользователь:
```
📊 *Финансовый итог за декабрь*

*Основные цифры*
Доходы: 85 000 ₽ | Расходы: 72 450 ₽ | Баланс: +12 550 ₽
К ноябрю расходы выросли на 8%, доходы остались стабильными.

*Куда ушли деньги*
1. 🛒 Продукты — 18 750 ₽ (26%)
2. 🏠 Жилье — 15 200 ₽ (21%)
3. 🚕 Транспорт — 9 840 ₽ (14%)

*Динамика к прошлому месяцу*
↑ Продукты: +12%
↓ Кафе и рестораны: -15%

*Финансовое здоровье*
Отличный результат! Норма сбережений 14.8%. Все бюджеты соблюдены.

Отличная финансовая дисциплина! 💪

📎 Подробный PDF отчет прикреплен ниже
```

### Ключевые особенности:
- ✅ AI анализирует данные за **текущий** и **предыдущий** месяцы
- ✅ Мультиязычность (русский/английский)
- ✅ Multi-level fallback: Gemini → OpenAI → Simple text
- ✅ Уведомления админу при ошибках
- ✅ Graceful degradation (если AI недоступен - отправляем без анализа)

---

## Архитектура решения

### Компоненты системы:

```
┌─────────────────────────────────────────────────────────────┐
│                  Celery Task: send_monthly_reports          │
│                  (celery_tasks.py:20-91)                    │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│          NotificationService.send_monthly_report            │
│          (bot/services/notifications.py:22-61)              │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ├──────────────────┐
                            ▼                  ▼
                ┌────────────────────┐  ┌──────────────────────┐
                │  MonthlyInsights   │  │  PDFReportService    │
                │  Service           │  │  (existing)          │
                │  (NEW)             │  │                      │
                └──────┬─────────────┘  └──────────────────────┘
                       │
                       ├─────────────────────┐
                       ▼                     ▼
            ┌──────────────────┐   ┌─────────────────────┐
            │  Data Collector  │   │   AI Prompts        │
            │  _prepare_data() │   │   get_prompt()      │
            └──────────────────┘   └──────────┬──────────┘
                                               │
                       ┌───────────────────────┴─────────────┐
                       ▼                                     ▼
            ┌──────────────────────┐           ┌─────────────────────┐
            │  Google Gemini API   │  Fallback │   OpenAI API        │
            │  (Priority 1)        │  ───────→ │   (Priority 2)      │
            └──────────────────────┘           └─────────────────────┘
                       │                                     │
                       └───────────────┬─────────────────────┘
                                       │ (both fail)
                                       ▼
                           ┌────────────────────────┐
                           │  Simple Fallback Text  │
                           │  "📊 Отчет за месяц"   │
                           └────────────────────────┘
```

---

## Структура файлов

### Новые файлы:

```
expense_bot/
├── bot/
│   └── services/
│       ├── ai_prompts.py                    # NEW - Промпты для AI
│       ├── monthly_insights.py              # NEW - Сервис генерации инсайтов
│       └── async_isolator.py                # NEW (копия из Nutrition_bot)
│
├── docs/
│   └── AI_MONTHLY_INSIGHTS_PLAN.md          # Этот документ
│
└── .env                                      # Обновить (добавить GOOGLE_MODEL_INSIGHTS)
```

### Изменяемые файлы:

```
bot/services/notifications.py                # Интеграция AI инсайтов
expense_bot/celery_tasks.py                  # Уже изменен (передача year/month)
```

---

## Переменные окружения

### Текущие настройки (.env):

```bash
# Model selection for Google
GOOGLE_MODEL_CATEGORIZATION=gemini-2.5-flash
GOOGLE_MODEL_CHAT=gemini-2.5-flash
GOOGLE_MODEL_DEFAULT=gemini-2.5-flash
```

### Добавить в .env:

```bash
# Model selection for Google
GOOGLE_MODEL_CATEGORIZATION=gemini-2.5-flash
GOOGLE_MODEL_CHAT=gemini-2.5-flash
GOOGLE_MODEL_DEFAULT=gemini-2.5-flash
GOOGLE_MODEL_INSIGHTS=gemini-2.0-flash-exp      # NEW - для месячных инсайтов

# Model selection for OpenAI
OPENAI_MODEL_CATEGORIZATION=gpt-4o-mini
OPENAI_MODEL_DEFAULT=gpt-4o-mini
OPENAI_MODEL_INSIGHTS=gpt-4o                     # NEW - для месячных инсайтов (fallback)
```

### Почему `gemini-2.0-flash-exp`?

- ✅ Экспериментальная модель с улучшенным анализом
- ✅ Быстрее чем gemini-1.5-pro
- ✅ Дешевле чем pro версия
- ✅ Лучше справляется с аналитическими задачами

Можно также использовать:
- `gemini-1.5-flash` - стабильная версия
- `gemini-1.5-pro` - максимальное качество (дороже)

---

## Подробное описание компонентов

### 1. **async_isolator.py** (Изоляция async вызовов)

**Расположение:** `bot/services/async_isolator.py`

**Цель:** Корректная работа async AI вызовов в sync Celery задачах

**⚠️ ВАЖНО: Используется ТОЛЬКО в Celery!**
- В aiogram (async контекст) - НЕ используем AsyncIsolator
- В Celery (sync контекст) - ОБЯЗАТЕЛЬНО используем AsyncIsolator

**Что делает:**
- Запускает async функции в отдельном потоке с новым event loop
- Предотвращает конфликты event loop в Celery
- Обеспечивает корректное закрытие всех async задач

**Код:**
```python
import asyncio
import threading
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)

class AsyncIsolator:
    """Изоляция async вызовов для предотвращения проблем с event loop"""

    @staticmethod
    def run_in_thread(async_func: Callable, *args, timeout: int = 60, **kwargs) -> Any:
        """
        Запускает async функцию в отдельном потоке с новым event loop

        Args:
            async_func: Async функция для выполнения
            *args: Позиционные аргументы
            timeout: Таймаут в секундах
            **kwargs: Именованные аргументы

        Returns:
            Результат выполнения async функции

        Raises:
            Exception: Если выполнение завершилось с ошибкой или таймаутом
        """
        result = {'value': None, 'error': None}

        def run_async():
            try:
                # Создаем новый event loop для этого потока
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                try:
                    # Выполняем async функцию
                    result['value'] = loop.run_until_complete(async_func(*args, **kwargs))
                finally:
                    # Корректно закрываем loop
                    loop.close()

            except Exception as e:
                result['error'] = e
                logger.error(f"Error in async isolation: {e}")

        # Запускаем в отдельном потоке
        thread = threading.Thread(target=run_async)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            raise TimeoutError(f"Async function execution exceeded {timeout}s timeout")

        if result['error']:
            raise result['error']

        return result['value']
```

**Использование в Celery задаче:**
```python
from bot.services.async_isolator import AsyncIsolator

# В CELERY ЗАДАЧЕ (sync контекст):
# ОБЯЗАТЕЛЬНО через AsyncIsolator для вызова async функции
insights = AsyncIsolator.run_in_thread(
    NotificationService.send_monthly_report,
    user_id, profile, year, month,
    timeout=120
)

# В AIOGRAM (async контекст):
# ПРЯМОЙ await - БЕЗ AsyncIsolator!
insights = await NotificationService.send_monthly_report(
    user_id, profile, year, month
)
```

---

### 2. **ai_prompts.py** (Промпты для AI)

**Расположение:** `bot/services/ai_prompts.py`

**Цель:** Централизованное хранение всех AI промптов

**Структура:**
```python
"""
Централизованное хранилище промптов для AI сервисов
"""
from decimal import Decimal
from typing import Dict, List, Optional
from bot.utils import get_month_name


class AIPrompts:
    """Класс для генерации промптов для различных AI задач"""

    @staticmethod
    def get_monthly_insights_prompt(user_data: dict, lang: str = 'ru') -> str:
        """
        Генерация промпта для месячных финансовых инсайтов

        Args:
            user_data: Словарь с данными пользователя:
                - current_month: dict - данные текущего месяца
                - previous_month: dict | None - данные предыдущего месяца
                - currency: str - валюта
                - budgets: list - бюджеты пользователя
            lang: Язык ('ru' или 'en')

        Returns:
            str: Сформированный промпт для AI
        """
        # Код промпта (см. ниже)

    @staticmethod
    def _format_categories(categories: List[dict], currency: str) -> str:
        """Форматирует категории расходов для промпта"""
        # ...

    @staticmethod
    def _format_income_categories(categories: List[dict], currency: str) -> str:
        """Форматирует категории доходов для промпта"""
        # ...

    @staticmethod
    def _format_top_expenses(expenses: List[dict], currency: str) -> str:
        """Форматирует топ-5 трат для промпта"""
        # ...

    @staticmethod
    def _format_weekday_stats(weekday_expenses: dict, currency: str, lang: str = 'ru') -> str:
        """Форматирует статистику по дням недели"""
        # ...

    @staticmethod
    def _format_budgets(budgets: List[dict], currency: str, lang: str = 'ru') -> str:
        """Форматирует бюджеты для промпта"""
        # ...
```

**Промпт (детальная версия см. в основном плане выше)**

---

### 3. **monthly_insights.py** (Основной сервис)

**Расположение:** `bot/services/monthly_insights.py`

**Цель:** Генерация AI инсайтов с multi-level fallback

**⚠️ ВАЖНО: Полностью async архитектура**
- Все методы async для корректной работы в aiogram
- AsyncIsolator используется ТОЛЬКО в Celery задаче
- Никаких `asyncio.run()` - только `await`

**Структура:**

```python
"""
Сервис генерации AI инсайтов для месячных финансовых отчетов
"""
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, Dict, List
from calendar import monthrange
import asyncio

from expenses.models import Profile, Expense, Income, Budget
from bot.services.expense import get_expenses_summary
from bot.services.income import get_incomes_summary
from bot.services.ai_prompts import AIPrompts
from bot.utils import get_month_name

logger = logging.getLogger(__name__)


class MonthlyInsightsService:
    """Сервис для генерации AI-powered месячных финансовых инсайтов"""

    @staticmethod
    async def generate_insights_with_ai(user_id: int, year: int, month: int) -> Optional[str]:
        """
        Генерация AI инсайтов с многоуровневым fallback

        ⚠️ ASYNC функция - вызывать через await

        Уровни fallback:
        1. Google Gemini (2 попытки, retry через 1 сек)
        2. OpenAI GPT-4o (1 попытка)
        3. None (будет использован простой fallback текст)

        Args:
            user_id: Telegram ID пользователя
            year: Год отчета
            month: Месяц отчета (1-12)

        Returns:
            str | None: AI-генерированный текст или None при ошибке
        """
        # Реализация (см. ниже)

    @staticmethod
    async def _prepare_user_data(user_id: int, year: int, month: int) -> Dict:
        """
        Подготовка данных пользователя для AI анализа

        ⚠️ ASYNC функция - использует await для get_expenses_summary

        Собирает:
        - Данные текущего месяца (расходы, доходы, категории, топ траты)
        - Данные предыдущего месяца (для сравнения)
        - Бюджеты пользователя
        - Язык и валюту

        Args:
            user_id: Telegram ID пользователя
            year: Год
            month: Месяц

        Returns:
            dict: Подготовленные данные для AI
        """
        # Реализация (см. ниже)

    @staticmethod
    def _notify_admin_insights_error(user_id: int, error_message: str, error_type: str):
        """
        Уведомление админа об ошибке генерации инсайтов

        Args:
            user_id: Telegram ID пользователя
            error_message: Текст ошибки
            error_type: Тип ошибки ('gemini_fail', 'openai_fail', 'both_fail')
        """
        # Реализация (см. ниже)

    @staticmethod
    def _notify_admin_fallback_used(user_id: int, year: int, month: int, fallback_type: str):
        """
        Уведомление админа об использовании fallback

        Args:
            user_id: Telegram ID
            year: Год
            month: Месяц
            fallback_type: Тип fallback ('openai', 'simple_text')
        """
        # Реализация (см. ниже)
```

**Детальная реализация методов:**

#### 3.1. `generate_insights_with_ai()` - ASYNC версия

```python
@staticmethod
async def generate_insights_with_ai(user_id: int, year: int, month: int) -> Optional[str]:
    """
    Генерация AI инсайтов с многоуровневым fallback

    ⚠️ ASYNC функция - вызывать через await из async контекста
    """
    try:
        # 1. Подготовка данных (ASYNC)
        logger.info(f"[INSIGHTS] Preparing data for user {user_id}, {year}-{month:02d}")
        user_data = await MonthlyInsightsService._prepare_user_data(user_id, year, month)

        if not user_data:
            logger.warning(f"[INSIGHTS] No data available for user {user_id}")
            return None

        # Проверка минимального количества операций
        if user_data['current_month']['expense_count'] < 3:
            logger.info(f"[INSIGHTS] Too few transactions for user {user_id}, skipping AI analysis")
            return None

        # 2. УРОВЕНЬ 1: Попытка через Google Gemini (ASYNC)
        try:
            logger.info(f"[INSIGHTS] Attempt 1: Google Gemini for user {user_id}")

            from bot.services.google_ai_service import GoogleAIService

            # ПРЯМОЙ AWAIT - без AsyncIsolator!
            insights = await GoogleAIService.generate_monthly_insights(user_data)

            logger.info(f"[INSIGHTS] ✓ Successfully generated via Gemini for user {user_id}")
            return insights

        except Exception as gemini_error:
            error_msg = str(gemini_error)[:100]
            logger.warning(f"[INSIGHTS] Gemini failed for user {user_id}: {error_msg}")

            # 3. УРОВЕНЬ 2: Попытка через OpenAI (ASYNC)
            try:
                logger.info(f"[INSIGHTS] Attempt 2: OpenAI fallback for user {user_id}")

                from bot.services.openai_service import OpenAIService

                # ПРЯМОЙ AWAIT - без AsyncIsolator!
                insights = await OpenAIService.generate_monthly_insights(user_data)

                logger.info(f"[INSIGHTS] ✓ Successfully generated via OpenAI for user {user_id}")

                # Уведомляем админа об использовании fallback (SYNC - нормально в async функции)
                await asyncio.to_thread(
                    MonthlyInsightsService._notify_admin_fallback_used,
                    user_id, year, month, "OpenAI (Gemini unavailable)"
                )

                return insights

            except Exception as openai_error:
                logger.error(f"[INSIGHTS] OpenAI also failed for user {user_id}: {openai_error}")

                # Уведомляем админа о полном отказе AI (SYNC - через to_thread)
                await asyncio.to_thread(
                    MonthlyInsightsService._notify_admin_insights_error,
                    user_id,
                    f"Gemini: {error_msg}, OpenAI: {str(openai_error)[:50]}",
                    'both_fail'
                )

                # 4. УРОВЕНЬ 3: Возвращаем None (будет использован простой текст)
                logger.error(f"[INSIGHTS] All AI providers failed for user {user_id}")
                return None

    except Exception as e:
        logger.error(f"[INSIGHTS] Critical error in generate_insights_with_ai: {e}", exc_info=True)
        return None
```

#### 3.2. `_prepare_user_data()` - ASYNC версия

```python
@staticmethod
async def _prepare_user_data(user_id: int, year: int, month: int) -> Dict:
    """
    Подготовка данных пользователя для AI анализа

    ⚠️ ASYNC функция - использует await для вызова get_expenses_summary
    """
    try:
        # Получаем профиль пользователя (SYNC - нормально)
        profile = await asyncio.to_thread(
            Profile.objects.filter(telegram_id=user_id).first
        )

        if not profile:
            logger.error(f"Profile not found for user {user_id}")
            return None

        # Определяем период текущего месяца
        start_date = date(year, month, 1)
        last_day = monthrange(year, month)[1]
        end_date = date(year, month, last_day)

        # Получаем данные текущего месяца (ASYNC - await!)
        current_summary = await get_expenses_summary(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date
        )

        # Получаем детальные расходы для топ-5 (SYNC ORM - через to_thread)
        current_expenses = await asyncio.to_thread(
            lambda: list(Expense.objects.filter(
                profile=profile,
                expense_date__gte=start_date,
                expense_date__lte=end_date
            ).select_related('category').order_by('-amount')[:5])
        )

        top_expenses = [
            {
                'description': exp.description or (exp.category.get_display_name(profile.language_code) if exp.category else 'Без категории'),
                'amount': float(exp.amount),
                'category': exp.category.get_display_name(profile.language_code) if exp.category else 'Без категории',
                'date': exp.expense_date.strftime('%Y-%m-%d')
            }
            for exp in current_expenses
        ]

        # Статистика по дням недели (SYNC - через to_thread)
        weekday_expenses = await asyncio.to_thread(
            MonthlyInsightsService._calculate_weekday_stats,
            profile, start_date, end_date
        )

        # Определяем предыдущий месяц
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        prev_start_date = date(prev_year, prev_month, 1)
        prev_last_day = monthrange(prev_year, prev_month)[1]
        prev_end_date = date(prev_year, prev_month, prev_last_day)

        # Получаем данные предыдущего месяца (если есть) (ASYNC - await!)
        previous_summary = None
        try:
            previous_summary = await get_expenses_summary(
                user_id=user_id,
                start_date=prev_start_date,
                end_date=prev_end_date
            )
        except Exception as e:
            logger.warning(f"Could not get previous month data: {e}")

        # Получаем бюджеты пользователя (SYNC ORM - через to_thread)
        budgets = await asyncio.to_thread(
            lambda: list(Budget.objects.filter(
                profile=profile,
                is_active=True
            ).select_related('category'))
        )

        budgets_data = []
        for budget in budgets:
            # Рассчитываем траты по этому бюджету (SYNC ORM - через to_thread)
            budget_expenses = await asyncio.to_thread(
                lambda: list(Expense.objects.filter(
                    profile=profile,
                    expense_date__gte=start_date,
                    expense_date__lte=end_date,
                    category=budget.category if budget.category else None
                ))
            )

            spent = sum(exp.amount for exp in budget_expenses)
            percentage_used = (spent / budget.amount * 100) if budget.amount > 0 else 0

            budgets_data.append({
                'category_name': budget.category.get_display_name(profile.language_code) if budget.category else 'Общий бюджет',
                'limit': float(budget.amount),
                'spent': float(spent),
                'percentage_used': float(percentage_used),
                'remaining': float(budget.amount - spent)
            })

        # Формируем итоговую структуру
        user_data = {
            'user_id': user_id,
            'profile_id': profile.id,
            'user_lang': profile.language_code or 'ru',
            'currency': current_summary.get('currency', 'RUB'),

            'current_month': {
                'year': year,
                'month': month,
                'month_name': get_month_name(month, profile.language_code or 'ru'),
                'income_total': float(current_summary.get('income_total', 0)),
                'income_count': current_summary.get('income_count', 0),
                'expense_total': float(current_summary.get('total', 0)),
                'expense_count': current_summary.get('count', 0),
                'balance': float(current_summary.get('balance', 0)),
                'cashback_total': float(current_summary.get('potential_cashback', 0)),
                'expense_categories': [
                    {
                        'name': cat['name'],
                        'amount': float(cat['total']),
                        'count': cat['count'],
                        'percentage': (float(cat['total']) / float(current_summary.get('total', 1)) * 100)
                    }
                    for cat in current_summary.get('by_category', [])[:10]
                ],
                'income_categories': [
                    {
                        'name': cat['name'],
                        'amount': float(cat['total']),
                        'count': cat['count'],
                        'percentage': (float(cat['total']) / float(current_summary.get('income_total', 1)) * 100) if current_summary.get('income_total', 0) > 0 else 0
                    }
                    for cat in current_summary.get('by_income_category', [])
                ],
                'top_expenses': top_expenses,
                'weekday_expenses': weekday_expenses
            },

            'budgets': budgets_data
        }

        # Добавляем данные предыдущего месяца если есть
        if previous_summary and previous_summary.get('count', 0) > 0:
            user_data['previous_month'] = {
                'year': prev_year,
                'month': prev_month,
                'month_name': get_month_name(prev_month, profile.language_code or 'ru'),
                'income_total': float(previous_summary.get('income_total', 0)),
                'expense_total': float(previous_summary.get('total', 0)),
                'balance': float(previous_summary.get('balance', 0)),
                'expense_categories': [
                    {
                        'name': cat['name'],
                        'amount': float(cat['total']),
                        'count': cat['count'],
                        'percentage': (float(cat['total']) / float(previous_summary.get('total', 1)) * 100)
                    }
                    for cat in previous_summary.get('by_category', [])[:10]
                ],
                'income_categories': [
                    {
                        'name': cat['name'],
                        'amount': float(cat['total']),
                        'count': cat['count'],
                        'percentage': (float(cat['total']) / float(previous_summary.get('income_total', 1)) * 100) if previous_summary.get('income_total', 0) > 0 else 0
                    }
                    for cat in previous_summary.get('by_income_category', [])
                ]
            }
        else:
            user_data['previous_month'] = None

        return user_data

    except Exception as e:
        logger.error(f"Error preparing user data: {e}", exc_info=True)
        return None


@staticmethod
def _calculate_weekday_stats(profile: Profile, start_date: date, end_date: date) -> Dict[str, float]:
    """Рассчитывает статистику расходов по дням недели"""
    weekday_totals = {
        'monday': Decimal('0'),
        'tuesday': Decimal('0'),
        'wednesday': Decimal('0'),
        'thursday': Decimal('0'),
        'friday': Decimal('0'),
        'saturday': Decimal('0'),
        'sunday': Decimal('0')
    }

    weekday_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

    expenses = Expense.objects.filter(
        profile=profile,
        expense_date__gte=start_date,
        expense_date__lte=end_date
    )

    for expense in expenses:
        weekday_index = expense.expense_date.weekday()
        weekday_name = weekday_names[weekday_index]
        weekday_totals[weekday_name] += expense.amount

    # Конвертируем в float
    return {day: float(amount) for day, amount in weekday_totals.items()}
```

#### 3.3. Уведомления админу

```python
@staticmethod
def _notify_admin_insights_error(user_id: int, error_message: str, error_type: str):
    """Уведомление админа об ошибке генерации инсайтов"""
    try:
        from bot.services.admin_notifier import send_admin_alert, escape_markdown_v2
        from django.core.cache import cache
        from datetime import datetime

        # Кеш для предотвращения спама (не чаще раза в 30 минут для одного пользователя)
        cache_key = f"insights_error_notification_{user_id}"
        if cache.get(cache_key):
            return

        # Счетчик ошибок за день
        error_count_key = f"insights_errors_{datetime.now().date()}"
        error_count = cache.get(error_count_key, 0) + 1
        cache.set(error_count_key, error_count, 86400)  # 24 часа

        message = (
            f"🔴 *Ошибка генерации месячных AI инсайтов*\n\n"
            f"👤 Пользователь: `{user_id}`\n"
            f"❌ Тип: {escape_markdown_v2(error_type)}\n"
            f"📝 Ошибка: {escape_markdown_v2(error_message[:200])}\n"
            f"📊 Всего ошибок за сегодня: {error_count}\n"
            f"🕐 Время: {escape_markdown_v2(datetime.now().strftime('%H:%M:%S'))}\n\n"
            f"⚠️ Отчет будет отправлен БЕЗ AI анализа"
        )

        # Отправляем асинхронно
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(send_admin_alert(message))
        loop.close()

        # Устанавливаем кеш на 30 минут
        cache.set(cache_key, True, 1800)

        logger.info(f"Admin notified about insights error for user {user_id}")

    except Exception as e:
        logger.error(f"Failed to notify admin about insights error: {e}")


@staticmethod
def _notify_admin_fallback_used(user_id: int, year: int, month: int, fallback_type: str):
    """Уведомление админа об использовании fallback"""
    try:
        from bot.services.admin_notifier import send_admin_alert, escape_markdown_v2
        from django.core.cache import cache
        from datetime import datetime

        # Счетчик использований fallback за день
        fallback_count_key = f"insights_fallback_{datetime.now().date()}"
        fallback_count = cache.get(fallback_count_key, 0) + 1
        cache.set(fallback_count_key, fallback_count, 86400)

        # Отправляем уведомление только раз в час (чтобы не спамить)
        notification_key = f"insights_fallback_notification_{datetime.now().hour}"
        if cache.get(notification_key):
            return

        message = (
            f"⚠️ *Использован fallback для месячных инсайтов*\n\n"
            f"👤 Пользователь: `{user_id}`\n"
            f"📅 Период: {escape_markdown_v2(f'{year}-{month:02d}')}\n"
            f"🔄 Fallback: {escape_markdown_v2(fallback_type)}\n"
            f"📊 Всего fallback за сегодня: {fallback_count}\n\n"
            f"ℹ️ Gemini недоступен, использован OpenAI"
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(send_admin_alert(message, disable_notification=True))
        loop.close()

        cache.set(notification_key, True, 3600)  # 1 час

        logger.info(f"Admin notified about fallback usage for user {user_id}")

    except Exception as e:
        logger.error(f"Failed to notify admin about fallback: {e}")
```

---

### 4. Интеграция в Google AI Service

**Расположение:** `bot/services/google_ai_service.py`

**Добавить метод:**

```python
import os
from bot.services.ai_prompts import AIPrompts

# В класс GoogleAIService добавить:

@classmethod
async def generate_monthly_insights(cls, user_data: dict) -> str:
    """
    Генерация месячных финансовых инсайтов через Gemini

    Args:
        user_data: Подготовленные данные пользователя

    Returns:
        str: AI-генерированный анализ

    Raises:
        Exception: При ошибке генерации
    """
    # Retry логика
    max_attempts = 2
    last_error = None

    for attempt in range(max_attempts):
        try:
            return await cls._generate_monthly_insights_impl(user_data)
        except Exception as e:
            last_error = e
            if attempt == max_attempts - 1:
                logger.error(f"Failed to generate monthly insights via Gemini after {max_attempts} attempts: {e}")
                raise Exception(f"Gemini insights generation failed: {str(e)}")
            else:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(1)  # Задержка перед повтором


@classmethod
async def _generate_monthly_insights_impl(cls, user_data: dict) -> str:
    """Внутренняя реализация генерации инсайтов"""
    import google.generativeai as genai

    # Получаем модель из env или используем дефолтную
    model_name = os.getenv('GOOGLE_MODEL_INSIGHTS', 'gemini-2.0-flash-exp')

    # Создаем модель
    model = genai.GenerativeModel(model_name)

    # Получаем промпт
    lang = user_data.get('user_lang', 'ru')
    prompt = AIPrompts.get_monthly_insights_prompt(user_data, lang)

    # Настройки генерации
    generation_config = genai.types.GenerationConfig(
        temperature=0.7,
        max_output_tokens=2000,
        top_p=0.9,
        top_k=40
    )

    # Генерируем
    response = await model.generate_content_async(
        prompt,
        generation_config=generation_config
    )

    result = response.text

    # Небольшая задержка для завершения внутренних операций
    await asyncio.sleep(0.05)

    return result
```

---

### 5. Интеграция в OpenAI Service

**Расположение:** `bot/services/openai_service.py`

**Добавить метод:**

```python
import os
from bot.services.ai_prompts import AIPrompts

# В класс OpenAIService добавить:

@staticmethod
async def generate_monthly_insights(user_data: dict) -> str:
    """
    Генерация месячных финансовых инсайтов через OpenAI GPT

    Args:
        user_data: Подготовленные данные пользователя

    Returns:
        str: AI-генерированный анализ

    Raises:
        Exception: При ошибке генерации
    """
    try:
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        # Получаем модель из env
        model_name = os.getenv('OPENAI_MODEL_INSIGHTS', 'gpt-4o')

        # Получаем промпт
        lang = user_data.get('user_lang', 'ru')
        prompt = AIPrompts.get_monthly_insights_prompt(user_data, lang)

        # Генерируем
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=model_name,
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0.7
        )

        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"Error generating insights via OpenAI: {e}")
        raise Exception(f"OpenAI insights generation failed: {str(e)}")
```

---

### 6. Интеграция в NotificationService

**Расположение:** `bot/services/notifications.py`

**Обновить метод `send_monthly_report`:**

```python
async def send_monthly_report(self, user_id: int, profile: Profile, year: int = None, month: int = None):
    """Send monthly expense report with AI insights (if available)"""
    try:
        from ..services.pdf_report import PDFReportService
        from ..services.monthly_insights import MonthlyInsightsService
        from aiogram.types import BufferedInputFile

        today = date.today()

        # Если год/месяц не указаны - используем текущий месяц
        report_year = year if year is not None else today.year
        report_month = month if month is not None else today.month

        # 1. Попытка сгенерировать AI инсайты (ASYNC - await!)
        insights_text = None
        try:
            logger.info(f"Generating AI insights for user {user_id}, {report_year}-{report_month:02d}")
            insights_text = await MonthlyInsightsService.generate_insights_with_ai(
                user_id=user_id,
                year=report_year,
                month=report_month
            )
        except Exception as e:
            logger.error(f"Failed to generate AI insights for user {user_id}: {e}")
            # Продолжаем без AI инсайтов

        # 2. Генерируем PDF отчет (существующая логика)
        pdf_service = PDFReportService()
        pdf_bytes = await pdf_service.generate_monthly_report(
            user_id=user_id,
            year=report_year,
            month=report_month
        )

        month_name = get_month_name(report_month, profile.language_code or 'ru')

        # 3. Формируем caption в зависимости от результатов
        if insights_text and pdf_bytes:
            # УСПЕХ: AI инсайты + PDF
            caption = f"{insights_text}\n\n📎 Подробный PDF отчет прикреплен ниже"
            logger.info(f"Sending monthly report WITH AI insights to user {user_id}")

        elif pdf_bytes:
            # FALLBACK: Только PDF (AI недоступен)
            caption = f"📊 Ежемесячный отчет за {month_name} {report_year}"
            logger.warning(f"Sending monthly report WITHOUT AI insights to user {user_id}")

        else:
            # ОШИБКА: Ни AI, ни PDF
            logger.warning(f"No data for monthly report: user {user_id}, {report_year}-{report_month:02d}")
            return

        # 4. Отправляем сообщение с PDF
        pdf_file = BufferedInputFile(
            pdf_bytes,
            filename=f"monthly_report_{report_year}_{report_month:02d}.pdf"
        )

        await self.bot.send_document(
            chat_id=user_id,
            document=pdf_file,
            caption=caption,
            parse_mode='Markdown'  # Поддержка *жирного* и _курсива_
        )

        logger.info(f"Monthly report sent to user {user_id} for {report_year}-{report_month:02d}")

    except Exception as e:
        logger.error(f"Error sending monthly report to user {user_id}: {e}")
```

---

## Схема работы

### Последовательность выполнения:

**⚠️ ВАЖНО: Два разных сценария вызова**

#### Сценарий 1: Из Celery задачи (SYNC контекст)

```
1. Celery задача: send_monthly_reports (1-го числа в 10:00 МСК)
   ↓
2. Для каждого пользователя:
   ↓
3. AsyncIsolator.run_in_thread(
       NotificationService.send_monthly_report(...)
   )  ← ОБЯЗАТЕЛЬНО через AsyncIsolator!
   ↓
4. Внутри send_monthly_report (уже в async контексте):
   ├─→ await MonthlyInsightsService.generate_insights_with_ai()
   │   ├─→ await _prepare_user_data() - собираем данные за 2 месяца
   │   │   ├─→ await get_expenses_summary() - текущий месяц
   │   │   └─→ await get_expenses_summary() - предыдущий месяц
   │   ├─→ await GoogleAIService.generate_monthly_insights()
   │   │   ├─→ SUCCESS ✓ → возвращаем AI текст
   │   │   └─→ FAIL ✗ → переходим к OpenAI
   │   │       ├─→ await OpenAIService.generate_monthly_insights()
   │   │       │   ├─→ SUCCESS ✓ → AI текст + уведомляем админа
   │   │       │   └─→ FAIL ✗ → уведомляем админа + None
   │   │       └─→ None
   │   └─→ insights_text (или None)
   │
   └─→ await PDFReportService.generate_monthly_report() → pdf_bytes

5. Формируем caption и отправляем
```

#### Сценарий 2: Из aiogram бота (ASYNC контекст)

```
1. Пользователь нажимает кнопку "Получить месячный отчет"
   ↓
2. ПРЯМОЙ вызов (без AsyncIsolator!):
   await NotificationService.send_monthly_report(...)
   ↓
3. Далее так же как в Сценарии 1 (начиная с шага 4)
```

### Временные метки:

```
09:59:59 - Celery beat запускает задачу
10:00:00 - send_monthly_reports() начинает работу
10:00:01 - Вычисляет предыдущий месяц (декабрь 2024)
10:00:02 - Находит 150 пользователей с расходами в декабре
10:00:03 - USER 1: Подготовка данных (0.5s)
10:00:03 - USER 1: Gemini генерация (2-5s)
10:00:08 - USER 1: PDF генерация (1-2s)
10:00:10 - USER 1: Отправка сообщения (0.5s)
10:00:10 - USER 2: Начало обработки...
...
10:15:00 - Все 150 пользователей обработаны
```

---

## Обработка ошибок и Fallback

### Уровни fallback:

```
┌─────────────────────────────────────────────┐
│  УРОВЕНЬ 1: Google Gemini                   │
│  - Model: gemini-2.0-flash-exp              │
│  - Timeout: 60s                             │
│  - Retry: 2 попытки с задержкой 1s          │
│  - Success rate: ~95%                       │
└──────────────┬──────────────────────────────┘
               │ FAIL (5%)
               ▼
┌─────────────────────────────────────────────┐
│  УРОВЕНЬ 2: OpenAI GPT-4o                   │
│  - Model: gpt-4o                            │
│  - Timeout: 60s                             │
│  - Retry: 1 попытка                         │
│  - Success rate: ~90%                       │
│  - Уведомление админу: "Gemini unavailable" │
└──────────────┬──────────────────────────────┘
               │ FAIL (<1%)
               ▼
┌─────────────────────────────────────────────┐
│  УРОВЕНЬ 3: Simple Fallback Text           │
│  - Caption: "📊 Ежемесячный отчет за месяц" │
│  - PDF отправляется БЕЗ AI анализа          │
│  - Уведомление админу: "Both AI failed"    │
└─────────────────────────────────────────────┘
```

### Примеры ошибок:

**1. Gemini Timeout:**
```
[INSIGHTS] Gemini failed for user 123456: TimeoutError: Async function execution exceeded 60s
[INSIGHTS] Attempt 2: OpenAI fallback
[INSIGHTS] ✓ Successfully generated via OpenAI
→ Админ получает: "⚠️ Использован fallback: OpenAI (Gemini unavailable)"
→ Пользователь получает: AI анализ от OpenAI
```

**2. Gemini API Error:**
```
[INSIGHTS] Gemini failed for user 123456: 503 Service Unavailable
[INSIGHTS] Attempt 2: OpenAI fallback
[INSIGHTS] ✓ Successfully generated via OpenAI
→ Админ: "⚠️ Gemini unavailable"
→ Пользователь: OpenAI анализ
```

**3. Оба AI недоступны:**
```
[INSIGHTS] Gemini failed: 503 Service Unavailable
[INSIGHTS] OpenAI also failed: Rate limit exceeded
[INSIGHTS] All AI providers failed for user 123456
→ Админ: "🔴 Ошибка: оба AI недоступны. Gemini: 503, OpenAI: Rate limit"
→ Пользователь: "📊 Ежемесячный отчет за декабрь 2024" (без AI анализа)
```

**4. Недостаточно данных:**
```
[INSIGHTS] Too few transactions for user 123456 (2 expenses), skipping AI analysis
→ Пользователь: "📊 Ежемесячный отчет за декабрь 2024"
→ Админ: НЕТ уведомления (это нормальная ситуация)
```

---

## Уведомления админу

### Типы уведомлений:

#### 1. **Использован Fallback (OpenAI)**

**Частота:** Максимум 1 раз в час (кеш)

**Сообщение:**
```
⚠️ *Использован fallback для месячных инсайтов*

👤 Пользователь: `123456789`
📅 Период: 2024-12
🔄 Fallback: OpenAI (Gemini unavailable)
📊 Всего fallback за сегодня: 3

ℹ️ Gemini недоступен, использован OpenAI
```

**Когда отправляется:**
- Gemini недоступен, но OpenAI успешно сгенерировал инсайты
- Не чаще 1 раза в час (чтобы не спамить)

#### 2. **Ошибка генерации (оба AI недоступны)**

**Частота:** Максимум 1 раз в 30 минут для одного пользователя

**Сообщение:**
```
🔴 *Ошибка генерации месячных AI инсайтов*

👤 Пользователь: `123456789`
❌ Тип: both_fail
📝 Ошибка: Gemini: 503 Service Unavailable, OpenAI: Rate limit exceeded
📊 Всего ошибок за сегодня: 5
🕐 Время: 10:15:23

⚠️ Отчет будет отправлен БЕЗ AI анализа
```

**Когда отправляется:**
- Оба AI провайдера недоступны
- Отчет отправлен без AI анализа
- Не чаще 1 раза в 30 минут для одного пользователя

#### 3. **Критическая ошибка в коде**

**Частота:** Каждый раз

**Сообщение:**
```
🔴 *Критическая ошибка в генерации инсайтов*

👤 Пользователь: `123456789`
❌ Ошибка: KeyError: 'current_month'
📝 Traceback: ...

⚠️ Требуется проверка кода
```

**Когда отправляется:**
- Exception в `_prepare_user_data()` или других методах
- Ошибки в коде, а не в AI сервисах

---

## Тестирование

### 1. Ручное тестирование в Django shell

```python
python manage.py shell

from bot.services.monthly_insights import MonthlyInsightsService
from datetime import date

# Тест генерации инсайтов
user_id = 123456789  # Ваш Telegram ID
year = 2024
month = 12

# Генерация
insights = MonthlyInsightsService.generate_insights_with_ai(user_id, year, month)
print(insights)
```

### 2. Тест подготовки данных

```python
from bot.services.monthly_insights import MonthlyInsightsService

user_data = MonthlyInsightsService._prepare_user_data(123456789, 2024, 12)

import json
print(json.dumps(user_data, indent=2, ensure_ascii=False, default=str))
```

### 3. Тест промпта

```python
from bot.services.ai_prompts import AIPrompts

# Подготовить user_data (см. выше)
prompt = AIPrompts.get_monthly_insights_prompt(user_data, 'ru')
print(prompt)
```

### 4. Тест Gemini напрямую

```python
import asyncio
from bot.services.google_ai_service import GoogleAIService

# Подготовить user_data
insights = asyncio.run(GoogleAIService.generate_monthly_insights(user_data))
print(insights)
```

### 5. Тест OpenAI напрямую

```python
import asyncio
from bot.services.openai_service import OpenAIService

insights = asyncio.run(OpenAIService.generate_monthly_insights(user_data))
print(insights)
```

### 6. Тест полного флоу отправки отчета

```python
from bot.services.notifications import NotificationService
from expenses.models import Profile
from aiogram import Bot
import os
import asyncio

bot = Bot(token=os.getenv('BOT_TOKEN'))
service = NotificationService(bot)

profile = Profile.objects.get(telegram_id=123456789)

asyncio.run(service.send_monthly_report(
    user_id=123456789,
    profile=profile,
    year=2024,
    month=12
))
```

---

## Этапы реализации

### Этап 1: Подготовка (30 мин)

- [x] Создать `docs/AI_MONTHLY_INSIGHTS_PLAN.md`
- [ ] Обновить `.env` (добавить `GOOGLE_MODEL_INSIGHTS` и `OPENAI_MODEL_INSIGHTS`)
- [ ] Скопировать `async_isolator.py` из Nutrition_bot

### Этап 2: Промпты и утилиты (1 час)

- [ ] Создать `bot/services/ai_prompts.py`
  - [ ] Класс `AIPrompts`
  - [ ] Метод `get_monthly_insights_prompt()` (русский)
  - [ ] Метод `get_monthly_insights_prompt()` (английский)
  - [ ] Вспомогательные методы форматирования

### Этап 3: Основной сервис (2 часа)

- [ ] Создать `bot/services/monthly_insights.py`
  - [ ] Класс `MonthlyInsightsService`
  - [ ] Метод `generate_insights_with_ai()`
  - [ ] Метод `_prepare_user_data()`
  - [ ] Метод `_calculate_weekday_stats()`
  - [ ] Методы уведомлений админу

### Этап 4: AI интеграция (1 час)

- [ ] Обновить `bot/services/google_ai_service.py`
  - [ ] Добавить `generate_monthly_insights()`
  - [ ] Добавить `_generate_monthly_insights_impl()`
- [ ] Обновить `bot/services/openai_service.py`
  - [ ] Добавить `generate_monthly_insights()`

### Этап 5: Интеграция в NotificationService (30 мин)

- [ ] Обновить `bot/services/notifications.py`
  - [ ] Метод `send_monthly_report()` - добавить вызов AI генерации
  - [ ] Обновить логику формирования caption

### Этап 6: Тестирование (2 часа)

- [ ] Тест подготовки данных
- [ ] Тест промпта
- [ ] Тест Gemini генерации
- [ ] Тест OpenAI генерации
- [ ] Тест fallback логики
- [ ] Тест уведомлений админу
- [ ] Тест полного флоу с реальными данными

### Этап 7: Деплой на сервер (1 час)

- [ ] Обновить `.env` на сервере
- [ ] Загрузить новые файлы через git
- [ ] Перезапустить контейнеры
- [ ] Проверить логи
- [ ] Тестовая отправка отчета

---

## Итого

**Общее время разработки:** ~8 часов

**Новые файлы:** 3
- `bot/services/ai_prompts.py`
- `bot/services/monthly_insights.py`
- `bot/services/async_isolator.py`

**Измененные файлы:** 3
- `bot/services/notifications.py`
- `bot/services/google_ai_service.py`
- `bot/services/openai_service.py`

**Переменные окружения:** +2
- `GOOGLE_MODEL_INSIGHTS=gemini-2.0-flash-exp`
- `OPENAI_MODEL_INSIGHTS=gpt-4o`

**Зависимости:** Нет новых (используем существующие Google AI и OpenAI SDK)

---

## Будущие улучшения (опционально)

1. **Кеширование AI ответов** - если данные не изменились, брать из кеша
2. **A/B тестирование промптов** - сравнить разные версии промптов
3. **Пользовательская настройка** - позволить отключить AI инсайты
4. **Расширенная аналитика** - добавить прогнозы на следующий месяц
5. **Сравнение с другими пользователями** - анонимная статистика
