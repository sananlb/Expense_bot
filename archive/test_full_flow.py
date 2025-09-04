"""
Тест полного цикла обработки сообщения о расходе
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
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_full_flow():
    """Тестируем полный цикл обработки расхода"""
    try:
        from bot.utils.expense_parser import parse_expense_message
        from expenses.models import Profile, ExpenseCategory
        from asgiref.sync import sync_to_async
        
        # Получаем профиль пользователя
        user_id = 881292737
        
        try:
            profile = await Profile.objects.aget(telegram_id=user_id)
            logger.info(f"Profile found for user {user_id}")
        except Profile.DoesNotExist:
            logger.error(f"Profile not found for user {user_id}")
            return
        
        # Тестовое сообщение
        test_text = "самокат 12000"
        
        logger.info(f"Testing message: '{test_text}'")
        logger.info("=" * 50)
        
        # Парсим сообщение с AI
        parsed = await parse_expense_message(
            text=test_text, 
            user_id=user_id, 
            profile=profile, 
            use_ai=True
        )
        
        logger.info(f"Parsing result: {parsed}")
        
        if parsed:
            logger.info(f"✅ Successfully parsed:")
            logger.info(f"  Amount: {parsed['amount']} {parsed.get('currency', 'RUB')}")
            logger.info(f"  Category: {parsed.get('category', 'Not found')}")
            logger.info(f"  Description: {parsed.get('description', '')}")
            logger.info(f"  Confidence: {parsed.get('confidence', 0)}")
            logger.info(f"  AI Provider: {parsed.get('ai_provider', 'none')}")
        else:
            logger.error("❌ Failed to parse message")
            
    except Exception as e:
        logger.error(f"Test error: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(test_full_flow())