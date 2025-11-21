"""
Скрипт для очистки FSM state конкретного пользователя в Redis
Используется для исправления "застрявших" пользователей

Использование:
    python clear_user_state.py <telegram_id>

Пример:
    python clear_user_state.py 491444398
"""
import sys
import asyncio
import redis.asyncio as redis
from config.settings import REDIS_HOST, REDIS_PORT, REDIS_DB

async def clear_user_state(telegram_id: int):
    """Очистить FSM state пользователя в Redis"""
    print(f"\n=== Очистка FSM state для telegram_id={telegram_id} ===\n")

    # Подключаемся к Redis
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True
    )

    try:
        # FSM keys format в aiogram: fsm:{bot_id}:{chat_id}:{user_id}:state
        # Для Telegram bot chat_id == user_id для личных чатов

        # Ищем все ключи связанные с пользователем
        pattern = f"fsm:*:{telegram_id}:*"
        print(f"🔍 Поиск ключей по паттерну: {pattern}")

        keys_found = []
        async for key in redis_client.scan_iter(match=pattern):
            keys_found.append(key)
            print(f"   Найден ключ: {key}")

        if not keys_found:
            print(f"\n✅ Ключи FSM state не найдены (пользователь не в состоянии)")
            await redis_client.close()
            return

        # Показываем текущее состояние
        print(f"\n📊 Текущее состояние пользователя:")
        for key in keys_found:
            value = await redis_client.get(key)
            print(f"   {key} = {value}")

        # Удаляем все ключи
        print(f"\n🗑️ Удаление {len(keys_found)} ключей...")
        deleted = await redis_client.delete(*keys_found)
        print(f"✅ Удалено ключей: {deleted}")

        # Проверяем что удалено
        print(f"\n🔍 Проверка после удаления...")
        remaining = []
        async for key in redis_client.scan_iter(match=pattern):
            remaining.append(key)

        if remaining:
            print(f"⚠️ Остались ключи: {remaining}")
        else:
            print(f"✅ Все ключи успешно удалены!")

        await redis_client.close()
        print(f"\n{'='*60}")
        print(f"✅ FSM state пользователя {telegram_id} очищен!")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        await redis_client.close()
        raise


async def list_all_states():
    """Показать все FSM states в Redis (для отладки)"""
    print(f"\n=== Список всех FSM states в Redis ===\n")

    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True
    )

    try:
        pattern = "fsm:*"
        print(f"🔍 Поиск всех FSM ключей...")

        count = 0
        async for key in redis_client.scan_iter(match=pattern):
            value = await redis_client.get(key)
            print(f"{count+1}. {key} = {value}")
            count += 1

        if count == 0:
            print("✅ FSM states не найдены")
        else:
            print(f"\n📊 Всего найдено FSM states: {count}")

        await redis_client.close()

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        await redis_client.close()
        raise


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("⚠️ Не указан telegram_id пользователя")
        print("\nИспользование:")
        print("  python clear_user_state.py <telegram_id>")
        print("\nПримеры:")
        print("  python clear_user_state.py 491444398")
        print("  python clear_user_state.py 1190249363")
        print("\nДля просмотра всех FSM states:")
        print("  python clear_user_state.py --list")
        sys.exit(1)

    if sys.argv[1] == "--list":
        asyncio.run(list_all_states())
    else:
        telegram_id = int(sys.argv[1])
        asyncio.run(clear_user_state(telegram_id))
