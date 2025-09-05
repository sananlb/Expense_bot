#!/usr/bin/env python3
"""
Скрипт для диагностики и сброса состояния пользователя в боте
Использование: python reset_user_state.py <telegram_id>
"""

import os
import sys
import asyncio
import redis
from pathlib import Path

# Добавляем корневую папку проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
import django
django.setup()

from aiogram import Bot
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from expense_bot.settings import TELEGRAM_BOT_TOKEN, REDIS_HOST, REDIS_PORT


async def check_user_state(user_id: int):
    """Проверка текущего состояния пользователя"""
    print(f"\n[INFO] Проверка состояния пользователя {user_id}")
    
    # Подключаемся к Redis
    redis_client = redis.Redis(
        host=REDIS_HOST, 
        port=REDIS_PORT, 
        db=0,
        decode_responses=True
    )
    
    # Ищем все ключи связанные с пользователем
    pattern = f"*{user_id}*"
    keys = redis_client.keys(pattern)
    
    if keys:
        print(f"[INFO] Найдено {len(keys)} ключей в Redis:")
        for key in keys:
            try:
                value = redis_client.get(key)
                print(f"  - {key}: {value[:100] if value else 'None'}...")
            except:
                print(f"  - {key}: [не удалось прочитать]")
    else:
        print("[INFO] Ключи для пользователя не найдены в Redis")
    
    return bool(keys)


async def reset_user_state(user_id: int, force: bool = False):
    """Сброс состояния пользователя"""
    print(f"\n[ACTION] Сброс состояния пользователя {user_id}")
    
    # Инициализируем бота и хранилище
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    redis_client = redis.asyncio.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=0
    )
    storage = RedisStorage(redis=redis_client)
    
    try:
        # Создаем контекст состояния
        state = FSMContext(
            storage=storage,
            key=StorageKey(
                bot_id=bot.id,
                user_id=user_id,
                chat_id=user_id
            )
        )
        
        # Получаем текущее состояние
        current_state = await state.get_state()
        state_data = await state.get_data()
        
        if current_state:
            print(f"[INFO] Текущее состояние: {current_state}")
            if state_data:
                print(f"[INFO] Данные состояния: {state_data}")
        else:
            print("[INFO] Пользователь не находится в специальном состоянии")
        
        if current_state or force:
            # Очищаем состояние
            await state.clear()
            print("[SUCCESS] Состояние успешно сброшено")
            
            # Также очищаем все ключи напрямую через синхронный клиент
            sync_redis = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=0
            )
            pattern = f"*{user_id}*"
            keys = sync_redis.keys(pattern)
            if keys:
                for key in keys:
                    sync_redis.delete(key)
                print(f"[SUCCESS] Удалено {len(keys)} ключей из Redis")
        else:
            print("[INFO] Сброс не требуется (нет активного состояния)")
            
    except Exception as e:
        print(f"[ERROR] Ошибка при сбросе состояния: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Закрываем соединения
        await bot.session.close()
        await redis_client.close()
        

async def send_notification(user_id: int):
    """Отправка уведомления пользователю о сбросе"""
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    try:
        await bot.send_message(
            chat_id=user_id,
            text="⚙️ Ваше состояние в боте было сброшено.\n\n"
                 "Если бот не отвечал, теперь он должен работать нормально.\n"
                 "Попробуйте использовать команду /start"
        )
        print("[SUCCESS] Уведомление отправлено пользователю")
    except Exception as e:
        print(f"[WARNING] Не удалось отправить уведомление: {e}")
    finally:
        await bot.session.close()


async def main():
    """Основная функция"""
    if len(sys.argv) < 2:
        print("Использование: python reset_user_state.py <telegram_id> [--force] [--notify]")
        print("  --force  - принудительный сброс даже если нет активного состояния")
        print("  --notify - отправить уведомление пользователю")
        sys.exit(1)
    
    try:
        user_id = int(sys.argv[1])
    except ValueError:
        print("[ERROR] telegram_id должен быть числом")
        sys.exit(1)
    
    force = "--force" in sys.argv
    notify = "--notify" in sys.argv
    
    print(f"{'='*50}")
    print(f"Сброс состояния для пользователя: {user_id}")
    print(f"{'='*50}")
    
    # Проверяем текущее состояние
    has_state = await check_user_state(user_id)
    
    # Сбрасываем состояние
    await reset_user_state(user_id, force)
    
    # Отправляем уведомление если нужно
    if notify:
        await send_notification(user_id)
    
    # Проверяем состояние после сброса
    print("\n[INFO] Проверка после сброса:")
    await check_user_state(user_id)
    
    print(f"\n{'='*50}")
    print("Операция завершена")
    print(f"{'='*50}")


if __name__ == "__main__":
    asyncio.run(main())