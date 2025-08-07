"""
Тестируем проблему с таймаутом Google AI
"""
import asyncio
import logging
import os
import sys
import django

# Настраиваем Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

# Настраиваем логирование
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_google_ai():
    """Тестируем прямой вызов Google AI"""
    try:
        # Импортируем после инициализации Django
        from bot.services.google_ai_service import GoogleAIService
        from expenses.models import Profile, ExpenseCategory
        
        # Получаем профиль пользователя
        user_id = 881292737
        profile = await Profile.objects.aget(telegram_id=user_id)
        
        # Получаем категории пользователя
        from asgiref.sync import sync_to_async
        categories = await sync_to_async(list)(
            ExpenseCategory.objects.filter(profile=profile).values_list('name', flat=True).distinct()
        )
        categories_list = categories
        logger.info(f"User categories: {categories_list}")
        
        # Создаем экземпляр сервиса
        service = GoogleAIService()
        
        # Тестовые данные
        test_text = "самокат 5000"
        amount = 5000
        currency = "RUB"
        
        logger.info(f"Testing Google AI categorization for: '{test_text}'")
        
        # Вызываем с таймаутом
        try:
            result = await asyncio.wait_for(
                service.categorize_expense(
                    text=test_text,
                    amount=amount,
                    currency=currency,
                    categories=categories_list,
                    user_context={}
                ),
                timeout=15.0  # 15 секунд
            )
            logger.info(f"Result: {result}")
        except asyncio.TimeoutError:
            logger.error("Timeout while calling Google AI")
        except Exception as e:
            logger.error(f"Error: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
    except Exception as e:
        logger.error(f"Setup error: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(test_google_ai())