"""
Тестовый скрипт для проверки обновления кешбека при изменении категории
"""
import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from decimal import Decimal
from datetime import datetime
from django.utils import timezone
from expenses.models import Profile, Expense, ExpenseCategory, Cashback, Subscription
from bot.services.expense import update_expense
from bot.services.cashback import calculate_expense_cashback_sync


def test_cashback_update():
    """Тестирование обновления кешбека при изменении категории"""
    
    # Получаем тестового пользователя
    try:
        profile = Profile.objects.first()
        if not profile:
            print("[ERROR] Нет профилей в базе данных")
            return
        
        print(f"[OK] Используем профиль: {profile.telegram_id}")
        
        # Проверяем наличие подписки
        subscription = Subscription.objects.filter(
            profile=profile,
            is_active=True,
            end_date__gt=timezone.now()
        ).first()
        
        if not subscription:
            print("[WARNING] У пользователя нет активной подписки, создаем тестовую...")
            subscription = Subscription.objects.create(
                profile=profile,
                type='monthly',
                start_date=timezone.now(),
                end_date=timezone.now() + timezone.timedelta(days=30),
                is_active=True,
                price=Decimal('99')
            )
            print("[OK] Создана тестовая подписка")
        
        # Получаем или создаем категории
        cat1, _ = ExpenseCategory.objects.get_or_create(
            name="Продукты",
            profile=profile
        )
        cat2, _ = ExpenseCategory.objects.get_or_create(
            name="Транспорт",
            profile=profile
        )
        
        print(f"[OK] Категория 1: {cat1.name} (ID: {cat1.id})")
        print(f"[OK] Категория 2: {cat2.name} (ID: {cat2.id})")
        
        # Создаем кешбеки для разных категорий
        current_month = datetime.now().month
        
        # Кешбек для категории "Продукты" - 5%
        cashback1, created = Cashback.objects.get_or_create(
            profile=profile,
            category=cat1,
            month=current_month,
            defaults={
                'cashback_percent': Decimal('5.0'),
                'bank_name': 'Тестовый банк 1'
            }
        )
        if not created:
            cashback1.cashback_percent = Decimal('5.0')
            cashback1.save()
        
        # Кешбек для категории "Транспорт" - 10%
        cashback2, created = Cashback.objects.get_or_create(
            profile=profile,
            category=cat2,
            month=current_month,
            defaults={
                'cashback_percent': Decimal('10.0'),
                'bank_name': 'Тестовый банк 2'
            }
        )
        if not created:
            cashback2.cashback_percent = Decimal('10.0')
            cashback2.save()
        
        print(f"[OK] Кешбек для '{cat1.name}': {cashback1.cashback_percent}%")
        print(f"[OK] Кешбек для '{cat2.name}': {cashback2.cashback_percent}%")
        
        # Создаем тестовую трату
        expense = Expense.objects.create(
            profile=profile,
            amount=Decimal('1000'),
            category=cat1,
            description="Тестовая трата",
            created_at=timezone.now()
        )
        
        # Рассчитываем начальный кешбек
        initial_cashback = calculate_expense_cashback_sync(
            user_id=profile.telegram_id,
            category_id=cat1.id,
            amount=expense.amount,
            month=current_month
        )
        expense.cashback_amount = initial_cashback
        expense.save()
        
        print(f"\n[INFO] Создана трата:")
        print(f"   Сумма: {expense.amount} руб.")
        print(f"   Категория: {expense.category.name}")
        print(f"   Кешбек: {expense.cashback_amount} руб. ({cashback1.cashback_percent}%)")
        
        # Изменяем категорию траты
        print(f"\n[ACTION] Изменяем категорию с '{cat1.name}' на '{cat2.name}'...")
        
        success = update_expense(
            user_id=profile.telegram_id,
            expense_id=expense.id,
            category_id=cat2.id
        )
        
        if success:
            # Обновляем объект из базы
            expense.refresh_from_db()
            
            print(f"\n[OK] Категория изменена!")
            print(f"   Новая категория: {expense.category.name}")
            print(f"   Новый кешбек: {expense.cashback_amount} руб. ({cashback2.cashback_percent}%)")
            
            # Проверяем корректность пересчета
            expected_cashback = expense.amount * (cashback2.cashback_percent / 100)
            if abs(expense.cashback_amount - expected_cashback) < Decimal('0.01'):
                print(f"\n[SUCCESS] ТЕСТ ПРОЙДЕН! Кешбек корректно пересчитан")
            else:
                print(f"\n[FAILED] ТЕСТ НЕ ПРОЙДЕН! Ожидался кешбек: {expected_cashback}, получен: {expense.cashback_amount}")
        else:
            print("[ERROR] Не удалось обновить трату")
        
        # Удаляем тестовые данные
        print("\n[CLEANUP] Удаление тестовых данных...")
        expense.delete()
        if created:  # Удаляем только если создали в этом тесте
            subscription.delete()
        
    except Exception as e:
        print(f"[ERROR] Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print(">>> Запуск теста обновления кешбека при изменении категории...\n")
    test_cashback_update()
    print("\n>>> Тест завершен!")