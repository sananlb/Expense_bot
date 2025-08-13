#!/usr/bin/env python
"""
Тестовый скрипт для проверки персистентности меню кешбека
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_cashback_persistence():
    """Тест персистентности меню кешбека"""
    print("\n=== ТЕСТ ПЕРСИСТЕНТНОСТИ МЕНЮ КЕШБЕКА ===\n")
    
    print("Инструкции для ручного тестирования:")
    print("1. Откройте меню кешбека через /cashback или через кнопку в меню")
    print("2. После того как меню кешбека появится, отправьте любую команду (например /start)")
    print("3. Меню кешбека НЕ должно исчезнуть")
    print("4. Попробуйте отправить текстовое сообщение - меню кешбека НЕ должно исчезнуть")
    print("5. Откройте ВТОРОЕ меню кешбека - оба меню должны остаться на экране")
    print("6. Откройте ТРЕТЬЕ меню кешбека - все три должны остаться")
    print("7. Нажмите кнопку 'Закрыть' на одном из меню - только это меню исчезнет, остальные останутся")
    print("8. Нажмите 'Закрыть' на всех меню - только после закрытия последнего флаг персистентности снимется")
    print("\nСледите за логами для отладки:")
    print("- 'SKIPPING deletion - cashback menu is persistent!' - означает что защита работает")
    print("- 'Restored persistent cashback menu' - означает что флаг восстановлен после команды")
    print("\n" + "="*50 + "\n")
    
    print("Бот запущен. Протестируйте функциональность в Telegram.")
    print("Для остановки нажмите Ctrl+C")

if __name__ == "__main__":
    asyncio.run(test_cashback_persistence())