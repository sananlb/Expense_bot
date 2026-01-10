"""
Тестирование нового keyword matching (Вариант C - Гибридный подход)

Проверяет:
1. Нормализацию текста
2. Точное совпадение (exact match)
3. Совпадение по началу фразы (prefix match)
4. Отсутствие ложных срабатываний
5. Защиту от коротких слов
"""

import sys
import os
import io

# Устанавливаем UTF-8 для Windows консоли
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.utils.keyword_service import normalize_keyword_text, match_keyword_in_text


def test_normalization():
    """Тест нормализации текста"""
    print("\n=== TEST 1: Нормализация текста ===")

    test_cases = [
        ("  Сосиска в ТЕСТЕ и чай  ", "сосиска в тесте и чай"),
        ("Тест", "тест"),
        ("", ""),
        ("Кофе, чай!", "кофе чай"),
        ("🍕 Пицца!", "пицца"),
        ("  Много    пробелов  ", "много пробелов"),
        ("Долг за тест 500", "долг за тест 500"),
    ]

    passed = 0
    failed = 0

    for input_text, expected in test_cases:
        result = normalize_keyword_text(input_text)
        if result == expected:
            print(f"✅ PASS: '{input_text}' → '{result}'")
            passed += 1
        else:
            print(f"❌ FAIL: '{input_text}' → '{result}' (expected: '{expected}')")
            failed += 1

    print(f"\nРезультат: {passed} passed, {failed} failed")
    return failed == 0


def test_exact_match():
    """Тест точного совпадения"""
    print("\n=== TEST 2: Точное совпадение ===")

    test_cases = [
        # (keyword, text, should_match, expected_type)
        ("сосиска в тесте и чай", "Сосиска в тесте и чай", True, "exact"),
        ("сосиска в тесте и чай", "СОСИСКА В ТЕСТЕ И ЧАЙ", True, "exact"),
        ("тест", "Тест", True, "exact"),
        ("долг за тест", "долг за тест 500", True, "prefix"),  # первые 3 слова совпадают (это правильно!)
    ]

    passed = 0
    failed = 0

    for keyword, text, should_match, expected_type in test_cases:
        matched, match_type = match_keyword_in_text(keyword, text)

        if matched == should_match and (not should_match or match_type == expected_type):
            print(f"✅ PASS: '{keyword}' vs '{text}' → matched={matched}, type={match_type}")
            passed += 1
        else:
            print(f"❌ FAIL: '{keyword}' vs '{text}' → matched={matched}, type={match_type} "
                  f"(expected: matched={should_match}, type={expected_type})")
            failed += 1

    print(f"\nРезультат: {passed} passed, {failed} failed")
    return failed == 0


def test_prefix_match():
    """Тест совпадения по началу фразы"""
    print("\n=== TEST 3: Совпадение по началу фразы ===")

    test_cases = [
        # (keyword, text, should_match, expected_type)
        ("сосиска в тесте и чай", "Сосиска в тесте 390", True, "prefix"),  # первые 3 слова совпадают
        ("сосиска в тесте", "сосиска в тесте и чай", True, "prefix"),  # начало совпадает
        ("кофе с молоком", "Кофе с молоком и сахаром", True, "prefix"),
        ("водица бутилированная", "Водица", False, "none"),  # текст слишком короткий
    ]

    passed = 0
    failed = 0

    for keyword, text, should_match, expected_type in test_cases:
        matched, match_type = match_keyword_in_text(keyword, text)

        if matched == should_match and (not should_match or match_type == expected_type):
            print(f"✅ PASS: '{keyword}' vs '{text}' → matched={matched}, type={match_type}")
            passed += 1
        else:
            print(f"❌ FAIL: '{keyword}' vs '{text}' → matched={matched}, type={match_type} "
                  f"(expected: matched={should_match}, type={expected_type})")
            failed += 1

    print(f"\nРезультат: {passed} passed, {failed} failed")
    return failed == 0


def test_no_false_positives():
    """Тест отсутствия ложных срабатываний"""
    print("\n=== TEST 4: Отсутствие ложных срабатываний ===")

    test_cases = [
        # (keyword, text, should_match) - все должны НЕ совпадать!
        ("долг за тест", "Тест 500", False),  # "тест" не должен совпадать с "долг за тест"
        ("тест", "Сосиска в тесте и чай", False),  # "тест" не должен совпадать с полной фразой
        ("водица", "Водица на тренировку", False),  # одно слово vs фраза
        ("95", "9500", False),  # защита от подстрок в числах
        ("в", "в магазине", False),  # защита от коротких слов
    ]

    passed = 0
    failed = 0

    for keyword, text, should_match in test_cases:
        matched, match_type = match_keyword_in_text(keyword, text)

        if matched == should_match:
            print(f"✅ PASS: '{keyword}' vs '{text}' → matched={matched} (no false positive)")
            passed += 1
        else:
            print(f"❌ FAIL: '{keyword}' vs '{text}' → matched={matched} "
                  f"(expected: matched={should_match}) - FALSE POSITIVE!")
            failed += 1

    print(f"\nРезультат: {passed} passed, {failed} failed")
    return failed == 0


def test_short_word_protection():
    """Тест защиты от коротких слов"""
    print("\n=== TEST 5: Защита от коротких слов ===")

    test_cases = [
        # (keyword, text, should_match)
        ("в", "в магазине", False),  # короткое слово - не должно совпадать
        ("на", "на улице", False),
        ("от", "от дома", False),
        ("ко", "ко мне", False),
        # НО: если это часть более длинной фразы (>= 3 символа после нормализации)
        ("кофе", "Кофе", True),  # 4 символа - должно совпадать
        ("чай", "Чай", True),  # 3 символа - должно совпадать
    ]

    passed = 0
    failed = 0

    for keyword, text, should_match in test_cases:
        matched, match_type = match_keyword_in_text(keyword, text)

        if matched == should_match:
            print(f"✅ PASS: '{keyword}' vs '{text}' → matched={matched}")
            passed += 1
        else:
            print(f"❌ FAIL: '{keyword}' vs '{text}' → matched={matched} "
                  f"(expected: matched={should_match})")
            failed += 1

    print(f"\nРезультат: {passed} passed, {failed} failed")
    return failed == 0


def test_inflections():
    """Тест совпадения со склонениями"""
    print("\n=== TEST 6: Совпадение со склонениями ===")

    test_cases = [
        # (keyword, text, should_match, expected_type)
        # ВАЖНО: склонения работают ТОЛЬКО для одиночных слов (keyword + text = по 1 слову)
        ("зарплата", "Зарплату", True, "inflection"),
        ("зарплата", "Зарплаты", True, "inflection"),
        ("зарплата", "Зарплате", True, "inflection"),
        ("фриланс", "Фрилансом", True, "inflection"),
        ("кофе", "Кофейня", False, "none"),  # разница > 2 символов
        ("95", "9500", False, "none"),  # НЕ склонение, защита от подстроки
        ("тест", "тестирование", False, "none"),  # разница > 2 символов
        # НЕ должны срабатывать если текст - несколько слов
        ("зарплата", "Зарплату перевели", False, "none"),
        ("водица", "Водица на тренировку", False, "none"),
    ]

    passed = 0
    failed = 0

    for keyword, text, should_match, expected_type in test_cases:
        matched, match_type = match_keyword_in_text(keyword, text)

        if matched == should_match and (not should_match or match_type == expected_type):
            print(f"✅ PASS: '{keyword}' vs '{text}' → matched={matched}, type={match_type}")
            passed += 1
        else:
            print(f"❌ FAIL: '{keyword}' vs '{text}' → matched={matched}, type={match_type} "
                  f"(expected: matched={should_match}, type={expected_type})")
            failed += 1

    print(f"\nРезультат: {passed} passed, {failed} failed")
    return failed == 0


def test_real_world_scenarios():
    """Тест реальных сценариев из production"""
    print("\n=== TEST 7: Реальные сценарии ===")

    # Реальные проблемы из плана
    test_cases = [
        # Сценарий 1: "Сосиска в тесте и чай 390" → "Родственники" (БАГ!)
        ("тест", "Сосиска в тесте и чай 390", False),  # НЕ должно совпадать

        # Сценарий 2: "Водица 130" → "Продукты", должно "Спорт"
        ("водица", "Водица на тренировку 130", False),  # НЕ должно совпадать (контекст изменился)

        # Сценарий 3: Правильное совпадение
        ("сосиска в тесте и чай", "Сосиска в тесте и чай 390", True),  # точное совпадение
        ("сосиска в тесте и чай", "Сосиска в тесте 400", True),  # prefix совпадение

        # Сценарий 4: Долг за тест
        ("долг за тест", "Долг за тест 500", True),  # точное совпадение
        ("долг за тест", "Тест 500", False),  # НЕ должно совпадать
    ]

    passed = 0
    failed = 0

    for keyword, text, should_match in test_cases:
        matched, match_type = match_keyword_in_text(keyword, text)

        if matched == should_match:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1

        print(f"{status}: keyword='{keyword}', text='{text}' → matched={matched}, type={match_type}")

    print(f"\nРезультат: {passed} passed, {failed} failed")
    return failed == 0


def main():
    """Запуск всех тестов"""
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ НОВОГО KEYWORD MATCHING (Вариант C)")
    print("=" * 60)

    all_passed = True

    # Запускаем все тесты
    all_passed &= test_normalization()
    all_passed &= test_exact_match()
    all_passed &= test_prefix_match()
    all_passed &= test_no_false_positives()
    all_passed &= test_short_word_protection()
    all_passed &= test_inflections()  # НОВЫЙ ТЕСТ для склонений
    all_passed &= test_real_world_scenarios()

    # Итоговый результат
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("=" * 60)
        return 0
    else:
        print("❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
