"""
Test script for monthly insights generation
Tests insights for 2 specific users locally
"""
import os
import django
import sys
import asyncio
from datetime import datetime

# Fix encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile
from bot.services.monthly_insights import MonthlyInsightsService


async def test_insights_for_users():
    """Generate insights for 2 test users"""

    # Test users
    test_users = [
        7967547829,  # User 1
        881292737,   # User 2
    ]

    # Month to test (November 2025)
    year = 2025
    month = 11

    service = MonthlyInsightsService()

    print(f"\n{'='*60}")
    print(f"Testing Monthly Insights Generation")
    print(f"Month: {month}/{year}")
    print(f"Users: {test_users}")
    print(f"{'='*60}\n")

    for telegram_id in test_users:
        print(f"\n{'-'*60}")
        print(f"Processing user: {telegram_id}")
        print(f"{'-'*60}")

        try:
            # Get profile
            profile = await asyncio.to_thread(
                lambda: Profile.objects.get(telegram_id=telegram_id)
            )
            print(f"✅ Profile found: ID={profile.id}, Lang={profile.language_code}")

            # Generate insight
            print(f"🔄 Generating insights (provider=deepseek)...")
            insight = await service.generate_insight(
                profile=profile,
                year=year,
                month=month,
                provider='deepseek',  # Primary provider
                force_regenerate=True  # Force new generation
            )

            if insight:
                print(f"✅ Insight generated successfully!")
                print(f"   - Total expenses: {insight.total_expenses}")
                print(f"   - Total incomes: {insight.total_incomes}")
                print(f"   - Expenses count: {insight.expenses_count}")
                print(f"   - AI provider: {insight.ai_provider}")
                print(f"   - AI model: {insight.ai_model_used}")
                print(f"\n   📝 AI Summary:")
                print(f"   {insight.ai_summary[:200]}...")
                print(f"\n   📊 AI Analysis:")
                print(f"   {insight.ai_analysis[:200]}...")
            else:
                print(f"⚠️  No insight generated (not enough data or no subscription)")

        except Profile.DoesNotExist:
            print(f"❌ Profile not found for telegram_id={telegram_id}")
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print("Test completed!")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    asyncio.run(test_insights_for_users())
