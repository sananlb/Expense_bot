# Generated migration for adding cashback_enabled field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('expenses', '0018_remove_monthly_summary_and_notification_time'),
    ]

    operations = [
        migrations.AddField(
            model_name='usersettings',
            name='cashback_enabled',
            field=models.BooleanField(default=True, verbose_name='Кешбэк включен'),
        ),
    ]