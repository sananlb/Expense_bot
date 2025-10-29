#!/usr/bin/env python3
"""
Скрипт для анализа callback действий пользователей из логов

Использование:
    python analyze_callbacks.py                    # За последние 24 часа
    python analyze_callbacks.py --days 7           # За последние 7 дней
    python analyze_callbacks.py --user 123456789   # Для конкретного пользователя
"""

import json
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import sys


def parse_log_line(line: str) -> dict:
    """Парсит строку лога и возвращает данные"""
    try:
        # Логи могут быть в формате: "INFO timestamp module {json}"
        # Ищем JSON в строке
        json_start = line.find('{')
        if json_start == -1:
            return None

        json_str = line[json_start:]
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        return None


def analyze_callbacks(log_file: str = 'logs/callback_tracking.log',
                     days: int = 1,
                     user_id: int = None,
                     verbose: bool = False):
    """
    Анализирует callback действия из логов

    Args:
        log_file: путь к файлу логов
        days: количество дней для анализа
        user_id: ID пользователя для фильтрации (опционально)
        verbose: детальный вывод
    """
    log_path = Path(log_file)

    if not log_path.exists():
        print(f"❌ Файл логов не найден: {log_file}")
        print(f"💡 Убедитесь что бот запущен и логи создаются")
        return

    # Счетчики
    actions = Counter()
    users = Counter()
    hourly_activity = defaultdict(int)
    user_actions = defaultdict(lambda: Counter())
    callback_data_examples = defaultdict(list)

    # Фильтр по времени
    cutoff = datetime.now() - timedelta(days=days)

    # Статистика
    total_lines = 0
    parsed_lines = 0
    filtered_lines = 0

    print(f"\n📊 Анализ callback логов...")
    print(f"📁 Файл: {log_file}")
    print(f"📅 Период: последние {days} дней")
    if user_id:
        print(f"👤 Фильтр по пользователю: {user_id}")
    print()

    # Читаем лог файл
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            total_lines += 1
            data = parse_log_line(line)

            if not data:
                continue

            parsed_lines += 1

            # Фильтр по времени
            try:
                timestamp = datetime.fromisoformat(data.get('timestamp', ''))
                if timestamp < cutoff:
                    continue
            except (ValueError, TypeError):
                continue

            # Фильтр по пользователю
            if user_id and data.get('user_id') != user_id:
                continue

            filtered_lines += 1

            # Собираем статистику
            action = data.get('callback_action', 'unknown')
            actions[action] += 1

            uid = data.get('user_id')
            if uid:
                users[uid] += 1
                user_actions[uid][action] += 1

            # Активность по часам
            try:
                hour = timestamp.hour
                hourly_activity[hour] += 1
            except:
                pass

            # Примеры callback_data для каждого action
            callback_data = data.get('callback_data', '')
            if callback_data and len(callback_data_examples[action]) < 3:
                callback_data_examples[action].append(callback_data)

    # Вывод результатов
    print(f"📈 Обработано строк: {total_lines}")
    print(f"✅ Распознано JSON: {parsed_lines}")
    print(f"🎯 После фильтрации: {filtered_lines}")
    print()

    if filtered_lines == 0:
        print("⚠️ Нет данных для анализа")
        print("💡 Попробуйте:")
        print("   - Увеличить период (--days 7)")
        print("   - Проверить что бот запущен")
        print("   - Убедиться что пользователи нажимают кнопки")
        return

    # Топ действий
    print("🔝 Топ-15 популярных действий:")
    print("─" * 50)
    for i, (action, count) in enumerate(actions.most_common(15), 1):
        percentage = (count / filtered_lines) * 100
        bar = "█" * int(percentage / 2)
        print(f"{i:2d}. {action:20s} │ {count:4d} ({percentage:5.1f}%) {bar}")

        # Примеры callback_data
        if verbose and action in callback_data_examples:
            examples = callback_data_examples[action]
            print(f"    Примеры: {', '.join(examples[:3])}")

    print()

    # Статистика по пользователям
    print(f"👥 Активность пользователей:")
    print("─" * 50)
    print(f"   Всего уникальных: {len(users)}")
    print(f"   Всего кликов: {sum(actions.values())}")

    # Защита от деления на ноль
    avg_per_user = (sum(actions.values()) / len(users)) if len(users) > 0 else 0
    print(f"   Среднее на пользователя: {avg_per_user:.1f}")
    print()

    # Топ-5 активных пользователей
    if not user_id:
        print("🏆 Топ-5 самых активных пользователей:")
        print("─" * 50)
        for i, (uid, count) in enumerate(users.most_common(5), 1):
            print(f"{i}. User ID {uid}: {count} действий")

            # Топ действия этого пользователя
            if verbose:
                user_top_actions = user_actions[uid].most_common(3)
                for action, cnt in user_top_actions:
                    print(f"   - {action}: {cnt}")
        print()

    # Активность по часам
    if hourly_activity:
        print("⏰ Активность по часам дня (UTC):")
        print("─" * 50)
        max_hour_count = max(hourly_activity.values())
        for hour in range(24):
            count = hourly_activity.get(hour, 0)
            if count > 0:
                bar_length = int((count / max_hour_count) * 30)
                bar = "█" * bar_length
                print(f"{hour:02d}:00 │ {count:4d} {bar}")
        print()

    # Детальная статистика по пользователю
    if user_id and user_id in user_actions:
        print(f"🔍 Детальная статистика для пользователя {user_id}:")
        print("─" * 50)
        for action, count in user_actions[user_id].most_common(10):
            print(f"   {action:25s}: {count:3d}")
        print()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Анализ callback действий из логов Expense Bot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python analyze_callbacks.py                    # За последние 24 часа
  python analyze_callbacks.py --days 7           # За последнюю неделю
  python analyze_callbacks.py --user 123456789   # Для конкретного пользователя
  python analyze_callbacks.py --verbose          # С детальной информацией
  python analyze_callbacks.py --file logs/callback_tracking.log.1  # Старый лог файл
        """
    )

    parser.add_argument(
        '--days',
        type=int,
        default=1,
        help='Количество дней для анализа (по умолчанию: 1)'
    )

    parser.add_argument(
        '--user',
        type=int,
        help='ID пользователя для фильтрации'
    )

    parser.add_argument(
        '--file',
        type=str,
        default='logs/callback_tracking.log',
        help='Путь к файлу логов (по умолчанию: logs/callback_tracking.log)'
    )

    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Детальный вывод с примерами'
    )

    args = parser.parse_args()

    try:
        analyze_callbacks(
            log_file=args.file,
            days=args.days,
            user_id=args.user,
            verbose=args.verbose
        )
    except KeyboardInterrupt:
        print("\n\n⚠️ Прервано пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
