"""
Меняем UserAnalytics.date с auto_now_add=True на default=timezone.localdate.

auto_now_add игнорирует явно переданное значение date в create(),
из-за чего collect_daily_analytics (запуск в 02:00) создавал записи
с датой "сегодня" вместо "вчера".
"""

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('expenses', '0059_alter_auto_convert_currency_default_true'),
    ]

    operations = [
        migrations.AlterField(
            model_name='useranalytics',
            name='date',
            field=models.DateField(default=django.utils.timezone.localdate),
        ),
    ]
