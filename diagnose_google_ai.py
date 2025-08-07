"""
Диагностика проблемы с Google AI
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

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_google_ai_step_by_step():
    """Пошаговая диагностика Google AI"""
    
    print("\n=== STEP 1: Checking API Key ===")
    from expense_bot import settings
    api_key = settings.GOOGLE_API_KEYS[0] if settings.GOOGLE_API_KEYS else None
    if not api_key:
        print("ERROR: No API key found!")
        return
    print(f"API Key found: {api_key[:20]}...")
    
    print("\n=== STEP 2: Importing Google AI library ===")
    try:
        import google.generativeai as genai
        print("SUCCESS: google.generativeai imported")
        print(f"Library version: {genai.__version__ if hasattr(genai, '__version__') else 'unknown'}")
    except ImportError as e:
        print(f"ERROR importing: {e}")
        return
    
    print("\n=== STEP 3: Configuring API ===")
    try:
        genai.configure(api_key=api_key)
        print("SUCCESS: API configured")
    except Exception as e:
        print(f"ERROR configuring: {e}")
        return
    
    print("\n=== STEP 4: Listing available models ===")
    try:
        models = genai.list_models()
        print("Available models:")
        for model in models:
            if 'generateContent' in model.supported_generation_methods:
                print(f"  - {model.name}")
    except Exception as e:
        print(f"ERROR listing models: {e}")
    
    print("\n=== STEP 5: Creating model ===")
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')  # Пробуем gemini-2.5-flash
        print(f"SUCCESS: Model created (gemini-2.5-flash)")
    except Exception as e:
        print(f"ERROR creating gemini-2.5-flash: {e}")
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            print(f"SUCCESS: Model created (gemini-1.5-flash) as fallback")
        except Exception as e2:
            print(f"ERROR creating gemini-1.5-flash: {e2}")
            return
    
    print("\n=== STEP 6: Simple sync test ===")
    try:
        simple_prompt = "Reply with exactly: OK"
        print(f"Sending simple prompt: '{simple_prompt}'")
        
        response = model.generate_content(simple_prompt)
        print(f"Response: {response.text[:100]}")
    except Exception as e:
        print(f"ERROR in sync call: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== STEP 7: Async test with asyncio.to_thread ===")
    try:
        print("Testing async call...")
        response = await asyncio.wait_for(
            asyncio.to_thread(model.generate_content, simple_prompt),
            timeout=5.0
        )
        print(f"Async response: {response.text[:100]}")
    except asyncio.TimeoutError:
        print("ERROR: Timeout after 5 seconds")
    except Exception as e:
        print(f"ERROR in async call: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== STEP 8: Test with generation config ===")
    try:
        generation_config = genai.GenerationConfig(
            temperature=0.1,
            max_output_tokens=100
        )
        print("Testing with generation config...")
        
        response = await asyncio.wait_for(
            asyncio.to_thread(
                model.generate_content, 
                simple_prompt,
                generation_config=generation_config
            ),
            timeout=5.0
        )
        print(f"Response with config: {response.text[:100]}")
    except asyncio.TimeoutError:
        print("ERROR: Timeout with generation config")
    except Exception as e:
        print(f"ERROR with config: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== STEP 9: Testing actual categorization prompt ===")
    try:
        prompt = """Return JSON: {"category": "test", "confidence": 0.8}"""
        print(f"Testing JSON prompt...")
        
        response = await asyncio.wait_for(
            asyncio.to_thread(model.generate_content, prompt),
            timeout=5.0
        )
        print(f"JSON response: {response.text[:200]}")
    except asyncio.TimeoutError:
        print("ERROR: Timeout with JSON prompt")
    except Exception as e:
        print(f"ERROR with JSON: {e}")
    
    print("\n=== DIAGNOSTICS COMPLETE ===")

if __name__ == "__main__":
    asyncio.run(test_google_ai_step_by_step())