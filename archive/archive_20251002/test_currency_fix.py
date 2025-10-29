#!/usr/bin/env python3
"""
Тестирование исправления определения валюты
"""
import re

# Новые паттерны с границами слов
CURRENCY_PATTERNS = {
    # Major world currencies
    'USD': [r'\$', r'\busd\b', r'долл', r'доллар'],
    'EUR': [r'€', r'\beur\b', r'евро', r'euro'],
    'GBP': [r'£', r'\bgbp\b', r'фунт', r'sterling', r'pounds?\b'],
    'CNY': [r'¥', r'\bcny\b', r'юан', r'yuan', r'renminbi', r'\brmb\b'],
    'CHF': [r'\bchf\b', r'₣', r'франк(?:ов|а)?\b', r'swiss\s+franc', r'francs?\b'],
    'INR': [r'\binr\b', r'₹', r'рупи[йяею]', r'индийск.*руп'],
    'TRY': [r'\btry\b', r'₺', r'лир[аиы]?\b', r'турец.*лир'],

    # Local currencies (CIS and nearby)
    'KZT': [r'\bkzt\b', r'₸', r'тенге', r'теньге', r'тенг[еиия]', r'тнг', r'tenge'],
    'UAH': [r'\buah\b', r'грн', r'гривн[а-я]*', r'гривен', r'hryvni?a', r'hryvnya'],
    'BYN': [r'\bbyn\b', r'\bbyr\b', r'бел[ао]рус.*руб', r'belarus.*rubl', r'belarusian\s+ruble'],
    'RUB': [r'₽', r'\brub\b', r'руб', r'рубл'],
    'UZS': [r'\buzs\b', r"so['']m", r'сум(?:ов|ы|у)?\b', r'узбек.*сум', r'uzbek.*som'],
    'AMD': [r'\bamd\b', r'драм', r'dram'],
    'TMT': [r'\btmt\b', r'туркмен.*манат', r'turkmen.*manat'],
    'AZN': [r'\bazn\b', r'азер.*манат', r'azer.*manat', r'манат(?:ов|ы)?\b'],
    'KGS': [r'\bkgs\b', r'\bkgz\b', r'сом(?:ов|ы|у)?\b', r'киргиз.*сом', r'кырг.*сом'],
    'TJS': [r'\btjs\b', r'сомон[ия]?\b', r'таджик.*сом', r'tajik.*somoni'],
    'MDL': [r'\bmdl\b', r'лей(?:ев|я|и|ем|ями)?\b', r'молдав.*лей', r'moldov.*le[ui]'],
    'GEL': [r'\bgel\b', r'лари\b', r'lari\b', r'gruzi.*lari'],

    # Latin American currencies
    'ARS': [r'\bars\b', r'аргентинских?', r'аргентинское', r'аргентинский', r'argentin[ea].*peso', r'песо'],
    'COP': [r'\bcop\b', r'колумбийских?', r'колумбийское', r'колумбийский', r'colombian.*peso'],
    'PEN': [r'\bpen\b', r'солей?', r'перуанских?', r'перуанское', r'перуанский', r'peruvian\s+sol'],
    'CLP': [r'\bclp\b', r'чилийских?', r'чилийское', r'чилийский', r'chilean.*peso'],
    'MXN': [r'\bmxn\b', r'мексиканских?', r'мексиканское', r'мексиканский', r'mexican.*peso'],
    'BRL': [r'\bbrl\b', r'реал(?:ов|ы)?', r'бразильских?', r'бразильское', r'бразильский', r'brazilian\s+real'],
}


def detect_currency(text: str, user_currency: str = 'RUB') -> str:
    """Detect currency from text"""
    text_lower = text.lower()

    for currency, patterns in CURRENCY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return currency

    return (user_currency or 'RUB').upper()


# Тестовые случаи
test_cases = [
    # Проблемные случаи (должны использовать RUB из профиля)
    ("OpenAI 1500", "RUB", "✅ ИСПРАВЛЕНО: OpenAI больше не содержит 'pen'"),
    ("Mars 500", "RUB", "✅ ИСПРАВЛЕНО: Mars больше не содержит 'ars'"),
    ("Cars 1000", "RUB", "✅ ИСПРАВЛЕНО: Cars больше не содержит 'ars'"),
    ("Stars 300", "RUB", "✅ ИСПРАВЛЕНО: Stars больше не содержит 'ars'"),
    ("Country 200", "RUB", "✅ ИСПРАВЛЕНО: Country больше не содержит 'try'"),
    ("Industry 500", "RUB", "✅ ИСПРАВЛЕНО: Industry больше не содержит 'try'"),
    ("Umbrella 300", "RUB", "✅ ИСПРАВЛЕНО: Umbrella больше не содержит 'brl'"),
    ("Pencil 200", "RUB", "✅ ИСПРАВЛЕНО: Pencil больше не содержит 'pen'"),

    # Корректные случаи с явной валютой (должны определить валюту из текста)
    ("Кофе $5", "USD", "✅ Символ $ распознается"),
    ("Обед €20", "EUR", "✅ Символ € распознается"),
    ("Такси ₽300", "RUB", "✅ Символ ₽ распознается"),
    ("100 usd", "USD", "✅ Код USD как отдельное слово"),
    ("pen 200", "PEN", "✅ Код PEN как отдельное слово"),
    ("ars 500", "ARS", "✅ Код ARS как отдельное слово"),
    ("try 100", "TRY", "✅ Код TRY как отдельное слово"),
    ("100 руб", "RUB", "✅ Слово 'руб' распознается"),
    ("50 долларов", "USD", "✅ Слово 'долларов' распознается"),
    ("30 евро", "EUR", "✅ Слово 'евро' распознается"),

    # Случаи без явной валюты (должны использовать валюту из профиля)
    ("Кофе 200", "RUB", "✅ Нет валюты → из профиля"),
    ("Coffee 150", "RUB", "✅ Нет валюты → из профиля"),
    ("Обед 500", "RUB", "✅ Нет валюты → из профиля"),
]

print("=" * 80)
print("ТЕСТИРОВАНИЕ ИСПРАВЛЕНИЯ ОПРЕДЕЛЕНИЯ ВАЛЮТЫ")
print("=" * 80)
print()

passed = 0
failed = 0

for text, expected_currency, description in test_cases:
    result = detect_currency(text, user_currency='RUB')
    status = "✅ PASS" if result == expected_currency else "❌ FAIL"

    if result == expected_currency:
        passed += 1
    else:
        failed += 1

    print(f"{status} | '{text}' → {result} (ожидалось: {expected_currency})")
    print(f"       {description}")
    print()

print("=" * 80)
print(f"РЕЗУЛЬТАТЫ: {passed} passed, {failed} failed из {len(test_cases)} тестов")
print("=" * 80)

if failed == 0:
    print("\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО! Исправление работает корректно.")
else:
    print(f"\n⚠️  {failed} тест(ов) провалилось. Требуется дополнительная проверка.")
