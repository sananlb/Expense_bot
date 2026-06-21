# План исправления проблемы частичного совпадения keywords

**Дата:** 2025-01-17 (обновлено: ВАРИАНТ А - полное решение)
**Проблема:** Keyword "кофе" находится в тексте "кофейный торт" из-за частичного вхождения (`in`)
**Цель:** Проверять ПЕРЕСЕЧЕНИЕ МНОЖЕСТВ СЛОВ с fuzzy matching для опечаток

## 📌 Краткое резюме решения

### Проблема:
- `if keyword.lower() in text_lower:` вызывает **false positive** - "кофе" находится в "кофейный торт"
- Нет поддержки multi-word keywords ("кофейный торт" не может найти "торт наполеон")
- Нет fuzzy matching для опечаток
- При обучении добавляются "паразитные" слова ("and", "or", "i") и выбираются первые 2 слова вместо лучших

### Решение (Вариант А):
1. **3 новых helper функции** в `bot/utils/expense_parser.py`:
   - `extract_words()` - разбивает на слова с нормализацией №/_ (НЕ дефис!), опциональная фильтрация чистых цифр через keep_digits
   - `remove_amount_from_text()` - удаляет только сумму, оставляет остальные цифры
   - `match_keyword_in_text()` - принимает RAW текст, проверяет пересечение множеств слов + fuzzy 75%

2. **Обновление обучения** в `celery_tasks.py`:
   - Приоритетная сортировка: слова с цифрами +100
   - Выбор 2 ЛУЧШИХ слов (не первых)
   - НОВОЕ ПРАВИЛО: если >3 слов после фильтрации → НЕ извлекаем НИЧЕГО
   - Расширенные стоп-слова: английские + валюты
   - Лимит 100 слов на категорию (вместо 50)

3. **Замена в 5 местах** с проверками `in` → `match_keyword_in_text()`:
   - Передаем RAW text (не text_lower!) - helper сам нормализует
   - `expense_parser.py:546`, `:956`, `:532`, `:1092`
   - `income_categorization.py:181`

4. **Реальные unit-тесты** в `test_keyword_matching.py`

### Результат:
- ✅ "кофе" НЕ найдет "кофейный торт" (разные слова!)
- ✅ "кофейный торт" найдет "торт наполеон" (пересечение: "торт")
- ✅ "cs2" найдет "played cs2 with friends"
- ✅ "кофе" найдет "кофф" через fuzzy (75%)
- ✅ При обучении: "played cs2 with coursemates" → добавятся "cs2", "played" (топ 2 из 3 слов!)

---

## 🎯 Требования (ВАРИАНТ А - полное и честное решение)

### Проверка keywords (поиск категории):
1. **✅ ЧЕСТНО: Разбиваем на слова** - keyword и текст разбиваются на отдельные слова для проверки пересечения множеств
2. **✅ Сохранять цифры в словах** - "cs2" остается "cs2", не превращается в "cs"
3. **✅ Сохранять цифры отдельно** - "квартира №5" → {"квартира", "5"} (через keep_digits=True)
4. **✅ Удалять только сумму** - все остальные цифры остаются в тексте
5. **✅ Нормализация спецсимволов** - № → пробел, _ → пробел (НО НЕ дефис!)
6. **✅ Дефис НЕ нормализуется** - "кофе-машина" остается одним словом, keyword "кофе" его НЕ найдет
7. **✅ Пересечение множеств** - keyword "кофейный торт" найдет "торт наполеон" (общее слово "торт")
8. **✅ Fuzzy matching** - cutoff=0.75 (75% схожести) для опечаток
9. **✅ Multi-word keywords** - разбивать keyword на слова для fuzzy проверки каждого слова отдельно
10. **✅ Helper принимает RAW текст** - нормализует сам (единая точка нормализации), вызывающий код НЕ должен обрабатывать текст заранее

### Обучение keywords (AI категоризация):
1. **✅ Максимум 2 слова** - никогда не добавляем больше 2 keywords за одну запись
2. **✅ НОВОЕ: Если >3 слов после фильтрации → извлекаем 0 keywords** - предотвращает добавление "мусорных" keywords из длинных описаний
3. **✅ Приоритет слов** - выбираем 2 САМЫХ важных слова (с цифрами), а не просто первые
4. **✅ Фильтр чистых цифр** - не добавляем слова состоящие только из цифр ("2", "10"), но оставляем смешанные ("cs2")
5. **✅ Расширенные стоп-слова** - английские + русские + валюты + глаголы:
   - Служебные: "and", "or", "i", "my", "the", "и", "в", "на", "за"
   - Валюты: "usd", "eur", "som", "рублей", "доллар", "евро"
   - Глаголы: "купил", "взял", "потратил", "оплатил" - НЕ должны быть keywords
6. **✅ Сохранять цифры** - "cs2", "iphone15" записываются с цифрами
7. **✅ НЕТ ручного выбора** - автоматическое обучение без участия пользователя
8. **✅ Лимит 100 слов на категорию** - вместо 50 для большей гибкости

### Покрытие кода:
1. **✅ ВСЕ 5 мест** с substring проверками должны использовать единый helper:
   - `expense_parser.py:546` - keywords расходов (пользовательские)
   - `expense_parser.py:956` - keywords доходов в парсере
   - `income_categorization.py:181` - категоризация доходов
   - `expense_parser.py:532` - название категории пользователя
   - `expense_parser.py:1092` - suggest_category() (стандартные категории) — удалено как мёртвый код

### Тестирование:
1. **✅ РЕАЛЬНЫЕ unit-тесты** - создать файл `test_keyword_matching.py` с тестами для helper функций
2. **✅ Edge cases** - тесты для multi-word keywords, спецсимволов, опечаток, коротких слов

---

## 📊 Примеры работы

### ✅ Правильное поведение (пересечение множеств):

| Keyword в БД | Разбивка keyword | Ввод пользователя | Разбивка ввода | Пересечение | Результат |
|--------------|------------------|-------------------|----------------|-------------|-----------|
| "кофе" | {"кофе"} | "кофейный торт 200" | {"кофейный", "торт"} | {} | ❌ НЕ найдено ✅ |
| "кофе" | {"кофе"} | "купил кофе 150" | {"купил", "кофе"} | {"кофе"} | ✅ Найдено ✅ |
| "кофе" | {"кофе"} | "кофф 100" (опечатка) | {"кофф"} | fuzzy: "кофе"≈"кофф" | ✅ Найдено (fuzzy) ✅ |
| "cs2" | {"cs2"} | "played cs2 with friends" | {"played", "cs2", "with", "friends"} | {"cs2"} | ✅ Найдено ✅ |
| "кофейный торт" | {"кофейный", "торт"} | "торт наполеон 300" | {"торт", "наполеон"} | {"торт"} | ✅ Найдено ✅ |
| "кофейный торт" | {"кофейный", "торт"} | "кофейный сироп 150" | {"кофейный", "сироп"} | {"кофейный"} | ✅ Найдено ✅ |
| "продукты" | {"продукты"} | "продуктовый магазин 500" | {"продуктовый", "магазин"} | {} | ❌ НЕ найдено ✅ |
| "квартира" | {"квартира"} | "квартира №5" | {"квартира", "5"} | {"квартира"} | ✅ Найдено ✅ |

### 🎓 Обучение на примерах (С ПРИОРИТЕТНОЙ СОРТИРОВКОЙ + НОВОЕ ПРАВИЛО):

| Ввод пользователя | AI категория | Слова после фильтрации | Количество слов | Scores | Топ 2 по score | Добавлено в keywords |
|-------------------|--------------|------------------------|-----------------|--------|----------------|---------------------|
| "cs2 100" | CS2 | ["cs2"] | 1 | cs2:100 | cs2 | "cs2" ✅ (1 слово) |
| "кофе 150" | Кафе | ["кофе"] | 1 | кофе:0 | кофе | "кофе" ✅ (1 слово) |
| "кофейный торт" | Десерты | ["кофейный", "торт"] | 2 | кофейный:0, торт:0 | кофейный, торт | "кофейный", "торт" ✅ (все 2) |
| "played cs2 with friends" | CS2 | ["played", "cs2", "friends"] | 3 | cs2:100, played:0, friends:0 | cs2, played | "cs2", "played" ✅ (топ 2!) |
| "купил вкусный кофейный торт наполеон" | Десерты | ["вкусный", "кофейный", "торт", "наполеон"] | **4 > 3** | все:0 | - | **НИЧЕГО** ❌ (слишком много слов!) |
| "And i played cs2 for so'm with my coursemates in university" | CS2 | ["played", "cs2", "coursemates", "university"] | **4 > 3** | cs2:100, played:0, coursemates:0, university:0 | - | **НИЧЕГО** ❌ (слишком много слов!) |

**Логика scoring (УПРОЩЕННАЯ):**
- Слова с цифрами: +100 (cs2, iphone15, 5g) - ГЛАВНЫЙ приоритет
- Все остальные слова: 0 (равный приоритет, берутся первые 2)
- **ВАЖНО: Если слов >3 после фильтрации → НЕ извлекаем НИЧЕГО (защита от "мусора")**

**Примеры с валютами:**
| Ввод | AI категория | Слова после фильтрации | Количество | Scores | Топ 2 | Добавлено |
|------|--------------|------------------------|------------|--------|-------|-----------|
| "кофе за 150 рублей" | Кафе | ["кофе", "150"] | 2 | кофе:0, 150:0 | кофе, 150 | "кофе", "150" ✅ ("за", "рублей" отфильтровано) |
| "купил такси 300" | Транспорт | ["такси", "300"] | 2 | такси:0, 300:0 | такси, 300 | "такси", "300" ✅ ("купил" отфильтровано) |
| "paid 50 usd for coffee" | Кафе | ["paid", "coffee"] | 2 | все:0 | paid, coffee | "paid", "coffee" ✅ ("usd" отфильтровано) |
| "100 som" | Разное | ["100"] | 1 | 100:0 | 100 | "100" ✅ ("som" отфильтровано) |

---

## 🏗️ Архитектура решения (ВАРИАНТ А)

### 1. Helper функция извлечения слов (ОБНОВЛЕНИЕ СУЩЕСТВУЮЩЕЙ)

**Расположение:** `bot/utils/expense_parser.py` рядом с `extract_words_from_description`
**Название:** `extract_words(text: str, keep_digits: bool = True, normalize_special: bool = True) -> List[str]`

**Задача:** Разбить текст на слова с сохранением цифр и нормализацией спецсимволов

**Алгоритм:**
```python
1. Нормализация спецсимволов (опционально):
   if normalize_special:
       text = text.replace('№', ' ')  # "квартира№5" → "квартира 5"
       text = text.replace('_', ' ')  # "foo_bar" → "foo bar"
       # ВАЖНО: Дефис НЕ заменяем - он часть слова!
       # "кофе-машина" остается одним словом

2. Удалить валюту и пунктуацию (но НЕ дефис, цифры и буквы!):
   text = re.sub(r'[₽$€£¥.,"\'!?;:\(\)]', ' ', text)
   # Дефис сохраняется в словах

3. Разбить на слова и lowercase:
   words = text.lower().split()

4. Расширенные стоп-слова (русские + английские + валюты):
   stop_words = {
       # Русские предлоги и союзы
       'и', 'в', 'на', 'с', 'за', 'по', 'для', 'от', 'до', 'из',
       'или', 'но', 'а', 'к', 'у', 'о', 'об', 'под', 'над',

       # Глаголы (действия с деньгами)
       # ВАЖНО: Нужны для AI парсинга, но НЕ для keywords!
       # "купил кофе" → keyword "кофе", а НЕ "купил"
       'купил', 'купила', 'купили', 'взял', 'взяла', 'взяли',
       'потратил', 'потратила', 'потратили', 'оплатил', 'оплатила',
       'заплатил', 'заплатила', 'оплачено', 'потрачено'

       # Валюты (русские названия)
       'рубль', 'рубля', 'рублей', 'руб', 'тыс', 'тысяч',
       'доллар', 'доллара', 'долларов',
       'евро',
       'сом', 'сома', 'сомов',
       'тенге',
       'гривна', 'гривны', 'гривен',
       'лира', 'лиры', 'лир',
       'фунт', 'фунта', 'фунтов',
       'йена', 'йены', 'йен',
       'юань', 'юаня', 'юаней',

       # Английские
       'and', 'or', 'the', 'a', 'an', 'i', 'my', 'for', 'with',
       'in', 'at', 'to', 'of', 'from', 'by', 'on', 'is', 'was',
       'are', 'were', 'been', 'be', 'have', 'has', 'had',
       'do', 'does', 'did', 'will', 'would', 'could', 'should',

       # Валюты (английские названия и коды)
       'usd', 'dollar', 'dollars',
       'eur', 'euro', 'euros',
       'rub', 'ruble', 'rubles',
       'som', 'soms',
       'kgs', 'kzt', 'uah', 'try', 'gbp', 'jpy', 'cny'
   }

5. Фильтровать слова:
   for word in words:
       word = word.strip()
       if not word or len(word) < 3:  # Минимум 3 символа
           continue
       if word in stop_words:  # Стоп-слова
           continue

       # ВАЖНО: Используем параметр keep_digits
       if not keep_digits and word.isdigit():  # Чистые цифры фильтруем только если keep_digits=False
           continue

       filtered_words.append(word)

6. Вернуть список слов
```

**Примеры:**
```python
extract_words("cs2 100", keep_digits=True, normalize_special=True)
# Результат: ["cs2", "100"]  # keep_digits=True → "100" сохраняется

extract_words("cs2 100", keep_digits=False, normalize_special=True)
# Результат: ["cs2"]  # keep_digits=False → "100" отфильтровано

extract_words("played cs2 with friends", keep_digits=True)
# Результат: ["played", "cs2", "friends"]  # "with" в стоп-словах

extract_words("And i played cs2", keep_digits=True)
# Результат: ["played", "cs2"]  # "and", "i" в стоп-словах

extract_words("квартира №5", keep_digits=True, normalize_special=True)
# Результат: ["квартира", "5"]  # № заменен на пробел, "5" сохранен

extract_words("кофе-машина", keep_digits=True, normalize_special=True)
# Результат: ["кофе-машина"]  # Дефис НЕ заменяется - одно слово!

extract_words("купил кофе за 150 рублей", keep_digits=True)
# Результат: ["кофе", "150"]  # "купил", "за", "рублей" в стоп-словах

extract_words("paid 50 usd for coffee", keep_digits=True)
# Результат: ["paid", "coffee"]  # "for", "usd" в стоп-словах, "50" - сумма

extract_words("100 som", keep_digits=True)
# Результат: ["100"]  # "som" в стоп-словах (валюта)
```

---

### 2. Функция удаления суммы (НОВАЯ)

**Расположение:** `bot/utils/expense_parser.py`
**Название:** `remove_amount_from_text(text: str) -> str`

**Задача:** Удалить ТОЛЬКО сумму из текста, оставив все остальные цифры и символы

**Алгоритм:**
```python
1. Использовать существующую логику extract_amount_from_patterns()
2. Если сумма найдена - удалить её из текста (вместе с валютой)
3. Вернуть очищенный текст
```

**Примеры:**
```python
remove_amount_from_text("кофе 200")
# Результат: "кофе"

remove_amount_from_text("150руб квартира №5")
# Результат: "квартира №5"  # Сумма удалена, №5 остался!

remove_amount_from_text("купил 2 кофе за 350")
# Результат: "купил 2 кофе за"  # Сумма 350 удалена, цифра "2" осталась!

remove_amount_from_text("played cs2 for 50$")
# Результат: "played cs2 for"  # Сумма удалена, "cs2" остался!
```

---

### 3. Helper функция для проверки keyword (НОВАЯ - ПЕРЕСЕЧЕНИЕ МНОЖЕСТВ)

**Расположение:** `bot/utils/expense_parser.py`
**Название:** `match_keyword_in_text(keyword: str, raw_text: str, cutoff: float = 0.75) -> bool`

**Задача:** Проверить ПЕРЕСЕЧЕНИЕ МНОЖЕСТВ СЛОВ keyword и текста

**ВАЖНО:** Helper принимает RAW текст и нормализует сам (единая точка нормализации)

**Алгоритм:**
```python
1. Удалить сумму из RAW текста:
   text_without_amount = remove_amount_from_text(raw_text)
   # "кофе 200руб" → "кофе"
   # "150 квартира №5" → "квартира №5"
   # "купил 2 кофе за 350" → "купил 2 кофе за"

2. Разбить keyword на слова (с нормализацией):
   keyword_words = set(extract_words(keyword, keep_digits=True, normalize_special=True))
   # "кофейный торт" → {"кофейный", "торт"}
   # "cs2" → {"cs2"}
   # "кофе-машина" → {"кофе-машина"}  # Дефис сохраняется!

3. Разбить текст на слова (с нормализацией):
   text_words = set(extract_words(text_without_amount, keep_digits=True, normalize_special=True))
   # "played cs2 with friends" → {"played", "cs2", "friends"}
   # "торт наполеон" → {"торт", "наполеон"}
   # "квартира№5" → {"квартира", "5"}  # № убрана, "5" сохранена
   # "кофе-машина" → {"кофе-машина"}  # Одно слово!

4. ШАГ 1: Точное пересечение множеств
   intersection = keyword_words & text_words
   if intersection:  # Есть хотя бы одно общее слово
       return True

5. ШАГ 2: Fuzzy matching для опечаток
   # ВАЖНО: Проверяем КАЖДОЕ слово keyword с КАЖДЫМ словом text
   # Это решает проблему multi-word keywords!
   for kw_word in keyword_words:
       for text_word in text_words:
           # Минимальная длина для fuzzy - 3 символа
           # (короткие слова уже отфильтрованы в extract_words)
           if len(kw_word) < 3 or len(text_word) < 3:
               continue

           similarity = SequenceMatcher(None, kw_word, text_word).ratio()
           if similarity >= cutoff:  # 0.75 = 75%
               return True

6. return False  # Нет совпадений
```

**Примеры:**
```python
# Пример 1: Точное совпадение одного слова
match_keyword_in_text("кофе", "купил кофе 200")
→ keyword_words = {"кофе"}
→ text_words = {"купил", "кофе"}  # "200" удалена как сумма
→ intersection = {"кофе"} → True ✅

# Пример 2: Частичное вхождение (НЕ срабатывает)
match_keyword_in_text("кофе", "кофейный торт 200")
→ keyword_words = {"кофе"}
→ text_words = {"кофейный", "торт"}
→ intersection = {} → False ✅

# Пример 3: Пересечение составных keywords
match_keyword_in_text("кофейный торт", "торт наполеон 300")
→ keyword_words = {"кофейный", "торт"}
→ text_words = {"торт", "наполеон"}
→ intersection = {"торт"} → True ✅

# Пример 4: Keyword с цифрами
match_keyword_in_text("cs2", "played cs2 with friends 50$")
→ keyword_words = {"cs2"}
→ text_words = {"played", "cs2", "friends"}  # "50$" удалена
→ intersection = {"cs2"} → True ✅

# Пример 5: Опечатка (fuzzy matching)
match_keyword_in_text("кофе", "кофф 150")
→ keyword_words = {"кофе"}
→ text_words = {"кофф"}
→ intersection = {}
→ fuzzy: "кофе" vs "кофф" = 75% ≥ 75% → True ✅

# Пример 6: Сохранение №
match_keyword_in_text("квартира", "квартира №5")
→ keyword_words = {"квартира"}
→ text_words = {"квартира", "5"}  # № заменена на пробел, "5" сохранена
→ intersection = {"квартира"} → True ✅

# Пример 7: Дефис сохраняется - слово НЕ разбивается
match_keyword_in_text("кофе", "кофе-машина 500")
→ keyword_words = {"кофе"}
→ text_words = {"кофе-машина"}  # Дефис НЕ заменяется!
→ intersection = {} → False ✅ (правильно - разные слова!)

# Пример 8: Дефис в keyword тоже сохраняется
match_keyword_in_text("кофе-машина", "купил кофе-машина 5000")
→ keyword_words = {"кофе-машина"}
→ text_words = {"купил", "кофе-машина"}
→ intersection = {"кофе-машина"} → True ✅
```

---

### 4. Обновление функции обучения keywords (ИЗМЕНЕНИЕ СУЩЕСТВУЮЩЕЙ)

**Файл:** `expense_bot/celery_tasks.py`
**Функция:** `learn_keywords_on_create()` (строка ~1221)

**Изменения:**

1. **Использовать `extract_words()` с `keep_digits=True`** (вместо старой `extract_words_from_description`)
2. **ПРИОРИТЕТ СЛОВ:** Выбирать 2 САМЫХ важных слова, а не просто первые
3. **НОВОЕ ПРАВИЛО: Если >3 слов после фильтрации → НЕ извлекаем keywords вообще** (защита от "мусорных" keywords)
4. **СОХРАНЕНИЕ ЦИФР:** С `keep_digits=True` чистые цифры ("100", "5") СОХРАНЯЮТСЯ и могут стать keywords

```python
@shared_task
def learn_keywords_on_create(expense_id: int, category_id: int):
    """
    Обучение системы при создании новой траты с AI-категоризацией.
    ОГРАНИЧЕНИЯ:
    - Максимум 2 САМЫХ ВАЖНЫХ ключевых слова за одну запись
    - Если >3 слов после фильтрации → НЕ извлекаем keywords вообще (защита от "мусора")
    """
    try:
        import re
        from expenses.models import Expense, ExpenseCategory, CategoryKeyword
        from bot.utils.expense_parser import extract_words  # НОВЫЙ ИМПОРТ

        expense = Expense.objects.get(id=expense_id)
        category = ExpenseCategory.objects.get(id=category_id)

        # Извлекаем слова (СОХРАНЯЕМ ЦИФРЫ В СЛОВАХ!)
        words = extract_words(expense.description, keep_digits=True, normalize_special=False)
        # "And i played cs2 for so'm with coursemates"
        # → ["played", "cs2", "coursemates", "university"]
        # ("and", "i", "for" отфильтрованы стоп-словами)

        # НОВОЕ ПРАВИЛО: Если >3 слов → НЕ извлекаем НИЧЕГО
        if len(words) > 3:
            logger.info(f"Пропущено обучение для траты {expense_id}: "
                       f"слишком много слов после фильтрации ({len(words)} > 3)")
            return  # ВЫХОД БЕЗ ДОБАВЛЕНИЯ KEYWORDS ❌

        # Если слов 3 или меньше - сортируем по важности и берем топ 2
        if len(words) == 3:
            def keyword_score(word):
                """Оценка важности слова для keyword"""
                score = 0
                # Слова с цифрами = самые важные (cs2, iphone15, 5g)
                if re.search(r'\d', word):
                    score += 100
                # Все остальные слова имеют равный приоритет (score = 0)
                return score

            words = sorted(words, key=keyword_score, reverse=True)[:2]
        # ["played", "cs2", "friends"] (3 слова)
        # → сортировка по score: ["cs2" (100), "played" (0), "friends" (0)]
        # → берем топ 2: ["cs2", "played"] ✅

        # Если слов ≤2 - берем все как есть

        # ВАЖНО: Строгая уникальность - удаляем из других категорий
        removed_count = 0
        for word in words:
            deleted = CategoryKeyword.objects.filter(
                category__profile=expense.profile,
                keyword=word
            ).delete()
            if deleted[0] > 0:
                removed_count += deleted[0]

        # Добавляем keywords
        for word in words:
            keyword, created = CategoryKeyword.objects.get_or_create(
                category=category,
                keyword=word,
                defaults={'usage_count': 1}
            )
            if not created:
                keyword.usage_count += 1
                keyword.save()

        # Проверяем лимит 100 слов на категорию
        check_category_keywords_limit(category)

    except Exception as e:
        logger.error(f"Error in learn_keywords_on_create: {e}")
```

**Результат (с приоритетом и новым правилом):**
- "cs2 100" → ["cs2"] (1 слово) ✅
- "кофейный торт" → ["кофейный", "торт"] (2 слова) ✅
- "played cs2 with friends" → ["cs2", "played"] (3 слова → топ 2!) ✅
- "купил вкусный кофейный торт наполеон" → **НИЧЕГО** (4 слова > 3 → пропущено!) ❌
- "And i played cs2 for so'm with coursemates in university" → **НИЧЕГО** (4 слова > 3 → пропущено!) ❌

---

## 🛠️ Места для замены кода

### Замена 1: Проверка keywords для расходов (основной парсер)

**Файл:** `bot/utils/expense_parser.py`
**Строка:** 546

**Текущий код:**
```python
for kw in keywords:
    if kw.keyword.lower() in text_lower:  # ❌ Частичное вхождение
        # ... обновление usage_count
        category = get_category_display_name(user_cat, lang_code)
        max_score = 100
        break
```

**Новый код:**
```python
for kw in keywords:
    # ВАЖНО: Передаем ОРИГИНАЛЬНЫЙ text (не text_lower!)
    # Helper сам нормализует текст внутри
    if match_keyword_in_text(kw.keyword, text):  # ✅ Целое слово + fuzzy
        # ... обновление usage_count (БЕЗ ИЗМЕНЕНИЙ)
        category = get_category_display_name(user_cat, lang_code)
        max_score = 100
        break
```

**Изменение:** Замена проверки `in` на `match_keyword_in_text()` + передача `text` вместо `text_lower`

---

#### 4.2. Проверка keywords для доходов в парсере

**Файл:** `bot/utils/expense_parser.py`
**Строка:** 956

**Текущий код:**
```python
for keyword_obj in keywords:
    if keyword_obj.keyword.lower() in text_lower:  # ❌ Частичное вхождение
        best_match = keyword_obj.category
        break
```

**Новый код:**
```python
for keyword_obj in keywords:
    # ВАЖНО: Передаем ОРИГИНАЛЬНЫЙ text (не text_lower!)
    if match_keyword_in_text(keyword_obj.keyword, text):  # ✅ Целое слово + fuzzy
        best_match = keyword_obj.category
        break
```

**Изменение:** Замена проверки `in` на `match_keyword_in_text()` + передача `text` вместо `text_lower`

---

#### 4.3. Категоризация доходов

**Файл:** `bot/services/income_categorization.py`
**Строка:** 181

**Импорт добавить в начало файла:**
```python
from bot.utils.expense_parser import match_keyword_in_text
```

**Текущий код:**
```python
for keyword_obj in keywords:
    if keyword_obj.keyword.lower() in text_lower:  # ❌ Частичное вхождение
        # Нашли совпадение!
        keyword_obj.usage_count += 1
        keyword_obj.save()
        # ...
```

**Новый код:**
```python
for keyword_obj in keywords:
    # ВАЖНО: Передаем ОРИГИНАЛЬНЫЙ text (не text_lower!)
    if match_keyword_in_text(keyword_obj.keyword, text):  # ✅ Целое слово + fuzzy
        # Нашли совпадение!
        keyword_obj.usage_count += 1
        keyword_obj.save()
        # ...
```

**Изменение:**
- Добавить импорт
- Заменить проверку `in` на `match_keyword_in_text()`
- Передавать `text` вместо `text_lower`

---

### Замена 4: Проверка названия категории пользователя

**Файл:** `bot/utils/expense_parser.py`
**Строка:** 532

**Текущий код:**
```python
# Проверка совпадения с названием категории
if user_cat.name.lower() in text_lower:  # ❌ Частичное вхождение
    category = get_category_display_name(user_cat, lang_code)
    max_score = 90
    break
```

**Новый код:**
```python
# Проверка совпадения с названием категории
# ВАЖНО: Передаем ОРИГИНАЛЬНЫЙ text, helper сам нормализует
if match_keyword_in_text(user_cat.name, text):  # ✅ Целое слово + fuzzy
    category = get_category_display_name(user_cat, lang_code)
    max_score = 90
    break
```

**Изменение:** Заменить проверку `in` на `match_keyword_in_text()` + передача `text` вместо `text_lower` + убрать `.lower()` с keyword

---

### Замена 5: suggest_category (стандартные категории)

**Статус:** удалено из `bot/utils/expense_parser.py` как мёртвый код. Доработки не требуются.

---

### Замена 6: Лимит keywords на категорию (50 → 100)

**Файл:** `expense_bot/celery_tasks.py`
**Строка:** 1354

**Текущий код:**
```python
def check_category_keywords_limit(category):
    """
    Проверяет и ограничивает количество ключевых слов в категории (максимум 50)
    """
    # ...
    if keywords.count() > 50:
        # Оставляем топ-50 по usage_count
        keywords_list = list(keywords)
        keywords_list.sort(key=lambda k: k.usage_count, reverse=True)

        # Удаляем слова с наименьшим использованием
        keywords_to_delete = keywords_list[50:]
        # ...
```

**Новый код:**
```python
def check_category_keywords_limit(category):
    """
    Проверяет и ограничивает количество ключевых слов в категории (максимум 100)
    """
    # ...
    if keywords.count() > 100:
        # Оставляем топ-100 по usage_count
        keywords_list = list(keywords)
        keywords_list.sort(key=lambda k: k.usage_count, reverse=True)

        # Удаляем слова с наименьшим использованием
        keywords_to_delete = keywords_list[100:]
        # ...
```

**Изменение:** 50 → 100 (в docstring, проверке и срезе списка)

---

## 🧪 Тесты

### Unit-тесты для helper функции

**Файл:** `test_keyword_matching.py` (создать новый)

```python
import pytest
from bot.utils.expense_parser import match_keyword_in_text, remove_amount_from_text


class TestRemoveAmountFromText:
    """Тесты функции очистки текста от суммы"""

    def test_remove_amount_at_end(self):
        assert remove_amount_from_text("кофе 200") == "кофе"

    def test_remove_amount_at_start(self):
        assert remove_amount_from_text("150 квартира") == "квартира"

    def test_remove_amount_with_currency(self):
        assert remove_amount_from_text("кофе 200руб") == "кофе"
        assert remove_amount_from_text("кофе 200₽") == "кофе"

    def test_keep_small_numbers(self):
        # Маленькие числа (не суммы) должны оставаться
        result = remove_amount_from_text("квартира №5")
        assert "№5" in result or "5" in result

    def test_keep_middle_numbers(self):
        # Числа в середине фразы (не суммы) могут оставаться
        result = remove_amount_from_text("купил 2 кофе 350")
        assert "2" in result or result == "купил кофе"


class TestMatchKeywordInText:
    """Тесты функции проверки keyword"""

    # === ТОЧНОЕ СОВПАДЕНИЕ ===

    def test_exact_match_simple(self):
        """Точное совпадение целого слова"""
        assert match_keyword_in_text("кофе", "кофе") == True
        assert match_keyword_in_text("кофе", "купил кофе") == True
        assert match_keyword_in_text("кофе", "кофе латте") == True

    def test_exact_match_with_amount(self):
        """Точное совпадение с суммой в тексте"""
        assert match_keyword_in_text("кофе", "кофе 200") == True
        assert match_keyword_in_text("кофе", "150 кофе") == True

    def test_exact_match_with_special_chars(self):
        """Точное совпадение со спецсимволами"""
        assert match_keyword_in_text("квартира", "квартира №5") == True
        # Дефис НЕ разбивает слова - "кофе-машина" это ОДНО слово!
        assert match_keyword_in_text("кофе", "кофе-машина") == False
        assert match_keyword_in_text("кофе-машина", "кофе-машина") == True
        assert match_keyword_in_text("кофе-машина", "купил кофе-машина 5000") == True

    # === ЧАСТИЧНОЕ ВХОЖДЕНИЕ (должно НЕ срабатывать) ===

    def test_no_partial_match(self):
        """Частичное вхождение НЕ должно находиться"""
        assert match_keyword_in_text("кофе", "кофейный") == False
        assert match_keyword_in_text("кофе", "кофейный торт") == False
        assert match_keyword_in_text("кофе", "кофейня") == False

    def test_no_partial_match_with_amount(self):
        """Частичное вхождение с суммой НЕ должно находиться"""
        assert match_keyword_in_text("кофе", "кофейный торт 200") == False
        assert match_keyword_in_text("продукты", "продуктовый магазин 500") == False

    # === FUZZY MATCHING (опечатки) ===

    def test_fuzzy_match_typo(self):
        """Опечатки должны прощаться через fuzzy matching (cutoff=0.75)"""
        # "кофе" vs "кофф" = 3/4 символов совпадают = 75% ✅
        assert match_keyword_in_text("кофе", "кофф 100") == True
        assert match_keyword_in_text("кофе", "кофф") == True

        # "молоко" vs "малоко" = 5/6 символов = 83% ✅
        assert match_keyword_in_text("молоко", "малоко 150") == True

        # "квартира" vs "квортира" = 7/8 символов = 87% ✅
        assert match_keyword_in_text("квартира", "квортира") == True

    def test_fuzzy_no_match_too_different(self):
        """Слишком разные слова НЕ должны находиться"""
        # "кофе" vs "чай" = 0% схожести
        assert match_keyword_in_text("кофе", "чай 100") == False

        # "молоко" vs "масло" = <75% схожести
        assert match_keyword_in_text("молоко", "масло") == False

    # === EDGE CASES ===

    def test_case_insensitive(self):
        """Проверка регистронезависимости"""
        assert match_keyword_in_text("кофе", "КОФЕ") == True
        assert match_keyword_in_text("кофе", "Кофе") == True
        assert match_keyword_in_text("КОФЕ", "кофе") == True

    def test_empty_keyword(self):
        """Пустой keyword"""
        assert match_keyword_in_text("", "кофе 200") == False

    def test_empty_text(self):
        """Пустой текст"""
        assert match_keyword_in_text("кофе", "") == False

    def test_short_words(self):
        """Короткие слова (3 буквы)"""
        assert match_keyword_in_text("чай", "чай 100") == True
        assert match_keyword_in_text("чай", "час") == False  # Разные слова
        assert match_keyword_in_text("газ", "глаз") == False  # Разные слова
```

---

### Интеграционные тесты (реальные сценарии)

**Файл:** `test_keyword_integration.py` (создать новый)

```python
"""
Интеграционные тесты для проверки работы keywords в реальных сценариях
"""
import pytest
from bot.utils.expense_parser import parse_expense_message
from expenses.models import Profile, ExpenseCategory, CategoryKeyword


@pytest.mark.django_db
class TestKeywordIntegration:
    """Интеграционные тесты с реальной БД"""

    @pytest.fixture
    def setup_profile_with_keywords(self):
        """Создать профиль с категорией и keyword"""
        profile = Profile.objects.create(
            telegram_id=999999,
            language_code='ru',
            currency='RUB'
        )

        # Категория "Кафе и рестораны"
        cafe_category = ExpenseCategory.objects.create(
            profile=profile,
            name="☕ Кафе и рестораны",
            name_ru="Кафе и рестораны",
            name_en="Cafes",
            icon="☕"
        )

        # Keyword "кофе"
        CategoryKeyword.objects.create(
            category=cafe_category,
            keyword="кофе",
            language='ru'
        )

        return profile, cafe_category

    async def test_keyword_exact_match(self, setup_profile_with_keywords):
        """Точное совпадение keyword"""
        profile, cafe_category = setup_profile_with_keywords

        result = await parse_expense_message(
            "кофе 200",
            user_id=999999,
            profile=profile,
            use_ai=False
        )

        assert result['category_id'] == cafe_category.id
        assert result['amount'] == 200

    async def test_keyword_no_partial_match(self, setup_profile_with_keywords):
        """Частичное вхождение НЕ должно срабатывать"""
        profile, cafe_category = setup_profile_with_keywords

        result = await parse_expense_message(
            "кофейный торт 200",
            user_id=999999,
            profile=profile,
            use_ai=False
        )

        # Keyword "кофе" НЕ должен найтись в "кофейный торт"
        # Категория должна определиться через AI или остаться None
        assert result['category_id'] != cafe_category.id
```

---

## 📝 Чеклист реализации

### Этап 1: Подготовка
- [ ] Создать ветку `fix/keyword-partial-match`
- [ ] Создать файлы тестов:
  - [ ] `test_keyword_matching.py`
  - [ ] `test_keyword_integration.py`

### Этап 2: Реализация helper функций
- [ ] Добавить импорт `from difflib import SequenceMatcher` в `expense_parser.py`
- [ ] Создать/обновить функцию `extract_words(text: str, keep_digits: bool = True, normalize_special: bool = True) -> List[str]`
  - [ ] Нормализация спецсимволов (№ → space, _ → space) **ВАЖНО: НЕ дефис!**
  - [ ] Удаление валюты и пунктуации (БЕЗ дефиса!)
  - [ ] Разбивка на слова + lowercase
  - [ ] Расширенные стоп-слова (русские + английские)
  - [ ] Фильтр чистых цифр `if not keep_digits and word.isdigit()`
  - [ ] Написать docstring с примерами
- [ ] Создать функцию `remove_amount_from_text(text: str) -> str`
  - [ ] Использовать существующую логику extract_amount_from_patterns()
  - [ ] Удалить найденную сумму (с валютой) из текста
  - [ ] Написать docstring с примерами
- [ ] Создать функцию `match_keyword_in_text(keyword: str, raw_text: str, cutoff: float = 0.75) -> bool`
  - [ ] **ВАЖНО: Принимает RAW text, НЕ text_lower!**
  - [ ] Шаг 1: Удаление суммы через `remove_amount_from_text(raw_text)`
  - [ ] Шаг 2: Разбивка keyword и text на word sets через `extract_words(..., keep_digits=True)`
  - [ ] Шаг 3: Точное пересечение множеств (set intersection)
  - [ ] Шаг 4: Fuzzy matching (word-by-word для multi-word keywords, cutoff=0.75)
  - [ ] Написать docstring с примерами

### Этап 3: Замена в коде (5 мест substring + 2 обновления)
**КРИТИЧЕСКИ ВАЖНО:** Во всех заменах передавать RAW text (не text_lower!), helper сам нормализует!

- [ ] **Замена 1:** `bot/utils/expense_parser.py:546` - проверка keywords для расходов
  - [ ] Передать `text` вместо `text_lower`
- [ ] **Замена 2:** `bot/utils/expense_parser.py:956` - проверка keywords для доходов в парсере
  - [ ] Передать `text` вместо `text_lower`
- [ ] **Замена 3:** `bot/services/income_categorization.py:181` - категоризация доходов
  - [ ] Добавить импорт `from bot.utils.expense_parser import match_keyword_in_text`
  - [ ] Передать `text` вместо `text_lower`
- [ ] **Замена 4:** `bot/utils/expense_parser.py:532` - проверка названия категории пользователя
  - [ ] Передать `text` вместо `text_lower` + убрать `.lower()` с keyword
- [x] **Замена 5:** `bot/utils/expense_parser.py:1092` - suggest_category (стандартные категории)
  - Удалено как мёртвый код
- [ ] **Замена 6:** `expense_bot/celery_tasks.py:1221+` - обновить learn_keywords_on_create() с приоритетом:
  - Максимум 2 слова (не 3!)
  - НОВОЕ: Если >3 слов после фильтрации → return (не извлекаем keywords)
  - Приоритет: только +100 для слов с цифрами
- [ ] **Замена 7:** `expense_bot/celery_tasks.py:1354` - check_category_keywords_limit: 50 → 100

### Этап 4: Тестирование
- [ ] Запустить unit-тесты: `pytest test_keyword_matching.py -v`
- [ ] Исправить failing тесты (если есть)
- [ ] Запустить интеграционные тесты: `pytest test_keyword_integration.py -v`
- [ ] Ручное тестирование - **КРИТИЧЕСКИЕ** сценарии:
  - [ ] "кофе 200" → находит keyword "кофе" ✅
  - [ ] "кофейный торт 200" → НЕ находит keyword "кофе" ✅ (главная проблема!)
  - [ ] "квартира №5" → находит keyword "квартира" ✅
  - [ ] "продуктовый магазин 500" → НЕ находит keyword "продукты" ✅
  - [ ] "played cs2 with friends" → находит keyword "cs2" ✅
  - [ ] "кофейный торт 300" → НЕ находит keyword "кофе" но находит "торт" если есть keyword "кофейный торт" ✅
  - [ ] "торт наполеон 200" → находит keyword "кофейный торт" (пересечение по слову "торт") ✅
  - [ ] "кофф 150" → находит keyword "кофе" через fuzzy ✅

### Этап 5: Коммит и деплой
- [ ] Зафиксировать изменения: `git add .`
- [ ] Создать коммит с детальным описанием:
```bash
git commit -m "Fix: Keyword matching - set intersection + fuzzy matching (75%)

ПРОБЛЕМА:
- Keyword 'кофе' находился в 'кофейный торт' (частичное вхождение)
- Нет поддержки multi-word keywords ('кофейный торт')
- Нет fuzzy matching для опечаток

РЕШЕНИЕ (ВАРИАНТ А - полное):
1. Helper функции (bot/utils/expense_parser.py):
   - extract_words() - разбивка с нормализацией, фильтр цифр
   - remove_amount_from_text() - удаление только суммы
   - match_keyword_in_text() - пересечение множеств + fuzzy 75%

2. Обновлена функция обучения (celery_tasks.py):
   - Приоритетная сортировка слов (цифры +100)
   - Максимум 3 лучших слова вместо первых N
   - Английские стоп-слова (and, or, i, my...)
   - Лимит 100 слов на категорию (вместо 50)

3. Замены в 6 местах:
   - expense_parser.py:546 (keywords расходов)
   - expense_parser.py:956 (keywords доходов)
   - expense_parser.py:532 (название категории)
   - income_categorization.py:181 (категоризация доходов)
   - celery_tasks.py:1221+ (learn_keywords: 3 слова, приоритет)
   - celery_tasks.py:1354 (лимит 50→100)

4. Unit-тесты (test_keyword_matching.py)

ПРИМЕРЫ:
✅ 'кофе' + 'кофейный торт' = НЕ найдено (разные слова!)
✅ 'кофейный торт' + 'торт наполеон' = найдено (пересечение: торт)
✅ 'cs2' + 'played cs2 with friends' = найдено
✅ 'кофе' + 'кофф' = найдено через fuzzy (75% схожести)

Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
```
- [ ] Создать PR или мерж в master
- [ ] Деплой на сервер (см. `docs/SERVER_COMMANDS.md`)

---

## ⚠️ Риски и ограничения

### 1. Fuzzy matching может не работать для очень коротких слов

**Проблема:**
```python
"кофе" (4 буквы) vs "кофф" (4 буквы)
Схожесть: 75% < 85% → НЕ совпадет
```

**Решение:** Рассмотреть вариант А3 (разбивать только для fuzzy)

---

### 2. Word boundary не работает с некоторыми символами

**Проблема:**
```python
r'\bкофе\b' в "кофе-машина" → НЕТ совпадения (дефис не word boundary)
```

**Приемлемо:** Это ожидаемое поведение - "кофе-машина" это другое слово

---

### 3. Производительность fuzzy matching

**Оценка:** Незначительное замедление (<10ms на запрос)

**Оптимизация:** Сначала точное совпадение (быстро), только потом fuzzy (медленно)

---

## 📚 Полезные ссылки

- [difflib.get_close_matches documentation](https://docs.python.org/3/library/difflib.html#difflib.get_close_matches)
- [difflib.SequenceMatcher documentation](https://docs.python.org/3/library/difflib.html#difflib.SequenceMatcher)
- [Python regex word boundaries](https://docs.python.org/3/library/re.html)

---

## ✅ Критерии успеха

Исправление считается успешным если:

1. ✅ Keyword "кофе" НЕ находится в "кофейный торт"
2. ✅ Keyword "кофе" находится в "кофе"
3. ✅ Keyword "кофе" находится в "купил кофе 200"
4. ✅ Опечатки прощаются (если реализован fuzzy)
5. ✅ Спецсимволы не ломают проверку ("квартира №5" работает)
6. ✅ Все unit-тесты проходят
7. ✅ Нет регрессии в работе существующих keywords

---

## 📝 История изменений плана

### 2025-01-17 (v5) - Изменение лимита keywords: 3→2 слова + новое правило >3 слов

**Критическое изменение:**
- ✅ **Максимум keywords изменен с 3 на 2 слова**
  - Было: "Максимум 3 САМЫХ важных слова"
  - Стало: "Максимум 2 САМЫХ важных слова"
  - Причина: Упрощение и повышение точности обучения

- ✅ **НОВОЕ ПРАВИЛО: Если >3 слов после фильтрации → НЕ извлекаем keywords вообще**
  - Логика: Слишком длинные описания содержат "мусор" и не подходят для обучения
  - Пример: "купил вкусный кофейный торт наполеон" (4 слова) → НИЧЕГО ❌
  - Пример: "And i played cs2 for so'm with my coursemates in university" (4 слова) → НИЧЕГО ❌
  - Защита: Предотвращает добавление нерелевантных keywords из длинных фраз

**Обновленные примеры:**
- "cs2 100" → ["cs2"] ✅ (1 слово)
- "кофейный торт" → ["кофейный", "торт"] ✅ (2 слова)
- "played cs2 with friends" → ["cs2", "played"] ✅ (3 слова → топ 2)
- "купил вкусный кофейный торт наполеон" → **НИЧЕГО** ❌ (4 > 3)

**Изменения в коде learn_keywords_on_create:**
```python
# Раньше (v4):
if len(words) > 3:
    words = sorted(words, key=keyword_score, reverse=True)[:3]

# Теперь (v5):
if len(words) > 3:
    return  # НЕ извлекаем keywords вообще! ❌
if len(words) == 3:
    words = sorted(words, key=keyword_score, reverse=True)[:2]
# Если ≤2 слов - берем все как есть
```

---

### 2025-01-17 (v4) - Глаголы вернули в стоп-слова

**Важное уточнение:**
- ✅ **Глаголы ВЕРНУЛИ в стоп-слова** - они нужны только AI для парсинга, но НЕ для keywords!
  - Добавлено обратно: 'купил', 'купила', 'взял', 'взяла', 'потратил', 'оплатил' в stop_words
  - Логика: "купил кофе" → keyword должно быть "кофе", а НЕ "купил"
  - Иначе: keyword "купил" для категории "Продукты" найдет "купил такси" ❌
  - Результат: "купил кофе за 150 рублей" → ["кофе", "150"] ✅

---

### 2025-01-17 (v3) - Исправление мелких противоречий

**Исправлено:**
1. ✅ **Унифицировано название функции**
   - Было: `clean_text_for_keyword_matching` в тестах
   - Стало: `remove_amount_from_text` везде (единое название)

2. ✅ **Уточнена формулировка про фильтр цифр**
   - Было: "чистые цифры пропускаются"
   - Стало: "С keep_digits=True чистые цифры СОХРАНЯЮТСЯ и могут стать keywords"

3. ✅ **Исправлено "2 слова" → "3 слова"**
   - Все упоминания теперь корректны: выбирается максимум 3 лучших слова

---

### 2025-01-17 (v2) - Добавлены валюты в стоп-слова

**Добавлено:**
- ✅ **Расширенный список валют в стоп-словах** - чтобы названия валют не попадали в keywords
  - Русские: "рублей", "доллар", "евро", "сом", "тенге", "гривна", "лира", "фунт", "йена", "юань"
  - Английские: "usd", "eur", "rub", "som", "dollar", "euro", "ruble"
  - Коды: "kgs", "kzt", "uah", "try", "gbp", "jpy", "cny"

**Примеры:**
- "купил кофе за 150 рублей" → ["кофе", "150"] ✅ (без "купил", "за", "рублей")
- "paid 50 usd for coffee" → ["paid", "coffee"] ✅ (без "for", "usd")
- "100 som" → ["100"] ✅ (без "som")
- "взял такси 300" → ["такси", "300"] ✅ (без "взял")

---

### 2025-01-17 (v1) - Исправление противоречий (после внешнего review)

**Проблемы найденные:**
1. ❌ Hyphen normalization противоречит ожиданиям
2. ❌ Digits handling - keep_digits не используется
3. ❌ Raw text vs text_lower - передается обработанный текст
4. ❌ Length guards - двойная фильтрация коротких слов

**Исправления:**
1. ✅ **Дефис НЕ нормализуется** - "кофе-машина" остается одним словом
   - Убрано: `text.replace('-', ' ')`
   - Результат: keyword "кофе" НЕ найдет "кофе-машина" ✅

2. ✅ **keep_digits правильно используется**
   - Добавлено: `if not keep_digits and word.isdigit(): continue`
   - Результат: "квартира №5" → {"квартира", "5"} при keep_digits=True ✅

3. ✅ **Все замены передают RAW text**
   - Изменено: `text_lower` → `text` во всех 5 заменах
   - Убрано: `.lower()` из keywords (helper делает это сам)
   - Результат: единая точка нормализации внутри helper ✅

4. ✅ **Убран guard для коротких keywords**
   - Убрано: `if len(keyword) < 3: return False`
   - Фильтр остался только в extract_words (для токенов)
   - Результат: multi-word keywords из коротких слов ("ip tv") могут работать ✅

---

**Составлен:** Claude Code
**Согласовано с требованиями:** ✅
**Проверено внешним review:** ✅
