"""
Скрипт для исправления INCOME категорий с пустыми name_ru/name_en

Проблема: При создании дефолтных категорий использовалось старое поле 'name',
а мультиязычные поля name_ru/name_en оставались пустыми.

Решение: Заполняем name_ru/name_en из поля name, определяем язык.
"""
import os
import django

# Настройка Django окружения
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import IncomeCategory, Profile
from django.db.models import Q
import re


def detect_language(text: str) -> str:
    """
    Определить язык текста (ru/en/mixed)

    Args:
        text: Текст для анализа

    Returns:
        'ru', 'en' или 'mixed'
    """
    if not text:
        return 'ru'  # По умолчанию русский

    # Убираем эмодзи для анализа
    text_clean = re.sub(
        r'[\U0001F000-\U0001F9FF\U00002600-\U000027BF\U0001F300-\U0001F64F'
        r'\U0001F680-\U0001F6FF\u2600-\u27BF\u2300-\u23FF\u2B00-\u2BFF'
        r'\u26A0-\u26FF\uFE00-\uFE0F\U000E0100-\U000E01EF]+\s*',
        '', text
    ).strip()

    if not text_clean:
        return 'ru'

    # Проверяем наличие кириллицы и латиницы
    has_cyrillic = bool(re.search(r'[а-яёА-ЯЁ]', text_clean))
    has_latin = bool(re.search(r'[a-zA-Z]', text_clean))

    if has_cyrillic and not has_latin:
        return 'ru'
    elif has_latin and not has_cyrillic:
        return 'en'
    else:
        return 'mixed'


def fix_broken_categories(dry_run: bool = True):
    """
    Исправить INCOME категории с пустыми name_ru/name_en

    Args:
        dry_run: Если True, только показывает что будет исправлено без изменений
    """
    print("=" * 70)
    print("POISK I ISPRAVLENIE BITYKH INCOME KATEGORIY")
    print("=" * 70)
    print()

    # Находим все категории где ОБА мультиязычных поля пустые
    # Используем & (AND) чтобы найти только полностью битые категории
    broken_categories = IncomeCategory.objects.filter(
        Q(name_ru__isnull=True) | Q(name_ru='')
    ).filter(
        Q(name_en__isnull=True) | Q(name_en='')
    )

    total_broken = broken_categories.count()
    print(f"Найдено битых категорий: {total_broken}")

    if total_broken == 0:
        print("[OK] Bitykh kategoriy ne naydeno!")
        return

    print()
    print("Примеры битых категорий:")
    print("-" * 70)

    for cat in broken_categories[:10]:
        # Безопасный вывод без эмодзи для Windows консоли
        name_safe = cat.name.encode('ascii', 'ignore').decode('ascii') if cat.name else ''
        name_ru_safe = (cat.name_ru or '(пусто)').encode('ascii', 'ignore').decode('ascii')
        name_en_safe = (cat.name_en or '(пусто)').encode('ascii', 'ignore').decode('ascii')
        print(f"ID: {cat.id}, Profile: {cat.profile_id}, name: '{name_safe}', "
              f"name_ru: '{name_ru_safe}', name_en: '{name_en_safe}'")

    if total_broken > 10:
        print(f"... i eshe {total_broken - 10} kategorij")

    print()

    if dry_run:
        print("[!] DRY RUN MODE - izmeneniya NE budut sokhraneny")
        print("Dlya real'nogo ispravleniya zapustite s parametrom dry_run=False")
        print()

    # Исправляем категории
    fixed_count = 0
    skipped_count = 0

    for category in broken_categories:
        # Пропускаем если name тоже пустое (такие категории нужно удалить вручную)
        if not category.name or category.name.strip() == '':
            skipped_count += 1
            continue

        # Извлекаем эмодзи для icon (первый эмодзи в строке)
        emoji_match = re.search(
            r'[\U0001F000-\U0001F9FF\U00002600-\U000027BF\U0001F300-\U0001F64F'
            r'\U0001F680-\U0001F6FF\u2600-\u27BF\u2300-\u23FF\u2B00-\u2BFF'
            r'\u26A0-\u26FF\uFE00-\uFE0F\U000E0100-\U000E01EF]',
            category.name
        )
        extracted_icon = emoji_match.group(0) if emoji_match else ''

        # Убираем эмодзи из названия
        name_clean = re.sub(
            r'[\U0001F000-\U0001F9FF\U00002600-\U000027BF\U0001F300-\U0001F64F'
            r'\U0001F680-\U0001F6FF\u2600-\u27BF\u2300-\u23FF\u2B00-\u2BFF'
            r'\u26A0-\u26FF\uFE00-\uFE0F\U000E0100-\U000E01EF]+\s*',
            '', category.name
        ).strip()

        if not name_clean:
            # Если после удаления эмодзи ничего не осталось
            skipped_count += 1
            continue

        # Определяем язык
        lang = detect_language(name_clean)

        # Заполняем поля
        if not dry_run:
            if lang == 'ru':
                category.name_ru = name_clean
                category.original_language = 'ru'
                category.is_translatable = True
            elif lang == 'en':
                category.name_en = name_clean
                category.original_language = 'en'
                category.is_translatable = True
            else:  # mixed
                # Для смешанного языка сохраняем в оба поля
                category.name_ru = name_clean
                category.name_en = name_clean
                category.original_language = 'mixed'
                category.is_translatable = False

            # Восстанавливаем icon если он был извлечен из названия
            if extracted_icon and not category.icon:
                category.icon = extracted_icon

            category.save()

        fixed_count += 1

    print()
    print("=" * 70)
    print("РЕЗУЛЬТАТЫ:")
    print("=" * 70)
    print(f"Всего найдено: {total_broken}")
    print(f"Исправлено: {fixed_count}")
    print(f"Пропущено (пустое name): {skipped_count}")
    print()

    if dry_run:
        print("[!] Eto byl testovyy progon. Dannye NE izmeneny.")
        print("Dlya primeneniya izmeneniy zapustite:")
        print("python fix_broken_income_categories.py --apply")
    else:
        print("[OK] Income kategorii uspeshno ispravleny!")
        print()
        print("Proverka posle ispravleniya...")
        remaining_broken = IncomeCategory.objects.filter(
            Q(name_ru__isnull=True) | Q(name_ru='')
        ).filter(
            Q(name_en__isnull=True) | Q(name_en='')
        )
        remaining_count = remaining_broken.count()
        print(f"Осталось битых категорий: {remaining_count}")

        if remaining_count > 0:
            print()
            print("Ostavshiesya bitye kategorii (trebuyut ruchnoy proverki):")
            for cat in remaining_broken[:10]:
                name_safe = cat.name.encode('ascii', 'ignore').decode('ascii') if cat.name else ''
                print(f"  ID: {cat.id}, Profile: {cat.profile_id}, name: '{name_safe}'")


if __name__ == '__main__':
    import sys

    # Проверяем аргументы командной строки
    apply_changes = '--apply' in sys.argv

    if apply_changes:
        print("[!] REZHIM PRIMENENIYA IZMENENIY")
        print()
        response = input("Вы уверены что хотите изменить данные? (yes/no): ")
        if response.lower() != 'yes':
            print("Отменено.")
            sys.exit(0)
        print()
        fix_broken_categories(dry_run=False)
    else:
        # Тестовый прогон по умолчанию
        fix_broken_categories(dry_run=True)
