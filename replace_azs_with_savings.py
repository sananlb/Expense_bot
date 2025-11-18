"""
Скрипт для замены категории АЗС на Накопления для пользователей без трат по АЗС.

Логика:
1. Находим всех пользователей с категорией АЗС/Gas Station
2. Проверяем есть ли у них траты по этой категории
3. Если трат НЕТ:
   - Удаляем категорию АЗС
   - Создаем категорию "Накопления" (если её ещё нет)
4. Если траты ЕСТЬ - не трогаем пользователя
"""

import os
import sys
import django
from datetime import datetime

# Настройка Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from django.db import transaction
from expenses.models import ExpenseCategory, Expense, RecurringPayment
import re


def clean_emoji(text):
    """Remove emojis from text for console output"""
    # Remove emoji characters
    emoji_pattern = re.compile("["
                               u"\U0001F600-\U0001F64F"  # emoticons
                               u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                               u"\U0001F680-\U0001F6FF"  # transport & map symbols
                               u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                               u"\U00002702-\U000027B0"
                               u"\U000024C2-\U0001F251"
                               "]+", flags=re.UNICODE)
    return emoji_pattern.sub('', text).strip()


def find_azs_categories():
    """Найти все категории АЗС/Gas Station"""
    categories = ExpenseCategory.objects.filter(
        name__icontains='gas'
    ) | ExpenseCategory.objects.filter(
        name_ru__icontains='gas'
    ) | ExpenseCategory.objects.filter(
        name_en__icontains='gas'
    ) | ExpenseCategory.objects.filter(
        name__icontains='азс'
    ) | ExpenseCategory.objects.filter(
        name_ru__icontains='азс'
    )

    return categories.distinct()


def analyze_azs_usage():
    """Анализ использования категорий АЗС"""
    azs_categories = find_azs_categories()

    print(f"\n{'='*80}")
    print(f"АНАЛИЗ КАТЕГОРИЙ АЗС/GAS STATION")
    print(f"{'='*80}\n")

    total_categories = azs_categories.count()
    print(f"Total AZS categories found: {total_categories}")

    # Группируем по профилям
    users_with_expenses = []
    users_without_expenses = []

    for category in azs_categories:
        expense_count = Expense.objects.filter(category=category).count()
        recurring_count = RecurringPayment.objects.filter(expense_category=category).count()

        user_info = {
            'profile_id': category.profile_id,
            'category_id': category.id,
            'category_name': category.name,
            'expense_count': expense_count,
            'recurring_count': recurring_count,
        }

        if expense_count > 0 or recurring_count > 0:
            users_with_expenses.append(user_info)
        else:
            users_without_expenses.append(user_info)

    print(f"\nUsers WITH AZS expenses: {len(users_with_expenses)}")
    if users_with_expenses:
        print("\n   Details:")
        for user in users_with_expenses:
            clean_name = clean_emoji(user['category_name'])
            print(f"   - Profile {user['profile_id']}: category '{clean_name}' "
                  f"(expenses: {user['expense_count']}, recurring: {user['recurring_count']})")

    print(f"\nUsers WITHOUT AZS expenses: {len(users_without_expenses)}")
    if len(users_without_expenses) > 0:
        print(f"   First 10: {[u['profile_id'] for u in users_without_expenses[:10]]}")

    return users_with_expenses, users_without_expenses


def replace_azs_with_savings(dry_run=True):
    """
    Заменить категорию АЗС на Накопления для пользователей без трат

    Args:
        dry_run: Если True, только показывает что будет сделано без изменений
    """
    users_with_expenses, users_without_expenses = analyze_azs_usage()

    if not users_without_expenses:
        print("\nAll users use AZS category. Nothing to do.")
        return

    print(f"\n{'='*80}")
    print(f"ZAMENA KATEGORIY AZS -> NAKOPLENIYA")
    print(f"{'='*80}\n")

    if dry_run:
        print("WARNING: DRY-RUN MODE (no changes will be applied)")
        print("   To apply changes run: python replace_azs_with_savings.py --apply\n")
    else:
        print("APPLY MODE: Changes WILL be applied\n")

    changes = []

    for user in users_without_expenses:
        profile_id = user['profile_id']
        azs_category_id = user['category_id']
        azs_category_name = user['category_name']

        # Проверяем есть ли уже категория "Накопления"
        existing_savings = ExpenseCategory.objects.filter(
            profile_id=profile_id,
            name_ru='Накопления'
        ).first()

        if not existing_savings:
            existing_savings = ExpenseCategory.objects.filter(
                profile_id=profile_id,
                name_en='Savings'
            ).first()

        change = {
            'profile_id': profile_id,
            'azs_category_id': azs_category_id,
            'azs_category_name': azs_category_name,
            'has_savings': existing_savings is not None,
            'savings_category_id': existing_savings.id if existing_savings else None,
        }
        changes.append(change)

    print(f"Users to process: {len(changes)}\n")

    # Группируем по действиям
    to_delete_only = [c for c in changes if c['has_savings']]
    to_create_and_delete = [c for c in changes if not c['has_savings']]

    print(f"Actions:")
    print(f"   - Delete AZS only (already has Savings): {len(to_delete_only)}")
    print(f"   - Create Savings + delete AZS: {len(to_create_and_delete)}")

    if not dry_run:
        with transaction.atomic():
            created_count = 0
            deleted_count = 0

            for change in changes:
                profile_id = change['profile_id']
                azs_category_id = change['azs_category_id']

                # Создаём "Накопления" если нужно
                if not change['has_savings']:
                    from expenses.models import Profile
                    profile = Profile.objects.get(id=profile_id)
                    lang = profile.language_code or 'ru'

                    savings = ExpenseCategory.objects.create(
                        profile=profile,
                        name='💎 Накопления' if lang == 'ru' else '💎 Savings',
                        name_ru='Накопления',
                        name_en='Savings',
                        icon='💎',
                        original_language=lang,
                        is_translatable=True,
                        is_active=True
                    )
                    created_count += 1
                    print(f"   [OK] Profile {profile_id}: created 'Savings' category (ID: {savings.id})")

                # Удаляем АЗС
                ExpenseCategory.objects.filter(id=azs_category_id).delete()
                deleted_count += 1
                print(f"   [DEL] Profile {profile_id}: deleted AZS category (ID: {azs_category_id})")

            print(f"\n[DONE] Completed!")
            print(f"   - Created 'Savings' categories: {created_count}")
            print(f"   - Deleted 'AZS' categories: {deleted_count}")
    else:
        print("\n[DRY-RUN] Changes NOT applied")
        print("   To apply run: python replace_azs_with_savings.py --apply")

    return changes


if __name__ == '__main__':
    import sys

    # Проверяем аргументы
    dry_run = '--apply' not in sys.argv

    print(f"\n{'='*80}")
    print(f"SCRIPT: REPLACE AZS -> SAVINGS CATEGORIES")
    print(f"Start date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}")

    try:
        replace_azs_with_savings(dry_run=dry_run)
    except Exception as e:
        print(f"\n[ERROR]: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print(f"\n{'='*80}\n")
