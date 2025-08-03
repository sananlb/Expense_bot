#!/usr/bin/env python3
"""
Тест интеграции латиноамериканских валют
"""
import asyncio
import sys
import os
from decimal import Decimal

# Добавляем путь к проекту
sys.path.append(os.path.dirname(__file__))

from bot.services.currency_conversion import CurrencyConverter

async def test_latin_currencies():
    """Тест конвертации латиноамериканских валют"""
    print("🚀 Тестирование интеграции латиноамериканских валют")
    print("=" * 60)
    
    converter = CurrencyConverter()
    
    # Тестируемые валюты
    test_currencies = ['ARS', 'COP', 'PEN', 'CLP', 'MXN']
    test_amount = Decimal('100')
    
    print("📊 Получение курсов валют...")
    
    # Тест 1: Получение курсов через Fawaz API
    print("\n1. Тест Fawaz API:")
    fawaz_rates = await converter.fetch_fawaz_rates('rub')
    
    if fawaz_rates:
        print("✅ Fawaz API доступен")
        print(f"   Получено курсов: {len(fawaz_rates)}")
        
        # Проверяем латиноамериканские валюты
        latin_found = 0
        for currency in test_currencies:
            if currency in fawaz_rates:
                rate = fawaz_rates[currency]['unit_rate']
                print(f"   {currency}: {rate} ₽")
                latin_found += 1
            else:
                print(f"   ❌ {currency}: не найден")
        
        print(f"   Найдено латиноамериканских валют: {latin_found}/{len(test_currencies)}")
    else:
        print("❌ Fawaz API недоступен")
    
    # Тест 2: Тест общего метода с fallback
    print("\n2. Тест общего метода с fallback:")
    general_rates = await converter.fetch_daily_rates()
    
    if general_rates:
        print("✅ Получение курсов работает")
        print(f"   Получено курсов: {len(general_rates)}")
        
        latin_found = 0
        for currency in test_currencies:
            if currency in general_rates:
                rate = general_rates[currency]['unit_rate']
                print(f"   {currency}: {rate} ₽")
                latin_found += 1
            else:
                print(f"   ❌ {currency}: не найден")
        
        print(f"   Найдено латиноамериканских валют: {latin_found}/{len(test_currencies)}")
    else:
        print("❌ Получение курсов не работает")
    
    # Тест 3: Конвертация валют
    print("\n3. Тест конвертации валют:")
    print(f"   Конвертируем {test_amount} единиц каждой валюты в RUB...")
    
    for currency in test_currencies:
        try:
            converted = await converter.convert(test_amount, currency, 'RUB')
            if converted:
                print(f"   {test_amount} {currency} = {converted:.2f} ₽")
            else:
                print(f"   ❌ Не удалось конвертировать {currency}")
        except Exception as e:
            print(f"   ❌ Ошибка конвертации {currency}: {e}")
    
    # Тест 4: Список доступных валют
    print("\n4. Тест списка доступных валют:")
    available = await converter.get_available_currencies()
    latin_currencies = [(code, name) for code, name in available if code in test_currencies]
    
    print(f"   Всего доступных валют: {len(available)}")
    print("   Латиноамериканские валюты:")
    for code, name in latin_currencies:
        print(f"     {code}: {name}")
    
    # Тест 5: Прямая конвертация между латиноамериканскими валютами
    print("\n5. Тест конвертации между латиноамериканскими валютами:")
    try:
        # COP -> ARS
        cop_to_ars = await converter.convert(Decimal('1000'), 'COP', 'ARS')
        if cop_to_ars:
            print(f"   1000 COP = {cop_to_ars:.2f} ARS")
        
        # MXN -> PEN
        mxn_to_pen = await converter.convert(Decimal('100'), 'MXN', 'PEN')
        if mxn_to_pen:
            print(f"   100 MXN = {mxn_to_pen:.2f} PEN")
        
        # BRL -> CLP
        brl_to_clp = await converter.convert(Decimal('50'), 'BRL', 'CLP')
        if brl_to_clp:
            print(f"   50 BRL = {brl_to_clp:.2f} CLP")
            
    except Exception as e:
        print(f"   ❌ Ошибка межвалютной конвертации: {e}")
    
    # Завершение
    await converter.cleanup()
    
    print("\n" + "=" * 60)
    print("✅ Тестирование завершено!")

if __name__ == "__main__":
    asyncio.run(test_latin_currencies())