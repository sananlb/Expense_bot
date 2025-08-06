# Generated manually
from django.db import migrations

def migrate_usage_counts(apps, schema_editor):
    """Переносим manual_usage_count в usage_count"""
    CategoryKeyword = apps.get_model('expenses', 'CategoryKeyword')
    
    for keyword in CategoryKeyword.objects.all():
        # Сохраняем значение manual_usage_count если оно есть
        if hasattr(keyword, 'manual_usage_count'):
            keyword.usage_count = keyword.manual_usage_count
            keyword.save()

def reverse_migrate(apps, schema_editor):
    """Обратная миграция"""
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('expenses', '0011_simplify_keyword_weights'),
    ]

    operations = [
        migrations.RunPython(migrate_usage_counts, reverse_migrate),
    ]