#!/usr/bin/env python
"""
Скрипт для создания суперпользователя Django
"""
import os
import sys
import django
import secrets
import string
from getpass import getpass

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

def generate_secure_password(length=16):
    """Генерация криптографически безопасного пароля"""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password

# Проверяем, есть ли уже суперпользователь
if User.objects.filter(is_superuser=True).exists():
    print("Суперпользователь уже существует!")
    admin = User.objects.filter(is_superuser=True).first()
    print(f"Username: {admin.username}")
else:
    # Получаем данные от пользователя или из переменных окружения
    username = os.getenv('DJANGO_SUPERUSER_USERNAME', 'admin')
    email = os.getenv('DJANGO_SUPERUSER_EMAIL', 'admin@expensebot.com')
    
    # Получаем пароль из переменной окружения или генерируем безопасный
    password = os.getenv('DJANGO_SUPERUSER_PASSWORD')
    
    if not password:
        # В интерактивном режиме запрашиваем пароль
        if sys.stdin.isatty():
            print(f"Создание суперпользователя: {username}")
            password = getpass("Введите пароль (или нажмите Enter для генерации): ")
            if not password:
                password = generate_secure_password()
                print(f"Сгенерирован безопасный пароль: {password}")
        else:
            # В неинтерактивном режиме генерируем пароль
            password = generate_secure_password()
            print(f"Сгенерирован безопасный пароль: {password}")
    
    User.objects.create_superuser(
        username=username,
        email=email,
        password=password
    )
    
    print(f"\n✅ Суперпользователь создан!")
    print(f"Username: {username}")
    print(f"Email: {email}")
    
    # Показываем пароль только если он был сгенерирован автоматически
    if not os.getenv('DJANGO_SUPERUSER_PASSWORD'):
        print(f"⚠️  ВАЖНО: Сохраните этот пароль в безопасном месте!")

print("\nДля доступа к админке:")
print("1. Запустите сервер: python manage.py runserver")
print("2. Откройте в браузере: http://127.0.0.1:8000/admin/")
print("3. Войдите с указанными выше данными")