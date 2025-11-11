#!/usr/bin/env python3
"""
Скрипт для поиска PII (Personally Identifiable Information) в коде
Ищет использование username, first_name, last_name из Telegram User объектов

ВАЖНО:
- bot_username - это НЕ PII (username бота), игнорируется
- Ищем только user.username, from_user.username и т.п.
- Проверяем Python файлы в bot/, не трогаем archive/
"""
import os
import re
from pathlib import Path
from typing import List, Dict, Tuple

# Паттерны для поиска PII
# Ищем обращения к username/first_name/last_name из User объектов Telegram
PII_PATTERNS = [
    # user.username (где user - объект User из aiogram)
    (r'\buser\.username\b', 'user.username'),
    (r'\buser\.first_name\b', 'user.first_name'),
    (r'\buser\.last_name\b', 'user.last_name'),

    # from_user.username (message.from_user, callback.from_user)
    (r'from_user\.username\b', 'from_user.username'),
    (r'from_user\.first_name\b', 'from_user.first_name'),
    (r'from_user\.last_name\b', 'from_user.last_name'),

    # event.from_user.username
    (r'event\.from_user\.username\b', 'event.from_user.username'),
    (r'event\.from_user\.first_name\b', 'event.from_user.first_name'),
    (r'event\.from_user\.last_name\b', 'event.from_user.last_name'),

    # Словари с PII ключами
    (r'["\']username["\']\s*:', '"username": (dictionary key)'),
    (r'["\']first_name["\']\s*:', '"first_name": (dictionary key)'),
    (r'["\']last_name["\']\s*:', '"last_name": (dictionary key)'),

    # profile.username (из старой модели, если осталось)
    (r'\bprofile\.username\b', 'profile.username'),
    (r'\bprofile\.first_name\b', 'profile.first_name'),
    (r'\bprofile\.last_name\b', 'profile.last_name'),

    # Параметры функций с PII
    (r'\busername:\s*(?:Optional\[)?str', 'username: str (function parameter)'),
    (r'\bfirst_name:\s*(?:Optional\[)?str', 'first_name: str (function parameter)'),
    (r'\blast_name:\s*(?:Optional\[)?str', 'last_name: str (function parameter)'),

    # Использование username/first_name как переменных (но НЕ bot_username)
    (r'\bif\s+username\s*:', 'if username: (variable check)'),
    (r'\bif\s+first_name\s*:', 'if first_name: (variable check)'),
    (r'\bif\s+last_name\s*:', 'if last_name: (variable check)'),

    # Передача в функции (escape, format и т.д.)
    (r'escape_markdown.*?\(username\)', 'escape_markdown(username)'),
    (r'escape_markdown.*?\(first_name\)', 'escape_markdown(first_name)'),
    (r'escape_markdown.*?\(last_name\)', 'escape_markdown(last_name)'),
]

# Паттерны для ИСКЛЮЧЕНИЯ (НЕ PII)
EXCLUDE_PATTERNS = [
    r'bot_username',  # Username бота, не пользователя
    r'BOT_USERNAME',  # Константа с username бота
    r'@param\s+username',  # Docstring параметр
    r'@param\s+first_name',  # Docstring параметр
    r'#.*username',  # Комментарий
    r'#.*first_name',  # Комментарий
    r'Args:',  # Docstring секция Args
    r'"""',  # Начало/конец docstring
    r"'''",  # Начало/конец docstring
]

# Директории для исключения
EXCLUDE_DIRS = {
    'venv', '.git', '__pycache__', 'staticfiles', 'node_modules',
    '.pytest_cache', 'htmlcov', '.mypy_cache', '.tox',
    # Архивы
    'archive', 'archive_20251102', 'archive_20251105',
    'archive_20251109', 'archive_20251110',
}

# Файлы для исключения
EXCLUDE_FILES = {
    'check_pii.py',  # Сам скрипт
}

class PIIMatch:
    """Найденное совпадение PII"""
    def __init__(self, file: str, line_num: int, line_content: str, pattern_name: str):
        self.file = file
        self.line_num = line_num
        self.line_content = line_content.strip()
        self.pattern_name = pattern_name

    def __repr__(self):
        return f"PIIMatch({self.file}:{self.line_num} - {self.pattern_name})"


def is_excluded_line(line: str) -> bool:
    """Проверить что строка должна быть исключена"""
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            return True
    return False


def check_file(file_path: Path) -> List[PIIMatch]:
    """Проверить файл на наличие PII"""
    matches = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                # Пропускаем исключенные строки
                if is_excluded_line(line):
                    continue

                # Проверяем каждый паттерн
                for pattern_regex, pattern_name in PII_PATTERNS:
                    if re.search(pattern_regex, line):
                        matches.append(PIIMatch(
                            file=str(file_path),
                            line_num=line_num,
                            line_content=line,
                            pattern_name=pattern_name
                        ))
    except Exception as e:
        print(f"⚠️  Ошибка при чтении {file_path}: {e}")

    return matches


def scan_directory(root_dir: str = 'bot') -> List[PIIMatch]:
    """Сканировать директорию на PII"""
    root = Path(root_dir)
    all_matches = []

    if not root.exists():
        print(f"❌ Директория {root_dir} не найдена!")
        return all_matches

    for file_path in root.rglob('*.py'):
        # Пропускаем исключенные директории
        if any(excluded in file_path.parts for excluded in EXCLUDE_DIRS):
            continue

        # Пропускаем исключенные файлы
        if file_path.name in EXCLUDE_FILES:
            continue

        matches = check_file(file_path)
        if matches:
            all_matches.extend(matches)

    return all_matches


def group_by_file(matches: List[PIIMatch]) -> Dict[str, List[PIIMatch]]:
    """Группировать совпадения по файлам"""
    by_file = {}
    for match in matches:
        if match.file not in by_file:
            by_file[match.file] = []
        by_file[match.file].append(match)
    return by_file


def generate_report(matches: List[PIIMatch]) -> str:
    """Сгенерировать отчет"""
    if not matches:
        return "[OK] PII not found in code!"

    by_file = group_by_file(matches)

    report_lines = [
        f"[PII FOUND] {len(by_file)} files contain PII:\n",
        "=" * 80,
        ""
    ]

    for file, file_matches in sorted(by_file.items()):
        report_lines.append(f"\n[FILE] {file} ({len(file_matches)} matches):")
        report_lines.append("-" * 80)

        for match in file_matches:
            # Обрезаем длинные строки
            content = match.line_content
            if len(content) > 100:
                content = content[:97] + "..."

            report_lines.append(f"  Line {match.line_num:4d}: {content}")
            report_lines.append(f"             Pattern: {match.pattern_name}")

    report_lines.append("")
    report_lines.append("=" * 80)
    report_lines.append(f"[SUMMARY] {len(matches)} total matches in {len(by_file)} files")
    report_lines.append("=" * 80)

    return "\n".join(report_lines)


def generate_summary(matches: List[PIIMatch]) -> Dict[str, int]:
    """Сгенерировать краткую сводку по типам PII"""
    summary = {}
    for match in matches:
        pattern = match.pattern_name
        summary[pattern] = summary.get(pattern, 0) + 1
    return summary


def main():
    """Основная функция"""
    print("Scanning project for PII...")
    print(f"Checking directories: bot/")
    print(f"Excluded directories: {', '.join(sorted(EXCLUDE_DIRS))}")
    print()

    # Сканируем bot/ (database/ перемещена в архив)
    matches = scan_directory('bot')

    # Генерируем отчет
    report = generate_report(matches)
    print(report)

    # Краткая сводка
    if matches:
        print("\n[PII Types Summary]")
        print("-" * 80)
        summary = generate_summary(matches)
        for pattern, count in sorted(summary.items(), key=lambda x: x[1], reverse=True):
            print(f"  {pattern:30s}: {count:3d} matches")

    # Сохраняем отчет в файл
    report_file = 'pii_scan_report.txt'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
        f.write("\n\n")
        f.write("[PII Types Summary]\n")
        f.write("-" * 80 + "\n")
        if matches:
            summary = generate_summary(matches)
            for pattern, count in sorted(summary.items(), key=lambda x: x[1], reverse=True):
                f.write(f"  {pattern:30s}: {count:3d} matches\n")

    print(f"\n[REPORT] Saved to {report_file}")

    # Exit код для CI/CD
    if matches:
        print(f"\n[FAIL] CHECK FAILED: found {len(matches)} PII usages")
        return 1
    else:
        print("\n[OK] CHECK PASSED: no PII found")
        return 0


if __name__ == '__main__':
    exit(main())
