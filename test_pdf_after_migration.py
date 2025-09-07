#!/usr/bin/env python
"""
Test PDF generation after migrations
"""
import os
import sys
import django
from datetime import datetime, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath('.')))
django.setup()

from expenses.models import Profile, Expense, Income, ExpenseCategory, IncomeCategory
from bot.services.pdf_report import PDFReportService
import tempfile
import asyncio
from asgiref.sync import sync_to_async

async def test_pdf_generation():
    """Test PDF generation with migrated data"""
    
    # Get a test user
    profile = await sync_to_async(Profile.objects.filter(expenses__isnull=False).first)()
    if not profile:
        print("No user with expenses found")
        return
    
    print(f"Testing PDF generation for user: {profile.telegram_id}")
    
    # Check if user has data
    expenses_count = await sync_to_async(Expense.objects.filter(profile=profile).count)()
    incomes_count = await sync_to_async(Income.objects.filter(profile=profile).count)()
    print(f"User has {expenses_count} expenses and {incomes_count} incomes")
    
    # Check categories
    expense_cats = await sync_to_async(ExpenseCategory.objects.filter(profile=profile).count)()
    income_cats = await sync_to_async(IncomeCategory.objects.filter(profile=profile).count)()
    print(f"User has {expense_cats} expense categories and {income_cats} income categories")
    
    # Sample category data
    if expense_cats > 0:
        cat = await sync_to_async(ExpenseCategory.objects.filter(profile=profile).first)()
        print(f"\nSample expense category:")
        print(f"  name_ru: {cat.name_ru}")
        print(f"  name_en: {cat.name_en}")
        print(f"  original_language: {cat.original_language}")
    
    if income_cats > 0:
        cat = await sync_to_async(IncomeCategory.objects.filter(profile=profile).first)()
        print(f"\nSample income category:")
        print(f"  name_ru: {cat.name_ru}")
        print(f"  name_en: {cat.name_en}")
        print(f"  original_language: {cat.original_language}")
    
    # Try to generate PDF
    print("\nGenerating PDF report...")
    try:
        # Generate for current month
        service = PDFReportService()
        year = datetime.now().year
        month = datetime.now().month
        
        pdf_bytes = await service.generate_monthly_report(
            user_id=profile.telegram_id,
            year=year,
            month=month
        )
        
        if pdf_bytes:
            print(f"✅ PDF generated successfully!")
            print(f"   Size: {len(pdf_bytes)} bytes")
        else:
            print("❌ PDF generation failed - no data returned")
            
    except Exception as e:
        print(f"❌ Error generating PDF: {e}")
        import traceback
        traceback.print_exc()
    
    print("\nTest completed!")

if __name__ == '__main__':
    asyncio.run(test_pdf_generation())