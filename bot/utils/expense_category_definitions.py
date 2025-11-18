"""
Shared definitions and helpers for expense categories.
Объединенные ключевые слова для категорий расходов (русские + английские).
"""
from typing import Optional, Dict

# ВАЖНО: Импортируем из централизованного модуля (включает ZWJ для композитных эмодзи)
from bot.utils.emoji_utils import strip_leading_emoji


EXPENSE_CATEGORY_DEFINITIONS: Dict[str, Dict[str, object]] = {
    'groceries': {
        'name_ru': '🛒 Продукты',
        'name_en': '🛒 Groceries',
        'keywords': [
            # Русские магазины и бренды
            'магнит', 'пятерочка', 'перекресток', 'ашан', 'лента', 'дикси', 'вкусвилл',
            'окей', 'азбука вкуса', 'продукты', 'супермаркет', 'гипермаркет',
            'овощи', 'фрукты', 'мясо', 'рыба', 'молоко', 'хлеб',
            'продуктовый', 'бакалея', 'сыр', 'колбаса', 'круглосуточный', '24 часа',
            'макароны', 'крупа', 'рис', 'гречка', 'яйца', 'масло', 'сахар', 'соль', 'мука',
            'хамса', 'килька', 'селедка', 'сельдь', 'скумбрия', 'минтай', 'треска',
            'кб', 'красное белое', 'вв',
            # Английские
            'groceries', 'supermarket', 'vegetables', 'fruits', 'meat', 'fish', 'milk',
            'bread', 'cheese', 'eggs', 'butter', 'food', 'store', 'walmart', 'target',
            'costco', 'whole foods', 'trader joes', 'grocery', 'market',
            # Международные бренды
            'metro',
        ],
        'aliases': ['продукты', 'groceries', 'еда', 'food'],
    },
    'cafes_restaurants': {
        'name_ru': '🍽️ Кафе и рестораны',
        'name_en': '🍽️ Cafes and Restaurants',
        'keywords': [
            # Русские
            'ресторан', 'кафе', 'бар', 'паб', 'кофейня', 'пиццерия', 'суши', 'фастфуд',
            'обед', 'ужин', 'завтрак', 'ланч', 'доставка еды', 'delivery club', 'яндекс еда',
            'шоколадница', 'теремок', 'крошка картошка', 'додо пицца', 'папа джонс',
            'кофе', 'капучино', 'латте', 'американо', 'эспрессо', 'чай', 'пицца',
            'бургер', 'роллы', 'паста', 'салат', 'десерт', 'мороженое', 'торт',
            # Английские
            'restaurant', 'cafe', 'bar', 'pub', 'diner', 'bistro', 'pizza', 'sushi',
            'fastfood', 'fast food', 'lunch', 'dinner', 'breakfast', 'brunch', 'meal',
            'burger', 'sandwich', 'pasta', 'salad', 'soup', 'dessert', 'ice cream',
            'cappuccino', 'latte', 'espresso', 'americano', 'tea', 'coffee',
            # Международные бренды
            'mcdonalds', 'kfc', 'burger king', 'subway', 'starbucks',
        ],
        'aliases': ['кафе', 'cafes', 'ресторан', 'restaurant', 'еда вне дома'],
    },
    'gas_station': {
        'name_ru': '⛽ АЗС',
        'name_en': '⛽ Gas Station',
        'keywords': [
            # Русские
            'азс', 'заправка', 'бензин', 'топливо', 'газпром', 'лукойл', 'роснефть',
            'татнефть', 'газпромнефть', 'дизель', 'газ', 'гсм',
            '92', '95', '98', 'аи-92', 'аи-95', 'аи-98', 'дт', 'автозаправка',
            # Английские
            'gas', 'gasoline', 'petrol', 'fuel', 'diesel', 'gas station', 'station',
            'chevron', 'exxon', 'mobil', 'texaco', 'citgo', '7-eleven', 'fill up',
            # Международные бренды
            'shell', 'bp', 'esso',
        ],
        'aliases': ['азс', 'gas station', 'заправка', 'бензин', 'gasoline'],
    },
    'transport': {
        'name_ru': '🚕 Транспорт',
        'name_en': '🚕 Transport',
        'keywords': [
            # Русские
            'такси', 'uber', 'яндекс такси', 'ситимобил', 'gett', 'wheely', 'метро',
            'автобус', 'троллейбус', 'трамвай', 'маршрутка', 'электричка', 'проезд',
            'транспорт', 'тройка', 'единый', 'билет', 'подорожник', 'проездной',
            # Английские
            'taxi', 'bus', 'metro', 'subway', 'train', 'tram', 'trolleybus', 'transport',
            'ride', 'lyft', 'bolt', 'ticket', 'travel card',
        ],
        'aliases': ['транспорт', 'transport', 'такси', 'taxi'],
    },
    'car': {
        'name_ru': '🚗 Автомобиль',
        'name_en': '🚗 Car',
        'keywords': [
            # Русские
            'автомобиль', 'машина', 'авто', 'сто', 'автосервис', 'шиномонтаж', 'мойка',
            'парковка', 'штраф', 'гибдд', 'осаго', 'каско', 'техосмотр', 'ремонт',
            'запчасти', 'масло', 'антифриз', 'стеклоомыватель', 'автозапчасти',
            'платная дорога', 'платная трасса', 'toll', 'м4', 'зсд', 'цкад',
            # АЗС и топливо (для пользователей без категории АЗС)
            'азс', 'заправка', 'бензин', 'топливо', 'газпром', 'лукойл', 'роснефть',
            'татнефть', 'газпромнефть', 'дизель', 'газ', 'гсм',
            '92', '95', '98', 'аи-92', 'аи-95', 'аи-98', 'дт', 'автозаправка',
            # Английские
            'car', 'vehicle', 'auto', 'repair', 'service', 'maintenance', 'parts',
            'oil', 'tire', 'tires', 'wash', 'parking', 'fine', 'ticket', 'insurance',
            'inspection', 'antifreeze', 'coolant', 'road toll',
            # АЗС и топливо (английские)
            'gas', 'gasoline', 'petrol', 'fuel', 'diesel', 'gas station', 'station',
            'chevron', 'exxon', 'mobil', 'texaco', 'citgo', '7-eleven', 'fill up',
            # Международные бренды АЗС
            'shell', 'bp', 'esso',
        ],
        'aliases': ['автомобиль', 'car', 'машина', 'авто', 'азс', 'заправка'],
    },
    'housing': {
        'name_ru': '🏠 Жилье',
        'name_en': '🏠 Housing',
        'keywords': [
            # Русские
            'квартира', 'аренда', 'ипотека', 'жкх', 'коммуналка', 'квартплата',
            'управляющая компания', 'тсж', 'жск', 'капремонт', 'домофон', 'консьерж',
            'охрана', 'уборка', 'ремонт квартиры', 'сантехник', 'электрик',
            # Английские
            'apartment', 'rent', 'rental', 'mortgage', 'utilities', 'housing', 'home',
            'plumber', 'electrician', 'repair', 'cleaning', 'security', 'maintenance',
        ],
        'aliases': ['жилье', 'housing', 'квартира', 'apartment'],
    },
    'pharmacies': {
        'name_ru': '💊 Аптеки',
        'name_en': '💊 Pharmacies',
        'keywords': [
            # Русские
            'аптека', 'ригла', 'асна', '36.6', 'горздрав', 'столички', 'фармация',
            'лекарства', 'медикаменты', 'таблетки', 'витамины', 'бад',
            'аптечный', 'рецепт', 'препарат', 'лекарственный', 'здравсити',
            # Английские
            'pharmacy', 'drugstore', 'medicine', 'pills', 'vitamins', 'supplements',
            'prescription', 'medication', 'drugs', 'cvs', 'walgreens', 'rite aid',
        ],
        'aliases': ['аптека', 'pharmacy', 'лекарства', 'medicine'],
    },
    'medicine': {
        'name_ru': '🏥 Медицина',
        'name_en': '🏥 Medicine',
        'keywords': [
            # Русские
            'клиника', 'больница', 'поликлиника', 'врач', 'доктор', 'медцентр',
            'стоматология', 'зубной', 'анализы', 'узи', 'мрт', 'кт', 'рентген',
            'осмотр', 'консультация', 'лечение', 'операция', 'медицинский', 'терапевт',
            # Английские
            'clinic', 'hospital', 'doctor', 'dentist', 'medical', 'health', 'checkup',
            'xray', 'mri', 'ct', 'scan', 'test', 'exam', 'consultation', 'surgery',
        ],
        'aliases': ['медицина', 'medicine', 'врач', 'doctor', 'клиника', 'clinic'],
    },
    'beauty': {
        'name_ru': '💄 Красота',
        'name_en': '💄 Beauty',
        'keywords': [
            # Русские
            'салон', 'парикмахерская', 'барбершоп', 'маникюр', 'педикюр', 'косметолог',
            'спа', 'spa', 'массаж', 'солярий', 'эпиляция', 'депиляция', 'стрижка',
            'окрашивание', 'укладка', 'косметика', 'beauty', 'красота', 'уход',
            # Английские
            'salon', 'hairdresser', 'barber', 'haircut', 'manicure', 'pedicure',
            'massage', 'cosmetics', 'makeup', 'grooming', 'styling', 'nails',
        ],
        'aliases': ['красота', 'beauty', 'салон', 'salon'],
    },
    'sports_fitness': {
        'name_ru': '🏃 Спорт и фитнес',
        'name_en': '🏃 Sports and Fitness',
        'keywords': [
            # Русские
            'фитнес', 'спортзал', 'тренажерный', 'бассейн', 'йога', 'пилатес', 'танцы',
            'спорт', 'тренировка', 'абонемент', 'world class', 'fitness', 'x-fit',
            'спортмастер', 'декатлон', 'спортивный', 'тренер', 'секция', 'фитнес клуб',
            # Английские
            'gym', 'workout', 'training', 'sport', 'swimming', 'pool',
            'yoga', 'pilates', 'dance', 'membership', 'trainer', 'exercise',
        ],
        'aliases': ['спорт', 'sports', 'фитнес', 'fitness', 'тренировка', 'workout'],
    },
    'clothes_shoes': {
        'name_ru': '👔 Одежда и обувь',
        'name_en': '👔 Clothes and Shoes',
        'keywords': [
            # Русские
            'одежда', 'обувь', 'магазин одежды',
            'бутик', 'джинсы', 'платье', 'костюм', 'кроссовки', 'туфли', 'сапоги',
            'куртка', 'пальто', 'рубашка', 'юбка', 'брюки', 'белье', 'носки',
            # Английские
            'clothes', 'clothing', 'shoes', 'dress', 'jeans', 'shirt', 'pants',
            'jacket', 'coat', 'suit', 'sneakers', 'boots', 'fashion', 'apparel',
            # Международные бренды
            'zara', 'h&m', 'uniqlo', 'mango', 'bershka',
        ],
        'aliases': ['одежда', 'clothes', 'обувь', 'shoes'],
    },
    'entertainment': {
        'name_ru': '🎭 Развлечения',
        'name_en': '🎭 Entertainment',
        'keywords': [
            # Русские
            'кино', 'театр', 'концерт', 'музей', 'выставка', 'клуб', 'караоке', 'боулинг',
            'бильярд', 'квест', 'развлечения', 'отдых', 'досуг', 'парк', 'аттракционы',
            'цирк', 'зоопарк', 'аквапарк', 'кинотеатр', 'синема', 'imax', 'билет',
            'пиво', 'вино', 'алкоголь', 'коктейль', 'виски', 'водка', 'коньяк', 'шампанское',
            # Английские
            'cinema', 'movie', 'theater', 'theatre', 'concert', 'museum', 'exhibition',
            'club', 'karaoke', 'bowling', 'billiards', 'entertainment', 'fun', 'leisure',
            'park', 'zoo', 'circus', 'amusement', 'beer', 'wine', 'alcohol', 'cocktail',
        ],
        'aliases': ['развлечения', 'entertainment', 'кино', 'cinema'],
    },
    'education': {
        'name_ru': '📚 Образование',
        'name_en': '📚 Education',
        'keywords': [
            # Русские
            'курсы', 'обучение', 'школа', 'университет', 'институт', 'колледж', 'учеба',
            'образование', 'тренинг', 'семинар', 'вебинар', 'репетитор', 'учебник',
            'книги', 'канцелярия', 'тетради', 'ручки', 'учебный', 'экзамен', 'диплом',
            # Английские
            'education', 'course', 'courses', 'school', 'university', 'college',
            'training', 'seminar', 'webinar', 'tutor', 'books', 'textbook', 'study',
            'learning', 'exam', 'diploma', 'certificate',
        ],
        'aliases': ['образование', 'education', 'обучение', 'learning'],
    },
    'gifts': {
        'name_ru': '🎁 Подарки',
        'name_en': '🎁 Gifts',
        'keywords': [
            # Русские
            'подарок', 'сувенир', 'цветы', 'букет', 'открытка', 'подарочный', 'презент',
            'поздравление', 'праздник', 'день рождения', 'юбилей', 'свадьба',
            'флорист', 'цветочный', 'упаковка', 'лента', 'шары', 'декор',
            # Английские
            'gift', 'present', 'souvenir', 'flowers', 'bouquet', 'card', 'birthday',
            'anniversary', 'wedding', 'celebration', 'party', 'balloons',
        ],
        'aliases': ['подарки', 'gifts', 'подарок', 'gift'],
    },
    'travel': {
        'name_ru': '✈️ Путешествия',
        'name_en': '✈️ Travel',
        'keywords': [
            # Русские
            'авиабилет', 'билет', 'самолет', 'поезд', 'ржд', 'аэрофлот', 'победа',
            's7', 'utair', 'отель', 'гостиница', 'хостел',
            'путешествие', 'отпуск', 'туризм', 'экскурсия', 'гид', 'виза', 'паспорт',
            # Английские
            'travel', 'trip', 'vacation', 'flight', 'plane', 'airport', 'hotel',
            'hostel', 'accommodation', 'tour', 'excursion', 'guide', 'visa', 'passport',
            # Международные бренды
            'booking', 'airbnb',
        ],
        'aliases': ['путешествия', 'travel', 'отпуск', 'vacation'],
    },
    'utilities_subscriptions': {
        'name_ru': '📱 Коммуналка и подписки',
        'name_en': '📱 Utilities and Subscriptions',
        'keywords': [
            # Русские
            'интернет', 'мобильная связь', 'телефон', 'мтс', 'билайн', 'мегафон', 'теле2',
            'ростелеком', 'электричество', 'газ', 'вода', 'отопление',
            'подписка', 'яндекс плюс', 'кинопоиск', 'иви',
            'окко', 'амедиатека', 'коммунальные',
            # Английские
            'internet', 'mobile', 'phone', 'cellular', 'electricity', 'water', 'heating',
            'subscription', 'streaming', 'apple music', 'amazon prime', 'disney plus',
            'hbo', 'hulu', 'utilities', 'bills',
            # Международные бренды
            'netflix', 'spotify', 'youtube', 'apple', 'google', 'xbox', 'playstation', 'steam',
        ],
        'aliases': ['коммуналка', 'utilities', 'подписки', 'subscriptions'],
    },
    'savings': {
        'name_ru': '💎 Накопления',
        'name_en': '💎 Savings',
        'keywords': [
            # Русские
            'накопления', 'брокер', 'инвестировал', 'вклад', 'кубышка', 'на пенсию',
            'сбережения', 'инвестиции', 'депозит', 'накопительный', 'пенсионный',
            'откладываю', 'отложил', 'копить', 'сберегательный', 'копилка',
            'инвестирую', 'вложил', 'вкладываю', 'портфель',
            'акции', 'облигации', 'фонд', 'етф', 'etf', 'пиф', 'иис',
            # Английские
            'savings', 'save', 'saving', 'nest egg', 'rainy day fund', 'emergency fund',
            'investment', 'invested', 'investing', 'portfolio', 'broker', 'brokerage',
            'stocks', 'bonds', 'fund', 'mutual fund', 'index fund',
            'deposit', 'bank deposit', 'term deposit', 'saving account',
            'pension', 'retirement', 'ira', '401k',
        ],
        'aliases': ['накопления', 'savings', 'инвестиции', 'investments'],
    },
    'other': {
        'name_ru': '💰 Прочие расходы',
        'name_en': '💰 Other Expenses',
        'keywords': [
            # Русские
            'прочее', 'разное', 'другое', 'иное', 'прочие',
            # Английские
            'other', 'misc', 'miscellaneous', 'various', 'different',
        ],
        'aliases': ['прочие', 'other', 'разное', 'misc'],
    },
}

DEFAULT_EXPENSE_CATEGORY_KEY = 'other'


def get_expense_category_display_name(category_key: str, language_code: str = 'ru') -> str:
    """Return the localized category name (with emoji) for the given key."""
    data = EXPENSE_CATEGORY_DEFINITIONS.get(category_key) or EXPENSE_CATEGORY_DEFINITIONS[DEFAULT_EXPENSE_CATEGORY_KEY]
    if language_code.lower().startswith('en'):
        return data['name_en']  # type: ignore[index]
    return data['name_ru']  # type: ignore[index]


def normalize_expense_category_key(label: Optional[str]) -> Optional[str]:
    """Map a raw category label to a canonical category key."""
    if not label:
        return None
    cleaned = strip_leading_emoji(label).lower()
    if not cleaned:
        return None

    for key, data in EXPENSE_CATEGORY_DEFINITIONS.items():
        potential_matches = {
            strip_leading_emoji(data['name_ru']).lower(),
            strip_leading_emoji(data['name_en']).lower(),
        }

        if cleaned in potential_matches:
            return key

        for alias in data.get('aliases', []):
            alias_lower = alias.lower()
            if alias_lower and (alias_lower == cleaned or alias_lower in cleaned or cleaned in alias_lower):
                return key

        for keyword in data.get('keywords', []):
            keyword_lower = keyword.lower()
            if keyword_lower and (keyword_lower == cleaned or keyword_lower in cleaned or cleaned in keyword_lower):
                return key

    return None


def detect_expense_category_key(text: str) -> Optional[str]:
    """Detect a category key by checking keywords against the text."""
    text_lower = text.lower()

    # Track best match with score
    best_key = None
    best_score = 0

    for key, data in EXPENSE_CATEGORY_DEFINITIONS.items():
        if key == DEFAULT_EXPENSE_CATEGORY_KEY:
            continue

        score = 0
        for keyword in data.get('keywords', []):
            if keyword in text_lower:
                score += 1

        if score > best_score:
            best_score = score
            best_key = key

    return best_key
