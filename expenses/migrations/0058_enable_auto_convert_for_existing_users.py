# Generated manually for enabling auto_convert_currency for existing users

from django.db import migrations


def enable_auto_convert_for_all(apps, schema_editor):
    """Включить автоконвертацию для всех существующих пользователей"""
    UserSettings = apps.get_model('expenses', 'UserSettings')
    updated = UserSettings.objects.filter(auto_convert_currency=False).update(auto_convert_currency=True)
    print(f"Updated {updated} UserSettings records: auto_convert_currency=True")


def disable_auto_convert_for_all(apps, schema_editor):
    """Откатить: выключить автоконвертацию для всех (reverse migration)"""
    UserSettings = apps.get_model('expenses', 'UserSettings')
    updated = UserSettings.objects.filter(auto_convert_currency=True).update(auto_convert_currency=False)
    print(f"Reverted {updated} UserSettings records: auto_convert_currency=False")


class Migration(migrations.Migration):

    dependencies = [
        ('expenses', '0057_add_auto_convert_currency'),
    ]

    operations = [
        migrations.RunPython(
            enable_auto_convert_for_all,
            reverse_code=disable_auto_convert_for_all
        ),
    ]
