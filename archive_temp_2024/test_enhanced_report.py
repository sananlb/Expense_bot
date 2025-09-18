#!/usr/bin/env python
"""
Скрипт для тестирования расширенного ежедневного отчета
Можно запустить для проверки работоспособности новой функциональности
"""
import os
import django
from datetime import datetime

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expense_bot.celery_tasks import send_daily_admin_report, system_health_check, collect_daily_analytics


def test_enhanced_daily_report():
    """Тест расширенного ежедневного отчета"""
    print("🧪 Тестирование расширенного ежедневного отчета...")
    print(f"⏰ Запуск: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    try:
        # Запускаем расширенный отчет
        result = send_daily_admin_report()
        print("✅ Ежедневный отчет выполнен успешно")
        
        if isinstance(result, dict):
            print(f"📊 Результат: {result}")
        
    except Exception as e:
        print(f"❌ Ошибка при выполнении отчета: {e}")
        import traceback
        traceback.print_exc()


def test_system_health_check():
    """Тест проверки здоровья системы"""
    print("\n🏥 Тестирование проверки здоровья системы...")
    print("=" * 60)
    
    try:
        result = system_health_check()
        print("✅ Проверка здоровья системы выполнена успешно")
        print(f"📊 Результат: {result}")
        
    except Exception as e:
        print(f"❌ Ошибка при проверке системы: {e}")
        import traceback
        traceback.print_exc()


def test_daily_analytics():
    """Тест сбора ежедневной аналитики"""
    print("\n📈 Тестирование сбора ежедневной аналитики...")
    print("=" * 60)
    
    try:
        result = collect_daily_analytics()
        print("✅ Сбор аналитики выполнен успешно")
        print(f"📊 Результат: {result}")
        
    except Exception as e:
        print(f"❌ Ошибка при сборе аналитики: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("🚀 Тестирование расширенных мониторинг-функций ExpenseBot")
    print(f"🗓 Дата: {datetime.now().strftime('%d.%m.%Y')}")
    print()
    
    # Проверяем переменные окружения
    admin_id = os.getenv('ADMIN_TELEGRAM_ID')
    monitoring_token = os.getenv('MONITORING_BOT_TOKEN')
    bot_token = os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
    
    print("🔧 Проверка конфигурации:")
    print(f"   ADMIN_TELEGRAM_ID: {'✅ Настроен' if admin_id else '❌ Не настроен'}")
    print(f"   MONITORING_BOT_TOKEN: {'✅ Настроен' if monitoring_token else '❌ Не настроен'}")
    print(f"   BOT_TOKEN: {'✅ Настроен' if bot_token else '❌ Не настроен'}")
    print()
    
    if not admin_id:
        print("⚠️  ПРЕДУПРЕЖДЕНИЕ: ADMIN_TELEGRAM_ID не настроен. Уведомления не будут отправлены.")
        print()
    
    # Запускаем тесты
    test_enhanced_daily_report()
    test_system_health_check()
    test_daily_analytics()
    
    print("\n" + "=" * 60)
    print("🏁 Тестирование завершено!")
    print(f"⏰ Окончание: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("📌 Следующие шаги:")
    print("   1. Проверьте логи Django на наличие ошибок")
    print("   2. Убедитесь, что администратор получил уведомления")
    print("   3. Проверьте данные в моделях SystemHealthCheck и UserAnalytics")
    print("   4. При необходимости скорректируйте конфигурацию")