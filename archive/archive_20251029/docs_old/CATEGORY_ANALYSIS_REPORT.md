# Анализ системы категорий в ExpenseBot

## Обзор проблемы

В системе обнаружены категории на разных языках у одних и тех же пользователей. Этот отчет анализирует причины возникновения такой ситуации и механизмы работы с категориями.

## 1. Как хранятся категории в моделях Django

### Модель ExpenseCategory (`expenses/models.py`)

```python
class ExpenseCategory(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)  # Название с эмодзи
    icon = models.CharField(max_length=10, default='💰')  # Устаревшее поле
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

**Ключевые особенности:**
- Категории персональные для каждого пользователя (`profile`)
- Название хранится в поле `name` вместе с эмодзи (например: "🛒 Продукты")
- Поле `icon` больше не используется, но остается в модели
- Связь `unique_together = ['profile', 'name']` предотвращает дублирование

## 2. Создание категорий при регистрации пользователя

### В `bot/services/user.py`:

```python
def create_default_categories(profile_id: int):
    profile = Profile.objects.get(telegram_id=profile_id)
    lang = profile.language_code or 'ru'
    
    if lang == 'en':
        default_categories = [
            ('Supermarkets', '🛒'),
            ('Other Products', '🫑'),
            # ... другие английские категории
        ]
    else:
        default_categories = [
            ('Супермаркеты', '🛒'),
            ('Другие продукты', '🫑'),
            # ... другие русские категории
        ]
    
    for name, icon in default_categories:
        category_with_icon = f"{icon} {name}"  # Эмодзи + название
        ExpenseCategory.objects.get_or_create(
            profile=profile,
            name=category_with_icon,
            defaults={'icon': ''}  # icon больше не используется
        )
```

**Проблема:** Список категорий для английского языка в `user.py` не полностью соответствует переводам в `language.py`.

## 3. Механизм переводов категорий

### В `bot/utils/language.py`:

```python
def translate_category_name(category_name: str, to_lang: str = 'en') -> str:
    translations = {
        'Продукты': 'Products',
        'Кафе и рестораны': 'Restaurants and Cafes',
        # ... другие переводы
        # Обратные переводы:
        'Products': 'Продукты',
        'Restaurants and Cafes': 'Кафе и рестораны',
    }
    
    # Извлекает эмодзи и текст, переводит только текст
    emoji_pattern = re.compile(r'^[эмодзи]+')
    match = emoji_pattern.match(category_name)
    
    if match:
        emoji = match.group()
        text = category_name[len(emoji):].strip()
    
    if text in translations:
        translated = translations[text]
        return f"{emoji} {translated}" if emoji else translated
    
    return category_name  # Если перевода нет, возвращает как есть
```

### В `bot/services/category.py`:

```python
async def update_default_categories_language(user_id: int, new_lang: str) -> bool:
    # Переводит только стандартные категории из DEFAULT_CATEGORIES
    # Пользовательские категории остаются без изменений
```

## 4. Почему у пользователя могут быть категории на разных языках

### Сценарий 1: Смена языка после регистрации

1. Пользователь регистрируется с `language_code='ru'`
2. Создаются русские категории: "🛒 Продукты", "🍽️ Кафе и рестораны"
3. Пользователь меняет язык на английский
4. Функция `update_default_categories_language()` переводит только стандартные категории
5. Если пользователь создал свои категории, они остаются на русском

### Сценарий 2: Несоответствие в списках категорий

**DEFAULT_CATEGORIES (русские):**
```python
[('Продукты', '🛒'), ('Кафе и рестораны', '🍽️'), ...]
```

**ENGLISH_CATEGORIES в user.py:**
```python
[('Supermarkets', '🛒'), ('Other Products', '🫑'), ('Restaurants and Cafes', '🍽️'), ...]
```

**TRANSLATIONS в language.py:**
```python
{'Продукты': 'Products', 'Кафе и рестораны': 'Restaurants and Cafes', ...}
```

**Проблемы:**
- "Продукты" переводится как "Products", но в user.py создается "Supermarkets" 
- В user.py есть "Other Products", которого нет в переводах
- Некоторые категории из user.py отсутствуют в словаре переводов

### Сценарий 3: AI категоризация

AI может предлагать категории на разных языках в зависимости от:
- Языка описания расходов пользователя
- Доступных категорий пользователя
- Контекста и недавних категорий

```python
def get_categorization_prompt(self, text: str, categories: List[str]):
    # AI получает список всех категорий пользователя (на разных языках)
    # Может выбрать любую из них для категоризации
```

### Сценарий 4: Ручное создание категорий

Пользователи могут создавать свои категории на любом языке через интерфейс бота:
- Русскоязычный пользователь может создать категорию на английском
- Англоязычный пользователь может создать категорию на русском

## 5. Где еще в коде используются категории

### 5.1. Поиск и сопоставление категорий (`bot/services/category.py`)

```python
def get_or_create_category(user_id: int, category_name: str) -> ExpenseCategory:
    # Использует словарь сопоставления:
    category_mapping = {
        'продукты': ['продукты', 'еда', 'супермаркет'],
        'кафе': ['кафе', 'ресторан', 'рестораны'],
        # ... другие сопоставления
    }
    
    # Ищет категорию по точному совпадению, частичному совпадению
    # и через словарь сопоставления
```

### 5.2. AI категоризация (`bot/services/ai_categorization.py`)

```python
async def categorize(self, text: str, user_id: int, profile: Optional[Profile] = None):
    # Получает все категории пользователя
    categories = list(ExpenseCategory.objects.filter(profile=profile).values_list('name', flat=True))
    
    # Передает их AI для выбора подходящей категории
    # AI может выбрать любую категорию из списка
```

### 5.3. Ключевые слова категорий (`expenses/models.py`)

```python
class CategoryKeyword(models.Model):
    category = models.ForeignKey(ExpenseCategory, related_name='keywords')
    keyword = models.CharField(max_length=100)
    usage_count = models.IntegerField(default=0)
    normalized_weight = models.FloatField(default=1.0)
```

Ключевые слова помогают автоматически определять категории, но они тоже могут быть на разных языках.

### 5.4. Категоризатор по ключевым словам (`bot/utils/expense_categorizer.py`)

```python
CATEGORY_KEYWORDS_EXACT = {
    'продукты': {
        'products': ['хлеб', 'молоко', ...],
        'stores': ['магазин', 'пятерочка', ...],
    },
    'кафе': {
        'drinks': ['кофе', 'чай', ...],
        'places': ['кафе', 'ресторан', ...],
    }
}

CATEGORY_KEYWORDS_EN = {
    'groceries': {
        'products': ['bread', 'milk', ...],
        'stores': ['grocery', 'supermarket', ...],
    }
}
```

## 6. Выводы и рекомендации

### Основные причины смешанных языков:

1. **Несоответствие в данных:** Списки категорий в разных файлах не синхронизированы
2. **Неполный перевод:** При смене языка переводятся не все категории
3. **AI поведение:** AI может выбирать категории на любом доступном языке
4. **Пользовательский ввод:** Пользователи могут создавать категории на любом языке

### Рекомендации для решения:

1. **Синхронизация данных:** Привести в соответствие все списки категорий
2. **Улучшение переводов:** Обеспечить полный перевод всех категорий при смене языка
3. **Фильтрация AI:** Настроить AI на выбор категорий только на текущем языке пользователя
4. **Валидация ввода:** Добавить проверки языка при создании новых категорий

### Влияние на пользователей:

- **Минимальное:** Функциональность не нарушена, категории работают корректно
- **Косметическое:** Смешанные языки могут выглядеть непрофессионально
- **UX:** Может затруднять поиск и управление категориями для пользователей