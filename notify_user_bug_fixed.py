#!/usr/bin/env python3
"""
Уведомление пользователя об исправлении бага с категориями доходов
User ID: 411977529 (столкнулся с ошибкой создания категории доходов 24.01.2026)
"""
import os
import sys
import django
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from aiogram import Bot


async def notify_user():
    """Отправить уведомление пользователю об исправлении бага"""

    # ID пользователя который столкнулся с багом
    user_id = 411977529

    # Текст сообщения
    message_text = (
        "Здравствуйте, ошибка при создании категории доходов устранена. "
        "Благодарим за использование бота Coins!"
    )

    print("=" * 80)
    print("УВЕДОМЛЕНИЕ ОБ ИСПРАВЛЕНИИ БАГА")
    print("=" * 80)
    print(f"User ID: {user_id}")
    print(f"Message: {message_text}")
    print()

    # Получаем токен бота
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        print('[ERROR] BOT_TOKEN not found in environment!')
        return False

    # Инициализируем бота
    bot = Bot(token=bot_token)

    try:
        # Отправляем сообщение (только текст, без кнопок)
        await bot.send_message(
            chat_id=user_id,
            text=message_text
        )

        print()
        print("=" * 80)
        print("[SUCCESS] Message sent successfully!")
        print("=" * 80)
        print()
        return True

    except Exception as e:
        print()
        print("=" * 80)
        print(f"[ERROR] Failed to send message: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Закрываем сессию бота
        await bot.session.close()


if __name__ == '__main__':
    success = asyncio.run(notify_user())
    sys.exit(0 if success else 1)
