"""
Упрощенный тест вопросов к боту (без полного Django setup)
Проверяет логику определения интентов
"""
import sys
import re
from datetime import datetime
from typing import Dict, List, Tuple


# Копия логики из expense_intent.py
def is_show_expenses_request(text: str) -> Tuple[bool, float]:
    """Определяет является ли текст запросом показа трат"""
    text_lower = text.lower().strip()

    # Антипаттерны - это НЕ запрос показа
    analytical_patterns = [
        'какая самая', 'какой самый', 'какие самые',
        'самая большая', 'самый большой', 'самые большие',
        'на что больше', 'на что меньше',
        'сколько раз', 'как часто',
        'в какой категории',
        'почему', 'зачем', 'для чего',
        'объясни', 'расскажи', 'опиши',
        'анализ', 'аналитика', 'статистика',
        'сравни', 'сравнение',
        'тренд', 'динамика', 'изменение',
        'прогноз', 'предсказание',
        'рекомендации', 'советы', 'предложения',
        'оптимизация', 'экономия', 'сократить',
        'средн'  # средняя сумма, средний чек
    ]

    if any(pattern in text_lower for pattern in analytical_patterns):
        return False, 0.0

    # Готовые фразы - точное совпадение
    show_expense_phrases = [
        'траты за', 'расходы за', 'траты вчера', 'траты сегодня',
        'покажи траты', 'показать траты', 'сколько потратил',
        'мои траты', 'дневник трат', 'история трат'
    ]

    for phrase in show_expense_phrases:
        if phrase in text_lower:
            return True, 1.0

    # Проверка паттернов
    show_verbs = ['показать', 'покажи', 'посмотреть', 'посмотри', 'вывести', 'выведи',
                  'дай', 'скажи', 'расскажи', 'сколько', 'какие', 'что', 'проверить']

    time_markers = ['сегодня', 'вчера', 'позавчера', 'неделя', 'месяц', 'год',
                    'январ', 'феврал', 'март', 'апрел', 'май', 'июн', 'июл', 'август',
                    'сентябр', 'октябр', 'ноябр', 'декабр']

    expense_words = ['трата', 'траты', 'расход', 'расходы', 'потратил', 'потратила',
                     'израсходовал', 'expense', 'expenses', 'spent',
                     'дневник', 'журнал', 'история']

    has_show_verb = any(verb in text_lower for verb in show_verbs)
    has_time_marker = any(marker in text_lower for marker in time_markers)
    has_expense_word = any(word in text_lower for word in expense_words)

    # Определение уверенности
    if has_show_verb and has_expense_word:
        return True, 0.95
    if has_show_verb and has_time_marker:
        return True, 0.9
    if 'сколько' in text_lower and 'потратил' in text_lower:
        return True, 0.85

    # УДАЛЕНО: Фразы типа "траты в сентябре" теперь идут в expense parser как записи

    return False, 0.0


# Копия логики из text_classifier.py (обновленная упрощенная версия)
def classify_message(text: str) -> Tuple[str, float]:
    """
    Классифицирует сообщение как 'expense' (трата) или 'chat'

    Упрощенная логика:
    1. Если есть '?' → chat
    2. Если начинается с вопросительного слова (что, как, где...) → chat
    3. Если есть слова-действия (покажи, найди, выведи) → chat
    4. Иначе → expense (трата)
    """
    text = text.strip()
    text_lower = text.lower()

    # Вопросительные слова
    question_words = ['что', 'как', 'где', 'когда', 'почему', 'зачем', 'кто', 'какой', 'какая', 'какие', 'сколько']

    # Слова-действия
    chat_action_words = [
        'покажи', 'найди', 'выведи', 'сравни',
        'покаж', 'найд', 'вывед', 'сравн'
    ]

    # 1. ПРИОРИТЕТ: Вопросительный знак → всегда чат
    if text.endswith('?'):
        return 'chat', 1.0

    # 2. Проверяем первое слово - вопросительное слово?
    words = text_lower.split()
    if words and words[0] in question_words:
        return 'chat', 0.95

    # 3. Проверяем наличие слов-действий (покажи, найди, выведи)
    for action_word in chat_action_words:
        if action_word in text_lower:
            return 'chat', 0.9

    # 4. ВСЕ ОСТАЛЬНОЕ → expense (трата)
    return 'expense', 0.8


# Простая эмуляция FAQ matcher
def check_faq_match(text: str) -> Tuple[float, str]:
    """Упрощенная проверка FAQ (без реального FAQ сервиса)"""
    text_norm = text.lower().strip().replace('ё', 'е')
    text_norm = re.sub(r'[^a-zа-я0-9\s]', ' ', text_norm)
    text_norm = re.sub(r'\s+', ' ', text_norm).strip()

    # Эмулируем FAQ вопросы (после наших изменений)
    faq_questions = {
        'что ты умеешь': ('capabilities', 1.0),
        'помощь': ('capabilities', 1.0),
        'как пользоваться ботом': ('capabilities', 0.95),
        'как добавить трату': ('add_expense', 1.0),
        'как работает кешбэк': ('cashback', 1.0),
        'как работает кэшбэк': ('cashback', 1.0),
        'как установить лимит': ('limits', 1.0),
        'что дает подписка': ('subscription', 1.0),
        'что даёт подписка': ('subscription', 1.0),
        'как управлять категориями': ('categories_manage', 1.0),
        'как получить отчет': ('view_reports', 1.0),
        'как получить отчёт': ('view_reports', 1.0),
        'где найти отчеты': ('view_reports', 0.95),
        'где найти отчёты': ('view_reports', 0.95),
        'как скачать excel': ('view_reports', 0.90),
        'как сгенерировать pdf': ('view_reports', 0.90),
    }

    # Точное совпадение
    if text_norm in faq_questions:
        faq_id, confidence = faq_questions[text_norm]
        return confidence, faq_id

    # Fuzzy matching (упрощенный)
    from difflib import SequenceMatcher
    best_ratio = 0.0
    best_id = None

    for faq_q, (faq_id, _) in faq_questions.items():
        ratio = SequenceMatcher(None, text_norm, faq_q).ratio()
        if ratio > best_ratio and ratio >= 0.72:
            best_ratio = ratio
            best_id = faq_id

    if best_ratio >= 0.72:
        return best_ratio, best_id

    return 0.0, None


# Тестовые вопросы
TEST_QUESTIONS = {
    "FAQ - Общие возможности": [
        "Что ты умеешь?",
        "Помощь",
        "Как пользоваться ботом?",
    ],
    "FAQ - Инструкции": [
        "Как добавить трату?",
        "Как работает кешбэк?",
        "Как установить лимит?",
        "Что дает подписка?",
        "Как управлять категориями?",
    ],
    "FAQ - Отчеты": [
        "Как получить отчет?",
        "Где найти отчеты?",
        "Как скачать Excel?",
        "Как сгенерировать PDF?",
    ],
    "Граничные случаи (короткие фразы)": [
        "Покажи траты",
        "Статистика",
        "Отчет",
    ],
    "AI - Запросы с периодами": [
        "Покажи траты за ноябрь",
        "Покажи все траты за октябрь",
        "Траты в сентябре",
        "Сколько я потратил в ноябре?",
        "Сколько я потратил сегодня?",
        "Покажи траты за последнюю неделю",
    ],
    "AI - Аналитические вопросы": [
        "На что я больше всего трачу?",
        "Какая самая большая трата в ноябре?",
        "Сравни траты в октябре и ноябре",
        "В какой категории больше всего расходов?",
        "Какая трата встречается чаще всего?",
        "Средняя сумма трат в день",
    ],
    "AI - Специфичные запросы": [
        "Сколько я потратил на кафе в ноябре?",
        "Покажи траты больше 5000 рублей",
        "Траты в ресторане за октябрь",
    ],
}


def test_question(text: str) -> Dict:
    """Тестирует один вопрос"""
    result = {'text': text}

    # 1. FAQ проверка
    faq_confidence, faq_id = check_faq_match(text)
    result['faq_confidence'] = faq_confidence
    result['faq_id'] = faq_id
    result['faq_matched'] = faq_confidence >= 0.60

    # 2. Show expenses intent
    is_show, show_confidence = is_show_expenses_request(text)
    result['show_intent'] = is_show
    result['show_confidence'] = show_confidence

    # 3. Text classifier
    msg_type, classify_confidence = classify_message(text)
    result['classifier_type'] = msg_type
    result['classifier_confidence'] = classify_confidence

    # 4. Определение финального обработчика
    if faq_confidence >= 0.85:
        result['handler'] = 'FAQ (high confidence)'
        result['handler_type'] = 'FAQ'
    elif faq_confidence >= 0.60:
        result['handler'] = 'FAQ (medium confidence)'
        result['handler_type'] = 'FAQ'
    elif is_show and show_confidence >= 0.7:
        result['handler'] = 'AI (show expenses)'
        result['handler_type'] = 'AI'
    elif msg_type == 'chat':
        result['handler'] = 'AI (chat classifier)'
        result['handler_type'] = 'AI'
    else:
        result['handler'] = 'Expense Parser (default)'
        result['handler_type'] = 'EXPENSE'

    return result


def run_tests():
    """Запускает все тесты"""
    print("=" * 80)
    print("🧪 АВТОМАТИЧЕСКОЕ ТЕСТИРОВАНИЕ ВОПРОСОВ К БОТУ")
    print("=" * 80)
    print(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    all_results = []
    total_questions = sum(len(questions) for questions in TEST_QUESTIONS.values())
    current = 0

    for category, questions in TEST_QUESTIONS.items():
        print(f"\n{'=' * 80}")
        print(f"📂 {category}")
        print(f"{'=' * 80}\n")

        for question in questions:
            current += 1
            print(f"[{current}/{total_questions}] Тестирую: \"{question}\"")

            result = test_question(question)
            all_results.append(result)

            # Вывод результата
            handler_emoji = {
                'FAQ': '📋',
                'AI': '🤖',
                'EXPENSE': '💸'
            }.get(result['handler_type'], '❓')

            print(f"  {handler_emoji} Обработчик: {result['handler']}")

            if result['faq_matched']:
                print(f"  📋 FAQ: {result['faq_id']} (уверенность: {result['faq_confidence']:.2f})")

            if result['show_intent']:
                print(f"  🔍 Show intent: {result['show_confidence']:.2f}")

            if result['classifier_type'] == 'chat':
                print(f"  💬 Classifier: {result['classifier_type']} ({result['classifier_confidence']:.2f})")

            print()

    # Итоговая статистика
    print("\n" + "=" * 80)
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 80)

    faq_count = sum(1 for r in all_results if r['handler_type'] == 'FAQ')
    ai_count = sum(1 for r in all_results if r['handler_type'] == 'AI')
    expense_count = sum(1 for r in all_results if r['handler_type'] == 'EXPENSE')

    print(f"\n📋 FAQ обработает: {faq_count}/{total_questions} ({faq_count/total_questions*100:.1f}%)")
    print(f"🤖 AI обработает: {ai_count}/{total_questions} ({ai_count/total_questions*100:.1f}%)")
    print(f"💸 Expense Parser: {expense_count}/{total_questions} ({expense_count/total_questions*100:.1f}%)")

    # Проблемные случаи
    print("\n" + "=" * 80)
    print("⚠️ ПРОБЛЕМНЫЕ СЛУЧАИ")
    print("=" * 80)

    problems = []

    # Блок 1-3: Должны идти в FAQ
    expected_faq = (
        TEST_QUESTIONS["FAQ - Общие возможности"] +
        TEST_QUESTIONS["FAQ - Инструкции"] +
        TEST_QUESTIONS["FAQ - Отчеты"]
    )
    for question in expected_faq:
        result = next(r for r in all_results if r['text'] == question)
        if result['handler_type'] != 'FAQ':
            problems.append({
                'question': question,
                'expected': 'FAQ',
                'actual': result['handler_type'],
                'reason': result['handler']
            })

    # Блок 5-7: Должны идти в AI, КРОМЕ фраз без призыва к действию
    # Исключения (должны быть EXPENSE):
    # - "Траты в сентябре" - нет глагола действия
    # - "Средняя сумма трат в день" - нет глагола действия
    # - "Траты в ресторане за октябрь" - нет глагола действия
    exceptions_to_expense = [
        "Траты в сентябре",
        "Средняя сумма трат в день",
        "Траты в ресторане за октябрь"
    ]

    expected_ai = (
        TEST_QUESTIONS["AI - Запросы с периодами"] +
        TEST_QUESTIONS["AI - Аналитические вопросы"] +
        TEST_QUESTIONS["AI - Специфичные запросы"]
    )
    for question in expected_ai:
        result = next(r for r in all_results if r['text'] == question)

        # Если это исключение, проверяем что оно EXPENSE
        if question in exceptions_to_expense:
            if result['handler_type'] != 'EXPENSE':
                problems.append({
                    'question': question,
                    'expected': 'EXPENSE',
                    'actual': result['handler_type'],
                    'reason': result['handler']
                })
        # Иначе должно быть AI
        elif result['handler_type'] == 'EXPENSE':
            problems.append({
                'question': question,
                'expected': 'AI',
                'actual': result['handler_type'],
                'reason': result['handler']
            })

    if problems:
        print(f"\n❌ Найдено {len(problems)} проблем:\n")
        for i, p in enumerate(problems, 1):
            print(f"{i}. \"{p['question']}\"")
            print(f"   Ожидалось: {p['expected']}")
            print(f"   Получено: {p['actual']} ({p['reason']})")
            print()
    else:
        print("\n✅ Проблем не найдено! Все вопросы обрабатываются корректно.")

    # Граничные случаи
    print("\n" + "=" * 80)
    print("🔍 ГРАНИЧНЫЕ СЛУЧАИ")
    print("=" * 80 + "\n")

    for question in TEST_QUESTIONS["Граничные случаи (короткие фразы)"]:
        result = next(r for r in all_results if r['text'] == question)
        print(f"• \"{question}\" → {result['handler_type']} ({result['handler']})")

    print("\n" + "=" * 80)
    print("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 80)

    return all_results, problems


if __name__ == "__main__":
    run_tests()
