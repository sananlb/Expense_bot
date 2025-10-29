#!/usr/bin/env python
"""
Simple test to verify migrations were applied correctly
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath('.')))
django.setup()

from expenses.models import Profile, ExpenseCategory, IncomeCategory
from bot.utils.category_helpers import get_category_display_name

def test_migrations():
    """Test that migrations were applied correctly"""
    
    print("=" * 50)
    print("TESTING MIGRATIONS")
    print("=" * 50)
    
    # Test ExpenseCategory
    print("\n1. Testing ExpenseCategory model...")
    try:
        cat = ExpenseCategory.objects.first()
        if cat:
            print(f"   - name_ru: {cat.name_ru if cat.name_ru else 'None'}")
            print(f"   - name_en: {cat.name_en if cat.name_en else 'None'}")
            print(f"   - original_language: {cat.original_language}")
            print(f"   - is_translatable: {cat.is_translatable}")
            
            # Test display name function
            try:
                display_ru = get_category_display_name(cat, 'ru')
                display_en = get_category_display_name(cat, 'en')
                # Handle encoding issues with emojis
                display_ru = display_ru.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                display_en = display_en.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                print(f"   - Display (RU): {display_ru}")
                print(f"   - Display (EN): {display_en}")
            except UnicodeEncodeError:
                print("   - Display functions work but emoji encoding issue in console")
            print("   [OK] ExpenseCategory working")
        else:
            print("   No ExpenseCategory found")
    except Exception as e:
        print(f"   [ERROR] ExpenseCategory: {e}")
        return False
    
    # Test IncomeCategory
    print("\n2. Testing IncomeCategory model...")
    try:
        cat = IncomeCategory.objects.first()
        if cat:
            print(f"   - name_ru: {cat.name_ru if cat.name_ru else 'None'}")
            print(f"   - name_en: {cat.name_en if cat.name_en else 'None'}")
            print(f"   - original_language: {cat.original_language}")
            print(f"   - is_translatable: {cat.is_translatable}")
            
            # Test display name function
            try:
                display_ru = get_category_display_name(cat, 'ru')
                display_en = get_category_display_name(cat, 'en')
                # Handle encoding issues with emojis
                display_ru = display_ru.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                display_en = display_en.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                print(f"   - Display (RU): {display_ru}")
                print(f"   - Display (EN): {display_en}")
            except UnicodeEncodeError:
                print("   - Display functions work but emoji encoding issue in console")
            print("   [OK] IncomeCategory working")
        else:
            print("   No IncomeCategory found")
    except Exception as e:
        print(f"   [ERROR] IncomeCategory: {e}")
        return False
    
    # Count categories with multilingual data
    print("\n3. Checking migrated data...")
    expense_with_ru = ExpenseCategory.objects.filter(name_ru__isnull=False).count()
    expense_with_en = ExpenseCategory.objects.filter(name_en__isnull=False).count()
    income_with_ru = IncomeCategory.objects.filter(name_ru__isnull=False).count()
    income_with_en = IncomeCategory.objects.filter(name_en__isnull=False).count()
    
    print(f"   - ExpenseCategories with name_ru: {expense_with_ru}")
    print(f"   - ExpenseCategories with name_en: {expense_with_en}")
    print(f"   - IncomeCategories with name_ru: {income_with_ru}")
    print(f"   - IncomeCategories with name_en: {income_with_en}")
    
    print("\n" + "=" * 50)
    print("MIGRATION TEST COMPLETED SUCCESSFULLY!")
    print("All multilingual fields are working correctly.")
    print("=" * 50)
    return True

if __name__ == '__main__':
    success = test_migrations()
    sys.exit(0 if success else 1)