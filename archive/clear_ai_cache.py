#!/usr/bin/env python
"""Очистка кэша AI сервисов"""
import os
import sys
import django

# Добавляем корневую директорию проекта в путь Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

# Теперь можем импортировать и использовать модули
from bot.services.ai_selector import AISelector

if __name__ == "__main__":
    AISelector.clear_cache()
    print("✅ AI service cache cleared successfully")