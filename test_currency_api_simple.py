#!/usr/bin/env python3
"""
Простой тест API валют без Django зависимостей
"""
import asyncio
import aiohttp
import json
from decimal import Decimal

async def test_fawaz_api():
    """Прямой тест Fawaz API для латиноамериканских валют"""
    print("Тестирование Fawaz Currency API")
    print("=" * 60)
    
    url = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/rub.json"
    
    # Тестируемые валюты
    test_currencies = ['ars', 'cop', 'pen', 'clp', 'mxn', 'brl']
    
    async with aiohttp.ClientSession() as session:
        try:
            print(f"Запрос к API: {url}")
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    print("API доступен")
                    data = await response.json()
                    
                    if 'rub' in data:
                        rates = data['rub']
                        print(f"Получено курсов: {len(rates)}")
                        print()
                        
                        print("Латиноамериканские валюты к рублю:")
                        print("-" * 40)
                        
                        found = 0
                        for currency in test_currencies:
                            if currency in rates:
                                rate = rates[currency]
                                print(f"   {currency.upper()}: {rate:.6f} руб")
                                found += 1
                            else:
                                print(f"   X {currency.upper()}: не найден")
                        
                        print(f"\nНайдено: {found}/{len(test_currencies)} валют")
                        
                        # Примеры конвертации
                        print("\nПримеры конвертации (1 единица валюты в рубли):")
                        print("-" * 50)
                        
                        examples = {
                            'ars': 'Аргентинское песо',
                            'cop': 'Колумбийское песо', 
                            'pen': 'Перуанский соль',
                            'clp': 'Чилийское песо',
                            'mxn': 'Мексиканское песо',
                            'brl': 'Бразильский реал'
                        }
                        
                        for currency, name in examples.items():
                            if currency in rates:
                                rate = rates[currency]
                                print(f"   1 {name} = {rate:.4f} руб")
                        
                        # Обратная конвертация - сколько валюты за 1000 рублей
                        print("\nОбратная конвертация (за 1000 руб):")
                        print("-" * 40)
                        
                        for currency, name in examples.items():
                            if currency in rates:
                                rate = rates[currency]
                                if rate > 0:
                                    reverse_rate = 1000 / rate
                                    print(f"   1000 руб = {reverse_rate:.2f} {currency.upper()}")
                        
                        # Тест конвертации между латиноамериканскими валютами
                        print("\nМежвалютная конвертация:")
                        print("-" * 30)
                        
                        if 'cop' in rates and 'ars' in rates and rates['cop'] > 0 and rates['ars'] > 0:
                            # 1000 COP в ARS
                            cop_rate = rates['cop']  # COP к рублю
                            ars_rate = rates['ars']  # ARS к рублю
                            
                            cop_to_rub = 1000 * cop_rate  # 1000 COP в рубли
                            rub_to_ars = cop_to_rub / ars_rate  # рубли в ARS
                            
                            print(f"   1000 COP = {rub_to_ars:.2f} ARS")
                        
                        if 'mxn' in rates and 'brl' in rates and rates['mxn'] > 0 and rates['brl'] > 0:
                            # 100 MXN в BRL
                            mxn_rate = rates['mxn']
                            brl_rate = rates['brl']
                            
                            mxn_to_rub = 100 * mxn_rate
                            rub_to_brl = mxn_to_rub / brl_rate
                            
                            print(f"   100 MXN = {rub_to_brl:.2f} BRL")
                        
                    else:
                        print("X Неверный формат ответа API")
                else:
                    print(f"X Ошибка API: {response.status}")
                    
        except asyncio.TimeoutError:
            print("X Таймаут при запросе к API")
        except Exception as e:
            print(f"X Ошибка: {e}")
    
    print("\n" + "=" * 60)
    print("Тестирование завершено!")

async def test_additional_apis():
    """Тест дополнительных API для сравнения"""
    print("\nТестирование дополнительных API")
    print("=" * 40)
    
    # ExchangeRate-API (бесплатный план)
    exchangerate_url = "https://api.exchangerate-api.com/v4/latest/RUB"
    
    async with aiohttp.ClientSession() as session:
        try:
            print("Тест ExchangeRate-API...")
            async with session.get(exchangerate_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    rates = data.get('rates', {})
                    
                    test_currencies = ['ARS', 'COP', 'PEN', 'CLP', 'MXN', 'BRL']
                    found = sum(1 for curr in test_currencies if curr in rates)
                    
                    print(f"   Доступен, найдено {found}/{len(test_currencies)} валют")
                    
                    for curr in test_currencies:
                        if curr in rates:
                            print(f"     {curr}: {rates[curr]:.6f}")
                else:
                    print(f"   X Ошибка: {response.status}")
        except Exception as e:
            print(f"   X Недоступен: {e}")

if __name__ == "__main__":
    asyncio.run(test_fawaz_api())
    asyncio.run(test_additional_apis())