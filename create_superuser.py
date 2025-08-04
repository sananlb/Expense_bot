#!/usr/bin/env python
"""
Скрипт для создания суперпользователя Django
"""
import os
import sys
import django

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Проверяем, есть ли уже суперпользователь
if User.objects.filter(is_superuser=True).exists():
    print("Суперпользователь уже существует!")
    admin = User.objects.filter(is_superuser=True).first()
    print(f"Username: {admin.username}")
else:
    # Создаем суперпользователя
    username = 'admin'
    email = 'admin@expensebot.com'
    password = 'admin123'
    
    User.objects.create_superuser(
        username=username,
        email=email,
        password=password
    )
    
    print(f"Суперпользователь создан!")
    print(f"Username: {username}")
    print(f"Password: {password}")
    print(f"Email: {email}")

print("\nДля доступа к админке:")
print("1. Запустите сервер: python manage.py runserver")
print("2. Откройте в браузере: http://127.0.0.1:8000/admin/")
print("3. Войдите с указанными выше данными")