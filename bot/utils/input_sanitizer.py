"""
Модуль санитизации входных данных для предотвращения prompt injection атак
"""
import re
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class InputSanitizer:
    """Централизованная санитизация входных данных для предотвращения prompt injection"""
    
    # Паттерны prompt injection для удаления
    INJECTION_PATTERNS = [
        # Попытки изменить инструкции
        r'(игнорир\w*|ignore\w*)\s+(все\s+)?(предыдущие\s+)?(инструкции|instructions)',
        r'(забудь|forget)\s+(всё|все|everything|all)',
        r'(отмени|cancel)\s+(правила|rules|ограничения|restrictions)',
        
        # Попытки заставить сказать что-то
        r'(скажи|say|tell|ответь|respond|напиши|write)\s*:',
        r'(повтори|repeat|echo)\s+(за\s+мной|after\s+me)',
        
        # Попытки изменить роль
        r'(новая\s+)?(роль|role)\s*:',
        r'(ты\s+)?(теперь|now)\s+(будешь|are|является|is)',
        r'(притворись|pretend|act)\s+(как|as|like)',
        
        # Попытки выполнить код или команды
        r'(выполни|execute|run|запусти)\s+(код|code|команду|command|скрипт|script)',
        r'```[^`]*```',  # Блоки кода
        
        # Попытки получить доступ к системе
        r'система\s+(взломана|hacked|скомпрометирована|compromised)',
        r'(покажи|show|reveal)\s+(пароль|password|ключ|key|токен|token)',
        r'(дай|give)\s+(доступ|access|права|permissions)',
        
        # SQL/команды инъекции
        r';\s*(DROP|DELETE|UPDATE|INSERT|SELECT|ALTER)\s+',
        r'--\s*$',  # SQL комментарии
        r'(rm\s+-rf|sudo|chmod|chown)\s+',
        
        # Попытки обойти фильтры
        r'(обойди|bypass|skip)\s+(фильтр|filter|проверку|check)',
        r'(отключи|disable|выключи|turn\s+off)\s+(безопасность|security|защиту|protection)',
    ]
    
    # Максимальные длины для разных типов данных
    MAX_TEXT_LENGTH = 1000
    MAX_CATEGORY_LENGTH = 100
    MAX_DESCRIPTION_LENGTH = 200
    
    @staticmethod
    def sanitize_text(
        text: str, 
        max_length: int = None,
        allow_newlines: bool = False
    ) -> str:
        """
        Санитизация текста для предотвращения prompt injection
        
        Args:
            text: Входной текст
            max_length: Максимальная длина (по умолчанию MAX_TEXT_LENGTH)
            allow_newlines: Разрешить переносы строк
            
        Returns:
            Очищенный текст
        """
        if not text or not isinstance(text, str):
            return ""
        
        if max_length is None:
            max_length = InputSanitizer.MAX_TEXT_LENGTH
        
        original_text = text
        
        # Удаляем паттерны injection
        for pattern in InputSanitizer.INJECTION_PATTERNS:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE)
        
        # Удаляем потенциальный HTML/Markdown
        text = re.sub(r'<[^>]+>', '', text)  # HTML теги
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # Markdown ссылки
        text = re.sub(r'[*_]{2,}', '', text)  # Markdown bold/italic
        
        # Экранируем специальные символы
        text = text.replace('\\', '')  # Удаляем обратные слеши
        text = text.replace('`', '')  # Удаляем обратные кавычки
        text = text.replace('$', '')  # Удаляем знаки доллара (переменные)
        text = text.replace('{', '').replace('}', '')  # Удаляем фигурные скобки
        
        # Обработка переносов строк
        if not allow_newlines:
            text = text.replace('\n', ' ').replace('\r', ' ')
        else:
            # Ограничиваем количество последовательных переносов
            text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Нормализуем пробелы
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Ограничиваем длину
        if len(text) > max_length:
            text = text[:max_length] + "..."
        
        # Логируем если были изменения
        if text != original_text and len(original_text) > 0:
            logger.debug(f"Sanitized text: {len(original_text)} -> {len(text)} chars")
        
        return text
    
    @staticmethod
    def sanitize_amount(amount: Any) -> float:
        """Санитизация суммы"""
        try:
            amount = float(amount)
            # Ограничиваем разумными пределами
            if amount < 0:
                amount = 0
            elif amount > 999999999:
                amount = 999999999
            return amount
        except (ValueError, TypeError):
            return 0
    
    @staticmethod
    def sanitize_category_name(category: str) -> str:
        """Санитизация названия категории"""
        return InputSanitizer.sanitize_text(
            category, 
            max_length=InputSanitizer.MAX_CATEGORY_LENGTH
        )
    
    @staticmethod
    def sanitize_description(description: str) -> str:
        """Санитизация описания расхода/дохода"""
        return InputSanitizer.sanitize_text(
            description,
            max_length=InputSanitizer.MAX_DESCRIPTION_LENGTH
        )
    
    @staticmethod
    def sanitize_context(context: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Санитизация контекста чата
        
        Args:
            context: Список сообщений контекста
            
        Returns:
            Очищенный контекст
        """
        if not context or not isinstance(context, list):
            return []
        
        sanitized = []
        for msg in context:
            if not isinstance(msg, dict):
                continue
                
            sanitized_msg = {
                'role': msg.get('role', 'user'),
                'content': InputSanitizer.sanitize_text(
                    msg.get('content', ''),
                    allow_newlines=True
                )
            }
            
            # Сохраняем timestamp если есть
            if 'timestamp' in msg:
                sanitized_msg['timestamp'] = msg['timestamp']
            
            sanitized.append(sanitized_msg)
        
        return sanitized
    
    @staticmethod
    def sanitize_user_context(user_context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Санитизация пользовательского контекста
        
        Args:
            user_context: Словарь с контекстом пользователя
            
        Returns:
            Очищенный контекст
        """
        if not user_context or not isinstance(user_context, dict):
            return None
        
        sanitized = {}
        
        # Санитизируем строковые поля
        string_fields = ['username', 'language', 'timezone', 'currency']
        for field in string_fields:
            if field in user_context:
                sanitized[field] = InputSanitizer.sanitize_text(
                    str(user_context[field]),
                    max_length=50
                )
        
        # Копируем безопасные поля как есть
        safe_fields = ['user_id', 'is_premium', 'created_at']
        for field in safe_fields:
            if field in user_context:
                sanitized[field] = user_context[field]
        
        return sanitized
    
    @staticmethod
    def validate_json_safe(data: Any) -> bool:
        """
        Проверка, что данные безопасны для JSON сериализации
        
        Args:
            data: Данные для проверки
            
        Returns:
            True если безопасно
        """
        try:
            import json
            json.dumps(data)
            return True
        except (TypeError, ValueError):
            return False
    
    @staticmethod
    def remove_sensitive_data(text: str) -> str:
        """
        Удаление потенциально чувствительных данных
        
        Args:
            text: Входной текст
            
        Returns:
            Текст без чувствительных данных
        """
        # Удаляем потенциальные токены (длинные hex/base64 строки)
        text = re.sub(r'\b[a-fA-F0-9]{32,}\b', '[REDACTED]', text)
        text = re.sub(r'\b[A-Za-z0-9+/]{40,}={0,2}\b', '[REDACTED]', text)
        
        # Удаляем email адреса
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
        
        # Удаляем номера телефонов
        text = re.sub(r'\+?\d{10,15}\b', '[PHONE]', text)
        
        # Удаляем номера карт
        text = re.sub(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '[CARD]', text)
        
        return text