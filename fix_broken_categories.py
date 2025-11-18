#\!/usr/bin/env python
# -*- coding: utf-8 -*-
import os, sys, django, re
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "expense_bot.settings")
django.setup()

from expenses.models import ExpenseCategory

STANDARD_CATEGORIES = {
    "Продукты": ("Продукты", "Groceries"),
    "Groceries": ("Продукты", "Groceries"),
    "Кафе и рестораны": ("Кафе и рестораны", "Cafes and Restaurants"),
    "Cafes and Restaurants": ("Кафе и рестораны", "Cafes and Restaurants"),
    "Транспорт": ("Транспорт", "Transport"),
    "Transport": ("Транспорт", "Transport"),
    "Автомобиль": ("Автомобиль", "Car"),
    "Car": ("Автомобиль", "Car"),
    "Жилье": ("Жилье", "Housing"),
    "Housing": ("Жилье", "Housing"),
    "Аптеки": ("Аптеки", "Pharmacies"),
    "Pharmacies": ("Аптеки", "Pharmacies"),
    "Медицина": ("Медицина", "Medicine"),
    "Medicine": ("Медицина", "Medicine"),
    "Красота": ("Красота", "Beauty"),
    "Beauty": ("Красота", "Beauty"),
    "Спорт и фитнес": ("Спорт и фитнес", "Sports and Fitness"),
    "Спорт": ("Спорт", "Sports and Fitness"),
    "Sports and Fitness": ("Спорт и фитнес", "Sports and Fitness"),
    "Одежда и обувь": ("Одежда и обувь", "Clothes and Shoes"),
    "Clothes and Shoes": ("Одежда и обувь", "Clothes and Shoes"),
    "Развлечения": ("Развлечения", "Entertainment"),
    "Entertainment": ("Развлечения", "Entertainment"),
    "Образование": ("Образование", "Education"),
    "Education": ("Образование", "Education"),
    "Подарки": ("Подарки", "Gifts"),
    "Gifts": ("Подарки", "Gifts"),
    "Путешествия": ("Путешествия", "Travel"),
    "Travel": ("Путешествия", "Travel"),
    "Коммуналка и подписки": ("Коммуналка и подписки", "Utilities and Subscriptions"),
    "Utilities and Subscriptions": ("Коммуналка и подписки", "Utilities and Subscriptions"),
    "АЗС": ("АЗС", "Gas Station"),
    "Заправка": ("Заправка", "Gas Stations"),
    "Gas Station": ("АЗС", "Gas Station"),
    "Gas Stations": ("Заправка", "Gas Stations"),
    "Прочие расходы": ("Прочие расходы", "Other Expenses"),
    "Other Expenses": ("Прочие расходы", "Other Expenses"),
}

EMOJI_RE = re.compile(r"[😀-🙏🌀-🗿🚀-🛿🇠-🇿☀-➿🤀-🧿🩰-🫿☀-⛿✀-➿‍\uFE00-\uFE0F]+", re.UNICODE)

def strip_emoji(text):
    return EMOJI_RE.sub("", text).strip()

def detect_language(text):
    clean = strip_emoji(text)
    return "ru" if re.search(r"[а-яА-ЯёЁ]", clean) else ("en" if re.search(r"[a-zA-Z]", clean) else None)

def fix_broken_categories(dry_run=True):
    print("=" * 80)
    print(f"MODE: {'DRY RUN' if dry_run else 'APPLY CHANGES'}")
    print("=" * 80)
    
    broken = ExpenseCategory.objects.filter(name_ru__isnull=True, name_en__isnull=True) | ExpenseCategory.objects.filter(name_ru="", name_en="")
    stats = {"total": broken.count(), "fixed": 0, "custom": 0, "errors": 0}

    print(f"\nFound broken categories: {stats['total']}\n")
    
    for cat in broken:
        try:
            clean_name = strip_emoji(cat.name)
            if clean_name in STANDARD_CATEGORIES:
                name_ru, name_en = STANDARD_CATEGORIES[clean_name]
                lang = detect_language(cat.name)

                if not dry_run:
                    cat.name_ru, cat.name_en = name_ru, name_en
                    cat.original_language = lang or cat.original_language
                    cat.is_translatable = True
                    cat.save()

                # Print after save (safe even if console encoding fails)
                try:
                    print(f"[FIX] ID={cat.id}: '{clean_name}' -> ru='{name_ru}', en='{name_en}'")
                except:
                    print(f"[FIX] ID={cat.id}: <encoding error>")

                stats["fixed"] += 1
            else:
                try:
                    print(f"[SKIP] ID={cat.id}: custom category '{clean_name}'")
                except:
                    print(f"[SKIP] ID={cat.id}: <encoding error>")
                stats["custom"] += 1
        except Exception as e:
            print(f"[ERROR] ID={cat.id}: {e}")
            stats["errors"] += 1
    
    print("\n" + "=" * 80)
    print(f"Total: {stats['total']}, Fixed: {stats['fixed']}, Skipped: {stats['custom']}, Errors: {stats['errors']}")
    print("=" * 80)

    if dry_run:
        print("\nDRY RUN MODE! To apply: python fix_broken_categories.py --apply")
    else:
        print("\nCHANGES APPLIED!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    fix_broken_categories(dry_run=not parser.parse_args().apply)
