#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест: классификатор сообщений record/chat
"""

import os
import sys
import django
import io

# Настройка кодировки для Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.utils.text_classifier import classify_message, get_expense_indicators

test_cases = [
    # Явные траты
    "огурец",
    "молоко",
    "красная икра",
    "вкусный торт",
    "кофе",
    "такси",
    "бензин 95",
    
    # Траты с глаголами
    "купил хлеб",
    "заплатил за интернет",
    "оплатил парковку",
    
    # Вопросы - должны быть chat
    "сколько я потратил?",
    "что купить?",
    "огурец?",
    "кофе?",
    
    # Приветствия и обращения - chat
    "привет",
    "спасибо",
    "помоги мне",
    
    # Команды - chat
    "покажи отчет",
    "настройки",
    "статистика за месяц",
    
    # Сложные случаи
    "вчера купил молоко",
    "нужно купить хлеб",
    "хочу кофе",
    "платная дорога",
    
    # Длинные предложения
    "сегодня я ходил в магазин и купил продукты",
    "расскажи мне о моих тратах за неделю",
]

print("=" * 80)
print("ТЕСТ КЛАССИФИКАТОРА СООБЩЕНИЙ")
print("=" * 80)

for text in test_cases:
    msg_type, confidence = classify_message(text)
    indicators = get_expense_indicators(text) if msg_type == 'record' else []
    
    emoji = "💰" if msg_type == "record" else "💬"
    print(f"\n{emoji} '{text}'")
    print(f"   Тип: {msg_type} (уверенность: {confidence:.0%})")
    if indicators:
        print(f"   Индикаторы: {', '.join(indicators)}")