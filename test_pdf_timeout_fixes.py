"""
Тесты для проверки исправлений PDF timeout инцидента от 2026-01-24

Проверяет все критичные исправления:
1. PDF генерация в фоне (asyncio.create_task)
2. Per-user lock для предотвращения дубликатов
3. Admin Notifier с HTML экранированием
4. PDF timeout защита (set_default_timeout + try/finally)
5. CSV/XLSX timeout wrapper
6. safe_edit_message helper
7. Chart.js локально (без CDN)

СТАТИЧЕСКАЯ ПРОВЕРКА - работает без запуска Django
"""
from pathlib import Path
import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestResults:
    """Класс для хранения результатов тестов"""
    def __init__(self):
        self.passed = []
        self.failed = []

    def add_pass(self, test_name: str):
        self.passed.append(test_name)
        logger.info(f"[PASS] {test_name}")

    def add_fail(self, test_name: str, error: str):
        self.failed.append((test_name, error))
        logger.error(f"[FAIL] {test_name}: {error}")

    def print_summary(self):
        print("\n" + "="*60)
        print("СВОДКА ТЕСТОВ")
        print("="*60)
        print(f"Пройдено: {len(self.passed)}")
        print(f"Провалено: {len(self.failed)}")
        print("="*60)

        if self.failed:
            print("\nFailed tests:")
            for test_name, error in self.failed:
                print(f"  - {test_name}: {error}")
        else:
            print("\nAll tests passed!")

        return len(self.failed) == 0


results = TestResults()


async def test_1_admin_notifier_delivery_defaults():
    """Тест #1: Admin Notifier с надежными дефолтами доставки"""
    try:
        with open('bot/services/admin_notifier.py', 'r', encoding='utf-8') as f:
            source = f.read()

        if "parse_mode: Optional[str] = None" in source:
            results.add_pass("Admin Notifier использует plain text по умолчанию")
        else:
            results.add_fail("Admin Notifier", "parse_mode не None по умолчанию")

        if 'allow_html_tags: bool = False' in source:
            results.add_pass("Admin Notifier безопасный allow_html_tags по умолчанию")
        else:
            results.add_fail("Admin Notifier", "allow_html_tags не False по умолчанию")

        if 'if parse_mode is not None:' in source:
            results.add_pass("Admin Notifier отправляет parse_mode только если он задан")
        else:
            results.add_fail("Admin Notifier", "parse_mode всегда отправляется")

    except Exception as e:
        results.add_fail("Admin Notifier", str(e))


async def test_2_pdf_service_chartjs_local():
    """Тест #2: Chart.js загружается локально"""
    try:
        with open('bot/services/pdf_report.py', 'r', encoding='utf-8') as f:
            source = f.read()

        if 'CHARTJS_PATH' in source:
            results.add_pass("PDFReportService имеет CHARTJS_PATH константу")
        else:
            results.add_fail("Chart.js", "Нет CHARTJS_PATH")

        if '_load_chartjs' in source:
            results.add_pass("PDFReportService имеет метод _load_chartjs")
        else:
            results.add_fail("Chart.js", "Нет метода _load_chartjs")

        if 'chart_js_code' in source:
            results.add_pass("PDFReportService передает chart_js_code в шаблон")
        else:
            results.add_fail("Chart.js", "Не передает chart_js_code")

        # Проверяем что _load_chartjs выбрасывает исключения
        if 'raise FileNotFoundError' in source and 'raise RuntimeError' in source:
            results.add_pass("Chart.js выбрасывает исключения при ошибке загрузки")
        else:
            results.add_fail("Chart.js", "Не выбрасывает исключения при ошибке")

        # Проверяем что файл Chart.js существует
        chartjs_path = Path('reports/templates/static/chart.min.js')
        if chartjs_path.exists():
            size = chartjs_path.stat().st_size
            if size > 100000:
                results.add_pass(f"Chart.js локальный файл существует ({size} байт)")
            else:
                results.add_fail("Chart.js", f"Файл слишком мал: {size} байт")
        else:
            results.add_fail("Chart.js", "Локальный файл не найден")

    except Exception as e:
        results.add_fail("Chart.js локально", str(e))


async def test_3_pdf_timeout_protection():
    """Тест #3: PDF timeout защита"""
    try:
        with open('bot/services/pdf_report.py', 'r', encoding='utf-8') as f:
            source = f.read()

        if 'try:' in source and 'finally:' in source:
            results.add_pass("PDF генерация использует try/finally")
        else:
            results.add_fail("PDF timeout", "Нет try/finally блока")

        if 'set_default_timeout' in source:
            results.add_pass("PDF использует set_default_timeout")
        else:
            results.add_fail("PDF timeout", "Нет set_default_timeout")

        if "wait_until='domcontentloaded'" in source:
            results.add_pass("PDF использует domcontentloaded вместо networkidle")
        else:
            results.add_fail("PDF timeout", "Не использует domcontentloaded")

    except Exception as e:
        results.add_fail("PDF timeout защита", str(e))


async def test_4_per_user_lock():
    """Тест #4: Per-user lock для PDF во всех entry points"""
    try:
        # Проверяем pdf_report.py
        with open('bot/routers/pdf_report.py', 'r', encoding='utf-8') as f:
            source_pdf = f.read()

        if 'cache.get' in source_pdf and 'cache.set' in source_pdf and 'lock_key' in source_pdf:
            results.add_pass("pdf_report.py использует per-user lock")
        else:
            results.add_fail("Per-user lock", "pdf_report.py: нет lock механизма")

        # Проверяем expense.py
        with open('bot/routers/expense.py', 'r', encoding='utf-8') as f:
            source_expense = f.read()

        if 'cache.get' in source_expense and 'cache.set' in source_expense and 'lock_key' in source_expense:
            results.add_pass("expense.py использует per-user lock")
        else:
            results.add_fail("Per-user lock", "expense.py: нет lock механизма")

        # Проверяем reports.py
        with open('bot/routers/reports.py', 'r', encoding='utf-8') as f:
            source_reports = f.read()

        if 'cache.get' in source_reports and 'cache.set' in source_reports and 'lock_key' in source_reports:
            results.add_pass("reports.py использует per-user lock")
        else:
            results.add_fail("Per-user lock", "reports.py: нет lock механизма")

    except Exception as e:
        results.add_fail("Per-user lock", str(e))


async def test_5_pdf_background_task():
    """Тест #5: PDF генерируется в фоне во всех entry points"""
    try:
        # Проверяем pdf_report.py
        with open('bot/routers/pdf_report.py', 'r', encoding='utf-8') as f:
            source_pdf = f.read()

        if 'asyncio.create_task' in source_pdf and '_generate_and_send_pdf_background' in source_pdf:
            results.add_pass("pdf_report.py использует фоновую генерацию")
        else:
            results.add_fail("PDF фоновая генерация", "pdf_report.py: нет background task")

        # Проверяем expense.py
        with open('bot/routers/expense.py', 'r', encoding='utf-8') as f:
            source_expense = f.read()

        if 'asyncio.create_task' in source_expense and '_generate_and_send_pdf_for_current_month' in source_expense:
            results.add_pass("expense.py использует фоновую генерацию")
        else:
            results.add_fail("PDF фоновая генерация", "expense.py: нет background task")

        # Проверяем reports.py
        with open('bot/routers/reports.py', 'r', encoding='utf-8') as f:
            source_reports = f.read()

        if 'asyncio.create_task' in source_reports and '_generate_and_send_pdf_from_monthly_notification' in source_reports:
            results.add_pass("reports.py использует фоновую генерацию")
        else:
            results.add_fail("PDF фоновая генерация", "reports.py: нет background task")

    except Exception as e:
        results.add_fail("PDF фоновая генерация", str(e))


async def test_6_csv_xlsx_timeout():
    """Тест #6: CSV/XLSX timeout wrapper"""
    try:
        with open('bot/routers/reports.py', 'r', encoding='utf-8') as f:
            source = f.read()

        if 'asyncio.wait_for' in source:
            results.add_pass("CSV использует asyncio.wait_for для timeout")
        else:
            results.add_fail("CSV timeout", "Нет asyncio.wait_for")

        if 'asyncio.TimeoutError' in source:
            results.add_pass("CSV обрабатывает TimeoutError")
        else:
            results.add_fail("CSV timeout", "Нет обработки TimeoutError")

    except Exception as e:
        results.add_fail("CSV/XLSX timeout", str(e))


async def test_7_safe_edit_message():
    """Тест #7: safe_edit_message helper"""
    try:
        with open('bot/utils/message_utils.py', 'r', encoding='utf-8') as f:
            source = f.read()

        if 'def safe_edit_message' in source or 'async def safe_edit_message' in source:
            results.add_pass("safe_edit_message helper существует")
        else:
            results.add_fail("safe_edit_message", "Функция не найдена")

        if 'message is not modified' in source:
            results.add_pass("safe_edit_message обрабатывает 'not modified'")
        else:
            results.add_fail("safe_edit_message", "Не обрабатывает 'not modified'")

    except Exception as e:
        results.add_fail("safe_edit_message", str(e))


async def test_8_pdf_metrics_logging():
    """Тест #8: Структурированное логирование PDF"""
    try:
        with open('bot/routers/pdf_report.py', 'r', encoding='utf-8') as f:
            source = f.read()

        if '[PDF_START]' in source and '[PDF_SUCCESS]' in source:
            results.add_pass("PDF имеет структурированное логирование (START/SUCCESS)")
        else:
            results.add_fail("PDF метрики", "Нет [PDF_START]/[PDF_SUCCESS]")

        if 'time.time()' in source and 'duration' in source:
            results.add_pass("PDF логирует длительность генерации")
        else:
            results.add_fail("PDF метрики", "Не логирует длительность")

        if 'duration > 30' in source:
            results.add_pass("PDF отправляет алерт при медленной генерации")
        else:
            results.add_fail("PDF метрики", "Нет алерта для медленной генерации")

    except Exception as e:
        results.add_fail("PDF метрики", str(e))


async def main():
    """Запуск всех тестов"""
    print("\n" + "="*60)
    print("ТЕСТЫ ИСПРАВЛЕНИЙ PDF TIMEOUT ИНЦИДЕНТА")
    print("="*60 + "\n")

    # Запускаем тесты
    await test_1_admin_notifier_delivery_defaults()
    await test_2_pdf_service_chartjs_local()
    await test_3_pdf_timeout_protection()
    await test_4_per_user_lock()
    await test_5_pdf_background_task()
    await test_6_csv_xlsx_timeout()
    await test_7_safe_edit_message()
    await test_8_pdf_metrics_logging()

    # Печатаем сводку
    success = results.print_summary()

    if success:
        print("\nALL FIXES VERIFIED SUCCESSFULLY")
        return 0
    else:
        print("\nSOME FIXES REQUIRE ATTENTION")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
