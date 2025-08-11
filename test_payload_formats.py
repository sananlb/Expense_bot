"""
Тестирование форматов payload для платежей
"""

# Примеры payload из кода
payloads = [
    # Обычная покупка (из строки 190)
    "subscription_monthly_123456789",
    "subscription_yearly_123456789",
    "subscription_lifetime_123456789",
    
    # С промокодом (из строки 480)
    "subscription_monthly_123456789_promo_5",
    "subscription_yearly_123456789_promo_10",
]

print("Проверка форматов payload:")
print("-" * 50)

for payload in payloads:
    parts = payload.split("_")
    print(f"\nPayload: {payload}")
    print(f"Частей: {len(parts)}")
    print(f"Части: {parts}")
    
    # Старая проверка (с ошибкой)
    old_check = len(parts) >= 4 and parts[0] == "subscription"
    # Новая проверка (исправленная)
    new_check = len(parts) >= 3 and parts[0] == "subscription"
    
    print(f"Старая проверка (>= 4 части): {'PASS' if old_check else 'FAIL'}")
    print(f"Новая проверка (>= 3 части): {'PASS' if new_check else 'FAIL'}")

print("\n" + "=" * 50)
print("ВЫВОД: Проблема была в том, что проверка требовала минимум 4 части,")
print("но обычная покупка без промокода создает только 3 части:")
print("subscription_TYPE_USER_ID")
print("\nИсправление: изменили проверку с >= 4 на >= 3")