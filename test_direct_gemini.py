"""
Прямой тест Gemini API без asyncio.to_thread
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')

from expense_bot import settings
import google.generativeai as genai

# Получаем ключ
api_key = settings.GOOGLE_API_KEYS[0] if settings.GOOGLE_API_KEYS else None
if not api_key:
    print("No API key found!")
    exit(1)

print(f"Using API key: {api_key[:10]}...")

# Конфигурируем
genai.configure(api_key=api_key)

# Создаем модель
print("Creating model...")
model = genai.GenerativeModel('gemini-1.5-flash')

# Создаем запрос
prompt = """Ты помощник в боте для учета личных расходов. Твоя задача - определить категорию траты.

Информация о трате:
Описание: "табурет"
Сумма: 3000 RUB

Доступные категории пользователя:
- 🛒 Продукты
- 🍽️ Кафе и рестораны  
- 🏠 Жилье
- 🎭 Развлечения
- 💰 Прочие расходы

ВАЖНО:
1. Выбери ТОЛЬКО из списка выше
2. Учитывай контекст личных расходов
3. Если не уверен, выбери наиболее подходящую общую категорию

Верни JSON:
{
    "category": "выбранная категория из списка",
    "confidence": число от 0 до 1,
    "reasoning": "краткое объяснение выбора"
}"""

print("Sending request to Gemini...")

# Генерация с настройками для JSON
generation_config = genai.GenerationConfig(
    temperature=0.1,
    max_output_tokens=1000,
    response_mime_type="application/json"
)

try:
    # Синхронный вызов
    response = model.generate_content(prompt, generation_config=generation_config)
    # Убираем эмоджи для вывода
    import json
    result = json.loads(response.text)
    print(f"Response received!")
    cat = result.get('category', 'unknown')
    # Убираем эмоджи
    cat_clean = ''.join(c for c in cat if ord(c) < 128).strip()
    print(f"Category: {cat_clean}")
    print(f"Confidence: {result.get('confidence', 0)}")
    reasoning = result.get('reasoning', 'none')
    reasoning_clean = ''.join(c for c in reasoning if ord(c) < 128).strip()
    print(f"Reasoning: {reasoning_clean}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()