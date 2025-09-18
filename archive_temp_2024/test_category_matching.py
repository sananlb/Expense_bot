#!/usr/bin/env python3
"""
Тест поиска категорий для понимания проблемы с "подарки"
"""
import re
from typing import Set

def _normalize_letters(s: str) -> str:
    return (
        s.lower()
        .replace('ё', 'е')
        .replace('э', 'е')
        .replace('-', '')
    )

def tokenize(s: str) -> Set[str]:
    s = _normalize_letters(s)
    toks = re.findall(r"[\wа-яА-Я]+", s)
    stop = {"и", "в", "на", "по"}
    return {t for t in toks if t and t not in stop}

def test_category_matching():
    # Реальные категории из базы
    categories = [
        "🎁 Gifts",
        "🎭 Entertainment", 
        "🍽️ Кафе и рестораны",
        "💰 Прочие расходы",
        "🛒 Products"
    ]
    
    # Поисковые запросы
    searches = [
        "подарки",
        "Подарки",
        "подарок",
        "gifts",
        "кафе",
        "кафе и рестораны",
        "рестораны",
        "продукты",
        "products"
    ]
    
    print("=== Тест поиска категорий ===\n")
    
    print("📋 Доступные категории:")
    for i, cat in enumerate(categories, 1):
        tokens = tokenize(cat)
        print(f"{i}. '{cat}' -> токены: {tokens}")
    print()
    
    print("🔍 Результаты поиска:")
    
    for search in searches:
        print(f"\n🔎 Поиск: '{search}'")
        search_tokens = tokenize(search)
        print(f"   Токены поиска: {search_tokens}")
        
        found = None
        
        # Метод 1: поиск подмножества токенов
        for cat in categories:
            cat_tokens = tokenize(cat)
            if search_tokens.issubset(cat_tokens):
                found = cat
                print(f"   ✅ Найдено (токены): '{cat}'")
                break
        
        if not found:
            # Метод 2: точное соответствие нормализованных названий
            search_norm = _normalize_letters(search.strip())
            for cat in categories:
                cleaned = _normalize_letters(re.sub(r"^[^\wа-яА-ЯёЁ]+", "", cat).strip())
                if cleaned == search_norm:
                    found = cat
                    print(f"   ✅ Найдено (точное): '{cat}' ('{cleaned}' == '{search_norm}')")
                    break
        
        if not found:
            print(f"   ❌ НЕ НАЙДЕНО")
            
            # Показываем почему не найдено
            print(f"      Причина: токены '{search_tokens}' не являются подмножеством ни одной категории")
            print(f"      И нет точного совпадения для '{_normalize_letters(search)}'")

if __name__ == "__main__":
    test_category_matching()