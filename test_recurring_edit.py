"""
Test script for recurring payments edit functionality
"""
import asyncio
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.services.recurring import (
    get_user_recurring_payments, 
    create_recurring_payment,
    get_recurring_payment_by_id,
    update_recurring_payment,
    delete_recurring_payment
)
from bot.services.category import get_user_categories


async def test_recurring_edit():
    """Test recurring payment edit functionality"""
    # Test user ID (replace with your actual telegram ID)
    user_id = 123456789  # Replace with your actual ID
    
    print("\n=== Testing Recurring Payments Edit ===\n")
    
    # 1. Get user categories
    categories = await get_user_categories(user_id)
    if not categories:
        print("❌ No categories found. Please create some categories first.")
        return
    
    # Use first category for testing
    test_category = categories[0]
    print(f"✅ Using category: {test_category.name}")
    
    # 2. Create a test recurring payment
    payment = await create_recurring_payment(
        user_id=user_id,
        category_id=test_category.id,
        amount=5000,
        description="Test Payment",
        day_of_month=15
    )
    print(f"✅ Created test payment: {payment.description} - {payment.amount} ₽")
    
    # 3. Test getting payment by ID
    fetched_payment = await get_recurring_payment_by_id(user_id, payment.id)
    if fetched_payment:
        print(f"✅ Successfully fetched payment by ID")
    else:
        print(f"❌ Failed to fetch payment by ID")
    
    # 4. Test updating payment status
    updated = await update_recurring_payment(user_id, payment.id, is_active=False)
    if updated:
        print(f"✅ Successfully updated payment status to inactive")
    else:
        print(f"❌ Failed to update payment status")
    
    # 5. Get all payments to verify
    all_payments = await get_user_recurring_payments(user_id)
    print(f"\n📋 All recurring payments for user {user_id}:")
    for p in all_payments:
        status = "✅" if p.is_active else "⏸"
        print(f"  {status} {p.description} - {p.amount} ₽ - {p.category.name} - Day {p.day_of_month}")
    
    # 6. Clean up - delete test payment
    deleted = await delete_recurring_payment(user_id, payment.id)
    if deleted:
        print(f"\n✅ Successfully deleted test payment")
    else:
        print(f"\n❌ Failed to delete test payment")
    
    print("\n=== Test Complete ===")


if __name__ == "__main__":
    asyncio.run(test_recurring_edit())