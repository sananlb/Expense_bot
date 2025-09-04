#!/usr/bin/env python
"""Прямой тест асинхронного Google AI"""
import asyncio
import logging
import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_async_api():
    """Тестируем асинхронный API напрямую"""
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print("ERROR: GOOGLE_API_KEY not found")
        return
    
    genai.configure(api_key=api_key)
    
    # Тестируем с generate_content_async
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    prompt = """
    Categorize the expense "Шахматы 1990" into one of these categories:
    ["Продукты", "Транспорт", "Развлечения", "Здоровье", "Образование", "Рестораны", "Покупки", "Услуги", "Другое"]
    
    Return ONLY JSON:
    {"category": "selected_category", "confidence": 0.8, "reasoning": "brief explanation"}
    """
    
    generation_config = genai.GenerationConfig(
        temperature=0.1,
        max_output_tokens=1000,
        candidate_count=1,
        top_p=0.95,
        top_k=40
    )
    
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]
    
    print("Testing async call...")
    
    try:
        # Асинхронный вызов
        response = await asyncio.wait_for(
            model.generate_content_async(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            ),
            timeout=10.0
        )
        
        if response and response.text:
            print(f"SUCCESS! Response: {response.text}")
        else:
            print(f"Empty response: {response}")
            
    except asyncio.TimeoutError:
        print("TIMEOUT after 10 seconds")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {str(e)}")

if __name__ == "__main__":
    print("=" * 50)
    print("Testing Google AI Async API directly")
    print("=" * 50)
    asyncio.run(test_async_api())