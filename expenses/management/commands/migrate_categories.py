from django.core.management.base import BaseCommand
from expenses.models import ExpenseCategory
import re


class Command(BaseCommand):
    help = 'Мигрировать категории - добавить эмодзи в поле name'

    def handle(self, *args, **kwargs):
        self.stdout.write('Starting categories migration...')
        
        # Словарь соответствия названий и эмодзи
        icon_map = {
            'супермаркет': '🛒',
            'продукт': '🥐', 
            'ресторан': '☕',
            'кафе': '☕',
            'азс': '⛽',
            'заправка': '⛽',
            'такси': '🚕',
            'общественный транспорт': '🚌',
            'автомобиль': '🚗',
            'жилье': '🏠',
            'жкх': '🏠',
            'аптек': '💊',
            'медицин': '🏥',
            'спорт': '⚽',
            'фитнес': '⚽',
            'одежда': '👕',
            'обувь': '👟',
            'цвет': '🌸',
            'развлечен': '🎮',
            'образован': '📚',
            'подарк': '🎁',
            'подарок': '🎁',
            'путешеств': '✈️',
            'связь': '📱',
            'интернет': '📱',
            'прочее': '💰',
            'прочие': '💰',
            'другое': '💰',
            'другие': '💰'
        }
        
        # Получаем все категории
        categories = ExpenseCategory.objects.all()
        updated_count = 0
        
        for category in categories:
            # Проверяем, есть ли уже эмодзи в начале
            emoji_pattern = r'^[\U0001F000-\U0001F9FF\U00002600-\U000027BF\U0001F300-\U0001F64F\U0001F680-\U0001F6FF]'
            
            if not re.match(emoji_pattern, category.name):
                # Если эмодзи нет, добавляем
                old_name = category.name
                
                if category.icon and category.icon.strip():
                    # Если есть иконка в поле icon, используем её
                    category.name = f"{category.icon} {category.name}"
                else:
                    # Иначе подбираем по названию
                    icon = '💰'  # По умолчанию
                    category_lower = category.name.lower()
                    
                    for keyword, emoji in icon_map.items():
                        if keyword in category_lower:
                            icon = emoji
                            break
                    
                    category.name = f"{icon} {category.name}"
                
                # Очищаем поле icon
                category.icon = ''
                category.save()
                
                self.stdout.write(f'Updated: {old_name} -> {category.name}')
                updated_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'\nMigration completed! Updated categories: {updated_count}'))