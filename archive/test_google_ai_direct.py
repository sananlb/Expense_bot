"""
Прямой тест Google AI API для диагностики зависания
"""
import os
import sys
import asyncio
import logging

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_google_ai():
    """Тестируем Google AI напрямую"""
    
    print("Starting Google AI test...")
    
    # 1. Проверяем наличие ключа
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print("ERROR: GOOGLE_API_KEY not found in environment")
        return
    print(f"API Key found: {api_key[:10]}...")
    
    # 2. Пробуем импортировать и настроить
    try:
        import google.generativeai as genai
        print("Google AI library imported successfully")
    except ImportError as e:
        print(f"ERROR importing google.generativeai: {e}")
        return
    
    # 3. Конфигурируем API
    try:
        genai.configure(api_key=api_key)
        print("API configured successfully")
    except Exception as e:
        print(f"ERROR configuring API: {e}")
        return
    
    # 4. Создаем модель
    try:
        print("Creating model...")
        model = genai.GenerativeModel('gemini-1.5-flash')
        print("Model created successfully")
    except Exception as e:
        print(f"ERROR creating model: {e}")
        return
    
    # 5. Делаем простой запрос
    try:
        print("Making simple request...")
        prompt = "Say 'Hello World' in JSON format: {\"message\": \"...\"}"
        
        # Синхронный вызов для теста
        print("Calling generate_content...")
        response = model.generate_content(prompt)
        print(f"Response received: {response.text}")
        
    except Exception as e:
        print(f"ERROR during API call: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 6. Тестируем асинхронный вызов через asyncio.to_thread
    try:
        print("\nTesting async call via asyncio.to_thread...")
        response = await asyncio.to_thread(
            model.generate_content,
            prompt
        )
        print(f"Async response: {response.text}")
    except Exception as e:
        print(f"ERROR in async call: {e}")
        import traceback
        traceback.print_exc()
    
    # 7. Тестируем с таймаутом
    try:
        print("\nTesting with timeout...")
        response = await asyncio.wait_for(
            asyncio.to_thread(model.generate_content, prompt),
            timeout=5.0
        )
        print(f"Response with timeout: {response.text}")
    except asyncio.TimeoutError:
        print("ERROR: Timeout after 5 seconds")
    except Exception as e:
        print(f"ERROR: {e}")
    
    print("\nTest completed!")

if __name__ == "__main__":
    asyncio.run(test_google_ai())