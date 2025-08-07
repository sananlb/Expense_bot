"""
Тест Google AI с использованием настроек Django
"""
import os
import sys
import asyncio
import logging
import django

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_google_ai():
    """Тестируем Google AI с настройками из Django"""
    
    print("Starting Google AI test with Django settings...")
    
    # 1. Получаем настройки через ai_selector
    from bot.services.ai_selector import get_provider_settings
    settings = get_provider_settings('google')
    api_key = settings['api_key']
    
    if not api_key:
        print("ERROR: API key not found in settings")
        return
    print(f"API Key from settings: {api_key[:10]}...")
    
    # 2. Создаем экземпляр GoogleAIService
    try:
        from bot.services.google_ai_service import GoogleAIService
        print("Creating GoogleAIService instance...")
        service = GoogleAIService()
        print("Service created successfully")
    except Exception as e:
        print(f"ERROR creating service: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 3. Тестируем простую категоризацию
    try:
        print("\nTesting categorization...")
        categories = ['🛒 Продукты', '🍽️ Кафе и рестораны', '🎭 Развлечения', '💰 Прочие расходы']
        
        result = await service.categorize_expense(
            text='пиво',
            amount=810,
            currency='RUB',
            categories=categories,
            user_context=None
        )
        
        if result:
            print(f"Success! Category: {result['category']}, confidence: {result['confidence']}")
        else:
            print("No result returned")
            
    except Exception as e:
        print(f"ERROR during categorization: {e}")
        import traceback
        traceback.print_exc()
    
    print("\nTest completed!")

if __name__ == "__main__":
    # Запускаем с timeout на весь тест
    try:
        asyncio.run(asyncio.wait_for(test_google_ai(), timeout=15.0))
    except asyncio.TimeoutError:
        print("\nERROR: Test timed out after 15 seconds!")