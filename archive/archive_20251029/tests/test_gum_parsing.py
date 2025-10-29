"""
Тест парсинга "Gum 4.5"
"""
import re
from decimal import Decimal

# Паттерны для извлечения суммы (из expense_parser.py)
AMOUNT_PATTERNS = [
    r'(\d+(?:[.,]\d+)?)\s*(?:руб|рублей|р|₽)',  # 100 руб, 100.50 р
    r'(\d+(?:[.,]\d+)?)\s*(?:usd|\$|долл|доллар)',  # 100 USD, $100
    r'(\d+(?:[.,]\d+)?)\s*(?:eur|€|евро)',  # 100 EUR, €100
    r'(\d+(?:[.,]\d+)?)\s*(?:cny|¥|юан|юаней)',  # 100 CNY
    # Latin American currencies
    r'(\d+(?:[.,]\d+)?)\s*(?:ars|песо|аргентинских?)',  # 100 ARS, Argentine Peso
    r'(\d+(?:[.,]\d+)?)\s*(?:cop|колумбийских?)',  # 100 COP, Colombian Peso
    r'(\d+(?:[.,]\d+)?)\s*(?:pen|солей?|перуанских?)',  # 100 PEN, Peruvian Sol
    r'(\d+(?:[.,]\d+)?)\s*(?:clp|чилийских?)',  # 100 CLP, Chilean Peso
    r'(\d+(?:[.,]\d+)?)\s*(?:mxn|мексиканских?)',  # 100 MXN, Mexican Peso
    r'(\d+(?:[.,]\d+)?)\s*(?:brl|реалов?|бразильских?)',  # 100 BRL, Brazilian Real
    r'(\d+(?:[.,]\d+)?)\s*$',  # просто число в конце
    r'^(\d+(?:[.,]\d+)?)\s',  # число в начале
    r'\s(\d+(?:[.,]\d+)?)\s',  # число в середине
]

def test_parsing(text):
    """Тестирует парсинг текста"""
    print(f"\n{'='*60}")
    print(f"Testing: '{text}'")
    print(f"{'='*60}")

    amount = None
    amount_str = None
    text_without_amount = None

    for i, pattern in enumerate(AMOUNT_PATTERNS):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '.')
            try:
                amount = Decimal(amount_str)
                # Убираем найденную сумму из текста
                match_start = match.start()
                match_end = match.end()
                text_without_amount = (text[:match_start] + ' ' + text[match_end:]).strip()

                print(f"[OK] Match found with pattern #{i}: {pattern}")
                print(f"   Amount string: '{amount_str}'")
                print(f"   Amount: {amount}")
                print(f"   Text without amount: '{text_without_amount}'")
                break
            except Exception as e:
                print(f"[ERROR] Error parsing amount: {e}")
                continue

    if not amount:
        print(f"[NO MATCH] Amount could not be parsed")

    return amount, text_without_amount

# Тестовые случаи
test_cases = [
    "Gum 4.5",
    "Gum 4,5",
    "Coffee 100",
    "200 кофе",
    "Продукты 1500 руб",
    "4.5",
    "4,5",
    "test 10.99",
    "Price: 15.50",
]

for test_text in test_cases:
    test_parsing(test_text)
