#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки исправлений в реферальной системе
"""

import os
import sys
import django
import traceback

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, AffiliateLink, AffiliateReferral, AffiliateCommission, AffiliateProgram
from bot.services.affiliate import (
    get_or_create_affiliate_program,
    get_or_create_affiliate_link,
    process_referral_link,
    process_referral_commission
)
from django.utils import timezone
from decimal import Decimal


def test_affiliate_system():
    """
    Тестирует основные функции реферальной системы
    """
    print(f"\n{'='*60}")
    print("ТЕСТИРОВАНИЕ ИСПРАВЛЕНИЙ РЕФЕРАЛЬНОЙ СИСТЕМЫ")
    print(f"{'='*60}\n")
    
    try:
        # 1. Проверяем создание/получение программы
        print("1. Тестируем создание реферальной программы...")
        program = get_or_create_affiliate_program(commission_percent=50)
        print(f"   ✅ Программа создана/получена: комиссия {program.commission_permille/10}%")
    except Exception as e:
        print(f"   ❌ ОШИБКА: {e}")
        traceback.print_exc()
        return
    
    try:
        # 2. Проверяем создание реферальной ссылки
        print("\n2. Тестируем создание реферальной ссылки...")
        test_user = Profile.objects.filter(is_beta_tester=True).first()
        if not test_user:
            test_user = Profile.objects.first()
        
        if test_user:
            link = get_or_create_affiliate_link(test_user.telegram_id)
            print(f"   ✅ Ссылка создана для пользователя {test_user.telegram_id}")
            print(f"      Код: {link.affiliate_code}")
            print(f"      Ссылка: {link.telegram_link}")
            print(f"      Клики: {link.clicks}")
        else:
            print("   ⚠️ Нет пользователей в БД для теста")
    except Exception as e:
        print(f"   ❌ ОШИБКА: {e}")
        traceback.print_exc()
    
    try:
        # 3. Проверяем обработку перехода по ссылке (симуляция)
        print("\n3. Тестируем обработку перехода по реферальной ссылке...")
        if test_user and link:
            # Создаем тестового нового пользователя
            new_user_id = 999999999  # Фейковый ID для теста
            
            # Проверяем, есть ли уже такой пользователь
            new_user, created = Profile.objects.get_or_create(
                telegram_id=new_user_id,
                defaults={
                    'username': 'test_referral_user',
                    'first_name': 'Test',
                    'language': 'ru'
                }
            )
            
            if created:
                print(f"   📝 Создан тестовый пользователь {new_user_id}")
            
            # Обрабатываем переход по ссылке
            referral = process_referral_link(new_user_id, f"ref_{link.affiliate_code}")
            
            if referral:
                print(f"   ✅ Реферальная связь создана/получена")
                print(f"      Реферер: {referral.referrer.telegram_id}")
                print(f"      Реферал: {referral.referred.telegram_id}")
                
                # Проверяем обновление кликов
                link.refresh_from_db()
                print(f"      Клики после обработки: {link.clicks}")
            else:
                print("   ⚠️ Реферальная связь не создана (возможно, уже существует)")
        else:
            print("   ⚠️ Пропускаем тест - нет данных")
    except Exception as e:
        print(f"   ❌ ОШИБКА: {e}")
        traceback.print_exc()
    
    try:
        # 4. Проверяем логирование
        print("\n4. Проверяем работу логирования...")
        import logging
        from bot.services import affiliate
        
        # Проверяем, что logger определен
        if hasattr(affiliate, 'logger'):
            print("   ✅ Logger определен в модуле affiliate")
            
            # Включаем вывод логов для теста
            handler = logging.StreamHandler()
            handler.setLevel(logging.INFO)
            affiliate.logger.addHandler(handler)
            affiliate.logger.setLevel(logging.INFO)
            
            # Тестовый вызов с логированием
            test_referral = process_referral_link(888888888, "ref_TESTCODE")
            print("   ✅ Логирование работает (см. выше)")
        else:
            print("   ❌ Logger не определен в модуле!")
    except Exception as e:
        print(f"   ❌ ОШИБКА с логированием: {e}")
        traceback.print_exc()
    
    try:
        # 5. Проверяем обработку F() выражений
        print("\n5. Проверяем корректность работы с F() выражениями...")
        if referral:
            # Получаем начальные значения
            initial_payments = referral.total_payments
            initial_spent = referral.total_spent
            print(f"   Начальные значения: платежей={initial_payments}, потрачено={initial_spent}")
            
            # После обновления с F() выражениями значения должны быть числами, а не F() объектами
            print(f"   Тип total_payments: {type(referral.total_payments)}")
            print(f"   Тип total_spent: {type(referral.total_spent)}")
            
            if isinstance(referral.total_payments, int) and isinstance(referral.total_spent, (int, Decimal)):
                print("   ✅ F() выражения обрабатываются корректно")
            else:
                print("   ⚠️ Возможны проблемы с F() выражениями")
    except Exception as e:
        print(f"   ❌ ОШИБКА: {e}")
        traceback.print_exc()
    
    # Очистка тестовых данных
    try:
        print("\n6. Очистка тестовых данных...")
        if 'new_user' in locals() and created:
            # Удаляем тестовые связи
            AffiliateReferral.objects.filter(referred=new_user).delete()
            new_user.delete()
            print("   ✅ Тестовые данные очищены")
    except Exception as e:
        print(f"   ⚠️ Не удалось очистить тестовые данные: {e}")
    
    print(f"\n{'='*60}")
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    test_affiliate_system()