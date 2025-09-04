# Generated manually 2025-09-03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('expenses', '0022_add_income_support_to_recurring_payments'),
    ]

    operations = [
        # Индексы для Profile
        migrations.AddIndex(
            model_name='profile',
            index=models.Index(fields=['telegram_id'], name='idx_profile_telegram_id'),
        ),
        
        # Индексы для Expense
        migrations.AddIndex(
            model_name='expense',
            index=models.Index(fields=['expense_date'], name='idx_expense_date'),
        ),
        migrations.AddIndex(
            model_name='expense',
            index=models.Index(fields=['profile', 'expense_date'], name='idx_expense_profile_date'),
        ),
        migrations.AddIndex(
            model_name='expense',
            index=models.Index(fields=['profile', '-expense_date', '-expense_time'], name='idx_expense_profile_recent'),
        ),
        
        # Индексы для Income
        migrations.AddIndex(
            model_name='income',
            index=models.Index(fields=['income_date'], name='idx_income_date'),
        ),
        migrations.AddIndex(
            model_name='income',
            index=models.Index(fields=['profile', 'income_date'], name='idx_income_profile_date'),
        ),
        migrations.AddIndex(
            model_name='income',
            index=models.Index(fields=['profile', '-income_date'], name='idx_income_profile_recent'),
        ),
        
        # Индексы для RecurringPayment
        migrations.AddIndex(
            model_name='recurringpayment',
            index=models.Index(fields=['day_of_month', 'is_active'], name='idx_recurring_day_active'),
        ),
        migrations.AddIndex(
            model_name='recurringpayment',
            index=models.Index(fields=['profile', 'is_active'], name='idx_recurring_profile_active'),
        ),
        
        # Индексы для ExpenseCategory
        migrations.AddIndex(
            model_name='expensecategory',
            index=models.Index(fields=['profile', 'is_active'], name='idx_category_profile_active'),
        ),
        
        # Индексы для IncomeCategory
        migrations.AddIndex(
            model_name='incomecategory',
            index=models.Index(fields=['profile', 'is_active'], name='idx_income_cat_profile_active'),
        ),
        
        # Индексы для Subscription
        migrations.AddIndex(
            model_name='subscription',
            index=models.Index(fields=['profile', 'is_active', 'end_date'], name='idx_sub_profile_active_end'),
        ),
        
        # Индексы для Cashback
        migrations.AddIndex(
            model_name='cashback',
            index=models.Index(fields=['profile', 'month'], name='idx_cashback_profile_month'),
        ),
    ]