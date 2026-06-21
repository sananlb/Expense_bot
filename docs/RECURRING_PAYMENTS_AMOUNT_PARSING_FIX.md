# Исправление парсинга сумм с пробелами в регулярных платежах

**Дата:** 2026-01-28
**Статус:** 🔴 Требует исправления
**Приоритет:** Средний (UX улучшение)
**Затронутый функционал:** Создание регулярных платежей
**Code Review:** ✅ Прошел внешний code review, исправлено 5 критических багов

---

## 🔍 Критические исправления после code review

1. ✅ **Regex теперь поддерживает ОБА формата** - с разделителями ("48 000") И без ("48000")
2. ✅ **Убраны упоминания "10k"** - мультипликаторы обрабатываются отдельным функционалом
3. ✅ **Точное совпадение "плюс" и "+"** - через `\b` для "плюс", `^\+` для + в начале, `\s\+\s` для + между пробелами, `\s\+(?=\d)` для + перед числом. Работает: "+5000", "+ 5000", "Зарплата +5000", "Зарплата + 5000". Не матчит "Plus Market", "C++".
4. ✅ **Сохранены оригинальные тексты ошибок** - все 4 варианта из старого кода, включая особый случай для allow_only_amount=True с описанием
5. ✅ **Валюта переиспользует detect_currency из expense_parser** - единый список валют/склонений, безопасное удаление валюты без обрезания слов

---

## 📋 Проблема

### Описание
Пользователи получают ошибку при вводе сумм регулярных платежей с пробелами в качестве разделителей тысяч.

### Реальный инцидент (28.01.2026)
**Пользователь:** 1453938432
**Попытка #1 (13:15:25):** "Аренда квартиры 48 000"
**Результат:** ❌ Ошибка "Неверный формат. Отправьте сумму или название и сумму."

Пользователь ввел пробел между "48" и "000", что привело к ошибке парсинга.

### Корневая причина
Функция `parse_description_amount` использует простой `split()` по пробелам, который разбивает число с пробелами на отдельные части:

```python
# Текущий код (bot/utils/validators.py:61)
parts = text.strip().split()
# "Аренда квартиры 48 000" → ["Аренда", "квартиры", "48", "000"]
amount_str = parts[-1]  # "000"
amount = float("000")  # 0.0 → затем ValueError("Сумма должна быть больше 0")
```

---

## 🔍 Текущее состояние

### ✅ Обычные траты - УЖЕ работает
**Файл:** `bot/utils/expense_parser.py:504-507`

```python
# Regex паттерн поддерживает пробелы в числах:
number_pattern = r'\s(\d{1,3}(?:[\s,]\d{3})*(?:[.,]\d+)?)\s'
amount_str = number_match.group(1).replace(' ', '').replace(',', '.')
# "кофе 10 000 рублей" → 10000.0 ✅
```

**Работающие примеры:**
- ✅ "кофе 10 000" → 10000
- ✅ "продукты 1 000 000" → 1000000
- ✅ "обед 5 500" → 5500

### ❌ Регулярные платежи - НЕ работает
**Файл:** `bot/utils/validators.py:61`

```python
# Простой split не понимает пробелы в числах:
parts = text.strip().split()
# "Аренда квартиры 48 000" → ["Аренда", "квартиры", "48", "000"]
```

**НЕ работающие примеры:**
- ❌ "Аренда 48 000" → Ошибка
- ❌ "Интернет 1 500" → Ошибка
- ❌ "Коммуналка 10 000.50" → Ошибка

---

## 💡 Решение

### Цель
Обеспечить одинаковый UX для обычных трат и регулярных платежей - поддержка пробелов в суммах.

### Подход
Заменить `split()` на regex-парсинг с поддержкой:
- Пробелов в числах: "48 000"
- Неразрывных пробелов: "48 000" (\\xa0)
- Запятых как разделителя тысяч: "48,000"
- Десятичных дробей: "10 000.50" или "10 000,50"
- Валют в конце (через общий детектор): "48 000 руб", "5000 сом", "200 тенге", "500р", "300 лир"

### Преимущества
1. ✅ Согласованность UX - одинаковое поведение везде
2. ✅ Поддержка больших сумм - важно для валют вроде сома (KGS)
3. ✅ Интуитивность - пользователи естественно вводят пробелы
4. ✅ Меньше ошибок - меньше случаев когда пользователь вводит повторно
5. ✅ Единый список валют/склонений с обычными тратами (re-use detect_currency)

---

## 🔧 План реализации

### Файл для изменения
`bot/utils/validators.py` - функция `parse_description_amount` (строки 46-134)

### Новый код (с исправлениями)

**Критические исправления:**
1. ✅ Regex поддерживает ОБА формата: с разделителями ("48 000") И без ("48000")
2. ✅ Убраны упоминания "10k" (мультипликаторы обрабатываются отдельно)
3. ✅ Точное определение дохода: `\bплюс\b` для слова, `^\+` для + в начале, `\s\+\s` для + между пробелами, `\s\+(?=\d)` для + перед числом. Работает: "+5000", "+ 5000", "Зарплата +5000", "Зарплата + 5000". Не матчит "C++"
4. ✅ Сохранены оригинальные тексты ошибок: все 4 варианта включая особый для allow_only_amount=True с описанием
5. ✅ Валюта переиспользует detect_currency из expense_parser (единый список валют/склонений, безопасное удаление валюты)

```python
import re
from typing import Dict, Any
from .expense_parser import detect_currency

def parse_description_amount(text: str, allow_only_amount: bool = False) -> Dict[str, Any]:
    """
    Парсит текст в формате 'Описание Сумма' или просто 'Сумма'
    Поддерживает суммы с пробелами: "48 000", "1 000 000"
    Поддерживает знак + или слово "плюс" для определения доходов

    Args:
        text: Текст для парсинга
        allow_only_amount: Разрешить ввод только суммы без описания

    Returns:
        dict: {'description': str или None, 'amount': float, 'is_income': bool}

    Raises:
        ValueError: Если формат неверный

    Examples:
        >>> parse_description_amount("Аренда 48 000", allow_only_amount=False)
        {'description': 'Аренда', 'amount': 48000.0, 'is_income': False}

        >>> parse_description_amount("Зарплата плюс 150 000")
        {'description': 'Зарплата', 'amount': 150000.0, 'is_income': True}

        >>> parse_description_amount("48 000", allow_only_amount=True)
        {'description': None, 'amount': 48000.0, 'is_income': False}

        >>> parse_description_amount("Такси 500")
        {'description': 'Такси', 'amount': 500.0, 'is_income': False}
    """
    # Проверяем на пустой ввод
    if not text or not text.strip():
        raise ValueError("Пустой ввод. Отправьте сумму или название и сумму.")

    text = text.strip()

    # Проверяем знак дохода
    is_income = False

    # ✅ ИСПРАВЛЕНИЕ 3: Точное совпадение слова "плюс" через границы слов
    if re.search(r'\bплюс\b', text, re.IGNORECASE):
        is_income = True
        text = re.sub(r'\bплюс\b', '', text, flags=re.IGNORECASE)
        text = ' '.join(text.split())  # Нормализуем пробелы

    # ✅ ИСПРАВЛЕНИЕ 3: Знак + распознается только если нет СЛОВА между + и суммой
    # Пробелы разрешены, но слова - нет. НЕ матчит "C++"
    # Паттерн 1: +5000 или "+ 5000" (в начале строки)
    if re.match(r'^\+', text.strip()):
        is_income = True
        text = text.strip()[1:]  # Убираем + из начала
    # Паттерн 2: Зарплата + 5000 (отдельный токен)
    elif re.search(r'\s\+\s', text):
        is_income = True
        text = re.sub(r'\s\+\s', ' ', text)  # Убираем " + "
        text = ' '.join(text.split())
    # Паттерн 3: Зарплата +5000 (слитно с числом)
    elif re.search(r'\s\+(?=\d)', text):
        is_income = True
        text = re.sub(r'\s\+(?=\d)', ' ', text)  # Убираем + перед числом
        text = ' '.join(text.split())

    # ✅ ИСПРАВЛЕНИЕ 1: Regex поддерживает ОБА формата - с разделителями И без
    # (?:\d{1,3}(?:[\s\xa0,]\d{3})+|\d+) - либо число с разделителями, либо просто число
    # Примеры: "48 000", "48000", "1 000 000.50", "5500"
    # + опциональный суффикс валюты (валидация через detect_currency)
    number_pattern = r'((?:\d{1,3}(?:[\s\xa0,]\d{3})+|\d+)(?:[.,]\d+)?)(?:\s*(?P<currency>[^\d\s].*))?$'
    match = re.search(number_pattern, text, re.IGNORECASE)

    if not match:
        if allow_only_amount:
            # ✅ ИСПРАВЛЕНИЕ 4: Сохранен оригинальный текст ошибки
            if len(text.split()) > 1:
                raise ValueError("Неверный формат. Отправьте сумму или название и сумму.")
            raise ValueError("Неверный формат суммы")
        else:
            raise ValueError("Неверный формат. Отправьте название и сумму через пробел.")

    currency_suffix = match.group('currency')
    if currency_suffix:
        currency_suffix = currency_suffix.strip()
        if currency_suffix:
            detected = detect_currency(f"1 {currency_suffix}", user_currency="XXX")
            if detected == "XXX":
                description_end = match.start()
                has_description = bool(text[:description_end].strip())
                if allow_only_amount and has_description:
                    raise ValueError("Неверный формат. Отправьте сумму или название и сумму.")
                raise ValueError("Неверный формат суммы")

    # Извлекаем найденное число
    amount_str = match.group(1)

    # Нормализуем число: удаляем пробелы и неразрывные пробелы
    amount_str = amount_str.replace(' ', '').replace('\xa0', '')

    # Определяем десятичный разделитель
    # Если есть и запятая и точка - точка это дробная часть: 1,000.50
    # Если только запятая - это может быть либо разделитель тысяч либо дробная часть
    if '.' in amount_str and ',' in amount_str:
        # Формат: 1,000.50 - запятая это тысячи, точка дробная часть
        amount_str = amount_str.replace(',', '')
    elif ',' in amount_str:
        # Проверяем контекст: если после запятой 1-2 цифры - это дробная часть
        comma_parts = amount_str.split(',')
        if len(comma_parts) == 2 and len(comma_parts[1]) <= 2:
            # После запятой 1-2 цифры - это дробная часть: 10,5 или 10,50
            amount_str = amount_str.replace(',', '.')
        else:
            # После запятой 3 цифры или несколько запятых - это разделитель тысяч: 1,000
            amount_str = amount_str.replace(',', '')

    try:
        amount = float(amount_str)
    except (ValueError, Exception):
        # ✅ ИСПРАВЛЕНИЕ 4: Оригинальный текст ошибки (точно как в старом коде)
        # Старый код имеет 4 разных сообщения в зависимости от контекста:
        # 1. allow_only_amount=True, одна часть → "Неверный формат суммы"
        # 2. allow_only_amount=False, одна часть → уже обработано выше
        # 3. allow_only_amount=True, есть описание → "Неверный формат. Отправьте сумму или название и сумму."
        # 4. allow_only_amount=False, несколько частей → "Неверный формат суммы"
        description_end = match.start()
        has_description = bool(text[:description_end].strip())

        if allow_only_amount and has_description:
            # Случай 3: allow_only_amount=True, есть описание, ошибка парсинга
            raise ValueError("Неверный формат. Отправьте сумму или название и сумму.")
        else:
            # Случаи 1 и 4: остальные варианты
            raise ValueError("Неверный формат суммы")

    if amount <= 0:
        raise ValueError("Сумма должна быть больше 0")

    # Извлекаем описание (всё до числа)
    description_end = match.start()
    description = text[:description_end].strip()

    # ✅ ИСПРАВЛЕНИЕ 5: Удаление валюты через detect_currency (без обрезания слов)
    if description:
        words = description.split()
        if len(words) >= 2:
            candidate = " ".join(words[-2:])
            if detect_currency(f"1 {candidate}", user_currency="XXX") != "XXX":
                description = " ".join(words[:-2]).strip()
        if description:
            candidate = description.split()[-1]
            if detect_currency(f"1 {candidate}", user_currency="XXX") != "XXX":
                description = " ".join(description.split()[:-1]).strip()

    # Проверяем что есть описание если требуется
    if not description and not allow_only_amount:
        # ✅ ИСПРАВЛЕНИЕ 4: Оригинальный текст ошибки
        raise ValueError("Неверный формат. Отправьте название и сумму через пробел.")

    # Капитализируем первую букву описания
    if description:
        description = description[0].upper() + description[1:] if len(description) > 1 else description.upper()
    else:
        description = None

    return {
        'description': description,
        'amount': amount,
        'is_income': is_income
    }
```

---

## ✅ Тестовые кейсы

### Должны работать после исправления:

```python
# Пробелы в числах
assert parse_description_amount("Аренда 48 000") == {
    'description': 'Аренда', 'amount': 48000.0, 'is_income': False
}

# Миллионы
assert parse_description_amount("Недвижимость 1 000 000") == {
    'description': 'Недвижимость', 'amount': 1000000.0, 'is_income': False
}

# Дробные числа
assert parse_description_amount("Интернет 1 500.50") == {
    'description': 'Интернет', 'amount': 1500.5, 'is_income': False
}

# С запятой как дробной частью
assert parse_description_amount("Кофе 150,5") == {
    'description': 'Кофе', 'amount': 150.5, 'is_income': False
}

# Только сумма с пробелами
assert parse_description_amount("48 000", allow_only_amount=True) == {
    'description': None, 'amount': 48000.0, 'is_income': False
}

# С индикатором дохода
assert parse_description_amount("Зарплата плюс 150 000") == {
    'description': 'Зарплата', 'amount': 150000.0, 'is_income': True
}

# С валютой в конце
assert parse_description_amount("Покупка 50 000 руб") == {
    'description': 'Покупка', 'amount': 50000.0, 'is_income': False
}

# Без пробелов (обратная совместимость) ✅ КРИТИЧНО!
assert parse_description_amount("Такси 500") == {
    'description': 'Такси', 'amount': 500.0, 'is_income': False
}

# Большое число без пробелов ✅ КРИТИЧНО!
assert parse_description_amount("Продукты 48000") == {
    'description': 'Продукты', 'amount': 48000.0, 'is_income': False
}

# Проверка что "Plus Market" НЕ определяется как доход
assert parse_description_amount("Plus Market 1000") == {
    'description': 'Plus Market', 'amount': 1000.0, 'is_income': False
}

# ✅ КРИТИЧНО: Проверка что "C++" НЕ определяется как доход
assert parse_description_amount("C++ книга 500") == {
    'description': 'C++ книга', 'amount': 500.0, 'is_income': False
}

# Проверка что "Прораб" не обрезается до "Прора"
assert parse_description_amount("Прораб 5000") == {
    'description': 'Прораб', 'amount': 5000.0, 'is_income': False
}

# ✅ Проверка что + в начале определяется как доход
assert parse_description_amount("+ 5000", allow_only_amount=True) == {
    'description': None, 'amount': 5000.0, 'is_income': True
}

# ✅ Проверка что + с пробелами определяется как доход (нет слова между + и суммой)
assert parse_description_amount("Зарплата + 5000") == {
    'description': 'Зарплата', 'amount': 5000.0, 'is_income': True
}

# ✅ КРИТИЧНО: Обратная совместимость - + слитно с числом
assert parse_description_amount("Зарплата +5000") == {
    'description': 'Зарплата', 'amount': 5000.0, 'is_income': True
}

# ✅ Валюты и склонения (переиспользуем detect_currency)
assert parse_description_amount("Обед 200 тенге") == {
    'description': 'Обед', 'amount': 200.0, 'is_income': False
}
assert parse_description_amount("Обед 200 теньге") == {
    'description': 'Обед', 'amount': 200.0, 'is_income': False
}
assert parse_description_amount("Такси 500р") == {
    'description': 'Такси', 'amount': 500.0, 'is_income': False
}
assert parse_description_amount("Подарок 750 рублей") == {
    'description': 'Подарок', 'amount': 750.0, 'is_income': False
}
assert parse_description_amount("Кофе 300 лир") == {
    'description': 'Кофе', 'amount': 300.0, 'is_income': False
}
```

### Должны выдавать ошибку:

```python
# Пустой ввод
with pytest.raises(ValueError, match="Пустой ввод"):
    parse_description_amount("")

# Нет суммы
with pytest.raises(ValueError, match="Неверный формат"):
    parse_description_amount("Только текст без числа")

# Нулевая сумма
with pytest.raises(ValueError, match="Сумма должна быть больше 0"):
    parse_description_amount("Тест 0")

# ✅ КРИТИЧНО: Особый случай из старого кода
# allow_only_amount=True + есть описание + ошибка парсинга → специальное сообщение
with pytest.raises(ValueError, match="Неверный формат. Отправьте сумму или название и сумму."):
    parse_description_amount("Описание непарсящеесячисло", allow_only_amount=True)
```

---

## 📊 Влияние изменения

### Затронутые места использования
`parse_description_amount` используется в:
1. ✅ `bot/routers/recurring.py:195` - создание регулярных платежей (основное место)
2. ✅ Любые другие места где парсится "описание + сумма"

### Обратная совместимость
✅ **Полная обратная совместимость** - все форматы которые работали раньше, продолжат работать:
- "Такси 500" → работает как раньше
- "Обед 50.5" → работает как раньше
- "Зарплата +5000" → работает как раньше
- **Сообщения об ошибках** → точно как раньше (все 4 варианта сохранены)

### Риски
🟢 **Очень низкий риск:**
- Изменение затрагивает только парсинг ввода
- Regex паттерн прошел code review (внешний AI выявил и исправил 5 критических багов)
- ✅ Обратная совместимость ПОЛНОСТЬЮ сохранена (тесты включают оба формата)
- ✅ Regex поддерживает числа БЕЗ разделителей (исправлена потенциальная регрессия)
- ✅ Точное определение дохода через word boundaries (не ломает "Plus Market")
- ✅ Безопасное удаление валют (не обрезает слова типа "Прораб")
- ✅ Валюты/склонения совпадают с обычными тратами (reuse detect_currency)

---

## 🚀 План внедрения

### Шаг 1: Локальное тестирование
1. Создать тесты в `tests/test_parse_description_amount.py`
2. Запустить все тесты локально
3. Убедиться что старые тесты проходят

### Шаг 2: Внедрение кода
1. Заменить функцию в `bot/utils/validators.py`
2. Добавить импорт `re` и `detect_currency` (если не добавлены)
3. Запустить полный набор тестов проекта

### Шаг 3: Деплой на сервер
1. Коммит и пуш изменений
2. Обновление на сервере через `quick_bot_update.sh`
3. Мониторинг логов в течение первого дня

### Шаг 4: Верификация
1. Проверить создание регулярного платежа с суммой "48 000"
2. Проверить обычное добавление траты - не сломалось
3. Мониторить логи на наличие ошибок парсинга

---

## 📝 Чеклист

- [ ] Создать тесты для новой функции
- [ ] Заменить код в `bot/utils/validators.py`
- [ ] Запустить локальные тесты
- [ ] Коммит и пуш
- [ ] Деплой на сервер
- [ ] Проверка на сервере
- [ ] Мониторинг логов 24 часа
- [ ] Обновить документацию (если есть)

---

## 🎯 Ожидаемый результат

После внедрения пользователи смогут вводить суммы регулярных платежей с пробелами:
- ✅ "Аренда квартиры 48 000" → работает
- ✅ "Интернет 1 500" → работает
- ✅ "Коммуналка 10 000.50" → работает
- ✅ "Зарплата плюс 150 000 сом" → работает
- ✅ "Обед 200 тенге" → работает
- ✅ "Такси 500р" → работает

**Меньше ошибок ввода = лучше UX = довольные пользователи!**

---

**Время на реализацию:** 1-2 часа (включая тестирование)
**Сложность:** Низкая
**Польза для пользователей:** Высокая
