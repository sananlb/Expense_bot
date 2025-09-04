"""
Простой тест Google AI без Django
"""
import os
import asyncio
import logging
import google.generativeai as genai

# Настраиваем логирование
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_google_ai_simple():
    """Простой тест Google AI API"""
    try:
        # Загружаем ключ из переменной окружения
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            logger.error("GOOGLE_API_KEY not found in environment")
            return
            
        logger.info(f"API key loaded: {api_key[:10]}...")
        
        # Конфигурируем API
        genai.configure(api_key=api_key)
        logger.info("API configured")
        
        # Создаем модель - используем ту же что и в боте
        model = genai.GenerativeModel('gemini-2.5-flash')
        logger.info(f"Model created: {model}")
        
        # Простой промпт
        prompt = """Категоризируй расход "самокат 5000 руб".
        
Доступные категории:
- Транспорт
- Продукты
- Развлечения

Ответь только названием категории."""
        
        logger.info("Calling generate_content...")
        
        # Синхронный вызов с таймаутом
        async def call_api():
            return await asyncio.to_thread(
                model.generate_content,
                prompt
            )
        
        try:
            response = await asyncio.wait_for(call_api(), timeout=10.0)
            logger.info(f"Response received: {response.text}")
        except asyncio.TimeoutError:
            logger.error("API call timeout after 10 seconds")
        except Exception as e:
            logger.error(f"API call error: {type(e).__name__}: {e}")
            
    except Exception as e:
        logger.error(f"Test error: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(test_google_ai_simple())