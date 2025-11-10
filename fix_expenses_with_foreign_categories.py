"""
Скрипт для поиска и исправления трат с "чужими" категориями

Проблема: Из-за отсутствия валидации category_id, траты могли быть
привязаны к категориям других пользователей.

Решение: Находим такие траты и либо переназначаем на правильную категорию,
либо переносим в "Прочие расходы".
"""
import os
import django

# Настройка Django окружения
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Expense, ExpenseCategory, Profile
from django.db.models import Q


def find_expenses_with_foreign_categories():
    """
    Найти все траты с категориями, не принадлежащими владельцу траты
    """
    print("=" * 70)
    print("ПОИСК ТРАТ С ЧУЖИМИ КАТЕГОРИЯМИ")
    print("=" * 70)
    print()

    # Находим все траты где profile_id не совпадает с category.profile_id
    # И пользователи не в одном household
    foreign_expenses = []

    for expense in Expense.objects.select_related('profile', 'category', 'category__profile').all():
        if expense.category is None:
            continue

        # Проверяем владельца категории
        is_valid = False

        # Случай 1: Категория принадлежит владельцу траты
        if expense.category.profile_id == expense.profile_id:
            is_valid = True
        # Случай 2: Оба в семейном бюджете и в одной семье
        elif (expense.profile.household_id is not None and
              expense.category.profile.household_id is not None and
              expense.profile.household_id == expense.category.profile.household_id):
            is_valid = True

        if not is_valid:
            foreign_expenses.append(expense)

    total_found = len(foreign_expenses)
    print(f"Найдено трат с чужими категориями: {total_found}")
    print()

    if total_found == 0:
        print("✅ Трат с чужими категориями не найдено!")
        return []

    # Группируем по пользователям
    by_user = {}
    for expense in foreign_expenses:
        user_id = expense.profile.telegram_id
        if user_id not in by_user:
            by_user[user_id] = []
        by_user[user_id].append(expense)

    print(f"Затронуто пользователей: {len(by_user)}")
    print()

    # Выводим статистику по пользователям
    print("Топ-10 пользователей с проблемными тратами:")
    print("-" * 70)
    sorted_users = sorted(by_user.items(), key=lambda x: len(x[1]), reverse=True)

    for user_id, expenses in sorted_users[:10]:
        print(f"  User {user_id}: {len(expenses)} трат")

        # Показываем первые 3 траты
        for exp in expenses[:3]:
            cat_name = exp.category.name_ru or exp.category.name_en or exp.category.name or '(без названия)'
            print(f"    - ID {exp.id}: {exp.description or '(без описания)'} "
                  f"({exp.amount} {exp.currency}) → Категория '{cat_name}' "
                  f"(profile_id={exp.category.profile_id})")

        if len(expenses) > 3:
            print(f"    ... и еще {len(expenses) - 3} трат")
        print()

    return foreign_expenses


def fix_expenses_with_foreign_categories(dry_run: bool = True):
    """
    Исправить траты с чужими категориями

    Стратегия:
    1. Если у пользователя есть категория с похожим названием - переназначить
    2. Иначе - переназначить на "Прочие расходы" пользователя
    3. Если нет "Прочих расходов" - создать

    Args:
        dry_run: Если True, только показывает что будет исправлено
    """
    foreign_expenses = find_expenses_with_foreign_categories()

    if not foreign_expenses:
        return

    print()
    print("=" * 70)
    print("ИСПРАВЛЕНИЕ ТРАТ")
    print("=" * 70)
    print()

    if dry_run:
        print("⚠️  DRY RUN MODE - изменения НЕ будут сохранены")
        print()

    fixed_count = 0
    reassigned_count = 0
    moved_to_other_count = 0

    for expense in foreign_expenses:
        user_profile = expense.profile
        foreign_category = expense.category

        # Получаем название чужой категории
        foreign_cat_name = (
            foreign_category.name_ru or
            foreign_category.name_en or
            foreign_category.name or
            ''
        ).lower().strip()

        # Пытаемся найти похожую категорию у пользователя
        user_category = None

        if foreign_cat_name:
            # Ищем категорию с похожим названием
            user_categories = ExpenseCategory.objects.filter(profile=user_profile)

            for cat in user_categories:
                cat_name = (
                    cat.name_ru or
                    cat.name_en or
                    cat.name or
                    ''
                ).lower().strip()

                if cat_name and foreign_cat_name in cat_name or cat_name in foreign_cat_name:
                    user_category = cat
                    break

        if user_category:
            # Нашли похожую категорию - переназначаем
            if not dry_run:
                expense.category = user_category
                expense.save()

            reassigned_count += 1
            fixed_count += 1

        else:
            # Не нашли - переносим в "Прочие расходы"
            other_category = ExpenseCategory.objects.filter(
                profile=user_profile
            ).filter(
                Q(name_ru__icontains='прочие') | Q(name_ru__icontains='other') |
                Q(name_en__icontains='other') | Q(name__icontains='прочие') |
                Q(name__icontains='other')
            ).first()

            if not other_category:
                # Создаем категорию "Прочие расходы" если её нет
                lang = user_profile.language_code or 'ru'

                if not dry_run:
                    other_category = ExpenseCategory.objects.create(
                        profile=user_profile,
                        name="💰 Прочие расходы" if lang == 'ru' else "💰 Other Expenses",
                        name_ru="Прочие расходы" if lang == 'ru' else None,
                        name_en="Other Expenses" if lang == 'en' else None,
                        original_language=lang,
                        is_translatable=True,
                        icon='💰',
                        is_active=True
                    )

            if not dry_run and other_category:
                expense.category = other_category
                expense.save()

            moved_to_other_count += 1
            fixed_count += 1

    print()
    print("=" * 70)
    print("РЕЗУЛЬТАТЫ:")
    print("=" * 70)
    print(f"Всего найдено трат: {len(foreign_expenses)}")
    print(f"Исправлено: {fixed_count}")
    print(f"  - Переназначено на похожую категорию: {reassigned_count}")
    print(f"  - Перенесено в 'Прочие расходы': {moved_to_other_count}")
    print()

    if dry_run:
        print("⚠️  Это был тестовый прогон. Данные НЕ изменены.")
        print("Для применения изменений запустите:")
        print("python fix_expenses_with_foreign_categories.py --apply")
    else:
        print("✅ Траты успешно исправлены!")
        print()
        print("Проверка после исправления...")
        remaining = []
        for expense in Expense.objects.select_related('profile', 'category', 'category__profile').all():
            if expense.category is None:
                continue

            is_valid = False
            if expense.category.profile_id == expense.profile_id:
                is_valid = True
            elif (expense.profile.household_id is not None and
                  expense.category.profile.household_id is not None and
                  expense.profile.household_id == expense.category.profile.household_id):
                is_valid = True

            if not is_valid:
                remaining.append(expense)

        print(f"Осталось трат с чужими категориями: {len(remaining)}")


if __name__ == '__main__':
    import sys

    # Проверяем аргументы командной строки
    apply_changes = '--apply' in sys.argv

    if apply_changes:
        print("⚠️  РЕЖИМ ПРИМЕНЕНИЯ ИЗМЕНЕНИЙ")
        print()
        response = input("Вы уверены что хотите изменить данные? (yes/no): ")
        if response.lower() != 'yes':
            print("Отменено.")
            sys.exit(0)
        print()
        fix_expenses_with_foreign_categories(dry_run=False)
    else:
        # Тестовый прогон по умолчанию
        fix_expenses_with_foreign_categories(dry_run=True)
