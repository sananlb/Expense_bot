"""
⚠️ WARNING - FOR MIGRATION SCRIPTS ONLY ⚠️

This file is ONLY used by migration/fix scripts (fix_*.py, migrate_*.py, comprehensive_category_migration.py)
and should NOT be imported in production code.

For production category creation, use:
- expenses/models.py::DEFAULT_CATEGORIES (16 unified categories)
- bot/services/category.py::create_default_categories_sync()

This file was updated to match the new 16-category structure but is kept only
for backward compatibility with existing migration scripts.

DO NOT use UNIFIED_CATEGORIES for creating new categories in production!

Единые категории по умолчанию для мультиязычной поддержки
"""

# Унифицированные категории с переводами и ключевыми словами
UNIFIED_CATEGORIES = [
    {
        'id': 'products',
        'icon': '🛒',
        'name_ru': 'Продукты',
        'name_en': 'Groceries',
        'keywords_ru': ['магазин', 'супермаркет', 'продукты', 'еда', 'пятерочка', 'перекресток', 'ашан', 'лента', 'магнит', 'дикси', 'вкусвилл'],
        'keywords_en': ['store', 'supermarket', 'groceries', 'food', 'market', 'grocery']
    },
    {
        'id': 'restaurants',
        'icon': '🍽️',
        'name_ru': 'Кафе и рестораны',
        'name_en': 'Cafes and Restaurants',
        'keywords_ru': ['ресторан', 'кафе', 'бар', 'пиццерия', 'суши', 'бургер', 'кофейня', 'столовая', 'фастфуд', 'макдоналдс', 'kfc'],
        'keywords_en': ['restaurant', 'cafe', 'bar', 'pizza', 'sushi', 'burger', 'coffee', 'diner', 'fastfood', 'mcdonalds']
    },
    {
        'id': 'transport',
        'icon': '🚕',
        'name_ru': 'Транспорт',
        'name_en': 'Transport',
        'keywords_ru': ['такси', 'метро', 'автобус', 'трамвай', 'троллейбус', 'электричка', 'поезд', 'яндекс', 'убер', 'транспорт'],
        'keywords_en': ['taxi', 'metro', 'bus', 'tram', 'train', 'uber', 'transport', 'subway']
    },
    {
        'id': 'car',
        'icon': '🚗',
        'name_ru': 'Автомобиль',
        'name_en': 'Car',
        'keywords_ru': ['автомобиль', 'машина', 'авто', 'сто', 'ремонт', 'запчасти', 'мойка', 'автомойка', 'страховка', 'осаго', 'каско', 'бензин', 'топливо', 'заправка', 'азс', 'дизель'],
        'keywords_en': ['car', 'auto', 'vehicle', 'repair', 'parts', 'wash', 'insurance', 'service', 'gas', 'fuel', 'petrol', 'gasoline', 'diesel', 'station']
    },
    {
        'id': 'housing',
        'icon': '🏠',
        'name_ru': 'Жилье',
        'name_en': 'Housing',
        'keywords_ru': ['аренда', 'квартира', 'жилье', 'ипотека', 'коммуналка', 'жкх', 'квартплата', 'электричество', 'вода', 'газ'],
        'keywords_en': ['rent', 'apartment', 'housing', 'mortgage', 'utilities', 'electricity', 'water', 'gas']
    },
    {
        'id': 'pharmacy',
        'icon': '💊',
        'name_ru': 'Аптеки',
        'name_en': 'Pharmacies',
        'keywords_ru': ['аптека', 'лекарства', 'таблетки', 'медикаменты', 'витамины', 'бады', 'ригла', 'горздрав'],
        'keywords_en': ['pharmacy', 'medicine', 'drugs', 'pills', 'vitamins', 'medications']
    },
    {
        'id': 'medicine',
        'icon': '🏥',
        'name_ru': 'Медицина',
        'name_en': 'Medicine',
        'keywords_ru': ['врач', 'доктор', 'клиника', 'больница', 'поликлиника', 'анализы', 'узи', 'мрт', 'стоматология', 'зубной', 'психолог'],
        'keywords_en': ['doctor', 'clinic', 'hospital', 'medical', 'dentist', 'analysis', 'mri', 'health']
    },
    {
        'id': 'beauty',
        'icon': '💄',
        'name_ru': 'Красота',
        'name_en': 'Beauty',
        'keywords_ru': ['салон', 'парикмахер', 'маникюр', 'педикюр', 'косметика', 'спа', 'массаж', 'солярий', 'барбер'],
        'keywords_en': ['salon', 'hairdresser', 'manicure', 'pedicure', 'cosmetics', 'spa', 'massage', 'barber']
    },
    {
        'id': 'sport',
        'icon': '🏃',
        'name_ru': 'Спорт и фитнес',
        'name_en': 'Sports and Fitness',
        'keywords_ru': ['спорт', 'фитнес', 'тренажерный', 'бассейн', 'йога', 'пилатес', 'абонемент', 'тренировка', 'зал'],
        'keywords_en': ['sport', 'fitness', 'gym', 'pool', 'yoga', 'pilates', 'training', 'workout']
    },
    {
        'id': 'clothes',
        'icon': '👔',
        'name_ru': 'Одежда и обувь',
        'name_en': 'Clothes and Shoes',
        'keywords_ru': ['одежда', 'обувь', 'джинсы', 'платье', 'костюм', 'кроссовки', 'зара', 'юникло', 'ботинки'],
        'keywords_en': ['clothes', 'shoes', 'jeans', 'dress', 'suit', 'sneakers', 'zara', 'uniqlo', 'boots']
    },
    {
        'id': 'entertainment',
        'icon': '🎭',
        'name_ru': 'Развлечения',
        'name_en': 'Entertainment',
        'keywords_ru': ['кино', 'театр', 'концерт', 'клуб', 'бар', 'развлечения', 'билеты', 'музей', 'выставка', 'парк'],
        'keywords_en': ['cinema', 'theater', 'concert', 'club', 'bar', 'entertainment', 'tickets', 'museum', 'exhibition']
    },
    {
        'id': 'education',
        'icon': '📚',
        'name_ru': 'Образование',
        'name_en': 'Education',
        'keywords_ru': ['курсы', 'обучение', 'школа', 'университет', 'книги', 'учебники', 'репетитор', 'экзамен', 'семинар'],
        'keywords_en': ['courses', 'education', 'school', 'university', 'books', 'textbooks', 'tutor', 'exam', 'seminar']
    },
    {
        'id': 'gifts',
        'icon': '🎁',
        'name_ru': 'Подарки',
        'name_en': 'Gifts',
        'keywords_ru': ['подарок', 'подарки', 'сувенир', 'цветы', 'букет', 'открытка', 'праздник', 'день рождения'],
        'keywords_en': ['gift', 'gifts', 'present', 'souvenir', 'flowers', 'bouquet', 'card', 'birthday']
    },
    {
        'id': 'travel',
        'icon': '✈️',
        'name_ru': 'Путешествия',
        'name_en': 'Travel',
        'keywords_ru': ['путешествие', 'отпуск', 'билеты', 'самолет', 'поезд', 'отель', 'гостиница', 'туризм', 'виза'],
        'keywords_en': ['travel', 'vacation', 'tickets', 'flight', 'train', 'hotel', 'tourism', 'visa', 'trip']
    },
    {
        'id': 'subscriptions',
        'icon': '📱',
        'name_ru': 'Коммуналка и подписки',
        'name_en': 'Utilities and Subscriptions',
        'keywords_ru': ['подписка', 'интернет', 'телефон', 'связь', 'коммуналка', 'жкх', 'электричество', 'вода', 'газ', 'netflix', 'spotify', 'яндекс', 'облако', 'хостинг'],
        'keywords_en': ['subscription', 'internet', 'phone', 'mobile', 'utilities', 'electricity', 'water', 'gas', 'netflix', 'spotify', 'cloud', 'hosting']
    },
    {
        'id': 'other',
        'icon': '💰',
        'name_ru': 'Прочие расходы',
        'name_en': 'Other Expenses',
        'keywords_ru': ['прочее', 'другое', 'разное', 'остальное'],
        'keywords_en': ['other', 'misc', 'various', 'miscellaneous']
    }
]

def get_category_by_id(category_id: str) -> dict:
    """Получить категорию по ID"""
    for cat in UNIFIED_CATEGORIES:
        if cat['id'] == category_id:
            return cat
    return None

def get_categories_for_language(language_code: str) -> list:
    """Получить список категорий для конкретного языка"""
    categories = []
    for cat in UNIFIED_CATEGORIES:
        name_key = f'name_{language_code}'
        if name_key in cat:
            categories.append({
                'id': cat['id'],
                'icon': cat['icon'],
                'name': cat[name_key],
                'keywords': cat.get(f'keywords_{language_code}', [])
            })
    return categories
