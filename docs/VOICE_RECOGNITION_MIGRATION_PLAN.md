# План миграции Voice Recognition: OpenAI Whisper → Yandex + OpenRouter

## Дата создания: 2025-11-23
## Обновлено: 2025-11-23 (v2 - исправлено по результатам code review)

---

## Status Update
- [done] Voice input number parsing done (convert_words_to_numbers in bot/utils/expense_parser.py; regression: tests/test_number_parser.py) - composite spoken numbers now convert correctly in both EN/RU.
- [done] Yandex SpeechKit integration (`bot/services/yandex_speech.py`)
- [done] OpenRouter key rotation (`bot/services/key_rotation_mixin.py` - OpenRouterKeyRotationMixin)
- [done] UnifiedAIService transcribe_voice method (`bot/services/unified_ai_service.py`)
- [done] VoiceRecognitionService with symmetric fallback (`bot/services/voice_recognition.py`)
- [done] ai_selector.py - 'voice' type + 'openrouter' provider support
- [done] settings.py - YANDEX_API_KEY, YANDEX_FOLDER_ID, OPENROUTER_API_KEYS
- [done] requirements.txt - pydub==0.25.1, aiohttp==3.10.5
- [done] Dockerfile - ffmpeg installed
- [done] Integration in expense router (bot/routers/expense.py:1747)

**🎉 MIGRATION COMPLETE!** Ready for deployment and testing.

---

## Изменения v2 → v3

### v3: Симметричный fallback + централизованное управление моделями

| Требование | Реализация |
|------------|------------|
| **Симметричный fallback** | RU: Yandex → OpenRouter, EN: OpenRouter → Yandex |
| **Централизованное управление моделями** | Все модели из .env через `get_model('voice')` |
| **ai_selector интеграция** | `get_service('voice')` + `get_model('voice')` |
| **Key rotation** | Наследует от KeyRotationMixin |
| **Metrics/observability** | _log_metrics как в reference |

---

## 1. Текущее состояние (expense_bot)

### Файлы:
- `bot/services/voice_recognition.py` - OpenAI Whisper
- `bot/services/voice_processing.py` - OpenAI Whisper (альтернативная реализация)

### Логика:
- **Для ВСЕХ языков:** OpenAI Whisper API
- **Формат аудио:** OGG Opus (Telegram) → напрямую в Whisper
- **Проблема:** OpenAI Whisper недоступен в некоторых регионах (403 Forbidden)

---

## 2. Целевое состояние

### Логика выбора провайдера по языку (СИММЕТРИЧНЫЙ FALLBACK):

```
Пользователь отправляет голосовое сообщение
                    ↓
        Получаем язык из profile.language_code
                    ↓
         ┌─────────┴─────────┐
         ↓                   ↓
    lang == 'ru'        lang != 'ru'
         ↓                   ↓
  Yandex SpeechKit     OpenRouter Gemini
  (OGG напрямую)       (OGG → MP3 → Base64)
         ↓                   ↓
    При ошибке:         При ошибке:
    fallback →          fallback →
    OpenRouter          Yandex SpeechKit
         ↓                   ↓
         └────────┬──────────┘
                  ↓
         Распознанный текст
                  ↓
           process_text()
```

### Провайдеры (СИММЕТРИЧНЫЙ FALLBACK):

| Язык | Primary | Fallback | Модель (из .env) |
|------|---------|----------|--------|
| `ru` | Yandex SpeechKit | OpenRouter Gemini | `OPENROUTER_MODEL_VOICE` |
| `en`, другие | OpenRouter Gemini | Yandex SpeechKit | `OPENROUTER_MODEL_VOICE` |

**ВАЖНО:** Симметричный fallback в обе стороны!

---

## 3. Этапы реализации

### Этап 1: Установка зависимостей

#### 1.1 Обновить `requirements.txt`:
```txt
# Добавить:
pydub==0.25.1                   # Конвертация OGG → MP3 (для OpenRouter)
aiohttp>=3.9.0                  # Асинхронные HTTP запросы (для Yandex)
```

#### 1.2 Обновить `Dockerfile`:
```dockerfile
# Добавить установку ffmpeg (требуется для pydub):
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
```

---

### Этап 2: Конфигурация переменных окружения

#### 2.1 Добавить в `.env` на сервере:

```env
# ==========================================
# YANDEX SPEECHKIT (для русского языка)
# ==========================================
YANDEX_API_KEY=<ваш_api_key>
YANDEX_FOLDER_ID=<ваш_folder_id>
YANDEX_SPEECH_TOPIC=general:rc

# ==========================================
# OPENROUTER (для английского и других языков)
# ==========================================
OPENROUTER_API_KEY=<ваш_api_key>
OPENROUTER_API_KEY_1=<ключ_1_для_ротации>
OPENROUTER_API_KEY_2=<ключ_2_для_ротации>

# ==========================================
# AI PROVIDER SELECTION
# ==========================================
AI_PROVIDER_VOICE=openrouter
OPENROUTER_MODEL_VOICE=google/gemini-2.5-flash-preview-09-2025
```

---

### Этап 3: Обновление settings.py

#### 3.1 Добавить загрузку YANDEX ключей:

```python
# Yandex SpeechKit
YANDEX_API_KEY = _env('YANDEX_API_KEY', '')
YANDEX_FOLDER_ID = _env('YANDEX_FOLDER_ID', '')
YANDEX_SPEECH_TOPIC = _env('YANDEX_SPEECH_TOPIC', 'general:rc')
```

#### 3.2 Добавить загрузку OPENROUTER ключей:

```python
# OpenRouter API Keys (ротация)
OPENROUTER_API_KEYS = []
for i in ['', '_1', '_2', '_3']:
    key = _env(f'OPENROUTER_API_KEY{i}', '')
    if key:
        OPENROUTER_API_KEYS.append(key)

if OPENROUTER_API_KEYS:
    logger.info(f"[SETTINGS] Загружено OpenRouter API ключей: {len(OPENROUTER_API_KEYS)}")
```

#### 3.3 Добавить конфигурацию AI_PROVIDERS['voice']:

```python
# В словарь AI_PROVIDERS добавить:
'voice': {
    'provider': _env('AI_PROVIDER_VOICE', 'openrouter'),
    'model': _env('OPENROUTER_MODEL_VOICE', 'google/gemini-2.5-flash-preview-09-2025'),
},
```

---

### Этап 4: Добавить OpenRouter Key Rotation (НАСЛЕДУЕМ ОТ БАЗОВОГО!)

#### 4.1 Обновить `bot/services/key_rotation_mixin.py`:

**ВАЖНО:** Используем общий базовый класс KeyRotationMixin как в reference!

```python
class OpenRouterKeyRotationMixin(KeyRotationMixin):
    """Миксин для ротации API ключей OpenRouter - наследует от общего KeyRotationMixin"""

    _key_index: ClassVar[int] = 0
    _key_lock: ClassVar[threading.Lock] = threading.Lock()
    _key_status: ClassVar[Dict[int, Tuple[bool, Optional[datetime]]]] = {}

    @classmethod
    def get_api_keys(cls) -> List[str]:
        if hasattr(settings, 'OPENROUTER_API_KEYS') and settings.OPENROUTER_API_KEYS:
            return settings.OPENROUTER_API_KEYS
        if hasattr(settings, 'OPENROUTER_API_KEY') and settings.OPENROUTER_API_KEY:
            return [settings.OPENROUTER_API_KEY]
        return []

    @classmethod
    def get_key_name(cls, key_index: int) -> str:
        return f"OPENROUTER_API_KEY_{key_index + 1}"
```

---

### Этап 5: Создать YandexSpeechKit сервис

#### 5.1 Создать файл `bot/services/yandex_speech.py`:

**ВАЖНО:** Fallback управляется централизованно в VoiceRecognitionService!

```python
"""
Yandex SpeechKit интеграция для распознавания речи
"""
import logging
import aiohttp
from typing import Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class YandexSpeechKit:
    """Интеграция с Yandex SpeechKit"""

    RECOGNITION_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"

    @classmethod
    async def transcribe_primary(cls, audio_bytes: bytes) -> Optional[str]:
        """
        Распознать речь через Yandex SpeechKit (без fallback).

        Fallback управляется в VoiceRecognitionService для симметричности.

        Returns:
            Распознанный текст или None при ошибке
        """
        try:
            api_key = getattr(settings, 'YANDEX_API_KEY', None)
            folder_id = getattr(settings, 'YANDEX_FOLDER_ID', None)

            if not api_key or not folder_id:
                logger.warning("[YANDEX] API_KEY или FOLDER_ID не настроены")
                return None

            headers = {
                'Authorization': f'Api-Key {api_key}',
            }

            params = {
                'topic': getattr(settings, 'YANDEX_SPEECH_TOPIC', 'general:rc'),
                'folderId': folder_id,
                'format': 'oggopus',
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    cls.RECOGNITION_URL,
                    headers=headers,
                    params=params,
                    data=audio_bytes,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        text = result.get('result', '').strip()

                        if text:
                            text = cls._postprocess_russian(text)
                            logger.info(f"[YANDEX] Распознал: {text}")
                            return text
                        else:
                            logger.warning("[YANDEX] Пустой результат")
                            return None
                    else:
                        error_text = await response.text()
                        logger.error(f"[YANDEX] Ошибка: {response.status} - {error_text}")
                        return None

        except Exception as e:
            logger.error(f"[YANDEX] Exception: {e}")
            return None

    @staticmethod
    def _postprocess_russian(text: str) -> str:
        """Постобработка русского текста для expense_bot"""
        if not text:
            return text

        text = text.rstrip('.,!?')

        corrections = {
            'рублей': 'руб',
            'рубля': 'руб',
            'рубль': 'руб',
            'долларов': '$',
            'доллара': '$',
            'доллар': '$',
            'евро': '€',
            ' и ': ', ',
            ' плюс ': ', ',
            ' еще ': ', ',
            ' ещё ': ', ',
        }

        text_lower = text.lower()
        for wrong, correct in corrections.items():
            if wrong in text_lower:
                text = text.replace(wrong, correct)
                text = text.replace(wrong.capitalize(), correct.capitalize())

        return text
```

---

### Этап 6: Расширить UnifiedAIService для OpenRouter Voice

#### 6.1 Добавить в `bot/services/unified_ai_service.py`:

**ВАЖНО:** Включаем _log_metrics для observability (как в reference)!

##### Импорты:
```python
from .key_rotation_mixin import (
    KeyRotationMixin,
    DeepSeekKeyRotationMixin,
    QwenKeyRotationMixin,
    OpenRouterKeyRotationMixin,  # ДОБАВИТЬ
)
```

##### Метод конвертации OGG → MP3:

```python
def _convert_ogg_to_mp3(self, audio_bytes: bytes) -> bytes:
    """Конвертирует OGG (Telegram voice) в MP3 для совместимости с Gemini."""
    try:
        from pydub import AudioSegment
        from io import BytesIO

        ogg_audio = AudioSegment.from_ogg(BytesIO(audio_bytes))
        mp3_buffer = BytesIO()
        ogg_audio.export(mp3_buffer, format="mp3", bitrate="128k")
        mp3_buffer.seek(0)

        logger.info(f"[{self.provider_name}] Конвертация OGG -> MP3 успешна, размер: {len(mp3_buffer.getvalue())} байт")
        return mp3_buffer.getvalue()

    except ImportError:
        logger.error("[VOICE] pydub не установлен! pip install pydub")
        raise
    except Exception as e:
        logger.error(f"[{self.provider_name}] Ошибка конвертации OGG -> MP3: {e}")
        raise
```

##### Метод transcribe_voice (С МЕТРИКАМИ!):

```python
async def transcribe_voice(self, audio_bytes: bytes, model: Optional[str] = None) -> Optional[str]:
    """
    Транскрибирует аудио через мультимодальную модель OpenRouter (Gemini).
    """
    if self.provider_name != 'openrouter':
        logger.warning(f"[{self.provider_name}] transcribe_voice поддерживается только для OpenRouter")
        return None

    start_time = time.time()
    try:
        mp3_audio = await asyncio.to_thread(self._convert_ogg_to_mp3, audio_bytes)
        b64_audio = base64.b64encode(mp3_audio).decode('utf-8')

        system_prompt = (
            "You are a speech-to-text transcription system. "
            "Your ONLY task is to transcribe audio to text verbatim. "
            "NEVER explain, interpret, translate, or comment on the content. "
            "NEVER add any text that was not spoken in the audio. "
            "Output ONLY the exact words spoken, nothing more."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Transcribe this audio. Output only the spoken words."},
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": b64_audio,
                            "format": "mp3"
                        }
                    },
                ],
            },
        ]

        # Используем get_model через ai_selector
        from .ai_selector import get_model
        voice_model = model or get_model('voice')

        response, elapsed = await self._chat_completion(
            messages=messages,
            model=voice_model,
            temperature=0.0,
        )

        transcribed_text = response.choices[0].message.content.strip()
        transcribed_text = transcribed_text.rstrip('.,!?')

        # Логируем метрики (как в reference)
        self._log_metrics(
            "transcribe_voice",
            elapsed,
            True,
            model=voice_model,
            input_len=len(audio_bytes),
            tokens=getattr(response.usage, 'total_tokens', None) if hasattr(response, 'usage') else None
        )

        logger.info(f"[{self.provider_name}] Gemini транскрибировал: {transcribed_text[:100]}...")
        return transcribed_text if transcribed_text else None

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[{self.provider_name}] transcribe_voice error: {e}")
        self._log_metrics(
            "transcribe_voice",
            elapsed,
            False,
            model=model,
            input_len=len(audio_bytes),
            error=e
        )
        return None
```

---

### Этап 7: Обновить Voice Recognition сервис

#### 7.1 Переписать `bot/services/voice_recognition.py`:

**ВАЖНО:** Симметричный fallback в обе стороны!

```python
"""
Voice Recognition Service - гибридная система распознавания речи

Логика выбора провайдера (СИММЕТРИЧНЫЙ FALLBACK):
- Русский (ru): Yandex SpeechKit → fallback OpenRouter Gemini
- Английский и другие: OpenRouter Gemini → fallback Yandex SpeechKit
"""
import logging
from typing import Optional

from .yandex_speech import YandexSpeechKit
from .ai_selector import get_service, get_model

logger = logging.getLogger(__name__)


class VoiceRecognitionService:
    """Гибридный сервис распознавания речи с симметричным fallback"""

    @classmethod
    async def transcribe(cls, audio_bytes: bytes, language_code: str = 'ru') -> Optional[str]:
        """
        Распознать речь с выбором провайдера по языку

        Args:
            audio_bytes: Аудио в формате OGG Opus (Telegram voice)
            language_code: Код языка пользователя ('ru', 'en', etc.)

        Returns:
            Распознанный текст или None при ошибке
        """
        if language_code == 'ru':
            # RU: Yandex → fallback OpenRouter
            return await cls._transcribe_russian(audio_bytes)
        else:
            # EN и другие: OpenRouter → fallback Yandex
            return await cls._transcribe_other(audio_bytes)

    @classmethod
    async def _transcribe_russian(cls, audio_bytes: bytes) -> Optional[str]:
        """RU: Yandex SpeechKit → fallback OpenRouter"""
        # Primary: Yandex
        result = await YandexSpeechKit.transcribe_primary(audio_bytes)
        if result:
            return result

        # Fallback: OpenRouter
        logger.warning("[VOICE] Yandex failed, trying OpenRouter fallback for RU")
        return await cls._transcribe_with_openrouter(audio_bytes)

    @classmethod
    async def _transcribe_other(cls, audio_bytes: bytes) -> Optional[str]:
        """EN и другие: OpenRouter → fallback Yandex"""
        # Primary: OpenRouter
        result = await cls._transcribe_with_openrouter(audio_bytes)
        if result:
            return result

        # Fallback: Yandex (поддерживает многие языки)
        logger.warning("[VOICE] OpenRouter failed, trying Yandex fallback for EN")
        return await YandexSpeechKit.transcribe_primary(audio_bytes)

    @classmethod
    async def _transcribe_with_openrouter(cls, audio_bytes: bytes) -> Optional[str]:
        """Распознавание через OpenRouter (модель из .env)"""
        try:
            voice_service = get_service('voice')

            if not hasattr(voice_service, 'transcribe_voice'):
                logger.error("Voice service does not support transcribe_voice method")
                return None

            # Модель берётся централизованно из .env через get_model
            result = await voice_service.transcribe_voice(
                audio_bytes,
                model=get_model('voice')
            )
            return result

        except Exception as e:
            logger.error(f"OpenRouter transcribe error: {e}")
            return None
```

---

### Этап 8: Обновить ai_selector.py

#### 8.1 Добавить поддержку OpenRouter провайдера в AISelector:

```python
# В класс AISelector.__new__ добавить:
elif provider_type == 'openrouter':
    logger.info(f"[AISelector] Creating UnifiedAIService for openrouter...")
    from .unified_ai_service import UnifiedAIService
    cls._instances[provider_type] = UnifiedAIService(provider_name='openrouter')
    logger.info(f"[AISelector] UnifiedAIService (openrouter) created successfully")
```

#### 8.2 Добавить настройки OpenRouter в get_provider_settings:

```python
elif provider == 'openrouter':
    from expense_bot import settings
    api_keys_available = False
    if hasattr(settings, 'OPENROUTER_API_KEYS') and settings.OPENROUTER_API_KEYS:
        api_keys_available = True
    elif hasattr(settings, 'OPENROUTER_API_KEY') or os.getenv('OPENROUTER_API_KEY'):
        api_keys_available = True

    return {
        'api_keys_available': api_keys_available,
        'default_model': 'google/gemini-2.5-flash-preview-09-2025',
        'max_tokens': 1024,
        'temperature': 0.0,
        'base_url': 'https://openrouter.ai/api/v1'
    }
```

#### 8.3 Добавить 'voice' в AI_PROVIDERS:

```python
# В AI_PROVIDERS добавить:
'voice': {
    'provider': os.getenv('AI_PROVIDER_VOICE', 'openrouter'),
    'model': {
        'openrouter': os.getenv('OPENROUTER_MODEL_VOICE', 'google/gemini-2.5-flash-preview-09-2025'),
    }
},
```

---

### Этап 9: Обновить UnifiedAIService __init__ для OpenRouter

```python
def __init__(self, provider_name: str = 'deepseek'):
    self.provider_name = provider_name
    self.base_url = None
    self.api_key_mixin: Optional[Type[KeyRotationMixin]] = None

    if provider_name == 'openrouter':
        self.base_url = 'https://openrouter.ai/api/v1'
        self.api_key_mixin = OpenRouterKeyRotationMixin
    elif provider_name == 'deepseek':
        self.base_url = 'https://api.deepseek.com/v1'
        self.api_key_mixin = DeepSeekKeyRotationMixin
    elif provider_name == 'qwen':
        self.base_url = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
        self.api_key_mixin = QwenKeyRotationMixin
    else:
        raise ValueError(f"Unknown provider: {provider_name}")
```

---

### Этап 10: Обновить обработчик голосовых сообщений

#### 10.1 В обработчике добавить access checks и user_data markers (как в reference):

```python
from bot.services.voice_recognition import VoiceRecognitionService

async def handle_voice_message(message: Message, state: FSMContext):
    """Обработать голосовое сообщение"""
    user_id = message.from_user.id

    # Получаем профиль
    profile = await get_or_create_profile(user_id)
    language_code = profile.language_code or 'ru'

    # === ACCESS CHECKS (как в reference) ===
    if not profile.can_use_bot:
        from django.utils import timezone
        if profile.trial_end_date and profile.trial_end_date <= timezone.now():
            text_msg = get_text('trial_expired', language_code)
        else:
            text_msg = get_text('no_access', language_code)
        await message.answer(text_msg)
        return None

    # === DELETE HELP MESSAGE (как в reference) ===
    # Удаляем справку если открыта
    await delete_help_message_if_exists(message, state)

    chat_id = message.chat.id
    message_id = message.message_id

    logger.info(f"[VOICE] process_voice: Chat ID: {chat_id}, Message ID: {message_id}, Lang: {language_code}")

    try:
        # Скачиваем голосовой файл
        file = await message.bot.get_file(message.voice.file_id)
        file_bytes = BytesIO()
        await file.download_to_memory(file_bytes)
        file_bytes.seek(0)

        # Распознаем речь
        transcribed_text = await VoiceRecognitionService.transcribe(
            file_bytes.read(),
            language_code=language_code
        )

        if not transcribed_text:
            await message.answer(get_text('voice_not_recognized', language_code))
            return None

        logger.info(f"Транскрибировано от {chat_id}: {transcribed_text}")

        # === USER_DATA MARKERS (как в reference) ===
        state_data = await state.get_data()
        state_data[f'voice_source_{message_id}'] = 'voice'
        state_data[f'original_voice_{message_id}'] = transcribed_text
        await state.set_data(state_data)

        # Передаем в text handler для обработки
        await process_text_message(message, state, transcribed_text)

    except Exception as e:
        logger.error(f"Ошибка при обработке голосового сообщения: {e}")
        await message.answer(get_text('voice_error', language_code))

    return None
```

---

## 4. Структура файлов после миграции

```
bot/services/
├── voice_recognition.py      # Главный сервис (обновить)
├── yandex_speech.py          # НОВЫЙ: Yandex SpeechKit с fallback
├── unified_ai_service.py     # Добавить transcribe_voice(), _convert_ogg_to_mp3(), _log_metrics
├── ai_selector.py            # Добавить поддержку 'openrouter' и 'voice'
├── key_rotation_mixin.py     # Добавить OpenRouterKeyRotationMixin (наследует от базового)

expense_bot/
├── settings.py               # Добавить YANDEX_*, OPENROUTER_*, AI_PROVIDERS['voice']

requirements.txt              # Добавить pydub, aiohttp
Dockerfile                    # Добавить ffmpeg
.env                          # Добавить YANDEX_*, OPENROUTER_*
```

---

## 5. Переменные окружения (итого)

```env
# Yandex SpeechKit
YANDEX_API_KEY=<ключ>
YANDEX_FOLDER_ID=<folder_id>
YANDEX_SPEECH_TOPIC=general:rc

# OpenRouter
OPENROUTER_API_KEY=<ключ>
OPENROUTER_API_KEY_1=<ключ_1>
OPENROUTER_API_KEY_2=<ключ_2>

# AI Provider для voice
AI_PROVIDER_VOICE=openrouter
OPENROUTER_MODEL_VOICE=google/gemini-2.5-flash-preview-09-2025
```

---

## 6. Тестирование

### 6.1 Локальное тестирование:
```bash
# Проверка импортов
python -c "from bot.services.voice_recognition import VoiceRecognitionService; print('OK')"
python -c "from bot.services.yandex_speech import YandexSpeechKit; print('OK')"
python -c "from pydub import AudioSegment; print('pydub OK')"
```

### 6.2 Тестовые сценарии (СИММЕТРИЧНЫЙ FALLBACK):
1. **RU пользователь** → голосовое → Yandex
2. **EN пользователь** → голосовое → OpenRouter Gemini
3. **RU + Yandex fail** → автоматический fallback на OpenRouter ✓
4. **EN + OpenRouter fail** → автоматический fallback на Yandex ✓

### 6.3 Проверка логов:
```bash
docker logs expense_bot_app 2>&1 | grep -E "(Yandex|OpenRouter|transcribe|voice|VOICE)"
```

---

## 7. Оценка трудозатрат

| Этап | Файлы | Оценка |
|------|-------|--------|
| 1. Зависимости | requirements.txt, Dockerfile | 10 мин |
| 2. .env | .env на сервере | 5 мин |
| 3. settings.py | expense_bot/settings.py | 15 мин |
| 4. Key Rotation | key_rotation_mixin.py | 15 мин |
| 5. Yandex Speech | yandex_speech.py (новый) | 25 мин |
| 6. UnifiedAIService | unified_ai_service.py | 30 мин |
| 7. Voice Recognition | voice_recognition.py | 15 мин |
| 8. AI Selector | ai_selector.py | 15 мин |
| 9. UnifiedAIService init | unified_ai_service.py | 10 мин |
| 10. Voice Handler | routers/voice.py | 20 мин |
| **Итого** | **7-8 файлов** | **~2.5 часа** |

---

## 8. Риски и митигация

| Риск | Митигация |
|------|-----------|
| ffmpeg не установлен в Docker | Добавить в Dockerfile явно |
| Yandex API недоступен | Автоматический fallback на OpenRouter (только для RU) |
| OpenRouter API недоступен | Для EN - None, для RU - не дойдет если Yandex работает |
| pydub конвертация падает | Try-catch с логированием, возврат None |
| Неверный формат аудио | Telegram всегда отправляет OGG Opus |

---

## 9. Порядок деплоя

1. **Локально:** Внести все изменения в код
2. **Локально:** Протестировать импорты
3. **Git:** Commit и push
4. **Сервер:** Добавить переменные в .env
5. **Сервер:** `git pull`
6. **Сервер:** `docker-compose build --no-cache`
7. **Сервер:** `docker-compose up -d`
8. **Тест:** Отправить голосовое сообщение с RU и EN аккаунтов
9. **Логи:** Проверить что используется правильный провайдер

---

## 10. Ключевые отличия v3 от исходного плана

| Аспект | Было (v1) | Стало (v3) |
|--------|-----------|------------|
| **EN fallback** | Нет | **Есть → Yandex** (симметричный) |
| **RU fallback** | OpenRouter | **OpenRouter** (без изменений) |
| **Управление fallback** | В каждом сервисе | **Централизованно в VoiceRecognitionService** |
| **Модель** | Прямо из settings | **Через get_model('voice') из .env** |
| **Сервис** | Прямое создание | **Через get_service('voice')** |
| Key rotation | Отдельный mixin | Наследует от KeyRotationMixin |
| Handler | Только транскрипция | + access checks + user_data markers |
| Metrics | Не было | _log_metrics |

### Архитектура fallback (v3):

```
VoiceRecognitionService (централизованное управление)
    │
    ├── RU: YandexSpeechKit.transcribe_primary()
    │       └── если None → _transcribe_with_openrouter()
    │
    └── EN: _transcribe_with_openrouter()
            └── если None → YandexSpeechKit.transcribe_primary()
```

### Централизованное управление моделями (.env):

```env
# Модель для голосового распознавания (OpenRouter)
OPENROUTER_MODEL_VOICE=google/gemini-2.5-flash-preview-09-2025

# Провайдер по умолчанию для voice
AI_PROVIDER_VOICE=openrouter
```

Все модели читаются через `get_model('voice')` из ai_selector.py.
