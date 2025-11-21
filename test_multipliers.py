"""
Тестовый скрипт для проверки работы множителей сумм
"""
import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.utils.expense_parser import extract_amount_from_patterns

test_cases = [
    # Русский язык
    ("10 тыс рублей", 10000, "рублей"),
    ("2 млн рублей", 2000000, "рублей"),
    ("5 тысяч на еду", 5000, "на еду"),
    ("1.5 млн долларов", 1500000, "долларов"),
    ("100 тыс", 100000, ""),
    ("3 миллиона", 3000000, ""),
    ("20 тысячи", 20000, ""),

    # Английский язык
    ("5 thousand", 5000, ""),
    ("1.5 million", 1500000, ""),
    ("100 thousands", 100000, ""),

    # Без множителей (должно работать как обычно)
    ("500 рублей", 500, "рублей"),
    ("1234", 1234, ""),
    ("100 долларов", 100, "долларов"),
]

print("\n" + "="*80)
print("ТЕСТИРОВАНИЕ МНОЖИТЕЛЕЙ СУММ")
print("="*80 + "\n")

passed = 0
failed = 0

for text, expected_amount, expected_desc in test_cases:
    result = extract_amount_from_patterns(text)

    if result:
        amount, desc = result

        # Проверяем что amount не None
        if amount is None:
            print(f"❌ FAIL: '{text}' - сумма None")
            failed += 1
            print()
            continue

        # Проверяем что desc не None
        if desc is None:
            desc = ""

        # Проверка суммы
        amount_ok = abs(float(amount) - expected_amount) < 0.01

        # Проверка описания (проверяем что основная часть совпадает)
        desc_clean = desc.strip().lower()
        expected_desc_clean = expected_desc.strip().lower()
        desc_ok = (expected_desc_clean in desc_clean or
                   desc_clean in expected_desc_clean or
                   (expected_desc == "" and desc.strip() == ""))

        if amount_ok and desc_ok:
            print(f"✅ PASS: '{text}'")
            print(f"   Сумма: {amount} (ожидалось: {expected_amount})")
            print(f"   Описание: '{desc}' (ожидалось: '{expected_desc}')")
            passed += 1
        else:
            print(f"❌ FAIL: '{text}'")
            print(f"   Сумма: {amount} (ожидалось: {expected_amount}) {'✅' if amount_ok else '❌'}")
            print(f"   Описание: '{desc}' (ожидалось: '{expected_desc}') {'✅' if desc_ok else '❌'}")
            failed += 1
    else:
        print(f"❌ FAIL: '{text}' - не удалось распарсить")
        failed += 1

    print()

print("="*80)
print(f"РЕЗУЛЬТАТЫ: {passed} пройдено, {failed} провалено из {passed + failed} тестов")
print("="*80 + "\n")

if failed == 0:
    print("🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
    sys.exit(0)
else:
    print(f"⚠️ ЕСТЬ ОШИБКИ: {failed} тестов провалено")
    sys.exit(1)
