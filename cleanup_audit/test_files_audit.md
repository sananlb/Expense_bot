# Test Files Audit

Все test* файлы в корне — это **одноразовые скрипты для отладки**, НЕ юнит-тесты.

## Рекомендация: Переместить ВСЕ в архив

**Причина:** Это не автоматические тесты, а разовые скрипты для исследования багов.
Если понадобятся — легко достать из архива.

## Список файлов для архивирования (26 шт.):

### Отладка конкретных проблем (можно смело архивировать):
1. `test_intent_debug.py` - отладка определения намерений
2. `test_marker_match.py` - поиск конкретного TIME_MARKER
3. `test_telegram_invoice.py` - тест форматирования invoice
4. `test_intent_cases.py` - тестовые случаи намерений
5. `test_db_typo_search.py` - поиск опечаток в БД
6. `test_check_all_expenses.py` - проверка всех трат
7. `test_similarity_logic.py` - логика похожести
8. `test_similar_search.py` - поиск похожих
9. `test_typo_matching.py` - подбор опечаток
10. `test_keyword_filtering.py` - фильтрация ключевых слов
11. `test_parser.py` - парсинг
12. `test_emoji_utils.py` - утилиты эмодзи
13. `test_extract_words.py` - извлечение слов
14. `test_newlines.py` - обработка переносов строк
15. `test_multipliers.py` - множители
16. `test_dynamic_layout.py` - динамический layout
17. `test_excel_export.py` - экспорт в Excel
18. `test_monthly_notification.py` - ежемесячные уведомления

### Тесты функциональности (можно архивировать, т.к. не автоматические):
19. `test_celery_quick.py` - быстрый тест Celery
20. `test_celery_helper_direct.py` - прямой тест Celery helper
21. `test_celery_routing.py` - роутинг Celery
22. `test_income_keywords_simple.py` - тест ключевых слов доходов (упрощенный)
23. `test_income_keywords_celery.py` - тест ключевых слов через Celery
24. `test_income_keywords_uniqueness.py` - тест уникальности ключевых слов
25. `test_category_language_conversion.py` - конверсия языков категорий
26. `test_normalized_weight_removal.py` - удаление нормализованных весов

### Важное уточнение:
Эти файлы НЕ являются `pytest`/`unittest` тестами для CI/CD.
Это **отладочные скрипты** которые запускаются вручную для исследования.

**Вывод:** Все можно безопасно переместить в `archive_20251124/`.
