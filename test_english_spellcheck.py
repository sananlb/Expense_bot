#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Testing English language support for expense categorization
"""
from bot.utils.expense_categorizer import correct_typos, categorize_expense, detect_language

def test_english_support():
    """Test English language detection and spell checking"""
    
    print("=" * 70)
    print("TESTING LANGUAGE DETECTION")
    print("=" * 70)
    
    test_texts = [
        ("кофе и вода", "ru"),
        ("coffee and water", "en"),
        ("такси до дома", "ru"),
        ("taxi to home", "en"),
        ("bread milk eggs", "en"),
        ("хлеб молоко яйца", "ru"),
    ]
    
    for text, expected_lang in test_texts:
        detected = detect_language(text)
        print(f"Text: {text}")
        print(f"Detected: {detected}, Expected: {expected_lang}")
        print(f"Status: {'OK' if detected == expected_lang else 'FAIL'}\n")
    
    print("=" * 70)
    print("TESTING ENGLISH SPELL CHECKING")
    print("=" * 70)
    
    typo_tests = [
        # (text with typos, expected correction)
        ("coffe and watter", "coffee and water"),
        ("groceris at store", "groceries at store"),
        ("taksi to home", "taxi to home"),
        ("medecine from farmacy", "medicine from pharmacy"),
        ("breckfast at cafe", "breakfast at cafe"),
        ("electrisity bill", "electricity bill"),
    ]
    
    for original, expected in typo_tests:
        corrected = correct_typos(original, language='en')
        print(f"Original: {original}")
        print(f"Corrected: {corrected}")
        print(f"Expected: {expected}")
        print(f"Status: {'OK' if corrected.lower() == expected.lower() else 'PARTIAL'}\n")
    
    print("=" * 70)
    print("TESTING ENGLISH CATEGORIZATION")
    print("=" * 70)
    
    expense_tests = [
        ("coffee and burger 15", "cafe"),
        ("groceries at walmart 150", "groceries"),
        ("uber to airport 45", "transport"),
        ("netflix subscription 12", "entertainment"),
        ("medicine at pharmacy 50", "health"),
        ("internet bill 60", "utilities"),
        ("shirt and shoes 120", "clothes"),
    ]
    
    for text, expected_category in expense_tests:
        category, confidence, corrected = categorize_expense(text, language='en')
        print(f"Input: {text}")
        print(f"Corrected: {corrected}")
        print(f"Category: {category}")
        print(f"Expected: {expected_category}")
        print(f"Confidence: {confidence:.2f}")
        print(f"Status: {'OK' if category == expected_category else 'FAIL'}\n")

if __name__ == "__main__":
    test_english_support()