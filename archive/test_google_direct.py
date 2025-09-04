#!/usr/bin/env python
"""
Прямой тест Google AI без Django и бота
"""
import os
import asyncio
import google.generativeai as genai
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

async def test_google_ai():
    """Тестируем Google AI напрямую"""
    
    # Настраиваем API
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print("ERROR: GOOGLE_API_KEY not found")
        return
    
    print(f"API key loaded: {api_key[:10]}...")
    genai.configure(api_key=api_key)
    
    # Создаем модель
    model = genai.GenerativeModel('gemini-2.5-flash')
    print(f"Model created: {model}")
    
    # Настройки генерации
    generation_config = genai.GenerationConfig(
        temperature=0.1,
        max_output_tokens=2000,
        top_p=0.95,
        top_k=40
    )
    
    # Safety settings
    safety_settings = [
        {
            "category": "HARM_CATEGORY_HARASSMENT",
            "threshold": "BLOCK_NONE"
        },
        {
            "category": "HARM_CATEGORY_HATE_SPEECH", 
            "threshold": "BLOCK_NONE"
        },
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_NONE"
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "BLOCK_NONE"
        }
    ]
    
    # Тестовый промпт
    prompt = """Категоризируй расход "шахматы 1600 руб".

Доступные категории:
- Развлечения
- Спорт и фитнес  
- Образование
- Хобби
- Прочие расходы

Ответь в формате JSON:
{
    "category": "название категории",
    "confidence": число от 0 до 1,
    "reasoning": "краткое объяснение"
}"""
    
    print("\nSending request to Google AI...")
    print(f"Prompt length: {len(prompt)} chars")
    
    try:
        # Прямой вызов
        import time
        start = time.time()
        
        response = model.generate_content(
            prompt,
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        
        elapsed = time.time() - start
        print(f"\nResponse received in {elapsed:.2f} seconds")
        
        if response.text:
            print(f"Response text ({len(response.text)} chars):")
            print(response.text)
        else:
            print("No response text")
            if response.candidates:
                for i, candidate in enumerate(response.candidates):
                    print(f"Candidate {i}: {candidate}")
                    if hasattr(candidate, 'safety_ratings'):
                        for rating in candidate.safety_ratings:
                            print(f"  Safety: {rating.category} = {rating.probability}")
    
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=" * 60)
    print("Direct Google AI Test")
    print("=" * 60)
    
    # Запускаем асинхронно
    asyncio.run(test_google_ai())
    
    print("\n" + "=" * 60)
    print("Test completed")