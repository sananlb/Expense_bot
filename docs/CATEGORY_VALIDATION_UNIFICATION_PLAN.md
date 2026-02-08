# План: Унификация валидации категорий расходов и доходов

**Дата:** 2026-02-08
**Статус:** Готов к реализации
**Приоритет:** Высокий

---

## Предыстория

### Инцидент 2026-02-08 21:37:12

Пользователь 5081318925 нажал "Без иконки" при создании категории дохода с уже существующим названием. Вместо понятного сообщения "Категория уже существует" получил "😔 Что-то пошло не так", админу ушёл алерт о "критической ошибке".

**Причина:** В `_apply_icon_and_finalize()` не было `except ValueError`. Бизнес-ошибка улетала в глобальный error_handler как unhandled exception.

### Уже исправлено (в текущей сессии)

1. ✅ Добавлен `except ValueError` в `_apply_icon_and_finalize` (`categories.py:166-170`)
2. ✅ Проверка дубликатов в `create_income_category` переведена на `name_ru__iexact`/`name_en__iexact` + fallback `name__iexact` (`income.py:1189-1195`)
3. ✅ Проверка дубликатов в `update_income_category` — аналогично (`income.py:1297-1303`)

### Обнаруженная асимметрия

При анализе выяснилось что реализация категорий расходов и доходов **сильно отличается**:

| Аспект | Расходы | Доходы | Кто лучше |
|--------|---------|--------|-----------|
| Проверка дубликатов (create) | `Q(name_ru=text) \| Q(name_en=text)` — case-sensitive | `Q(name_ru__iexact=text) \| Q(name_en__iexact=text) \| Q(name__iexact=display_name)` | ✅ Доходы |
| При дубликате (create) | Молча возвращает existing | Бросает `ValueError` | ✅ Доходы |
| Проверка дубликатов (update) | **Отсутствует!** | Есть с `.exclude(id=category_id)` | ✅ Доходы |
| Фильтр `is_active` | Нет | Да | ✅ Доходы |
| Регистронезависимость | Нет | Да (`iexact`) | ✅ Доходы |
| Fallback на legacy `name` | Нет | Да | ✅ Доходы |
| Лимит категорий (50) | Да | **Нет** | ✅ Расходы |
| `transaction.atomic()` | Да | **Нет** | ✅ Расходы |

**Цель:** Взять лучшее из обоих реализаций, вынести общую логику в утилиты, устранить дублирование.

---

## Файлы для изменения

| Файл | Действие |
|------|----------|
| `bot/utils/category_validators.py` | **СОЗДАТЬ** — общие валидаторы |
| `bot/services/income.py` | Рефакторинг: использовать утилиты, добавить `transaction.atomic()` и лимит 50 |
| `bot/services/category.py` | Рефакторинг: использовать утилиты, добавить проверку дубликатов в update, бросать ValueError |
| `bot/routers/categories.py` | Обновить `process_edit_category_name` (строка 955): добавить `try/except ValueError` |

---

## Шаг 1: Создать `bot/utils/category_validators.py`

Обе модели (`ExpenseCategory`, `IncomeCategory`) имеют идентичную структуру полей: `name`, `name_ru`, `name_en`, `icon`, `is_active`, `profile`. Это позволяет сделать универсальные функции.

### Функции:

```python
"""Общие валидаторы для категорий расходов и доходов."""

import re
import logging
from typing import Type
from django.db import models
from django.db.models import Q
from bot.utils.input_sanitizer import InputSanitizer

logger = logging.getLogger(__name__)

MAX_CATEGORIES_PER_USER = 50


def validate_category_name(raw_name: str) -> str:
    """
    Валидация и очистка названия категории.

    Returns:
        Очищенное название

    Raises:
        ValueError: если название невалидно
    """
    if len(raw_name) > InputSanitizer.MAX_CATEGORY_LENGTH:
        raise ValueError(
            f"Название категории слишком длинное "
            f"(максимум {InputSanitizer.MAX_CATEGORY_LENGTH} символов)"
        )

    sanitized = InputSanitizer.sanitize_category_name(raw_name).strip()
    if not sanitized:
        raise ValueError("Название категории не может быть пустым")

    return sanitized


def detect_category_language(text: str, fallback_lang: str = 'ru') -> str:
    """
    Определяет язык текста категории.

    Returns:
        'ru', 'en' или fallback_lang
    """
    has_cyrillic = bool(re.search(r'[а-яА-ЯёЁ]', text))
    has_latin = bool(re.search(r'[a-zA-Z]', text))

    if has_cyrillic and not has_latin:
        return 'ru'
    elif has_latin and not has_cyrillic:
        return 'en'
    return fallback_lang


def check_category_duplicate(
    model_class: Type[models.Model],
    profile,
    text: str,
    display_name: str,
    exclude_id: int = None
) -> bool:
    """
    Проверяет наличие дубликата категории.

    Проверяет по name_ru/name_en (iexact) + fallback на legacy name.
    Фильтрует только активные категории.

    Args:
        model_class: ExpenseCategory или IncomeCategory
        profile: объект профиля пользователя
        text: название без иконки (для проверки name_ru/name_en)
        display_name: полное название с иконкой (для проверки legacy name)
        exclude_id: ID текущей категории (исключить при update)

    Returns:
        True если дубликат найден
    """
    qs = model_class.objects.filter(
        profile=profile,
        is_active=True
    ).filter(
        Q(name_ru__iexact=text) | Q(name_en__iexact=text) | Q(name__iexact=display_name)
    )

    if exclude_id is not None:
        qs = qs.exclude(id=exclude_id)

    return qs.exists()


def validate_category_limit(
    model_class: Type[models.Model],
    profile,
    limit: int = MAX_CATEGORIES_PER_USER
) -> None:
    """
    Проверяет лимит количества категорий.

    Raises:
        ValueError: если лимит превышен
    """
    count = model_class.objects.filter(profile=profile, is_active=True).count()
    if count >= limit:
        logger.warning(
            "User %s reached categories limit (%d)",
            profile.telegram_id, limit
        )
        raise ValueError(f"Достигнут лимит категорий (максимум {limit})")
```

---

## Шаг 2: Рефакторинг `bot/services/income.py`

### 2.1 create_income_category (строки ~1164-1237)

**Добавить:**
- `transaction.atomic()` — обернуть весь блок
- `validate_category_limit(IncomeCategory, profile)` — проверка лимита 50

**Заменить на вызовы утилит:**
- Валидация имени: ~~ручная проверка длины + sanitize~~ → `validate_category_name(text)`
- Определение языка: ~~has_cyrillic/has_latin~~ → `detect_category_language(text, profile.language_code or 'ru')`
- Проверка дубликатов: ~~Q-фильтры inline~~ → `check_category_duplicate(IncomeCategory, profile, text, display_name)`

**Было (~15 строк валидации), станет (~5 строк):**
```python
from bot.utils.category_validators import (
    validate_category_name, detect_category_language,
    check_category_duplicate, validate_category_limit,
)
from django.db import transaction

# ...внутри _create_income_category():
with transaction.atomic():
    profile = get_or_create_user_profile_sync(telegram_id)
    validate_category_limit(IncomeCategory, profile)

    # ... парсинг иконки (оставить как есть) ...

    text = validate_category_name(text)
    display_name = f"{parsed_icon} {text}".strip() if parsed_icon else text

    if check_category_duplicate(IncomeCategory, profile, text, display_name):
        raise ValueError("Категория с таким названием уже существует")

    original_language = detect_category_language(text, profile.language_code or 'ru')

    # ... создание категории (оставить как есть) ...
```

### 2.2 update_income_category (строки ~1262-1350)

**Заменить на вызовы утилит:**
- Валидация имени → `validate_category_name(text)`
- Определение языка → `detect_category_language(text, profile.language_code or 'ru')`
- Проверка дубликатов → `check_category_duplicate(IncomeCategory, profile, text, display_name, exclude_id=category_id)`

---

## Шаг 3: Рефакторинг `bot/services/category.py`

### 3.1 create_category (строки 320-394)

**Заменить на вызовы утилит:**
- Лимит: ~~`categories_count >= 50`~~ → `validate_category_limit(ExpenseCategory, profile)`
- Валидация имени: ~~ручная~~ → `validate_category_name(raw_name)`
- Определение языка: ~~ручная~~ → `detect_category_language(clean_name, user_lang)`
- Проверка дубликатов: ~~`Q(name_ru=clean_name) | Q(name_en=clean_name)`~~ → `check_category_duplicate(...)`

**Исправить поведение при дубликате:**
```python
# БЫЛО: молча возвращает existing
if existing:
    return existing, False

# СТАНЕТ: бросает ValueError (единообразие с доходами)
if check_category_duplicate(ExpenseCategory, profile, clean_name, display_name):
    raise ValueError("Категория с таким названием уже существует")
```

**Упростить возврат:**
```python
# БЫЛО: кортеж
return category, True
# ...
category, is_new = await _create_category()
return category

# СТАНЕТ: просто категория
return category
# ...
return await _create_category()
```

### 3.2 update_category_name (строки 417-490)

**Добавить проверку дубликатов (сейчас отсутствует!):**
```python
# После получения category и до вызова update_category():
display_name = f"{icon} {name_without_icon}".strip() if icon else name_without_icon
if check_category_duplicate(ExpenseCategory, category.profile, name_without_icon, display_name, exclude_id=category_id):
    raise ValueError("Категория с таким названием уже существует")
```

**Исправить возврат при ошибке:**
```python
# БЫЛО: return False при невалидном имени
if not name_sanitized:
    return False

# СТАНЕТ: бросает ValueError (через validate_category_name)
name_without_icon = validate_category_name(name_without_icon)
```

---

## Шаг 4: Обновить вызывающий код

### 4.1 `_apply_icon_and_finalize` (categories.py:148-182)
Уже имеет `except ValueError` — покрывает все пути. **Ничего менять не нужно.**

### 4.2 `process_edit_category_name` (categories.py:955)

**Сейчас:**
```python
new_category_ok = await _update_category_name(user_id, cat_id, final_name)

if new_category_ok:
    # ... успех
else:
    # ... "Не удалось обновить категорию"
```

**Станет:**
```python
try:
    await _update_category_name(user_id, cat_id, final_name)
    # ... успех (тот же код что был в if new_category_ok)
except ValueError as e:
    await message.answer(f"❌ {str(e)}")
    await state.clear()
```

---

## Проверка после реализации

| # | Сценарий | Ожидаемый результат |
|---|----------|-------------------|
| 1 | Создание расходной категории с дубликатом | "❌ Категория с таким названием уже существует" |
| 2 | Создание доходной категории с дубликатом | То же сообщение |
| 3 | Переименование расходной категории в дубликат | Ошибка (раньше проходило молча!) |
| 4 | Переименование доходной категории в дубликат | Ошибка |
| 5 | Создание >50 категорий расходов | "❌ Достигнут лимит категорий (максимум 50)" |
| 6 | Создание >50 категорий доходов | То же (новое!) |
| 7 | Создание "кафе" когда есть "Кафе" | Дубликат (iexact) |
| 8 | Создание категории с новым уникальным названием | Успех |
| 9 | Переименование категории в уникальное название | Успех |

---

## Риски

| Риск | Митигация |
|------|-----------|
| `create_category` раньше возвращала existing — кто-то мог на это полагаться | Проверено: единственный внешний вызов (`categories.py:165`) не использует результат |
| `update_category_name` раньше возвращала `bool` — вызов на строке 955 | Обернём в `try/except ValueError` |
| Fallback на legacy `name` может дать false positive | Маловероятно: `name__iexact` проверяет полное имя с иконкой, а `name_ru/name_en` — без. Пересечение минимально |
