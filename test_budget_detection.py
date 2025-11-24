"""Простой smoke-тест для detect_budget_intent."""
import sys

sys.path.insert(0, ".")

from bot.utils.expense_parser import detect_budget_intent


test_cases = [
    # Должны определяться как бюджет/баланс
    ("50000 бюджет", True),
    ("лимит 100000", True),
    ("бюджет на месяц 50000", True),
    ("баланс 80000", True),
    ("всего 120000", True),
    ("осталось 50000", True),
    ("budget 50000", True),
    ("limit 100000", True),
    ("monthly budget 50000", True),
    ("50000 на месяц", True),
    # Не бюджет
    ("кофе 200", False),
    ("зарплата 50000", False),  # это доход, не бюджет
    ("расскажи про бюджет", False),  # нет числа
    ("мне нужен budget", False),  # нет числа
    ("потратил всего 5000", False),  # речь про трату
]


def main() -> None:
    print("=" * 60)
    print("Smoke-тест detect_budget_intent")
    print("=" * 60)

    passed = failed = 0
    for text, expected in test_cases:
        result = detect_budget_intent(text)
        status = "PASS" if result == expected else "FAIL"
        if result == expected:
            passed += 1
        else:
            failed += 1
        print(f"[{status}] '{text}' -> {result} (expected: {expected})")

    print("=" * 60)
    print(f"Итог: {passed} passed, {failed} failed")
    print("=" * 60)


if __name__ == "__main__":
    main()
