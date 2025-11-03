from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='broadcastmessage',
            name='language_filter',
            field=models.CharField(
                choices=[('all', 'Все языки'), ('ru', 'Русский'), ('en', 'English')],
                default='all',
                help_text='Ограничить рассылку пользователями конкретного языка',
                max_length=5,
                verbose_name='Язык получателей',
            ),
        ),
    ]
