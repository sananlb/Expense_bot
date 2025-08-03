"""
Интеграция улучшенного парсера расходов с существующей архитектурой expense_bot
"""
import os
from typing import Optional, Dict, Any, List
from decimal import Decimal
from datetime import date
from asgiref.sync import sync_to_async

# Импортируем улучшенный парсер
from .expense_parser_improved import (
    parse_expense_message, 
    parse_multiple_expenses,
    validate_expense_data,
    ExpenseParserAI,
    ParsedExpense
)

# Импортируем модели Django
from database.models import Profile, ExpenseCategory, Expense


class ExpenseParserService:
    """Сервис для обработки расходов с интеграцией AI"""
    
    def __init__(self):
        self.ai_parser = None
        self._init_ai_parser()
    
    def _init_ai_parser(self):
        """Инициализация AI парсера если доступен API ключ"""
        openai_key = os.getenv('OPENAI_API_KEY')
        if openai_key:
            self.ai_parser = ExpenseParserAI(api_key=openai_key)
    
    async def parse_text_message(
        self, 
        text: str, 
        user_id: int,
        use_ai: bool = True
    ) -> Optional[ParsedExpense]:
        """
        Парсинг текстового сообщения с учетом контекста пользователя
        """
        if not text or not text.strip():
            return None
        
        # Получаем контекст пользователя для AI
        user_context = None
        if use_ai and self.ai_parser:
            user_context = await self._get_user_context(user_id)
            result = await self.ai_parser.parse_expense_with_ai(text, user_context)
        else:
            result = parse_expense_message(text, use_ai=False)
        
        return result
    
    async def parse_multiple_text_messages(
        self, 
        text: str, 
        user_id: int
    ) -> List[ParsedExpense]:
        """
        Парсинг множественных расходов из одного сообщения
        """
        results = parse_multiple_expenses(text)
        
        # Если найден только один расход, пытаемся улучшить его с AI
        if len(results) == 1 and self.ai_parser:
            user_context = await self._get_user_context(user_id)
            ai_result = await self.ai_parser.parse_expense_with_ai(text, user_context)
            if ai_result and ai_result.confidence > results[0].confidence:
                results[0] = ai_result
        
        return results
    
    @sync_to_async
    def _get_user_context(self, user_id: int) -> Dict[str, Any]:
        """Получение контекста пользователя для улучшения AI парсинга"""
        try:
            profile = Profile.objects.get(telegram_id=user_id)
            
            # Получаем недавние категории
            recent_expenses = Expense.objects.filter(
                profile=profile,
                is_deleted=False
            ).select_related('category').order_by('-created_at')[:20]
            
            recent_categories = list(set(
                exp.category.name for exp in recent_expenses 
                if exp.category
            ))
            
            # Получаем часто используемые места/описания
            popular_descriptions = list(
                Expense.objects.filter(
                    profile=profile,
                    is_deleted=False
                ).values_list('description', flat=True)
                .distinct()[:10]
            )
            
            return {
                'recent_categories': recent_categories[:5],
                'preferred_places': popular_descriptions[:5],
                'currency': getattr(profile.settings, 'currency', 'RUB') if hasattr(profile, 'settings') else 'RUB'
            }
        
        except Profile.DoesNotExist:
            return {}
    
    @sync_to_async
    def create_expense_from_parsed(
        self, 
        parsed: ParsedExpense, 
        user_id: int
    ) -> Optional[Expense]:
        """
        Создание объекта Expense из распарсенных данных
        """
        try:
            # Получаем профиль пользователя
            profile = Profile.objects.get(telegram_id=user_id)
            
            # Получаем или создаем категорию
            category = self._get_or_create_category(profile, parsed.category)
            
            # Создаем расход
            expense = Expense.objects.create(
                profile=profile,
                category=category,
                amount=Decimal(str(parsed.amount)),
                currency=parsed.currency,
                description=parsed.description,
                date=date.today(),
                ai_processed=parsed.ai_processed,
                ai_confidence=parsed.confidence
            )
            
            return expense
        
        except (Profile.DoesNotExist, Exception) as e:
            print(f"Error creating expense: {e}")
            return None
    
    def _get_or_create_category(self, profile: Profile, category_name: str) -> ExpenseCategory:
        """
        Получение или создание категории для пользователя
        """
        # Сначала ищем пользовательскую категорию
        category = ExpenseCategory.objects.filter(
            profile=profile,
            name__iexact=category_name,
            is_active=True
        ).first()
        
        if category:
            return category
        
        # Если не найдена, создаем новую
        icon_mapping = {
            'продукты': '🍔',
            'транспорт': '🚌', 
            'кафе': '☕',
            'развлечения': '🎮',
            'здоровье': '💊',
            'одежда': '👕',
            'связь': '📱',
            'дом': '🏠',
            'подарки': '🎁',
            'другое': '💰'
        }
        
        category = ExpenseCategory.objects.create(
            profile=profile,
            name=category_name,
            icon=icon_mapping.get(category_name.lower(), '💰'),
            is_system=False
        )
        
        return category
    
    async def validate_and_suggest_improvements(
        self, 
        parsed: ParsedExpense
    ) -> Dict[str, Any]:
        """
        Валидация и предложения по улучшению
        """
        # Базовая валидация
        errors = validate_expense_data(parsed)
        
        result = {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'suggestions': []
        }
        
        # AI предложения если доступны
        if self.ai_parser and parsed.confidence < 0.8:
            try:
                ai_suggestions = await self.ai_parser.suggest_expense_improvements(parsed)
                result['ai_suggestions'] = ai_suggestions
            except Exception:
                pass
        
        # Базовые предложения
        if parsed.confidence < 0.5:
            result['suggestions'].append("Низкая уверенность в категории - уточните описание")
        
        if not parsed.description or len(parsed.description) < 3:
            result['suggestions'].append("Добавьте более подробное описание")
        
        if parsed.amount > 10000:
            result['suggestions'].append("Большая сумма - проверьте правильность")
        
        return result


class ExpenseMessageProcessor:
    """Процессор для обработки различных типов сообщений о расходах"""
    
    def __init__(self):
        self.parser_service = ExpenseParserService()
    
    async def process_text_message(
        self, 
        message_text: str, 
        user_id: int
    ) -> Dict[str, Any]:
        """
        Обработка текстового сообщения
        
        Возвращает:
        - success: bool - успешность обработки
        - expenses: List[Expense] - созданные расходы
        - errors: List[str] - ошибки
        - suggestions: List[str] - предложения
        """
        result = {
            'success': False,
            'expenses': [],
            'errors': [],
            'suggestions': []
        }
        
        try:
            # Парсим сообщение
            parsed_expenses = await self.parser_service.parse_multiple_text_messages(
                message_text, user_id
            )
            
            if not parsed_expenses:
                result['errors'].append("Не удалось распознать расход в сообщении")
                return result
            
            # Обрабатываем каждый распарсенный расход
            created_expenses = []
            
            for parsed in parsed_expenses:
                # Валидируем
                validation = await self.parser_service.validate_and_suggest_improvements(parsed)
                
                if validation['is_valid']:
                    # Создаем расход в БД
                    expense = await self.parser_service.create_expense_from_parsed(
                        parsed, user_id
                    )
                    
                    if expense:
                        created_expenses.append(expense)
                    else:
                        result['errors'].append(f"Не удалось сохранить расход: {parsed.description}")
                else:
                    result['errors'].extend(validation['errors'])
                
                # Добавляем предложения
                result['suggestions'].extend(validation.get('suggestions', []))
            
            result['expenses'] = created_expenses
            result['success'] = len(created_expenses) > 0
            
        except Exception as e:
            result['errors'].append(f"Ошибка обработки: {str(e)}")
        
        return result
    
    async def process_voice_message(
        self, 
        voice_file_path: str, 
        user_id: int
    ) -> Dict[str, Any]:
        """
        Обработка голосового сообщения (требует speech-to-text)
        """
        # Placeholder для будущей реализации
        return {
            'success': False,
            'expenses': [],
            'errors': ['Обработка голосовых сообщений пока не реализована'],
            'suggestions': []
        }
    
    async def process_receipt_photo(
        self, 
        photo_file_path: str, 
        user_id: int
    ) -> Dict[str, Any]:
        """
        Обработка фото чека (требует OCR)
        """
        # Placeholder для будущей реализации
        return {
            'success': False,
            'expenses': [],
            'errors': ['Обработка фото чеков пока не реализована'],
            'suggestions': []
        }


# Фабрика для создания процессора
def create_expense_processor() -> ExpenseMessageProcessor:
    """Создание экземпляра процессора расходов"""
    return ExpenseMessageProcessor()


# Утилиты для миграции старых данных
class LegacyParserMigration:
    """Утилиты для миграции от старого парсера к новому"""
    
    @staticmethod
    def compare_parsers(text: str) -> Dict[str, Any]:
        """Сравнение результатов старого и нового парсера"""
        # Импортируем старый парсер
        from .expense_parser import parse_expense_message as old_parse
        
        # Результаты старого парсера
        old_result = old_parse(text)
        
        # Результаты нового парсера
        new_result = parse_expense_message(text)
        
        return {
            'text': text,
            'old_parser': old_result,
            'new_parser': new_result.__dict__ if new_result else None,
            'improvements': {
                'better_amount_detection': new_result is not None and old_result is None,
                'better_category': (
                    new_result and old_result and 
                    new_result.confidence > 0.7 and 
                    new_result.category != old_result.get('category')
                ),
                'ai_processed': new_result.ai_processed if new_result else False
            }
        }
    
    @staticmethod
    async def migrate_expense_suggestions(user_id: int, limit: int = 100):
        """
        Повторная обработка последних расходов пользователя новым парсером
        для улучшения категоризации
        """
        # Placeholder для будущей реализации
        pass