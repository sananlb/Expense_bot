#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Universal script to fix categories for all users
Combines multilingual field fixes and duplicate merging
Production-ready with comprehensive logging
"""

import os
import sys
import django
from pathlib import Path
from datetime import datetime
import logging
from typing import Dict, List, Tuple, Optional
import json

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Add project root to PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, ExpenseCategory, Expense, Cashback, Budget, IncomeCategory
from django.db import transaction
from django.db.models import Count, Sum, Q
from bot.utils.default_categories import UNIFIED_CATEGORIES

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('category_fix.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class CategoryFixer:
    """Universal category fixer for all users"""
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.stats = {
            'users_processed': 0,
            'users_fixed': 0,
            'categories_fixed': 0,
            'duplicates_merged': 0,
            'expenses_moved': 0,
            'cashbacks_moved': 0,
            'budgets_moved': 0,
            'empty_deleted': 0,
            'errors': []
        }
    
    def fix_multilingual_fields(self, profile: Profile, categories: list, local_stats: dict):
        """Fix missing multilingual fields in categories"""
        fixed_count = 0
        
        for cat in categories:
            updated = False
            
            # Skip system categories
            if cat.name and cat.name.startswith('_'):
                continue
            
            # Try to fill missing fields
            if not cat.name_ru or not cat.name_en:
                # Search in UNIFIED_CATEGORIES
                for unified_cat in UNIFIED_CATEGORIES:
                    # Match by any available field
                    if (cat.name and unified_cat['name'] == cat.name) or \
                       (cat.name_ru and unified_cat['name_ru'] == cat.name_ru) or \
                       (cat.name_en and unified_cat['name_en'] == cat.name_en):
                        
                        if not cat.name_ru and unified_cat.get('name_ru'):
                            cat.name_ru = unified_cat['name_ru']
                            updated = True
                        
                        if not cat.name_en and unified_cat.get('name_en'):
                            cat.name_en = unified_cat['name_en']
                            updated = True
                        
                        if not cat.icon and unified_cat.get('icon'):
                            cat.icon = unified_cat['icon']
                            updated = True
                        
                        break
                
                # If still missing, try to extract from name field
                if not updated and cat.name:
                    import re
                    # Remove emoji from name
                    clean_name = re.sub(r'[^\w\s\-]', '', cat.name, flags=re.UNICODE).strip()
                    
                    if clean_name:
                        # Check if it's English
                        if all(ord(c) < 128 for c in clean_name.replace(' ', '')):
                            if not cat.name_en:
                                cat.name_en = clean_name
                                updated = True
                        else:
                            if not cat.name_ru:
                                cat.name_ru = clean_name
                                updated = True
            
            if updated and not self.dry_run:
                cat.save()
                fixed_count += 1
                logger.debug(f"  Fixed category ID={cat.id}: name_ru='{cat.name_ru}', name_en='{cat.name_en}'")
        
        local_stats['fields_fixed'] = fixed_count
        return fixed_count
    
    def merge_duplicates(self, profile: Profile, local_stats: dict):
        """Merge duplicate categories and transfer all related data"""
        all_categories = profile.categories.filter(is_active=True)
        
        # Group by unique key (prioritize name_ru, then name_en)
        category_groups = {}
        
        for cat in all_categories:
            # Determine grouping key
            if cat.name_ru:
                key = cat.name_ru.lower().strip()
            elif cat.name_en:
                key = cat.name_en.lower().strip()
            elif cat.name:
                import re
                clean_name = re.sub(r'[^\w\s]', '', cat.name).strip().lower()
                key = clean_name if clean_name else f"unknown_{cat.id}"
            else:
                key = f"unknown_{cat.id}"
            
            if key not in category_groups:
                category_groups[key] = []
            category_groups[key].append(cat)
        
        merged_count = 0
        expenses_moved = 0
        cashbacks_moved = 0
        budgets_moved = 0
        
        for key, cats in category_groups.items():
            if len(cats) <= 1:
                continue
            
            # Select main category (prioritize: active, has expenses, complete data, oldest)
            main_cat = None
            max_score = -1
            
            for cat in cats:
                score = 0
                if cat.is_active:
                    score += 1000
                
                expense_count = Expense.objects.filter(profile=profile, category=cat).count()
                score += expense_count * 10
                
                if cat.name_ru and cat.name_en:
                    score += 100
                elif cat.name_ru or cat.name_en:
                    score += 50
                
                if cat.icon:
                    score += 5
                
                # Older = higher priority
                score -= cat.id * 0.001
                
                if score > max_score:
                    max_score = score
                    main_cat = cat
            
            # Merge duplicates into main
            for cat in cats:
                if cat.id == main_cat.id:
                    continue
                
                if not self.dry_run:
                    # Move expenses
                    moved = Expense.objects.filter(
                        profile=profile, category=cat
                    ).update(category=main_cat)
                    expenses_moved += moved
                    
                    # Move cashbacks
                    for cb in Cashback.objects.filter(profile=profile, category=cat):
                        existing = Cashback.objects.filter(
                            profile=profile,
                            category=main_cat,
                            month=cb.month
                        ).first()
                        
                        if existing:
                            if cb.cashback_percent > existing.cashback_percent:
                                existing.cashback_percent = cb.cashback_percent
                                existing.limit_amount = cb.limit_amount
                                existing.save()
                            cb.delete()
                        else:
                            cb.category = main_cat
                            cb.save()
                        cashbacks_moved += 1
                    
                    # Move budgets
                    for budget in Budget.objects.filter(profile=profile, category=cat):
                        existing = Budget.objects.filter(
                            profile=profile,
                            category=main_cat,
                            period_type=budget.period_type
                        ).first()
                        
                        if existing:
                            if budget.amount > existing.amount:
                                existing.amount = budget.amount
                                existing.save()
                            budget.delete()
                        else:
                            budget.category = main_cat
                            budget.save()
                        budgets_moved += 1
                    
                    # Delete duplicate
                    cat.delete()
                    merged_count += 1
                else:
                    # Dry run - just count
                    expenses_moved += Expense.objects.filter(profile=profile, category=cat).count()
                    cashbacks_moved += Cashback.objects.filter(profile=profile, category=cat).count()
                    budgets_moved += Budget.objects.filter(profile=profile, category=cat).count()
                    merged_count += 1
            
            # Update main category fields from duplicates
            if not self.dry_run:
                updated = False
                for cat in cats:
                    if cat.id != main_cat.id:
                        if not main_cat.name_ru and cat.name_ru:
                            main_cat.name_ru = cat.name_ru
                            updated = True
                        if not main_cat.name_en and cat.name_en:
                            main_cat.name_en = cat.name_en
                            updated = True
                        if not main_cat.icon and cat.icon:
                            main_cat.icon = cat.icon
                            updated = True
                
                if updated:
                    main_cat.save()
        
        local_stats['duplicates_merged'] = merged_count
        local_stats['expenses_moved'] = expenses_moved
        local_stats['cashbacks_moved'] = cashbacks_moved
        local_stats['budgets_moved'] = budgets_moved
        
        return merged_count
    
    def cleanup_empty_categories(self, profile: Profile, local_stats: dict):
        """Remove empty inactive categories"""
        empty_count = 0
        
        # Find empty inactive categories
        empty_categories = profile.categories.filter(
            is_active=False
        ).annotate(
            expense_count=Count('expenses'),
            cashback_count=Count('cashbacks'),
            budget_count=Count('budgets')
        ).filter(
            expense_count=0,
            cashback_count=0,
            budget_count=0
        )
        
        if not self.dry_run:
            empty_count = empty_categories.count()
            empty_categories.delete()
        else:
            empty_count = empty_categories.count()
        
        local_stats['empty_deleted'] = empty_count
        return empty_count
    
    def fix_user_categories(self, profile: Profile) -> dict:
        """Fix all category issues for a single user"""
        local_stats = {
            'fields_fixed': 0,
            'duplicates_merged': 0,
            'expenses_moved': 0,
            'cashbacks_moved': 0,
            'budgets_moved': 0,
            'empty_deleted': 0
        }
        
        try:
            with transaction.atomic():
                # Get all categories
                categories = list(profile.categories.all())
                
                if not categories:
                    return local_stats
                
                # Step 1: Fix multilingual fields
                self.fix_multilingual_fields(profile, categories, local_stats)
                
                # Step 2: Merge duplicates
                self.merge_duplicates(profile, local_stats)
                
                # Step 3: Cleanup empty categories
                self.cleanup_empty_categories(profile, local_stats)
                
                if self.dry_run:
                    # Rollback transaction in dry run mode
                    transaction.set_rollback(True)
            
            return local_stats
            
        except Exception as e:
            logger.error(f"Error fixing user {profile.telegram_id}: {e}")
            self.stats['errors'].append({
                'user': profile.telegram_id,
                'error': str(e)
            })
            return local_stats
    
    def process_all_users(self, specific_user: Optional[int] = None):
        """Process all users or a specific user"""
        logger.info("="*70)
        logger.info(f"CATEGORY FIX - {'DRY RUN' if self.dry_run else 'EXECUTE'} MODE")
        logger.info("="*70)
        
        # Get profiles to process
        if specific_user:
            profiles = Profile.objects.filter(telegram_id=specific_user)
            if not profiles.exists():
                logger.error(f"User {specific_user} not found")
                return
        else:
            # Process all active users (those with expenses in last 90 days)
            from datetime import timedelta
            from django.utils import timezone
            cutoff_date = timezone.now() - timedelta(days=90)
            
            profiles = Profile.objects.filter(
                Q(expenses__created_at__gte=cutoff_date) |
                Q(last_activity__gte=cutoff_date)
            ).distinct()
        
        total_profiles = profiles.count()
        logger.info(f"Found {total_profiles} profiles to process")
        
        for idx, profile in enumerate(profiles, 1):
            logger.info(f"\n[{idx}/{total_profiles}] Processing user {profile.telegram_id}")
            
            # Get initial state
            initial_categories = profile.categories.filter(is_active=True).count()
            initial_expenses = Expense.objects.filter(profile=profile).count()
            
            # Fix categories
            local_stats = self.fix_user_categories(profile)
            
            # Get final state
            final_categories = profile.categories.filter(is_active=True).count()
            
            # Update global stats
            self.stats['users_processed'] += 1
            if any(local_stats.values()):
                self.stats['users_fixed'] += 1
                self.stats['categories_fixed'] += local_stats['fields_fixed']
                self.stats['duplicates_merged'] += local_stats['duplicates_merged']
                self.stats['expenses_moved'] += local_stats['expenses_moved']
                self.stats['cashbacks_moved'] += local_stats['cashbacks_moved']
                self.stats['budgets_moved'] += local_stats['budgets_moved']
                self.stats['empty_deleted'] += local_stats['empty_deleted']
            
            # Log results
            if any(local_stats.values()):
                logger.info(f"  ✓ Fixed: fields={local_stats['fields_fixed']}, "
                          f"merged={local_stats['duplicates_merged']}, "
                          f"expenses_moved={local_stats['expenses_moved']}")
                logger.info(f"  Categories: {initial_categories} -> {final_categories}")
            else:
                logger.info(f"  - No issues found")
        
        # Print summary
        logger.info("\n" + "="*70)
        logger.info("SUMMARY")
        logger.info("="*70)
        logger.info(f"Users processed: {self.stats['users_processed']}")
        logger.info(f"Users with fixes: {self.stats['users_fixed']}")
        logger.info(f"Categories fixed: {self.stats['categories_fixed']}")
        logger.info(f"Duplicates merged: {self.stats['duplicates_merged']}")
        logger.info(f"Expenses moved: {self.stats['expenses_moved']}")
        logger.info(f"Cashbacks moved: {self.stats['cashbacks_moved']}")
        logger.info(f"Budgets moved: {self.stats['budgets_moved']}")
        logger.info(f"Empty categories deleted: {self.stats['empty_deleted']}")
        
        if self.stats['errors']:
            logger.warning(f"\nErrors encountered: {len(self.stats['errors'])}")
            for error in self.stats['errors'][:5]:
                logger.warning(f"  User {error['user']}: {error['error']}")
        
        if self.dry_run:
            logger.info("\n⚠️  This was a DRY RUN. No changes were made.")
            logger.info("To execute changes, run with --execute flag")
        else:
            logger.info("\n✅ All categories have been fixed successfully!")
            
            # Save detailed report
            report_file = f"category_fix_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
            logger.info(f"Detailed report saved to {report_file}")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix categories for all users')
    parser.add_argument('telegram_id', type=int, nargs='?',
                        help='Specific user Telegram ID (optional)')
    parser.add_argument('--execute', action='store_true',
                        help='Execute changes (default is dry run)')
    parser.add_argument('--verbose', action='store_true',
                        help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    fixer = CategoryFixer(dry_run=not args.execute)
    fixer.process_all_users(specific_user=args.telegram_id)
    
    return 0 if not fixer.stats['errors'] else 1


if __name__ == "__main__":
    exit(main())