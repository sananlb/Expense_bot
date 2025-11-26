"""
Ключевые слова для категорий трат, разделённые по языкам
"""

# Русские ключевые слова для категорий
# Ключи - русские названия категорий
CATEGORY_KEYWORDS_RU = {
    'Продукты': [
        'магнит', 'пятерочка', 'перекресток', 'ашан', 'лента', 'дикси', 'вкусвилл',
        'окей', 'азбука вкуса', 'продукты', 'супермаркет', 'гипермаркет',
        'овощи', 'фрукты', 'мясо', 'рыба', 'молоко', 'хлеб',
        'продуктовый', 'бакалея', 'сыр', 'колбаса', 'круглосуточный', '24 часа',
        'макароны', 'крупа', 'рис', 'гречка', 'яйца', 'масло', 'сахар', 'соль', 'мука',
        'хамса', 'килька', 'селедка', 'сельдь', 'скумбрия', 'минтай', 'треска',
        'кб', 'красное белое', 'вв',
        # Международные бренды (латиница)
        'metro',
    ],
    'Кафе и рестораны': [
        'ресторан', 'кафе', 'бар', 'паб', 'кофейня', 'пиццерия', 'суши', 'фастфуд',
        'обед', 'ужин', 'завтрак', 'ланч', 'доставка еды', 'delivery club', 'яндекс еда',
        'шоколадница', 'теремок', 'крошка картошка', 'додо пицца', 'папа джонс',
        'кофе', 'капучино', 'латте', 'американо', 'эспрессо', 'чай', 'пицца',
        'бургер', 'роллы', 'паста', 'салат', 'десерт', 'мороженое', 'торт',
        # Международные бренды (латиница)
        'mcdonalds', 'kfc', 'burger king', 'subway', 'starbucks', 'coffee',
    ],
    'АЗС': [
        'азс', 'заправка', 'бензин', 'топливо', 'газпром', 'лукойл', 'роснефть',
        'татнефть', 'газпромнефть', 'дизель', 'газ', 'гсм',
        '92', '95', '98', 'аи-92', 'аи-95', 'аи-98', 'дт', 'автозаправка',
        # Международные бренды (латиница)
        'shell', 'bp', 'esso',
    ],
    'Транспорт': [
        'такси', 'uber', 'яндекс такси', 'ситимобил', 'gett', 'wheely', 'метро',
        'автобус', 'троллейбус', 'трамвай', 'маршрутка', 'электричка', 'проезд',
        'транспорт', 'тройка', 'единый', 'билет', 'подорожник', 'проездной',
    ],
    'Автомобиль': [
        'автомобиль', 'машина', 'авто', 'сто', 'автосервис', 'шиномонтаж', 'мойка',
        'парковка', 'штраф', 'гибдд', 'осаго', 'каско', 'техосмотр', 'ремонт',
        'запчасти', 'масло', 'антифриз', 'стеклоомыватель', 'автозапчасти',
        'платная дорога', 'платная трасса', 'toll', 'м4', 'зсд', 'цкад',
    ],
    'Жилье': [
        'квартира', 'аренда', 'ипотека', 'жкх', 'коммуналка', 'квартплата',
        'управляющая компания', 'тсж', 'жск', 'капремонт', 'домофон', 'консьерж',
        'охрана', 'уборка', 'ремонт квартиры', 'сантехник', 'электрик',
    ],
    'Аптеки': [
        'аптека', 'ригла', 'асна', '36.6', 'горздрав', 'столички', 'фармация',
        'лекарства', 'медикаменты', 'таблетки', 'витамины', 'бад', 'pharmacy',
        'аптечный', 'рецепт', 'препарат', 'лекарственный', 'здравсити',
    ],
    'Медицина': [
        'клиника', 'больница', 'поликлиника', 'врач', 'доктор', 'медцентр',
        'стоматология', 'зубной', 'анализы', 'узи', 'мрт', 'кт', 'рентген',
        'осмотр', 'консультация', 'лечение', 'операция', 'медицинский', 'терапевт',
    ],
    'Красота': [
        'салон', 'парикмахерская', 'барбершоп', 'маникюр', 'педикюр', 'косметолог',
        'спа', 'spa', 'массаж', 'солярий', 'эпиляция', 'депиляция', 'стрижка',
        'окрашивание', 'укладка', 'косметика', 'beauty', 'красота', 'уход',
    ],
    'Спорт и фитнес': [
        'фитнес', 'спортзал', 'тренажерный', 'бассейн', 'йога', 'пилатес', 'танцы',
        'спорт', 'тренировка', 'абонемент', 'world class', 'fitness', 'x-fit',
        'спортмастер', 'декатлон', 'спортивный', 'тренер', 'секция', 'фитнес клуб',
    ],
    'Одежда и обувь': [
        'одежда', 'обувь', 'zara', 'h&m', 'uniqlo', 'mango', 'bershka', 'магазин одежды',
        'бутик', 'джинсы', 'платье', 'костюм', 'кроссовки', 'туфли', 'сапоги',
        'куртка', 'пальто', 'рубашка', 'юбка', 'брюки', 'белье', 'носки',
        # маркетплейсы и онлайн-магазины
        'вб', 'валдбериз', 'wildberries', 'ozon', 'озон', 'ламода', 'lamoda',
    ],
    'Развлечения': [
        'кино', 'театр', 'концерт', 'музей', 'выставка', 'клуб', 'караоке', 'боулинг',
        'бильярд', 'квест', 'развлечения', 'отдых', 'досуг', 'парк', 'аттракционы',
        'цирк', 'зоопарк', 'аквапарк', 'кинотеатр', 'синема', 'imax', 'билет',
        'пиво', 'вино', 'алкоголь', 'коктейль', 'виски', 'водка', 'коньяк', 'шампанское',
    ],
    'Образование': [
        'курсы', 'обучение', 'школа', 'университет', 'институт', 'колледж', 'учеба',
        'образование', 'тренинг', 'семинар', 'вебинар', 'репетитор', 'учебник',
        'книги', 'канцелярия', 'тетради', 'ручки', 'учебный', 'экзамен', 'диплом',
    ],
    'Подарки': [
        'подарок', 'сувенир', 'цветы', 'букет', 'открытка', 'подарочный', 'презент',
        'поздравление', 'праздник', 'день рождения', 'юбилей', 'свадьба', 'gift',
        'флорист', 'цветочный', 'упаковка', 'лента', 'шары', 'декор',
    ],
    'Путешествия': [
        'авиабилет', 'билет', 'самолет', 'поезд', 'ржд', 'аэрофлот', 'победа',
        's7', 'utair', 'отель', 'гостиница', 'хостел', 'booking', 'airbnb',
        'путешествие', 'отпуск', 'туризм', 'экскурсия', 'гид', 'виза', 'паспорт',
    ],
    'Коммуналка и подписки': [
        'интернет', 'мобильная связь', 'телефон', 'мтс', 'билайн', 'мегафон', 'теле2',
        'ростелеком', 'электричество', 'газ', 'вода', 'отопление', 'netflix', 'spotify',
        'youtube', 'подписка', 'apple', 'google', 'яндекс плюс', 'кинопоиск', 'иви',
        'окко', 'амедиатека', 'xbox', 'playstation', 'steam', 'коммунальные',
    ],
    'Накопления': [
        'накопления', 'брокер', 'инвестировал', 'вклад', 'кубышка', 'на пенсию',
        'сбережения', 'инвестиции', 'депозит', 'накопительный', 'пенсионный',
        'откладываю', 'отложил', 'копить', 'сберегательный', 'копилка',
        'инвестировал', 'инвестирую', 'вложил', 'вкладываю', 'портфель',
        'акции', 'облигации', 'фонд', 'етф', 'etf', 'пиф', 'иис',
    ],
    'Прочие расходы': [
        # Общие слова
        'прочее', 'разное', 'другое', 'иное', 'прочие',
    ],
}

# Английские ключевые слова для категорий
# Ключи - английские названия категорий
CATEGORY_KEYWORDS_EN = {
    'Groceries': [
        'groceries', 'supermarket', 'vegetables', 'fruits', 'meat', 'fish', 'milk',
        'bread', 'cheese', 'eggs', 'butter', 'food', 'store', 'walmart', 'target',
        'costco', 'whole foods', 'trader joes', 'grocery', 'market',
        # Международные бренды
        'metro',
    ],
    'Cafes and Restaurants': [
        'restaurant', 'cafe', 'bar', 'pub', 'diner', 'bistro', 'pizza', 'sushi',
        'fastfood', 'fast food', 'lunch', 'dinner', 'breakfast', 'brunch', 'meal',
        'burger', 'sandwich', 'pasta', 'salad', 'soup', 'dessert', 'ice cream',
        'cappuccino', 'latte', 'espresso', 'americano', 'tea', 'coffee',
        # Бренды
        'mcdonalds', 'kfc', 'burger king', 'subway', 'starbucks',
    ],
    'Gas Station': [
        'gas', 'gasoline', 'petrol', 'fuel', 'diesel', 'gas station', 'station',
        'chevron', 'exxon', 'mobil', 'texaco', 'citgo', '7-eleven', 'fill up',
        # Международные бренды
        'shell', 'bp', 'esso',
    ],
    'Transport': [
        'taxi', 'bus', 'metro', 'subway', 'train', 'tram', 'trolleybus', 'transport',
        'ride', 'lyft', 'bolt', 'ticket', 'travel card', 'uber',
    ],
    'Car': [
        'car', 'vehicle', 'auto', 'repair', 'service', 'maintenance', 'parts',
        'oil', 'tire', 'tires', 'wash', 'parking', 'fine', 'ticket', 'insurance',
        'inspection', 'antifreeze', 'coolant', 'road toll', 'toll',
    ],
    'Housing': [
        'apartment', 'rent', 'rental', 'mortgage', 'utilities', 'housing', 'home',
        'plumber', 'electrician', 'repair', 'cleaning', 'security', 'maintenance',
    ],
    'Pharmacies': [
        'pharmacy', 'drugstore', 'medicine', 'pills', 'vitamins', 'supplements',
        'prescription', 'medication', 'drugs', 'cvs', 'walgreens', 'rite aid',
    ],
    'Medicine': [
        'clinic', 'hospital', 'doctor', 'dentist', 'medical', 'health', 'checkup',
        'xray', 'mri', 'ct', 'scan', 'test', 'exam', 'consultation', 'surgery',
    ],
    'Beauty': [
        'salon', 'hairdresser', 'barber', 'haircut', 'manicure', 'pedicure',
        'massage', 'cosmetics', 'makeup', 'grooming', 'styling', 'nails', 'beauty', 'spa',
    ],
    'Sports and Fitness': [
        'gym', 'fitness', 'workout', 'training', 'sport', 'swimming', 'pool',
        'yoga', 'pilates', 'dance', 'membership', 'trainer', 'exercise',
    ],
    'Clothes and Shoes': [
        'clothes', 'clothing', 'shoes', 'dress', 'jeans', 'shirt', 'pants',
        'jacket', 'coat', 'suit', 'sneakers', 'boots', 'fashion', 'apparel',
        # Бренды
        'zara', 'h&m', 'uniqlo', 'mango', 'bershka',
    ],
    'Entertainment': [
        'cinema', 'movie', 'theater', 'theatre', 'concert', 'museum', 'exhibition',
        'club', 'karaoke', 'bowling', 'billiards', 'entertainment', 'fun', 'leisure',
        'park', 'zoo', 'circus', 'amusement', 'beer', 'wine', 'alcohol', 'cocktail',
        'imax',
    ],
    'Education': [
        'education', 'course', 'courses', 'school', 'university', 'college',
        'training', 'seminar', 'webinar', 'tutor', 'books', 'textbook', 'study',
        'learning', 'exam', 'diploma', 'certificate',
    ],
    'Gifts': [
        'gift', 'present', 'souvenir', 'flowers', 'bouquet', 'card', 'birthday',
        'anniversary', 'wedding', 'celebration', 'party', 'balloons',
    ],
    'Travel': [
        'travel', 'trip', 'vacation', 'flight', 'plane', 'airport', 'hotel',
        'hostel', 'accommodation', 'tour', 'excursion', 'guide', 'visa', 'passport',
        # Бренды
        'booking', 'airbnb',
    ],
    'Utilities and Subscriptions': [
        'internet', 'mobile', 'phone', 'cellular', 'electricity', 'water', 'heating',
        'subscription', 'streaming', 'apple music', 'amazon prime', 'disney plus',
        'hbo', 'hulu', 'utilities', 'bills',
        # Бренды
        'netflix', 'spotify', 'youtube', 'apple', 'google', 'xbox', 'playstation', 'steam',
    ],
    'Savings': [
        'savings', 'save', 'saving', 'nest egg', 'rainy day fund', 'emergency fund',
        'investment', 'invested', 'investing', 'portfolio', 'broker', 'brokerage',
        'stocks', 'bonds', 'fund', 'mutual fund', 'etf', 'index fund',
        'deposit', 'bank deposit', 'term deposit', 'saving account',
        'pension', 'retirement', 'ira', '401k',
    ],
    'Other Expenses': [
        # Generic words
        'other', 'misc', 'miscellaneous', 'various', 'different',
    ],
}

# Маппинг между русскими и английскими названиями категорий
# Используется для конвертации названий категорий между языками
CATEGORY_NAME_MAPPING = {
    # Русский -> Английский
    'Продукты': 'Groceries',
    'Кафе и рестораны': 'Cafes and Restaurants',
    'АЗС': 'Gas Station',
    'Транспорт': 'Transport',
    'Автомобиль': 'Car',
    'Жилье': 'Housing',
    'Аптеки': 'Pharmacies',
    'Медицина': 'Medicine',
    'Красота': 'Beauty',
    'Спорт и фитнес': 'Sports and Fitness',
    'Одежда и обувь': 'Clothes and Shoes',
    'Развлечения': 'Entertainment',
    'Образование': 'Education',
    'Подарки': 'Gifts',
    'Путешествия': 'Travel',
    'Коммуналка и подписки': 'Utilities and Subscriptions',
    'Накопления': 'Savings',
    'Прочие расходы': 'Other Expenses',

    # Английский -> Русский (обратный маппинг)
    'Groceries': 'Продукты',
    'Cafes and Restaurants': 'Кафе и рестораны',
    'Gas Station': 'АЗС',
    'Transport': 'Транспорт',
    'Car': 'Автомобиль',
    'Housing': 'Жилье',
    'Pharmacies': 'Аптеки',
    'Medicine': 'Медицина',
    'Beauty': 'Красота',
    'Sports and Fitness': 'Спорт и фитнес',
    'Clothes and Shoes': 'Одежда и обувь',
    'Entertainment': 'Развлечения',
    'Education': 'Образование',
    'Gifts': 'Подарки',
    'Travel': 'Путешествия',
    'Utilities and Subscriptions': 'Коммуналка и подписки',
    'Savings': 'Накопления',
    'Other Expenses': 'Прочие расходы',
}

# Старый словарь оставляем для обратной совместимости
# Используется как fallback если язык не определён
CATEGORY_KEYWORDS = CATEGORY_KEYWORDS_RU
